from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from ukfactors import stats


def test_nw_lags_follow_the_newey_west_rule() -> None:
    assert stats.nw_lags(100) == 4
    assert stats.nw_lags(651) == 6  # 1972-2026 monthly
    assert stats.nw_lags(20) == 2


def test_long_run_variance_with_no_lags_is_the_plain_variance() -> None:
    x = np.random.default_rng(0).normal(size=400)
    assert stats.long_run_variance(x, lags=0) == pytest.approx(x.var())


def test_nw_t_matches_statsmodels() -> None:
    sm = pytest.importorskip("statsmodels.api")
    x = 0.004 + np.random.default_rng(1).normal(0, 0.04, 360)
    lags = stats.nw_lags(x.size)
    fit = sm.OLS(x, np.ones_like(x)).fit(cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": False})
    assert stats.nw_tstat(x) == pytest.approx(float(fit.tvalues[0]), abs=1e-10)


def test_positive_autocorrelation_shrinks_the_t_statistic() -> None:
    rng = np.random.default_rng(2)
    e = rng.normal(0, 0.04, 2000)
    x = np.empty_like(e)
    x[0] = e[0]
    for t in range(1, e.size):
        x[t] = 0.5 * x[t - 1] + e[t]
    x += 0.003
    naive = x.mean() / (x.std() / np.sqrt(x.size))
    assert abs(stats.nw_tstat(x)) < 0.75 * abs(naive)


def test_sharpe_se_reduces_to_the_iid_formula_without_autocorrelation() -> None:
    x = 0.005 + np.random.default_rng(3).normal(0, 0.04, 100_000)
    sr = x.mean() / x.std(ddof=1)
    iid = np.sqrt(12) * np.sqrt((1 + sr**2 / 2) / x.size)
    assert stats.sharpe_se(x) == pytest.approx(iid, rel=0.03)


def test_max_drawdown_known_path() -> None:
    # up 10%, down 50%, up 20%: peak 1.1, trough 0.55
    assert stats.max_drawdown([0.1, -0.5, 0.2]) == pytest.approx(0.5)
    assert stats.max_drawdown([0.01, 0.02, 0.03]) == 0.0
    assert stats.max_drawdown([-0.2]) == pytest.approx(0.2)  # a fall in the first month counts


@settings(max_examples=60, deadline=None)
@given(arrays(np.float64, st.integers(2, 120), elements=st.floats(-0.6, 0.6)))
def test_max_drawdown_between_zero_and_one(x: np.ndarray) -> None:
    dd = stats.max_drawdown(x)
    assert 0.0 <= dd <= 1.0  # 0.5**54 rounds a total loss to exactly one
    assert dd == pytest.approx(-stats.drawdown_path(pd.Series(x)).min(), abs=1e-12)


def test_stationary_bootstrap_is_reproducible_and_centred() -> None:
    x = np.random.default_rng(4).normal(0.01, 0.05, 400)
    a = stats.stationary_bootstrap(x, lambda v: float(v.mean()), reps=300, seed=7)
    b = stats.stationary_bootstrap(x, lambda v: float(v.mean()), reps=300, seed=7)
    np.testing.assert_array_equal(a, b)
    assert a.mean() == pytest.approx(x.mean(), abs=0.002)


def test_stationary_bootstrap_keeps_blocks() -> None:
    # with long blocks, consecutive draws are mostly consecutive observations
    x = np.arange(500, dtype=float)
    seen: list[float] = []
    stats.stationary_bootstrap(x, lambda v: seen.append(float(np.mean(np.diff(v) == 1.0))) or 0.0, reps=20, block=50, seed=1)
    assert np.mean(seen) > 0.95


def test_summary_and_table() -> None:
    idx = pd.date_range("2000-01-31", periods=240, freq="ME")
    rng = np.random.default_rng(5)
    frame = pd.DataFrame({"A": rng.normal(0.01, 0.04, 240), "B": rng.normal(0.0, 0.04, 240)}, index=idx)
    frame.iloc[:12, 1] = np.nan
    t = stats.table(frame, reps=200)
    assert list(t.index) == ["A", "B"]
    assert t.loc["B", "months"] == 228 and t.loc["B", "start"] == "2001-01"
    assert t.loc["A", "sharpe_lo"] < t.loc["A", "sharpe"] < t.loc["A", "sharpe_hi"]
    assert t.loc["A", "mean"] == pytest.approx(12 * frame["A"].mean())


def test_by_period_skips_short_periods() -> None:
    idx = pd.date_range("1975-01-31", "2004-12-31", freq="ME")
    s = pd.Series(0.01, index=idx) + np.random.default_rng(6).normal(0, 0.01, idx.size)
    out = stats.by_period(s, ["1970", "1980", "1990", "2000", "2010"])
    assert list(out["period"]) == ["1970-1979", "1980-1989", "1990-1999", "2000-2009"]
    assert out["months"].tolist() == [60, 120, 120, 60]
    assert stats.by_period(s.loc["2004"], ["2000", "2010"]).empty
