from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ukfactors import survivorship
from ukfactors.data import yahoo


def _prices(n: int = 120, k: int = 50, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2005-01-31", periods=n, freq="ME")
    return pd.DataFrame(np.exp(np.cumsum(rng.normal(0.005, 0.07, (n, k)), axis=0)) * 100, index=idx)


def test_clean_drops_whole_series_with_impossible_moves() -> None:
    px = _prices()
    px.iloc[50:, 3] *= 100  # pence reported as pounds from month 50: a +9,900% month
    px.iloc[70, 7] /= 10  # a single x10 slip: a -90% month and a +900% month
    c = survivorship.clean(px)
    assert c.excluded == ["3", "7"]
    assert c.kept == 48 and c.returns.shape[1] == 48


def test_clean_keeps_ordinary_series_and_honours_the_cut_off() -> None:
    px = _prices()
    c = survivorship.clean(px, last_complete=px.index[99])
    assert c.excluded == [] and c.returns.index[-1] == px.index[99]
    assert np.isnan(c.returns.iloc[0]).all()


def test_non_positive_prices_are_missing_not_returns() -> None:
    px = _prices(k=2)
    px.iloc[10, 0] = 0.0
    r = survivorship.clean(px).returns
    assert np.isnan(r.iloc[10, 0]) and np.isnan(r.iloc[11, 0])


def test_momentum_signal_is_the_return_from_t_minus_12_to_t_minus_2() -> None:
    idx = pd.date_range("2000-01-31", periods=30, freq="ME")
    r = pd.DataFrame({"a": np.linspace(-0.05, 0.05, 30)}, index=idx)
    sig = survivorship.momentum_signal(r)
    assert sig.iloc[:12].isna().all().all()
    t = 20
    expected = np.prod(1 + r["a"].iloc[t - 12 : t - 1]) - 1
    assert sig["a"].iloc[t] == pytest.approx(expected)


def test_long_short_buys_winners_and_sells_losers() -> None:
    idx = pd.date_range("2000-01-31", periods=3, freq="ME")
    names = [f"s{i}" for i in range(40)]
    signal = pd.DataFrame([np.arange(40.0)] * 3, index=idx, columns=names)
    returns = pd.DataFrame(
        [np.where(np.arange(40) >= 28, 0.02, np.where(np.arange(40) <= 11, -0.01, 0.0))] * 3, index=idx, columns=names
    )
    ls = survivorship.long_short(returns, signal)
    assert ls.tolist() == pytest.approx([0.03, 0.03, 0.03])
    assert survivorship.long_short(returns.iloc[:, :20], signal.iloc[:, :20]).empty  # fewer than 30 stocks: no portfolio


def test_measure_on_the_synthetic_sample(use_data: Path) -> None:
    px = yahoo.prices()
    idx = px.index
    clean_mom = pd.Series(0.0, index=idx)
    market = pd.Series(0.0, index=idx)
    bias = survivorship.measure(px, clean_mom, market, idx[-1])
    assert bias.stocks.max() == 59  # the flipped series is excluded
    assert bias.momentum_survivors.size > 200
    assert np.isfinite(bias.survivors_premium) and bias.survivors_premium > 0  # random walks with drift
