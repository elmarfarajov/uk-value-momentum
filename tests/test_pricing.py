"""Asset-pricing tests: GRS, Fama-MacBeth, macro innovations, publication and size spreads."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ukfactors import pricing as P

IDX = pd.date_range("1980-01-31", periods=480, freq="ME")


@pytest.fixture(scope="module")
def market() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(1)
    f = pd.DataFrame(rng.normal([0.006, 0.004], [0.045, 0.03], (480, 2)), index=IDX, columns=["M", "U"])
    b = rng.uniform(0.3, 1.5, (10, 2))
    y = pd.DataFrame(f.to_numpy() @ b.T + rng.normal(0, 0.01, (480, 10)), index=IDX, columns=[f"P{i}" for i in range(10)])
    return y, f


def test_grs_accepts_a_correct_model_and_rejects_planted_alphas(market) -> None:
    y, f = market
    ok = P.grs(y, f)
    assert ok.p > 0.01 and ok.months == 480
    bad = P.grs(y + 0.004, f)  # 4.8% a year of alpha on every portfolio
    assert bad.p < 1e-6 and bad.mean_abs_alpha == pytest.approx(0.048, abs=0.01)
    assert bad.sharpe_all > bad.sharpe_factors


def test_grs_one_asset_matches_the_closed_form(market) -> None:
    y, f = market
    g = P.grs(y[["P0"]], f[["M"]])
    t = len(y)
    x = np.column_stack([np.ones(t), f["M"]])
    b, *_ = np.linalg.lstsq(x, y["P0"], rcond=None)
    e = y["P0"].to_numpy() - x @ b
    s2 = e @ e / (t - 2)
    sr2 = f["M"].mean() ** 2 / f["M"].var(ddof=1)
    assert g.stat == pytest.approx(t * (t - 2) / (t - 2) * b[0] ** 2 / s2 / (1 + sr2))


def test_betas_shape(market) -> None:
    y, f = market
    assert P.betas(y, f).shape == (10, 2)


def test_fama_macbeth_lambdas_equal_factor_means(market) -> None:
    y, f = market
    fm = P.fama_macbeth(y, f)
    assert fm.lambdas[["M", "U"]].to_numpy() == pytest.approx(f.mean().to_numpy(), abs=0.002)
    assert (fm.se_shanken[["M", "U"]] >= fm.se[["M", "U"]]).all()
    assert fm.r2 > 0.8
    nc = P.fama_macbeth(y, f, constant=False)
    assert "const" not in nc.lambdas.index


def test_macro_units() -> None:
    rf = pd.Series((1.05) ** (1 / 12) - 1, index=IDX[:3])
    rf.iloc[2] = (1.06) ** (1 / 12) - 1
    gilt = pd.Series([0.07, 0.07, 0.07], index=IDX[:3])
    fx = pd.Series([1.0, 1.1, 1.1], index=IDX[:3])
    m = P.macro(rf, gilt, fx)
    assert m.loc[IDX[1], "D_SHORT"] == pytest.approx(0.0) and m.loc[IDX[2], "D_SHORT"] == pytest.approx(1.0)
    assert m.loc[IDX[2], "D_TERM"] == pytest.approx(-1.0) and m.loc[IDX[1], "GBP"] == pytest.approx(10.0)


def test_publication_split() -> None:
    s = pd.Series(np.r_[np.full(120, 0.01), np.full(120, 0.0)], index=IDX[:240])
    r = P.publication(s, str(IDX[119].date()))
    assert r["before"] == pytest.approx(0.12) and r["after"] == pytest.approx(0.0)
    assert r["months_before"] == 120 and r["change"] == pytest.approx(-0.12)


def test_spread_by_size() -> None:
    cols = ["SL", "SM", "SH", "BL", "BM", "BH"]
    ports = pd.DataFrame(np.tile([0.0, 0.01, 0.03, 0.0, 0.01, 0.02], (5, 1)), columns=cols)
    sp = P.spread_by_size(ports, 3)
    assert sp["Q1"].iloc[0] == pytest.approx(0.03) and sp["Q2"].iloc[0] == pytest.approx(0.02)
    with pytest.raises(ValueError):
        P.spread_by_size(ports, 4)


def test_rolling_alpha_positive(market) -> None:
    y, f = market
    r = P.rolling_alpha(y + 0.002, f, window=120)
    assert len(r) == 480 - 119 and r.mean() == pytest.approx(0.024, abs=0.01)
