from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ukfactors import industry as I

IDX = pd.date_range("2000-01-31", periods=96, freq="ME")


def _panel(seed: int = 0, ind_persist: float = 0.0) -> tuple[pd.DataFrame, pd.Series]:
    """60 stocks in 6 groups; with ``ind_persist`` > 0 each group has a slowly moving expected return."""
    rng = np.random.default_rng(seed)
    groups = pd.Series([f"g{i % 6}" for i in range(60)], index=[f"s{i}" for i in range(60)])
    drift = np.cumsum(rng.normal(0, ind_persist, (IDX.size, 6)), axis=0) if ind_persist else np.zeros((IDX.size, 6))
    gi = np.array([i % 6 for i in range(60)])
    ret = 0.008 + drift[:, gi] + rng.normal(0, 0.06, (IDX.size, 60))
    return pd.DataFrame(ret, index=IDX, columns=groups.index), groups


def test_groups_split_trusts_but_not_reits() -> None:
    c = pd.DataFrame(
        {
            "yahoo": ["A.L", "B.L", "C.L", "D.L"],
            "sector": ["Investment Trusts", "Real Estate Investment Trusts", "Banks", "Equity Investment Instruments"],
        }
    )
    g = I.groups(c)
    assert g.to_dict() == {"A.L": "Investment Trusts", "B.L": "Real Estate", "C.L": "Financials", "D.L": "Investment Trusts"}


def test_industry_returns_and_minimum_members() -> None:
    ret, grp = _panel()
    ret.iloc[:5, [0, 6, 12, 18, 24, 30, 36, 42]] = np.nan  # g0 has only 2 members in the first five months
    ir, cnt = I.industry_returns(ret, grp, min_members=3)
    assert cnt.loc[IDX[0], "g0"] == 2 and np.isnan(ir.loc[IDX[0], "g0"])
    np.testing.assert_allclose(ir.loc[IDX[10], "g1"], ret.loc[IDX[10], grp.index[grp == "g1"]].mean())


def test_industry_momentum_found_when_industries_persist() -> None:
    ret, grp = _panel(1, ind_persist=0.006)
    ir, _ = I.industry_returns(ret, grp)
    s = I.industry_momentum(ir, 11, 1, top=2).wml.dropna()
    assert len(s) > 60 and s.mean() > 0


def test_industry_momentum_holds_top_and_bottom() -> None:
    ret, grp = _panel(2)
    ir, _ = I.industry_returns(ret, grp)
    s = I.industry_momentum(ir, 3, 1, top=2)
    valid = s.long.any(axis=1)
    assert (s.long[valid].sum(axis=1) == 2).all() and (s.short[valid].sum(axis=1) == 2).all()


def test_signals_decompose_the_stock_return() -> None:
    ret, grp = _panel(3)
    ir, _ = I.industry_returns(ret, grp, min_members=1)
    neutral = I.neutral_signal(ret, grp)
    sums = neutral.T.groupby(grp.to_numpy()).sum(min_count=1).T
    assert np.nanmax(np.abs(sums.to_numpy())) < 1e-12
    isig = I.industry_signal(ret, grp, ir)
    row = isig.iloc[30]
    for g in grp.unique():
        assert row[grp.index[grp == g]].nunique() == 1  # every member carries its industry's signal


def test_fama_macbeth_recovers_a_planted_slope() -> None:
    rng = np.random.default_rng(4)
    x = pd.DataFrame(rng.normal(size=(IDX.size, 200)), index=IDX)
    y = (
        0.01
        + 0.02 * (x - x.mean(axis=1).to_numpy()[:, None]) / x.std(axis=1, ddof=0).to_numpy()[:, None]
        + rng.normal(0, 0.01, x.shape)
    )
    fm = I.fama_macbeth(y, {"x": x})
    assert fm.frame().loc["x", "mean"] == pytest.approx(0.02, abs=0.001)
    assert fm.frame().loc["x", "t_nw"] > 20


def test_cross_autocorrelation_finds_a_lead() -> None:
    rng = np.random.default_rng(5)
    a = rng.normal(size=IDX.size)
    b = np.r_[0.0, a[:-1]] + 0.3 * rng.normal(size=IDX.size)
    ir = pd.DataFrame({"a": a, "b": b}, index=IDX)
    ca = I.cross_autocorrelation(ir, 1)
    assert ca.loc["a", "b"] > 0.8 and abs(ca.loc["b", "a"]) < 0.3
    assert I.pair_months(ir, 1).loc["a", "b"] == IDX.size - 1


def test_random_groups_keep_sizes() -> None:
    _, grp = _panel()
    rg = I.random_groups(grp, 7)
    assert rg.value_counts().sort_index().equals(grp.value_counts().sort_index())
    assert (rg != grp).any()


def test_placebo_and_dispersion() -> None:
    ret, grp = _panel(6)
    pl = I.placebo(ret, grp, draws=5)
    assert len(pl) == 5 and set(pl.columns) == {"draw", "mean", "sharpe", "dispersion"}
    ir, _ = I.industry_returns(ret, grp)
    assert (I.dispersion(ir).dropna() > 0).all()


def test_relative_returns_and_autocorrelation() -> None:
    ret, grp = _panel(7)
    ir, _ = I.industry_returns(ret, grp)
    rel = I.relative_returns(ir)
    np.testing.assert_allclose(rel.sum(axis=1), 0.0, atol=1e-12)
    assert I.own_autocorrelation(ir).abs().max() < 0.4


def test_within_and_rotation() -> None:
    ret, grp = _panel(8)
    big = pd.concat([ret, ret.add_suffix("x")], axis=1)
    g2 = pd.concat([grp, grp.rename(lambda c: c + "x")])
    s = I.within(big, g2, "g0")
    assert s.wml.notna().sum() > 50
    ex = I.within(big, g2, "g0", exclude=True)
    assert ex.long.shape[1] == 100
    ir, _ = I.industry_returns(ret, grp)
    w = I.winners_by_year(I.industry_momentum(ir, 1, 1, 0, top=2))
    assert w.abs().max().max() <= 1.0


def test_spanning() -> None:
    rng = np.random.default_rng(9)
    x = pd.Series(rng.normal(0.01, 0.04, IDX.size), index=IDX)
    y = 0.5 * x + 0.002 + rng.normal(0, 0.001, IDX.size)
    r = I.spanning(y, pd.DataFrame({"x": x}))
    assert r.coef[1] == pytest.approx(0.5, abs=0.01) and r.alpha == pytest.approx(0.024, abs=0.003)


def test_groups_on_synthetic_constituents(use_data: Path) -> None:
    from ukfactors.data import yahoo

    g = I.groups(yahoo.constituents())
    assert g.notna().all() and g.nunique() >= 5
