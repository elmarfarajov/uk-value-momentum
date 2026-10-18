"""Performance statistics for monthly factor returns, with honest standard errors.

Factor returns are autocorrelated a little and fat-tailed a lot, so the textbook ``t = mean /
(sd / sqrt(T))`` overstates significance. This module reports:

* annualised mean (12 x monthly), volatility (sqrt(12) x monthly) and Sharpe ratio;
* the **Newey-West t-statistic** of the mean, with the automatic lag ``floor(4 (T/100)^(2/9))``
  and Bartlett weights (Newey and West, 1987; 1994);
* the **standard error of the Sharpe ratio** under serial correlation (Lo, 2002);
* **stationary-bootstrap** confidence intervals (Politis and Romano, 1994), which resample
  blocks of random length and so keep the dependence a plain bootstrap would destroy;
* skewness, excess kurtosis, the worst month, and the **maximum drawdown** of the cumulative
  excess return.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray
from scipy import stats as sps

Array = NDArray[np.float64]


def nw_lags(n: int) -> int:
    """Newey and West's (1994) automatic lag length for a sample of ``n``."""
    return int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))


def long_run_variance(x: ArrayLike, lags: int | None = None) -> float:
    """Bartlett-weighted long-run variance of a series about its mean."""
    v = np.asarray(x, dtype=np.float64)
    v = v - v.mean()
    n = v.size
    q = nw_lags(n) if lags is None else lags
    total = float(v @ v) / n
    for j in range(1, q + 1):
        weight = 1.0 - j / (q + 1.0)
        total += 2.0 * weight * float(v[j:] @ v[:-j]) / n
    return total


def nw_tstat(x: ArrayLike, lags: int | None = None) -> float:
    """Newey-West t-statistic of the mean of ``x``."""
    v = np.asarray(x, dtype=np.float64)
    return float(v.mean() / np.sqrt(long_run_variance(v, lags) / v.size))


def sharpe_se(x: ArrayLike, annualise: int = 12) -> float:
    """Standard error of the annualised Sharpe ratio (Lo, 2002).

    The monthly ratio's standard error ``sqrt((1 + SR^2 / 2) / T)`` is scaled by Lo's
    ``eta = q / sqrt(q + 2 sum_{k<q} (q - k) rho_k)`` with ``q = 12``, which replaces
    ``sqrt(12)`` when returns are autocorrelated.
    """
    v = np.asarray(x, dtype=np.float64)
    n = v.size
    sr = v.mean() / v.std(ddof=1)
    rho = [float(np.corrcoef(v[k:], v[:-k])[0, 1]) for k in range(1, annualise)]
    eta = annualise / np.sqrt(annualise + 2.0 * sum((annualise - k) * r for k, r in enumerate(rho, start=1)))
    return float(eta * np.sqrt((1.0 + 0.5 * sr**2) / n))


def max_drawdown(x: ArrayLike) -> float:
    """The largest peak-to-trough fall of the cumulative return ``prod(1 + r)``, as a positive fraction."""
    wealth = np.cumprod(1.0 + np.asarray(x, dtype=np.float64))
    peak = np.maximum.accumulate(np.concatenate([[1.0], wealth]))[1:]
    return float(np.max(1.0 - wealth / peak))


def drawdown_path(x: pd.Series) -> pd.Series:
    wealth = (1.0 + x).cumprod()
    peak = wealth.cummax().clip(lower=1.0)
    out = wealth / peak - 1.0
    out.name = x.name
    return out


def stationary_bootstrap(
    x: ArrayLike, statistic: Callable[[Array], float], reps: int = 2000, block: float = 6.0, seed: int = 0
) -> Array:
    """Politis-Romano stationary bootstrap: blocks of geometric length with mean ``block``, wrapping round."""
    v = np.asarray(x, dtype=np.float64)
    n = v.size
    rng = np.random.default_rng(seed)
    p = 1.0 / block
    out = np.empty(reps)
    for b in range(reps):
        idx = np.empty(n, dtype=int)
        idx[0] = rng.integers(n)
        new_block = rng.random(n) < p
        starts = rng.integers(n, size=n)
        for t in range(1, n):
            idx[t] = starts[t] if new_block[t] else (idx[t - 1] + 1) % n
        out[b] = statistic(v[idx])
    return out


def annual_sharpe(v: Array) -> float:
    return float(np.sqrt(12.0) * v.mean() / v.std(ddof=1))


@dataclass(frozen=True)
class Summary:
    name: str
    start: str
    end: str
    months: int
    mean: float  # annualised
    vol: float  # annualised
    sharpe: float
    t_nw: float
    sharpe_se: float
    sharpe_lo: float  # 95% stationary-bootstrap interval
    sharpe_hi: float
    skew: float
    excess_kurtosis: float
    worst_month: float
    max_drawdown: float

    def row(self) -> dict[str, object]:
        return self.__dict__.copy()


def summarise(series: pd.Series, reps: int = 2000, seed: int = 0) -> Summary:
    s = series.dropna()
    v = s.to_numpy(dtype=np.float64)
    boot = stationary_bootstrap(v, annual_sharpe, reps=reps, seed=seed)
    return Summary(
        str(s.name),
        f"{s.index[0]:%Y-%m}",
        f"{s.index[-1]:%Y-%m}",
        int(v.size),
        float(12.0 * v.mean()),
        float(np.sqrt(12.0) * v.std(ddof=1)),
        annual_sharpe(v),
        nw_tstat(v),
        sharpe_se(v),
        float(np.percentile(boot, 2.5)),
        float(np.percentile(boot, 97.5)),
        float(sps.skew(v)),
        float(sps.kurtosis(v)),
        float(v.min()),
        max_drawdown(v),
    )


def table(frame: pd.DataFrame, reps: int = 2000) -> pd.DataFrame:
    """One row of :class:`Summary` per column."""
    return pd.DataFrame([summarise(frame[c], reps=reps).row() for c in frame.columns]).set_index("name")


def by_period(series: pd.Series, edges: list[str]) -> pd.DataFrame:
    """Annualised mean and its Newey-West t-statistic in each period between ``edges`` (year strings)."""
    rows = []
    s = series.dropna()
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        part = s.loc[lo : str(int(hi) - 1)]
        if part.size < 24:
            continue
        v = part.to_numpy(dtype=np.float64)
        se = np.sqrt(long_run_variance(v) / v.size)
        rows.append(
            {"period": f"{lo}-{int(hi) - 1}", "months": v.size, "mean": 12 * v.mean(), "se": 12 * se, "t_nw": v.mean() / se}
        )
    return pd.DataFrame(rows)
