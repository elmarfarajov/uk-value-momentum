"""Momentum crashes and tail risk: states, the short call, scaling and extreme values."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ukfactors import crashes as C

IDX = pd.date_range("1980-01-31", periods=600, freq="ME")


@pytest.fixture(scope="module")
def mkt() -> pd.Series:
    return pd.Series(np.random.default_rng(1).normal(0.006, 0.045, 600), index=IDX)


def test_bear_uses_only_past_returns(mkt: pd.Series) -> None:
    b = C.bear(mkt)
    assert b.iloc[:24].isna().all() and b.iloc[24] in (0.0, 1.0)
    changed = mkt.copy()
    changed.iloc[100] = -0.9  # a crash in month 100 cannot change the state of month 100
    assert C.bear(changed).iloc[100] == b.iloc[100]


def test_realised_vol_is_lagged() -> None:
    x = pd.Series([0.01, -0.01] * 10, index=IDX[:20])
    v = C.realised_vol(x, 6)
    assert v.first_valid_index() == IDX[6]
    assert v.iloc[10] == pytest.approx(np.sqrt(12) * x.iloc[4:10].std())


def test_optionality_finds_a_planted_short_call(mkt: pd.Series) -> None:
    b = C.bear(mkt).fillna(0)
    y = -0.7 * b * (mkt > 0) * mkt + pd.Series(np.random.default_rng(2).normal(0, 0.01, 600), index=IDX)
    r = C.optionality(y, mkt)
    assert r.coef[r.names.index("B_U_Rm")] == pytest.approx(-0.7, abs=0.15)


def test_state_table_rows(mkt: pd.Series) -> None:
    s = pd.Series(np.random.default_rng(3).normal(0.01, 0.04, 600), index=IDX)
    t = C.state_table(s, mkt)
    assert list(t.index) == ["all", "bull", "bear", "panic", "panic, market up"]
    assert t.loc["bull", "months"] + t.loc["bear", "months"] == t.loc["all", "months"]


def test_constant_vol_equalises_risk() -> None:
    rng = np.random.default_rng(4)
    sig = np.where(np.arange(600) % 120 < 60, 0.02, 0.08)  # calm and turbulent regimes
    s = pd.Series(rng.normal(0.0, 1.0, 600) * sig, index=IDX, name="X")
    cv = C.constant_vol(s, target=0.12)
    calm, wild = cv[(np.arange(600) % 120 < 60)[-len(cv) :]], cv[(np.arange(600) % 120 >= 60)[-len(cv) :]]
    assert np.sqrt(12) * calm.std() == pytest.approx(np.sqrt(12) * wild.std(), rel=0.35)
    assert C.constant_vol(s, cap=1.0).abs().le(s.abs().reindex(C.constant_vol(s, cap=1.0).index) + 1e-15).all()


def test_dynamic_is_out_of_sample_and_scaled(mkt: pd.Series) -> None:
    s = pd.Series(np.random.default_rng(5).normal(0.01, 0.04, 600), index=IDX)
    d = C.dynamic(s, mkt, start=120)
    assert set(d.columns) == {"weight", "return"}
    assert d["return"].std() == pytest.approx(s.loc[d.index].std())
    cut = C.dynamic(s.iloc[:400], mkt.iloc[:400], start=120)
    shared = cut.index
    ratio = (d.loc[shared, "weight"] / cut["weight"]).to_numpy()
    assert np.allclose(ratio, ratio[0])  # later data changes only the scale, never the month-by-month forecast


def test_distribution_keys() -> None:
    d = C.distribution(pd.Series(np.random.default_rng(6).normal(0, 0.05, 200)))
    assert set(d) == {"mean", "vol", "sharpe", "skew", "kurt", "worst", "maxdd", "months"}


def test_pot_var_es_ordering_and_thin_tail() -> None:
    x = pd.Series(np.random.default_rng(7).normal(0.0, 0.05, 20000))
    t = C.pot(x, 0.95)
    assert abs(t.xi) < 0.15  # the normal is in the thin-tailed (Gumbel) domain
    assert t.var(0.99) < t.var(0.999) < t.es(0.999)
    table = C.risk_table(x)
    assert table.loc[0.99, "evt_var"] == pytest.approx(table.loc[0.99, "normal_var"], rel=0.1)


def test_hill_on_exact_pareto() -> None:
    loss = (1.0 - np.random.default_rng(8).random(20000)) ** (-0.5)  # xi = 1/2
    assert C.hill(pd.Series(-loss), np.array([400]))[0] == pytest.approx(0.5, abs=0.06)
