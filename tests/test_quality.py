"""Quality and value traps: the factor-level tools and the stock-level trap buckets."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ukfactors import quality as Q

IDX = pd.date_range("1990-01-31", periods=480, freq="ME")


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    m = rng.normal(0.005, 0.045, 480)
    q = -0.4 * m + rng.normal(0.004, 0.02, 480)
    h = 0.003 - 0.5 * q + rng.normal(0, 0.025, 480)
    return pd.DataFrame({"MKT": m, "HML": h, "QMJ": q}, index=IDX)


def test_sample_starts_with_qmj_and_tolerates_missing_val() -> None:
    p = pd.DataFrame({c: 0.01 for c in ("MKT", "SMB", "HML", "HML_DEVIL", "UMD", "QMJ", "VAL")}, index=IDX)
    p.loc[:"1993-06", "QMJ"] = np.nan
    p.iloc[-3:, p.columns.get_loc("VAL")] = np.nan
    s = Q.sample(p)
    assert s.index[0] == pd.Timestamp("1993-07-31") and s.index[-1] == IDX[-1]


def test_mix_is_the_weighted_average(frame: pd.DataFrame) -> None:
    m = Q.mix(frame["HML"], frame["QMJ"], 0.25)
    assert m.to_numpy() == pytest.approx((0.75 * frame["HML"] + 0.25 * frame["QMJ"]).to_numpy())
    assert m.name == "MIX25"


def test_adjusted_alpha_finds_the_negative_loading(frame: pd.DataFrame) -> None:
    a = Q.adjusted_alpha(frame["HML"], frame[["MKT"]], frame["QMJ"])
    assert a.loading == pytest.approx(-0.5, abs=0.1)
    assert a.with_quality.alpha > a.base.alpha  # removing the junk exposure raises the alpha
    assert a.base.months == a.with_quality.months


def test_periods_compound_correctly() -> None:
    f = pd.DataFrame({"X": 0.01}, index=IDX[:24])
    t = Q.periods(f, {"all": (None, None), "first year": (None, str(IDX[11].date()))})
    assert t.loc[("all", "X"), "total"] == pytest.approx(1.01**24 - 1)
    assert t.loc[("first year", "X"), "annual"] == pytest.approx(1.01**12 - 1)


def test_flight_to_quality(frame: pd.DataFrame) -> None:
    f = Q.flight_to_quality(frame["QMJ"], frame["MKT"])
    assert f["worst"] > f["middle"] > f["best"]
    assert f["beta"] < -0.2 and f["beta_t"] < -3


def test_international_table() -> None:
    rng = np.random.default_rng(2)
    q = pd.DataFrame(rng.normal(0.004, 0.02, (300, 2)), index=IDX[-300:], columns=["A", "B"])
    h = pd.DataFrame({"A": -q["A"] + rng.normal(0.006, 0.02, 300), "B": rng.normal(0.004, 0.02, 300)}, index=q.index)
    t = Q.international(q, h, start="1990-01")
    assert t.loc["A", "corr"] < -0.5 < t.loc["B", "corr"]
    assert set(t.columns) >= {"corr", "value", "quality", "mix", "gain"}


def test_sharpe_gain_is_positive_for_a_hedge(frame: pd.DataFrame) -> None:
    g = Q.sharpe_gain(frame["HML"], frame["QMJ"], reps=60, seed=3)
    assert g.shape == (60,) and np.median(g) > 0


def test_cheapness_and_volatility_are_lagged() -> None:
    r = pd.DataFrame({"A": np.full(80, 0.01)}, index=IDX[:80])
    c = Q.cheapness(r)
    assert c["A"].first_valid_index() == IDX[60]
    assert c["A"].iloc[70] == pytest.approx(1.01**48 - 1)
    v = Q.volatility(r)
    assert v["A"].first_valid_index() == IDX[30]


def test_trap_buckets_shapes_and_order() -> None:
    rng = np.random.default_rng(4)
    sig = np.linspace(0.03, 0.15, 120)
    r = pd.DataFrame(rng.normal(0.008, 1.0, (110, 120)) * sig, index=IDX[:110])
    b, tab = Q.trap_buckets(r, min_stocks=100)
    assert list(b.columns) == ["V1", "V2", "V3", "CHEAP", "ALL"]
    assert tab.loc["V1", "volatility"] < tab.loc["V3", "volatility"]
    assert tab.loc["V1", "trap_rate"] < tab.loc["V3", "trap_rate"]
    assert tab.loc["CHEAP", "obs"] == pytest.approx(0.3 * tab.loc["ALL", "obs"], rel=0.05)
