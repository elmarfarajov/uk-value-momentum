"""How much survivorship bias is worth: momentum on today's FTSE 350 against AQR's survivorship-free UK momentum.

The sample built from today's index members contains only the winners of history's selection:
companies that failed, were bought cheaply or fell out of the index are missing. Two measures:

* **the survivors' premium**: the equal-weighted average return of today's companies, month
  by month, against the UK market;
* **the momentum bias**: a 12-1 momentum strategy (rank on the return from month ``t - 12`` to
  ``t - 2``, buy the top 30%, sell the bottom 30%, equal weights, monthly) run on the survivors,
  against AQR's survivorship-free UK momentum over the same months.

Momentum's short side is the losers - exactly the companies most likely to have disappeared -
so the bias need not even have the sign one expects; this is measured, not assumed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Cleaning:
    returns: pd.DataFrame
    excluded: list[str]  # series with impossible moves, dropped whole
    kept: int


def clean(
    prices: pd.DataFrame,
    last_complete: pd.Timestamp | None = None,
    up: float = 3.0,
    down: float = -0.8,
    flip: float = 3.0,
    window: int = 36,
) -> Cleaning:
    """Monthly returns of the series with no impossible move and no unit flip, each dropped whole.

    Two rules (ADR 0003, ADR 0011):

    * **impossible moves**: any month above ``up`` (+300%) or below ``down`` (-80%). Yahoo's London
      prices flip between pence and pounds (a factor of 100), by a factor of 10 for some trusts, and
      once by a factor of 4.6 that never reverses (an unadjusted consolidation);
    * **unit flips**: two months within ``window`` months whose returns are each at least a factor
      ``flip`` in size, of opposite sign, and cancel to within a quarter of the larger. A price that
      jumps five-fold and falls back five-fold is a change of units, not two trades; a genuine crash
      or rally does not reverse itself exactly.

    Repairing such series would mean guessing which months are wrong, so they are dropped whole and
    counted. A FTSE 350 survivor with a genuine move of this kind is rare enough to lose.
    """
    px = prices.sort_index()
    if last_complete is not None:
        px = px.loc[:last_complete]
    px = px.where(px > 0)
    ret = px.pct_change(fill_method=None)
    bad = ((ret > up) | (ret < down)).any()
    log = np.log1p(ret)
    big = np.log(flip)
    for col in ret.columns:
        if bad[col]:
            continue
        x = log[col].dropna()
        hits = x[x.abs() >= big]
        if hits.size < 2:
            continue
        pos = {d: i for i, d in enumerate(x.index)}
        for a, b in zip(hits.index[:-1], hits.index[1:], strict=True):
            va, vb = float(hits[a]), float(hits[b])
            if va * vb < 0 and pos[b] - pos[a] <= window and abs(va + vb) <= 0.25 * max(abs(va), abs(vb)):
                bad[col] = True
                break
    dropped = list(bad[bad].index)
    return Cleaning(ret.drop(columns=dropped), sorted(str(c) for c in dropped), int((~bad).sum()))


def monthly_returns(prices: pd.DataFrame, last_complete: pd.Timestamp | None = None) -> pd.DataFrame:
    """Simple monthly returns from month-end prices, unfinished month dropped and series with impossible moves excluded."""
    return clean(prices, last_complete).returns


def momentum_signal(returns: pd.DataFrame, lookback: int = 12, skip: int = 1) -> pd.DataFrame:
    """Cumulative return from ``t - lookback`` to ``t - skip - 1``, known at the end of month ``t - 1``, for holding in ``t``."""
    log = pd.DataFrame(np.log1p(returns), index=returns.index, columns=returns.columns)
    window = log.rolling(lookback - skip, min_periods=lookback - skip).sum().shift(skip + 1)
    return pd.DataFrame(np.expm1(window), index=window.index, columns=window.columns)


def long_short(returns: pd.DataFrame, signal: pd.DataFrame, share: float = 0.3, min_stocks: int = 30) -> pd.Series:
    """Equal-weighted top ``share`` minus bottom ``share`` of the signal, rebalanced monthly."""
    out = {}
    for date in returns.index:
        s = signal.loc[date].dropna()
        r = returns.loc[date]
        s = s[r.reindex(s.index).notna()]
        if s.size < min_stocks:
            continue
        lo, hi = s.quantile(share), s.quantile(1.0 - share)
        winners = r[s.index[s >= hi]]
        losers = r[s.index[s <= lo]]
        out[date] = float(winners.mean() - losers.mean())
    return pd.Series(out, name="MOM_SURVIVORS")


@dataclass(frozen=True)
class Bias:
    survivors_premium: float  # annualised mean of survivors' equal-weighted average minus the market
    momentum_survivors: pd.Series
    momentum_clean: pd.Series
    mean_gap: float  # annualised, survivors minus clean
    correlation: float
    stocks: pd.Series  # number of stocks with a signal each month


def measure(prices: pd.DataFrame, clean_momentum: pd.Series, market_total: pd.Series, last_complete: pd.Timestamp) -> Bias:
    ret = clean(prices, last_complete).returns
    signal = momentum_signal(ret)
    survivors = long_short(ret, signal)
    common = survivors.index.intersection(clean_momentum.dropna().index)
    s, c = survivors.loc[common], clean_momentum.loc[common]
    average = ret.mean(axis=1, skipna=True)
    overlap = average.index.intersection(market_total.dropna().index)
    premium = 12.0 * float((average.loc[overlap] - market_total.loc[overlap]).mean())
    count = signal.notna().sum(axis=1)
    return Bias(premium, s, c, 12.0 * float(s.mean() - c.mean()), float(s.corr(c)), count)
