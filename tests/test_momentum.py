from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ukfactors import momentum as M
from ukfactors import sectors

IDX = pd.date_range("2000-01-31", periods=96, freq="ME")


def _returns(n_stocks: int = 60, seed: int = 0, persistence: float = 0.0) -> pd.DataFrame:
    """Random stock returns; with ``persistence`` > 0 each stock has a slowly moving expected return (momentum by design)."""
    rng = np.random.default_rng(seed)
    drift = np.cumsum(rng.normal(0, persistence, (IDX.size, n_stocks)), axis=0) if persistence else 0.0
    return pd.DataFrame(0.008 + drift + rng.normal(0, 0.07, (IDX.size, n_stocks)), index=IDX)


def test_formation_return_window() -> None:
    r = _returns()
    f = M.formation_return(r, 11, 1)
    h = 30
    expected = np.prod(1 + r.iloc[h - 12 : h - 1], axis=0) - 1
    np.testing.assert_allclose(f.iloc[h], expected)
    assert f.iloc[:12].isna().all().all()
    g = M.formation_return(r, 3, 0)  # months h-3 .. h-1
    np.testing.assert_allclose(g.iloc[h], np.prod(1 + r.iloc[h - 3 : h], axis=0) - 1)


def test_ranks_pick_deciles_and_skip_thin_months() -> None:
    sig = pd.DataFrame([np.arange(50.0), np.r_[np.arange(20.0), [np.nan] * 30]], columns=range(50))
    win, lose = M.ranks(sig, 0.1, 30)
    assert win.iloc[0].sum() == 5 and lose.iloc[0].sum() == 5
    assert win.iloc[0, 49] and lose.iloc[0, 0]
    assert not win.iloc[1].any()  # 20 stocks: below the 30 needed


def test_overlapping_cohorts_average() -> None:
    r = _returns()
    one = M.jt(r, 6, 1).wml
    three = M.jt(r, 6, 3).wml
    assert three.first_valid_index() > one.first_valid_index()  # needs three formed cohorts
    assert three.notna().sum() == one.notna().sum() - 2


def test_momentum_by_design_is_found() -> None:
    r = _returns(persistence=0.004, seed=3)
    s = M.jt(r, 11, 1)
    assert s.wml.mean() > 0 and M.summary(s.wml)["t_nw"] > 2
    assert (s.winners - s.losers - s.wml).abs().max() < 1e-12


def test_noise_has_no_momentum_and_turnover_is_bounded() -> None:
    s = M.jt(_returns(seed=4), 11, 1)
    assert abs(M.summary(s.wml)["t_nw"]) < 3
    t = s.turnover.dropna()
    assert ((t >= 0) & (t <= 1)).all()
    longer = M.jt(_returns(seed=4), 11, 6).turnover.dropna()
    assert longer.mean() < t.mean()


def test_grid_shape() -> None:
    g = M.grid(_returns(), [3, 6], [1, 3])
    assert len(g) == 4 and set(g.columns) >= {"J", "K", "mean", "t_nw", "sharpe"}


def test_event_time_profile() -> None:
    r = _returns(persistence=0.004, seed=5)
    e = M.event_time(r, M.formation_return(r, 11, 1), horizon=12)
    assert list(e.index[:3]) == [1, 2, 3]
    assert e["cumulative"].iloc[-1] == pytest.approx(e["mean"].sum())
    assert e.loc[1, "mean"] > 0


def test_high_ratio_is_at_most_one_and_lagged() -> None:
    r = _returns(seed=6)
    hr = M.high_ratio(r)
    assert (hr.dropna() <= 1 + 1e-12).all().all()
    assert hr.iloc[:12].isna().all().all()
    # a stock that only rises sits at its high
    up = pd.DataFrame({"a": np.full(30, 0.02)}, index=IDX[:30])
    assert M.high_ratio(up).iloc[20, 0] == pytest.approx(1.0)


def test_residual_signal_removes_factor_exposure() -> None:
    rng = np.random.default_rng(7)
    fac = pd.DataFrame(rng.normal(0, 0.05, (IDX.size, 1)), index=IDX, columns=["m"])
    betas = np.linspace(0.2, 2.0, 60)
    r = pd.DataFrame(fac.to_numpy() * betas + rng.normal(0, 0.03, (IDX.size, 60)), index=IDX)
    sig = M.residual_signal(r, fac)
    # raw past returns rank on beta after a market move; residual signals do not
    h = 60
    raw_corr = np.corrcoef(M.formation_return(r, 11, 1).iloc[h], betas)[0, 1]
    res_corr = np.corrcoef(sig.iloc[h], betas)[0, 1]
    assert abs(res_corr) < abs(raw_corr) or abs(res_corr) < 0.3
    assert sig.iloc[:36].isna().all().all()


