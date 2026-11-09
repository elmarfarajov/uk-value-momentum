from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ukfactors import lostdecade as L

IDX = pd.date_range("1990-01-31", periods=420, freq="ME")


def _series(seed: int = 0, mean: float = 0.004) -> pd.Series:
    return pd.Series(np.random.default_rng(seed).normal(mean, 0.03, IDX.size), index=IDX, name="x")


def test_cumulative_and_episode() -> None:
    s = pd.Series(0.01, index=IDX)
    assert L.cumulative(s.iloc[:12]) == pytest.approx(1.01**12 - 1)
    e = L.episode(_series(1), ("2000-01", "2009-12"))
    assert e.start == pd.Timestamp("2000-01-31") and e.end == pd.Timestamp("2009-12-31")
    assert e.annual == pytest.approx((1 + e.cumulative) ** (1 / 10) - 1)
    assert np.isfinite([e.sharpe_before, e.sharpe_during, e.sharpe_after]).all()


def test_sup_wald_finds_a_planted_break_and_not_a_missing_one() -> None:
    rng = np.random.default_rng(2)
    x = pd.Series(np.r_[rng.normal(0.01, 0.03, 250), rng.normal(-0.005, 0.03, 170)], index=IDX)
    path, date, stat = L.sup_wald(x)
    assert abs((date - IDX[250]).days) < 730 and stat > 8.85  # break dates are imprecise in noisy samples
    assert path.index[0] == IDX[int(0.15 * IDX.size)]
    _, _, calm = L.sup_wald(_series(3))
    assert calm < stat


def test_sup_wald_pvalue_small_for_a_break_and_large_for_noise() -> None:
    rng = np.random.default_rng(4)
    short = IDX[:160]
    x = pd.Series(np.r_[rng.normal(0.015, 0.02, 90), rng.normal(-0.01, 0.02, 70)], index=short)
    _, p_break = L.sup_wald_pvalue(x, reps=19, seed=1)
    _, p_noise = L.sup_wald_pvalue(_series(5).iloc[:160], reps=19, seed=1)
    assert p_break <= 0.1 < p_noise


def test_loss_probability_orders_sensibly() -> None:
    h = _series(6, mean=0.006)
    worse = L.loss_probability(h, 120, -0.5, reps=400, seed=1)
    milder = L.loss_probability(h, 120, 0.0, reps=400, seed=1)
    assert 0 <= worse < milder <= 1
    assert L.loss_probability(h.iloc[:50], 120, 0.0, reps=50, seed=1) >= 0  # longer than the history: blocks are chained


def test_expanding_mean_band() -> None:
    em = L.expanding_mean(_series(7), start=60)
    assert len(em) == IDX.size - 59
    assert (em["lo"] < em["mean"]).all() and (em["mean"] < em["hi"]).all()
    assert (em["hi"] - em["lo"]).iloc[-1] < (em["hi"] - em["lo"]).iloc[0]


def test_attribution_adds_up() -> None:
    rng = np.random.default_rng(8)
    x = pd.DataFrame(rng.normal(0.005, 0.04, (IDX.size, 2)), index=IDX, columns=["A", "B"])
    y = 0.4 * x["A"] + pd.Series(rng.normal(0, 0.01, IDX.size), index=IDX)
    a = L.attribution(y, x, ("1990", "1999"))
    assert a.drop("total").sum() == pytest.approx(a["total"], abs=1e-12)
    assert a["total"] == pytest.approx(y.loc[L.LOST[0] : L.LOST[1]].sum())


def test_rate_beta() -> None:
    rng = np.random.default_rng(9)
    lvl = pd.Series(0.05 + np.cumsum(rng.normal(0, 0.002, IDX.size)), index=IDX)
    y = -0.02 * (100 * lvl.diff()) + pd.Series(rng.normal(0, 0.002, IDX.size), index=IDX)
    assert L.rate_beta(y, lvl).coef[1] == pytest.approx(-0.02, abs=0.002)
    assert L.rate_beta(y, lvl, ("2000", "2005")).months == 72


def test_legs() -> None:
    dec = pd.DataFrame({"V1": [0.01, 0.02], "V10": [0.03, -0.01]}, index=IDX[:2])
    m = pd.Series([0.005, 0.0], index=IDX[:2])
    rf = pd.Series([0.001, 0.001], index=IDX[:2])
    lg = L.legs(dec, m, rf)
    assert lg["value_vs_market"].iloc[0] == pytest.approx(0.03 - 0.001 - 0.005)
    assert lg["value_minus_growth"].iloc[1] == pytest.approx(-0.03)


def test_rolling_correlation() -> None:
    a = _series(10)
    assert L.rolling_correlation(a, a, 24).dropna().round(12).eq(1.0).all()


def test_on_synthetic_data(use_data: Path) -> None:
    from ukfactors import panel

    p = panel.build()
    e = L.episode(p["HML"].rename("HML"))
    assert e.start == pd.Timestamp("2007-01-31") and np.isfinite(e.cumulative)
