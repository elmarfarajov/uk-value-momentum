from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ukfactors import tsmom as T

IDX = pd.date_range("1970-01-31", periods=480, freq="ME")


def _iid(seed: int = 0, n: int = 3, vol: float = 0.05) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(0.003, vol, (IDX.size, n)), index=IDX, columns=[f"a{i}" for i in range(n)])


def _trending(seed: int = 1, n: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    mu = np.zeros((IDX.size, n))
    for t in range(1, IDX.size):
        mu[t] = 0.97 * mu[t - 1] + rng.normal(0, 0.004, n)
    return pd.DataFrame(mu + rng.normal(0, 0.04, (IDX.size, n)), index=IDX, columns=[f"a{i}" for i in range(n)])


def test_gilt_flat_yield_earns_the_coupon_and_rising_yields_lose() -> None:
    y = pd.Series([0.04, 0.04, 0.05, 0.03], index=IDX[:4])
    r = T.gilt_returns(y)
    assert r.iloc[0] == pytest.approx(0.04 / 12, abs=1e-14)
    assert r.iloc[1] < -0.06  # a 1-point rise costs about 8% on a 10-year bond
    assert r.iloc[2] > 0.15
    assert len(r) == 3


def test_gbp_excess_is_the_carry_trade_return() -> None:
    fx = pd.Series([0.01, -0.02], index=IDX[:2])
    uk = pd.Series([0.004, 0.004], index=IDX[:2])
    us = pd.Series([0.001, 0.001], index=IDX[:2])
    r = T.gbp_excess(fx, uk, us)
    assert r.iloc[0] == pytest.approx(1.01 * 1.004 - 1.001)
    assert r.iloc[1] == pytest.approx(0.98 * 1.004 - 1.001)


def test_assets_frame(use_data: Path) -> None:
    from ukfactors import panel
    from ukfactors.data import aqr, fred

    a = T.assets(panel.build(), T.gilt_returns(fred.gilt_yield()), aqr.us_bill())
    assert list(a.columns) == ["EQUITY", "GILT", "GBP"]
    assert a["GILT"].abs().max() < 0.5 and a.notna().sum().min() > 200


def test_ex_ante_vol_is_known_in_advance_and_annualised() -> None:
    r = _iid(vol=0.05)
    v = T.ex_ante_vol(r)
    assert v.iloc[:11].isna().all().all()
    ratio = float(v.iloc[100:].mean().mean()) / (0.05 * np.sqrt(12))
    assert 0.75 < ratio < 1.0  # a short EWMA estimate is biased low (about 15% here); see ADR 0013
    r2 = r.copy()
    r2.iloc[200] = 5.0  # a shock at t changes the volatility at t, not before
    pd.testing.assert_frame_equal(T.ex_ante_vol(r2).iloc[:200], v.iloc[:200])


def test_signals() -> None:
    r = pd.DataFrame({"a": [0.01] * 30 + [-0.02] * 30}, index=IDX[:60])
    s = T.signal(r, 12)
    assert s["a"].iloc[20] == 1 and s["a"].iloc[50] == -1 and np.isnan(s["a"].iloc[5])
    lin = T.signal(r, 12, "linear")
    assert lin.abs().max().max() <= 1.0
    ma = T.signal(r, 12, "ma")
    assert ma["a"].iloc[25] == 1 and ma["a"].iloc[55] == -1
    with pytest.raises(ValueError, match="unknown"):
        T.signal(r, 12, "nonsense")


def test_positions_use_only_past_information() -> None:
    r = _iid(2)
    base = T.tsmom(r)
    r2 = r.copy()
    r2.iloc[300:] = -r2.iloc[300:]  # change the future
    alt = T.tsmom(r2)
    pd.testing.assert_frame_equal(base.positions.loc[: IDX[300]], alt.positions.loc[: IDX[300]])
    assert not base.positions.loc[IDX[320]].equals(alt.positions.loc[IDX[320]])


def test_trend_is_found_and_noise_is_not() -> None:
    assert T.summary(T.tsmom(_trending()).portfolio)["sharpe"] > 0.4
    assert abs(T.summary(T.tsmom(_iid(3)).portfolio)["sharpe"]) < 0.35


def test_holding_period_averages_positions_and_unscaled_holds_units() -> None:
    r = _iid(4)
    one, three = T.tsmom(r, hold=1), T.tsmom(r, hold=3)
    w = one.positions
    expected = (w + w.shift(1) + w.shift(2)) / 3
    pd.testing.assert_frame_equal(three.positions.iloc[5:], expected.reindex(three.positions.index).iloc[5:], check_freq=False)
    raw = T.tsmom(r, target=None).positions
    assert set(np.unique(raw.dropna().to_numpy())) <= {-1.0, 0.0, 1.0}


def test_grid_and_predictability() -> None:
    g = T.grid(_trending(), (3, 12), (1, 3))
    assert g.shape == (2, 2) and (g > 0).all().all()
    p = T.predictability(_trending(), 3)
    assert list(p.columns) == ["beta", "t", "n"] and p["t"].iloc[0] > 2
    ps = T.predictability(_iid(5), 2, sign=True)
    assert ps["t"].abs().max() < 3


def test_smile_recovers_a_planted_straddle() -> None:
    rng = np.random.default_rng(6)
    m = pd.Series(rng.normal(0.005, 0.045, IDX.size), index=IDX)
    q = T.quarterly(m, m)
    s_q = 0.8 * q["m"] ** 2 + rng.normal(0, 0.002, len(q))
    # spread each quarter's return evenly over its months so the quarterly compounding is close
    monthly = ((1 + s_q) ** (1 / 3) - 1).reindex(IDX, method="bfill")
    reg = T.smile(monthly, m)
    assert reg.coef[2] == pytest.approx(0.8, abs=0.15) and reg.tstat[2] > 5


def test_quarterly_drops_partial_quarters() -> None:
    m = pd.Series(0.01, index=IDX[:12])
    s = pd.Series(0.01, index=IDX[1:12])
    q = T.quarterly(s, m)
    assert len(q) == 3 and q.index[0] == IDX[5]


def test_placebo_and_crises() -> None:
    pl = T.placebo(_iid(7), draws=10)
    assert pl.shape == (10,) and np.isfinite(pl).all()
    s = pd.Series(0.01, index=IDX)
    m = pd.Series(-0.02, index=IDX)
    t = T.crisis_table(s, m, {"x": ("1970-01", "1970-03")})
    assert t.loc["x", "months"] == 3 and t.loc["x", "tsmom"] == pytest.approx(1.01**3 - 1)


def test_stock_strategies_decompose() -> None:
    rng = np.random.default_rng(8)
    ret = pd.DataFrame(rng.normal(0.008, 0.08, (200, 50)), index=IDX[:200])
    rf = pd.Series(0.003, index=IDX[:200])
    s = T.stock_strategies(ret, rf)
    assert {"TS", "XS", "NET", "MKT", "LONG_SHARE"} <= set(s.columns) and len(s) > 150
    assert s["LONG_SHARE"].between(0, 1).all()
    # every month the TS weights are +/- 1/N, so |TS| cannot exceed the largest absolute excess return
    assert (s["TS"].abs() <= (ret.sub(rf, axis=0)).abs().max(axis=1).reindex(s.index) + 1e-12).all()


def test_summary() -> None:
    s = pd.Series([0.1, -0.05, 0.02, 0.03], index=IDX[:4])
    out = T.summary(s)
    assert out["months"] == 4 and out["maxdd"] == pytest.approx(-0.05)