def test_deciles_and_transitions() -> None:
    r = _returns(seed=8)
    sig = M.formation_return(r, 11, 1)
    d = M.deciles(r, sig)
    assert list(d.columns) == list(range(1, 11))
    t = M.transitions(sig, 1, 5)
    np.testing.assert_allclose(t.sum(axis=1), 1.0)
    assert t.loc[5, 5] > 0.5  # an 11-month signal moves slowly


def test_spells() -> None:
    long = pd.DataFrame({"a": [1, 1, 0, 1, 1, 1, 0], "b": [0, 0, 0, 0, 0, 1, 1]}).astype(bool)
    assert sorted(M.spells(long).tolist()) == [2, 2, 3]


def test_composition_shares_sum_to_one() -> None:
    members = pd.DataFrame({"A.L": [True, True], "B.L": [True, False], "C.L": [False, True]})
    ind = pd.Series({"A.L": "Energy", "B.L": "Financials", "C.L": "Energy"})
    c = M.composition(members, ind)
    np.testing.assert_allclose(c.sum(axis=1), 1.0)
    assert c.loc[1, "Energy"] == 1.0


def test_market_states_split_and_difference() -> None:
    rng = np.random.default_rng(9)
    mkt = pd.Series(rng.normal(0.005, 0.05, IDX.size), index=IDX)
    past = np.log1p(mkt).rolling(24).sum().shift(1)
    strat = pd.Series(np.where(past < 0, -0.02, 0.02), index=IDX) + rng.normal(0, 0.001, IDX.size)
    out = M.market_states(strat, mkt)
    assert out.loc["UP", "mean"] == pytest.approx(0.24, abs=0.01)
    assert out.loc["DOWN - UP", "mean"] == pytest.approx(-0.48, abs=0.02)
    assert out.loc["UP", "months"] + out.loc["DOWN", "months"] == out.loc["DOWN - UP", "months"]


def test_conditional_beta() -> None:
    rng = np.random.default_rng(10)
    m = pd.Series(rng.normal(0, 0.04, IDX.size), index=IDX)
    cb = M.conditional_beta(-0.5 * m + rng.normal(0, 0.001, IDX.size), m, 24)
    assert cb["beta"].between(-0.55, -0.45).all()


def test_calendar_and_seasonal_regression() -> None:
    idx = pd.date_range("1990-01-31", periods=240, freq="ME")
    rng = np.random.default_rng(11)
    s = pd.Series(0.01 + rng.normal(0, 0.005, 240), index=idx)
    s[idx.month == 4] -= 0.03
    cal = M.calendar(s)
    assert cal.loc[4, "mean"] < 0 < cal.loc[5, "mean"] and cal["years"].sum() == 240
    reg = M.seasonal_regression(s)
    assert reg.coef[2] == pytest.approx(-0.03, abs=0.003) and reg.tstat[2] < -10


def test_summary_keys() -> None:
    s = pd.Series(np.random.default_rng(12).normal(0.01, 0.04, 120), index=pd.date_range("2000-01-31", periods=120, freq="ME"))
    out = M.summary(s, s * 0.5 + 0.001)
    assert {"mean", "vol", "sharpe", "t_nw", "max_drawdown", "beta", "alpha"} <= set(out)
    assert out["beta"] == pytest.approx(2.0, rel=1e-6)


def test_sector_mapping() -> None:
    assert sectors.industry("Pharmaceuticals & Biotechnology") == "Health Care"
    assert sectors.industry("Gas, Water & Multiutilities") == "Utilities"
    assert sectors.industry("Travel and Leisure") == "Consumer Discretionary"
    assert sectors.industry("Banking services") == "Financials"
    assert sectors.industry("something new") == "Other"
    c = pd.DataFrame({"yahoo": ["A.L", "B.L"], "sector": ["Mining", "Software & Computer Services"]})
    assert sectors.by_ticker(c).to_dict() == {"A.L": "Basic Materials", "B.L": "Technology"}


def test_market_total_on_synthetic_data(use_data: Path) -> None:
    m = M.market_total()
    assert m.notna().all() and m.index.is_monotonic_increasing and m.index.is_unique
    assert m.index[-1] >= pd.Timestamp("2026-01-31")
