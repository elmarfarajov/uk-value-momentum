"""The deeper Day 1 analysis: alphas, the value-momentum mix, the Exeter portfolio grids, and how robust each premium is.

* :func:`regress` - OLS of a factor on others with Newey-West standard errors (alphas annualised).
* :func:`mix_frontier` and :func:`tangency_weight` - value and momentum combined, by weight.
* :func:`rebuild_factor` - SMB, HML and UMD rebuilt from Exeter's six 2x3 portfolios, the check
  that the published factors are what their portfolios say they are.
* :func:`grid` - mean excess returns and t-statistics of a 5x5 sort, and the high-minus-low
  spread within each size row.
* :func:`start_sensitivity`, :func:`calendar_years`, :func:`acf`, :func:`drawdown_episodes`,
  :func:`market_states` - how much each premium depends on when one looks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from . import stats

Array = NDArray[np.float64]


@dataclass(frozen=True)
class Regression:
    names: list[str]  # "alpha" first, then the regressors
    coef: Array  # monthly
    se: Array  # Newey-West
    tstat: Array
    r2: float
    months: int

    @property
    def alpha(self) -> float:
        """Annualised intercept."""
        return 12.0 * float(self.coef[0])

    @property
    def alpha_t(self) -> float:
        return float(self.tstat[0])

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame({"coef": self.coef, "se": self.se, "t": self.tstat}, index=self.names)


def regress(y: pd.Series, x: pd.DataFrame, lags: int | None = None) -> Regression:
    """OLS of ``y`` on a constant and ``x`` over their common months, with Bartlett-weighted (Newey-West) errors.

    The covariance is ``(X'X)^-1 S (X'X)^-1`` with ``S = sum_j w_j (Gamma_j + Gamma_j')``,
    ``Gamma_j = sum_t u_t u_{t-j} x_t x_{t-j}'`` and Bartlett weights ``w_j = 1 - j/(q+1)``; no
    small-sample correction, which is statsmodels' ``HAC`` with ``use_correction=False``.
    """
    data = pd.concat([y.rename("__y__"), x], axis=1).dropna()
    yv = data["__y__"].to_numpy(dtype=np.float64)
    xv = np.column_stack([np.ones(len(data)), data[list(x.columns)].to_numpy(dtype=np.float64)])
    n = yv.size
    q = stats.nw_lags(n) if lags is None else lags
    xtx_inv = np.linalg.inv(xv.T @ xv)
    beta = xtx_inv @ xv.T @ yv
    u = yv - xv @ beta
    score = xv * u[:, None]
    s = score.T @ score
    for j in range(1, q + 1):
        g = score[j:].T @ score[:-j]
        s += (1.0 - j / (q + 1.0)) * (g + g.T)
    cov = xtx_inv @ s @ xtx_inv
    se = np.sqrt(np.diag(cov))
    r2 = 1.0 - float(u @ u) / float(((yv - yv.mean()) ** 2).sum())
    return Regression(["alpha", *[str(c) for c in x.columns]], beta, se, beta / se, r2, n)


def rolling_correlation(a: pd.Series, b: pd.Series, window: int = 36) -> pd.Series:
    j = pd.concat([a, b], axis=1).dropna()
    return j.iloc[:, 0].rolling(window).corr(j.iloc[:, 1])


def mix_frontier(a: pd.Series, b: pd.Series, weights: Array | None = None) -> pd.DataFrame:
    """Annualised mean, volatility, Sharpe ratio and maximum drawdown of ``w b + (1 - w) a`` for each weight ``w``."""
    j = pd.concat([a, b], axis=1).dropna()
    w = np.linspace(0.0, 1.0, 21) if weights is None else np.asarray(weights, dtype=np.float64)
    rows = []
    for wi in w:
        mix = ((1.0 - wi) * j.iloc[:, 0] + wi * j.iloc[:, 1]).to_numpy(dtype=np.float64)
        rows.append(
            {
                "weight": float(wi),
                "mean": 12.0 * float(mix.mean()),
                "vol": float(np.sqrt(12.0) * mix.std(ddof=1)),
                "sharpe": stats.annual_sharpe(mix),
                "max_drawdown": stats.max_drawdown(mix),
            }
        )
    return pd.DataFrame(rows).set_index("weight")


def tangency_weight(a: pd.Series, b: pd.Series) -> float:
    """The weight on ``b`` that maximises the Sharpe ratio of ``w b + (1 - w) a``: ``Sigma^-1 mu``, normalised to sum to one."""
    j = pd.concat([a, b], axis=1).dropna().to_numpy(dtype=np.float64)
    raw = np.linalg.solve(np.cov(j, rowvar=False), j.mean(axis=0))
    return float(raw[1] / raw.sum())


def calendar_years(frame: pd.DataFrame, min_months: int = 12) -> pd.DataFrame:
    """Compounded return of each column in each calendar year with at least ``min_months`` observations."""
    grouped = frame.groupby(pd.DatetimeIndex(frame.index).year)
    compounded = grouped.apply(lambda g: (1.0 + g).prod() - 1.0)
    counts = grouped.count()
    return compounded.where(counts >= min_months)


def start_sensitivity(series: pd.Series, first: int, last: int) -> pd.DataFrame:
    """Sharpe ratio and Newey-West t from each start year to the end of the sample."""
    s = series.dropna()
    rows = []
    for year in range(first, last + 1):
        v = s.loc[str(year) :].to_numpy(dtype=np.float64)
        if v.size < 60:
            break
        rows.append({"start": year, "months": v.size, "sharpe": stats.annual_sharpe(v), "t_nw": stats.nw_tstat(v)})
    return pd.DataFrame(rows).set_index("start")


def acf(series: pd.Series, lags: int = 24) -> pd.Series:
    """Sample autocorrelations at lags 1..``lags`` (the usual estimator, divided by the lag-0 sum of squares)."""
    v = series.dropna().to_numpy(dtype=np.float64)
    v = v - v.mean()
    denom = float(v @ v)
    return pd.Series([float(v[k:] @ v[:-k]) / denom for k in range(1, lags + 1)], index=range(1, lags + 1))


def ljung_box(series: pd.Series, lags: int = 12) -> tuple[float, float]:
    """Ljung-Box Q over ``lags`` autocorrelations and its chi-squared p-value."""
    from scipy import stats as sps

    n = int(series.dropna().size)
    r = acf(series, lags).to_numpy()
    q = n * (n + 2) * float(np.sum(r**2 / (n - np.arange(1, lags + 1))))
    return q, float(sps.chi2.sf(q, lags))


@dataclass(frozen=True)
class Episode:
    peak: pd.Timestamp
    trough: pd.Timestamp
    recovery: pd.Timestamp | None  # None: not yet recovered
    depth: float  # positive fraction
    to_trough: int  # months from peak to trough
    to_recover: int | None  # months from trough to recovery


def drawdown_episodes(series: pd.Series, top: int = 5) -> list[Episode]:
    """The ``top`` deepest non-overlapping drawdowns of cumulative wealth, each from its peak to its recovery."""
    s = series.dropna()
    wealth = (1.0 + s).cumprod()
    episodes: list[Episode] = []
    peak_value, peak_date = 1.0, s.index[0] - pd.offsets.MonthEnd(1)
    trough_value, trough_date = 1.0, peak_date
    in_dd = False
    for date, w in wealth.items():
        ts = pd.Timestamp(str(date))
        if w >= peak_value:
            if in_dd:
                episodes.append(_episode(peak_date, trough_date, ts, 1.0 - trough_value / peak_value))
                in_dd = False
            peak_value, peak_date = float(w), ts
            trough_value, trough_date = float(w), ts
        else:
            in_dd = True
            if w < trough_value:
                trough_value, trough_date = float(w), ts
    if in_dd:
        episodes.append(_episode(peak_date, trough_date, None, 1.0 - trough_value / peak_value))
    return sorted(episodes, key=lambda e: -e.depth)[:top]


def _episode(peak: pd.Timestamp, trough: pd.Timestamp, recovery: pd.Timestamp | None, depth: float) -> Episode:
    def months(a: pd.Timestamp, b: pd.Timestamp) -> int:
        return (b.year - a.year) * 12 + (b.month - a.month)

    return Episode(peak, trough, recovery, depth, months(peak, trough), None if recovery is None else months(trough, recovery))


def rebuild_factor(six: pd.DataFrame, kind: str) -> pd.Series:
    """A factor rebuilt from a 2x3 sort's six value-weighted portfolios (columns SL, SM, SH, BL, BM, BH).

    HML and UMD are ``(SH + BH)/2 - (SL + BL)/2``: high book-to-market (or past winners) minus
    low, averaged over small and big. SMB is the average of the three small portfolios minus the
    average of the three big ones.
    """
    if kind in ("HML", "UMD"):
        return ((six["SH"] + six["BH"]) - (six["SL"] + six["BL"])) / 2.0
    if kind == "SMB":
        return six[["SL", "SM", "SH"]].mean(axis=1) - six[["BL", "BM", "BH"]].mean(axis=1)
    raise ValueError(f"unknown factor {kind}")


SIZE_ROWS = ["Small", "2", "3", "4", "Big"]
SORT_COLS = ["Low", "2", "3", "4", "High"]


def grid(ports: pd.DataFrame, rf: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Annualised mean excess returns and Newey-West t of a 5x5 size sort, and each size row's high-minus-low spread.

    Exeter's 25 portfolios are ordered smallest size first, and within a size group from the low
    to the high end of the second sort (book-to-market, or past return).
    """
    excess = ports.sub(rf.reindex(ports.index), axis=0).dropna()
    means = np.empty((5, 5))
    ts = np.empty((5, 5))
    for k, col in enumerate(ports.columns[:25]):
        v = excess[col].to_numpy(dtype=np.float64)
        means[k // 5, k % 5] = 12.0 * v.mean()
        ts[k // 5, k % 5] = stats.nw_tstat(v)
    rows = []
    cols = list(ports.columns[:25])
    for i in range(5):
        spread = (ports[cols[5 * i + 4]] - ports[cols[5 * i]]).dropna().to_numpy(dtype=np.float64)
        rows.append({"size": SIZE_ROWS[i], "spread": 12.0 * spread.mean(), "t_nw": stats.nw_tstat(spread)})
    return (
        pd.DataFrame(means, index=SIZE_ROWS, columns=SORT_COLS),
        pd.DataFrame(ts, index=SIZE_ROWS, columns=SORT_COLS),
        pd.DataFrame(rows).set_index("size"),
    )


def deciles(ports: pd.DataFrame, rf: pd.Series) -> pd.DataFrame:
    """Annualised mean excess return, volatility, Sharpe ratio and NW t of each of ten portfolios."""
    excess = ports.sub(rf.reindex(ports.index), axis=0).dropna()
    rows = []
    for c in excess.columns:
        v = excess[c].to_numpy(dtype=np.float64)
        rows.append(
            {
                "portfolio": c,
                "mean": 12.0 * v.mean(),
                "vol": float(np.sqrt(12.0) * v.std(ddof=1)),
                "sharpe": stats.annual_sharpe(v),
                "t_nw": stats.nw_tstat(v),
            }
        )
    return pd.DataFrame(rows).set_index("portfolio")


def market_states(factors: pd.DataFrame, market: pd.Series) -> pd.DataFrame:
    """Each factor's annualised mean in months when the market rose and when it fell, and in the market's worst 5% of months."""
    j = pd.concat([factors, market.rename("__m__")], axis=1)
    rows = []
    for c in factors.columns:
        d = j[[c, "__m__"]].dropna()
        up, down = d[d["__m__"] > 0][c], d[d["__m__"] <= 0][c]
        worst = d[d["__m__"] <= d["__m__"].quantile(0.05)][c]
        rows.append(
            {
                "factor": c,
                "up_months": int(up.size),
                "up": 12.0 * float(up.mean()),
                "down_months": int(down.size),
                "down": 12.0 * float(down.mean()),
                "worst5_monthly": float(worst.mean()),
                "beta_up": float(np.polyfit(d.loc[up.index, "__m__"], up, 1)[0]),
                "beta_down": float(np.polyfit(d.loc[down.index, "__m__"], down, 1)[0]),
            }
        )
    return pd.DataFrame(rows).set_index("factor")


def bootstrap_sharpes(series: pd.Series, reps: int = 2000, seed: int = 0) -> Array:
    v = series.dropna().to_numpy(dtype=np.float64)
    return stats.stationary_bootstrap(v, stats.annual_sharpe, reps=reps, seed=seed)
