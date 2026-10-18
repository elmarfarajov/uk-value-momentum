from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ukfactors import analysis

IDX = pd.date_range("1990-01-31", periods=360, freq="ME")


def _series(mu: float, sd: float, seed: int) -> pd.Series:
    return pd.Series(np.random.default_rng(seed).normal(mu, sd, IDX.size), index=IDX)


def test_regress_recovers_known_coefficients() -> None:
    rng = np.random.default_rng(0)
    x = pd.DataFrame({"m": rng.normal(0, 0.04, 5000), "v": rng.normal(0, 0.03, 5000)})
    y = 0.002 + 0.5 * x["m"] - 0.8 * x["v"] + rng.normal(0, 0.01, 5000)
    r = analysis.regress(y, x)
    assert r.names == ["alpha", "m", "v"]
    np.testing.assert_allclose(r.coef, [0.002, 0.5, -0.8], atol=0.01)
    assert r.alpha == pytest.approx(12 * r.coef[0])
    assert 0.8 < r.r2 < 1.0 and r.months == 5000


def test_regress_matches_statsmodels_hac() -> None:
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(1)
    x = pd.DataFrame({"a": rng.normal(0, 0.04, 400)})
    y = pd.Series(0.003 + 0.4 * x["a"] + rng.normal(0, 0.02, 400))
    ours = analysis.regress(y, x, lags=5)
    fit = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HAC", cov_kwds={"maxlags": 5, "use_correction": False})
    np.testing.assert_allclose(ours.se, fit.bse.to_numpy(), rtol=1e-10)
    assert list(ours.frame().columns) == ["coef", "se", "t"]


def test_regress_uses_common_months_only() -> None:
    y = _series(0.01, 0.04, 2)
    x = pd.DataFrame({"a": _series(0.0, 0.04, 3)})
    x.iloc[:60] = np.nan
    assert analysis.regress(y, x).months == 300


def test_mix_frontier_endpoints_are_the_two_factors() -> None:
    a, b = _series(0.002, 0.04, 4), _series(0.006, 0.04, 5)
    f = analysis.mix_frontier(a, b)
    assert f.index[0] == 0.0 and f.index[-1] == 1.0 and len(f) == 21
    assert f["mean"].iloc[0] == pytest.approx(12 * a.mean())
    assert f["mean"].iloc[-1] == pytest.approx(12 * b.mean())


def test_negative_correlation_lowers_mix_volatility() -> None:
    a = _series(0.004, 0.04, 6)
    b = -0.8 * a + _series(0.008, 0.02, 7)
    f = analysis.mix_frontier(a, b)
    assert f["vol"].min() < min(f["vol"].iloc[0], f["vol"].iloc[-1]) / 2


def test_tangency_weight_maximises_the_sharpe_ratio() -> None:
    a, b = _series(0.003, 0.04, 8), _series(0.005, 0.05, 9)
    w = analysis.tangency_weight(a, b)
    grid = analysis.mix_frontier(a, b, np.linspace(0, 1, 2001))
    assert w == pytest.approx(float(grid["sharpe"].idxmax()), abs=1e-3)


def test_rolling_correlation_of_a_series_with_itself_is_one() -> None:
    a = _series(0.0, 0.04, 10)
    rc = analysis.rolling_correlation(a, 2 * a, 36)
    assert rc.iloc[:35].isna().all() and np.allclose(rc.dropna(), 1.0)


def test_calendar_years_compound_and_skip_partial_years() -> None:
    idx = pd.date_range("2000-01-31", "2002-06-30", freq="ME")
    frame = pd.DataFrame({"x": 0.01}, index=idx)
    cy = analysis.calendar_years(frame)
    assert cy.loc[2000, "x"] == pytest.approx(1.01**12 - 1)
    assert np.isnan(cy.loc[2002, "x"])


def test_start_sensitivity_needs_five_years() -> None:
    s = _series(0.01, 0.04, 11)
    out = analysis.start_sensitivity(s, 1990, 2030)
    assert out.index[0] == 1990 and out.index[-1] == 2015  # 2015-2019 is exactly 60 months; 2016 onwards fewer
    assert out.loc[1990, "months"] == 360


