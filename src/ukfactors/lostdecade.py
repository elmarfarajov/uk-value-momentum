"""Value's lost decade in the UK: how deep, how unusual, and what the free data can say about why.

Value lost money in the UK, as in the US, from about 2007 to 2020. Arnott, Harvey, Kalesnik and
Linnainmaa (2021) decompose the US loss into revaluation (value stocks becoming relatively
cheaper), migration and profitability. That decomposition needs book values, which free UK data
does not provide (ADR 0015). This module asks the questions the return data can answer:

* how the episode compares with the factor's history and with other markets (:func:`episode`);
* whether the mean changed, with a sup-Wald break test and a bootstrap (:func:`sup_wald`);
* how likely a loss this long was under the earlier distribution (:func:`loss_probability`);
* how much of it lines up with other factors or with gilt yields (:func:`attribution`,
  :func:`rate_beta`);
* which leg lost: value stocks or growth stocks against the market (:func:`legs`).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import analysis, stats

LOST = ("2007-01", "2020-09")  # the episode studied: from the start of 2007 to the trough of value in late 2020


@dataclass(frozen=True)
class Episode:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp
    cumulative: float  # compounded return over the window
    annual: float  # annualised
    sharpe_before: float
    sharpe_during: float
    sharpe_after: float


def cumulative(s: pd.Series) -> float:
    v = s.dropna().to_numpy()
    return float(np.prod(1.0 + v) - 1.0)


def _sharpe(s: pd.Series) -> float:
    s = s.dropna()
    return float(np.sqrt(12) * s.mean() / s.std()) if len(s) > 12 else float("nan")


def episode(s: pd.Series, window: tuple[str, str] = LOST, name: str | None = None) -> Episode:
    """The factor's record before, during and after the window."""
    a, b = window
    during = s.loc[a:b].dropna()
    before = s.loc[: pd.Timestamp(a) - pd.offsets.MonthEnd(1)]
    after = s.loc[pd.Timestamp(b) + pd.offsets.MonthEnd(1) :]
    c = cumulative(during)
    years = len(during) / 12
    return Episode(
        name or str(s.name),
        during.index[0],
        during.index[-1],
        c,
        (1 + c) ** (1 / years) - 1 if years > 0 else float("nan"),
        _sharpe(before),
        _sharpe(during),
        _sharpe(after),
    )


# ------------------------------------------------------------------ was it unusual


def sup_wald(s: pd.Series, trim: float = 0.15) -> tuple[pd.Series, pd.Timestamp, float]:
    """Wald statistics for a single break in the mean at every date in the trimmed middle of the sample (Andrews 1993).

    Each statistic is the squared Newey-West t-statistic of a dummy for the months after the date.
    Returns the path, the date of the largest statistic, and the largest statistic.
    """
    x = s.dropna()
    n = len(x)
    lo, hi = int(trim * n), int((1 - trim) * n)
    out = {}
    for k in range(lo, hi):
        dummy = pd.Series(np.r_[np.zeros(k), np.ones(n - k)], index=x.index, name="after")
        r = analysis.regress(x, dummy.to_frame())
        out[x.index[k]] = float(r.tstat[1] ** 2)
    path = pd.Series(out)
    return path, pd.Timestamp(path.idxmax()), float(path.max())


def sup_wald_pvalue(s: pd.Series, reps: int = 200, seed: int = 0, trim: float = 0.15, block: float = 12.0) -> tuple[float, float]:
    """Bootstrap p-value of the sup-Wald statistic: resample the demeaned series in blocks (no break by construction)."""
    x = s.dropna()
    _, _, stat = sup_wald(x, trim)
    demeaned = (x - x.mean()).to_numpy()
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(reps):
        idx = _block_indices(len(x), block, rng)
        _, _, b = sup_wald(pd.Series(demeaned[idx], index=x.index), trim)
        exceed += b >= stat
    return stat, (exceed + 1) / (reps + 1)


def _block_indices(n: int, block: float, rng: np.random.Generator, length: int | None = None) -> np.ndarray:
    """Stationary-bootstrap indices into a series of ``n``: ``length`` of them (default ``n``), wrapping round."""
    m = n if length is None else length
    idx = np.empty(m, dtype=int)
    idx[0] = rng.integers(n)
    new = rng.random(m) < 1.0 / block
    starts = rng.integers(n, size=m)
    for t in range(1, m):
        idx[t] = starts[t] if new[t] else (idx[t - 1] + 1) % n
    return idx


def loss_probability(history: pd.Series, months: int, loss: float, reps: int = 5000, seed: int = 0, block: float = 12.0) -> float:
    """Probability that a ``months``-long stretch drawn from ``history`` (block bootstrap) compounds to ``loss`` or worse."""
    v = history.dropna().to_numpy()
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(reps):
        idx = _block_indices(len(v), block, rng, length=months)
        hits += np.prod(1.0 + v[idx]) - 1.0 <= loss
    return hits / reps


def expanding_mean(s: pd.Series, start: int = 60) -> pd.DataFrame:
    """The mean an investor would have estimated at each date, with a 95% Newey-West band, annualised."""
    x = s.dropna()
    rows = {}
    for k in range(start, len(x) + 1):
        v = x.iloc[:k].to_numpy()
        se = np.sqrt(stats.long_run_variance(v) / v.size)
        rows[x.index[k - 1]] = (12 * v.mean(), 12 * (v.mean() - 1.96 * se), 12 * (v.mean() + 1.96 * se))
    return pd.DataFrame.from_dict(rows, orient="index", columns=["mean", "lo", "hi"])


# ------------------------------------------------------------------ what lines up with it


def attribution(y: pd.Series, x: pd.DataFrame, fit: tuple[str, str] | None, window: tuple[str, str] = LOST) -> pd.Series:
    """Split ``y``'s cumulative arithmetic return over ``window`` into loadings x factor returns, alpha and residual.

    Loadings are estimated over ``fit`` (None: the whole sample). Sums of monthly returns are used so
    that the parts add up exactly.
    """
    data = pd.concat([y.rename("y"), x], axis=1).dropna()
    est = data.loc[fit[0] : fit[1]] if fit else data
    r = analysis.regress(est["y"], est[list(x.columns)])
    w = data.loc[window[0] : window[1]]
    parts = {c: float(r.coef[i + 1] * w[c].sum()) for i, c in enumerate(x.columns)}
    parts["alpha"] = float(r.coef[0] * len(w))
    parts["residual"] = float(w["y"].sum()) - sum(parts.values())
    parts["total"] = float(w["y"].sum())
    return pd.Series(parts)


def rate_beta(y: pd.Series, gilt_yield: pd.Series, window: tuple[str, str] | None = None) -> analysis.Regression:
    """Regression of the factor's monthly return on the month's change in the ten-year gilt yield (in percentage points)."""
    dy = (100 * gilt_yield.diff()).rename("d_yield")
    data = pd.concat([y.rename("y"), dy], axis=1).dropna()
    if window:
        data = data.loc[window[0] : window[1]]
    return analysis.regress(data["y"], data[["d_yield"]])


def legs(deciles: pd.DataFrame, market: pd.Series, rf: pd.Series, value: str = "V10", growth: str = "V1") -> pd.DataFrame:
    """Excess returns over the market of the value decile and of the growth decile, and their difference."""
    m = market.reindex(deciles.index)
    r = rf.reindex(deciles.index)
    return pd.DataFrame(
        {
            "value_vs_market": deciles[value] - r - m,
            "growth_vs_market": deciles[growth] - r - m,
            "value_minus_growth": deciles[value] - deciles[growth],
        }
    ).dropna()


def rolling_correlation(a: pd.Series, b: pd.Series, window: int = 36) -> pd.Series:
    return analysis.rolling_correlation(a, b, window)