def test_acf_of_white_noise_is_small_and_of_ar1_is_phi() -> None:
    rng = np.random.default_rng(12)
    e = rng.normal(size=20000)
    x = np.empty_like(e)
    x[0] = e[0]
    for t in range(1, e.size):
        x[t] = 0.6 * x[t - 1] + e[t]
    assert analysis.acf(pd.Series(x), 2).iloc[0] == pytest.approx(0.6, abs=0.02)
    assert abs(analysis.acf(pd.Series(e), 1).iloc[0]) < 0.03
    q, p = analysis.ljung_box(pd.Series(x), 12)
    assert q > 1000 and p < 1e-10


def test_drawdown_episodes_known_path() -> None:
    idx = pd.date_range("2000-01-31", periods=8, freq="ME")
    r = pd.Series([0.1, -0.5, 0.2, 1.0, 0.1, -0.1, -0.1, 0.0], index=idx)
    eps = analysis.drawdown_episodes(r, 5)
    first = eps[0]
    assert first.depth == pytest.approx(0.5)
    assert first.peak == idx[0] and first.trough == idx[1] and first.recovery == idx[3]
    assert first.to_trough == 1 and first.to_recover == 2
    assert eps[1].recovery is None and eps[1].depth == pytest.approx(1 - 0.81)


def test_rebuild_factor_formulae() -> None:
    six = pd.DataFrame({"SL": [0.0], "SM": [0.01], "SH": [0.04], "BL": [0.01], "BM": [0.01], "BH": [0.03]})
    assert analysis.rebuild_factor(six, "HML").iloc[0] == pytest.approx(0.03)
    assert analysis.rebuild_factor(six, "SMB").iloc[0] == pytest.approx(0.0)
    with pytest.raises(ValueError):
        analysis.rebuild_factor(six, "QMJ")


def test_grid_shapes_and_spread() -> None:
    rng = np.random.default_rng(13)
    tilt = np.tile(np.linspace(0.0, 0.004, 5), 5)
    ports = pd.DataFrame(0.005 + tilt + rng.normal(0, 0.01, (IDX.size, 25)), index=IDX, columns=[f"p{k}" for k in range(25)])
    means, ts, spread = analysis.grid(ports, pd.Series(0.0, index=IDX))
    assert means.shape == (5, 5) and ts.shape == (5, 5)
    assert list(spread.index) == analysis.SIZE_ROWS
    assert spread["spread"].mean() == pytest.approx(12 * 0.004, abs=0.015)  # standard error about 0.004


def test_deciles_subtract_the_risk_free_rate() -> None:
    ports = pd.DataFrame({"V1": 0.01, "V2": 0.02}, index=IDX) + _series(0, 0.01, 14).to_frame().values
    d = analysis.deciles(ports, pd.Series(0.005, index=IDX))
    assert d.loc["V2", "mean"] - d.loc["V1", "mean"] == pytest.approx(0.12)


def test_market_states_split() -> None:
    m = _series(0.0, 0.04, 15)
    f = pd.DataFrame({"hedge": -m})
    ms = analysis.market_states(f, m)
    assert ms.loc["hedge", "up"] < 0 < ms.loc["hedge", "down"]
    assert ms.loc["hedge", "up_months"] + ms.loc["hedge", "down_months"] == IDX.size
    assert ms.loc["hedge", "beta_up"] == pytest.approx(-1.0)


def test_bootstrap_sharpes_reproducible() -> None:
    s = _series(0.01, 0.04, 16)
    np.testing.assert_array_equal(analysis.bootstrap_sharpes(s, 50, 1), analysis.bootstrap_sharpes(s, 50, 1))


def test_alpha_table_on_synthetic_data(use_data: Path) -> None:
    from ukfactors.gallery import deepdive, foundation

    foundation._panel.cache_clear()
    t = deepdive.alpha_table()
    foundation._panel.cache_clear()
    assert list(t.index) == ["VAL", "MOM", "HML", "HML_DEVIL", "UMD", "QMJ", "SMB"]
    assert t["months"].min() > 100 and np.isfinite(t["alpha_t"]).all()
