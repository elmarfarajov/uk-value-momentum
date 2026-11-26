"""Risk or mispricing? Asset-pricing tests of UK value and momentum.

* :func:`grs`: Gibbons, Ross and Shanken (1989): are the time-series alphas of a set of test
  portfolios jointly zero under a factor model?
* :func:`fama_macbeth`: Fama and MacBeth (1973) two-pass regressions. Betas come from full-sample
  time-series regressions; prices of risk are the averages of monthly cross-sectional
  regressions, with standard errors corrected for the estimated betas (Shanken 1992).
* :func:`exposures`: factor returns on macroeconomic innovations (bank rate, term spread,
  sterling), with Newey-West errors.
* :func:`publication`: returns before and after a publication date (McLean and Pontiff 2016):
  a premium that is risk compensation should not shrink when academics publish it.
* :func:`spread_by_size`: the high-minus-low spread in each size quintile of a 5x5 sort. If
  limits to arbitrage matter, mispricing is larger among small stocks.

The test portfolios are Exeter's 25 size-book-to-market portfolios and its six size-momentum
portfolios, both rebalanced as the factors are, with Exeter's factors (October 1980 to June 2016).
Exeter's 25 size-momentum portfolios are re-sorted only once a year, so they are a robustness
check, not the main test set (ADR 0018).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as sps

from . import analysis, stats


@dataclass(frozen=True)
class GRS:
    stat: float
    p: float
    alphas: pd.Series  # monthly
    mean_abs_alpha: float  # annualised
    sharpe_factors: float  # monthly ex post maximum Sharpe ratio of the factors
    sharpe_all: float  # of factors and test assets together
    months: int


def grs(excess: pd.DataFrame, factors: pd.DataFrame) -> GRS:
    """Gibbons-Ross-Shanken test that all alphas of ``excess`` (T x N) on ``factors`` (T x K) are zero.

    ``J = (T / N) (T - N - K) / (T - K - 1) * a' S^-1 a / (1 + mu' O^-1 mu)`` is F(N, T - N - K) under
    normal errors, with ``S`` the residual covariance (divisor T - K - 1) and ``O`` the factors'
    covariance (divisor T - 1).
    """
    data = pd.concat([excess, factors], axis=1).dropna()
    y = data[excess.columns].to_numpy(dtype=np.float64)
    f = data[factors.columns].to_numpy(dtype=np.float64)
    t, n = y.shape
    k = f.shape[1]
    x = np.column_stack([np.ones(t), f])
    b = np.linalg.lstsq(x, y, rcond=None)[0]
    e = y - x @ b
    a = b[0]
    sigma = e.T @ e / (t - k - 1)
    mu = f.mean(axis=0)
    omega = np.atleast_2d(np.cov(f, rowvar=False))
    quad_a = float(a @ np.linalg.solve(sigma, a))
    quad_f = float(mu @ np.linalg.solve(omega, mu))
    j = (t / n) * (t - n - k) / (t - k - 1) * quad_a / (1.0 + quad_f)
    p = float(sps.f.sf(j, n, t - n - k))
    return GRS(
        j,
        p,
        pd.Series(a, index=excess.columns),
        12.0 * float(np.abs(a).mean()),
        float(np.sqrt(quad_f)),
        float(np.sqrt(quad_f + quad_a)),
        t,
    )


def betas(excess: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """Full-sample time-series slopes of each test asset on the factors (rows: assets)."""
    data = pd.concat([excess, factors], axis=1).dropna()
    x = np.column_stack([np.ones(len(data)), data[factors.columns].to_numpy(dtype=np.float64)])
    b = np.linalg.lstsq(x, data[excess.columns].to_numpy(dtype=np.float64), rcond=None)[0]
    return pd.DataFrame(b[1:].T, index=excess.columns, columns=factors.columns)


@dataclass(frozen=True)
class FamaMacBeth:
    lambdas: pd.Series  # monthly, including "const"
    se: pd.Series  # Fama-MacBeth
    se_shanken: pd.Series
    r2: float  # cross-sectional R^2 of mean returns on betas (with the constant)
    fitted: pd.Series  # mean excess return implied by the model, monthly
    realised: pd.Series
    months: int

    @property
    def t(self) -> pd.Series:
        return self.lambdas / self.se

    @property
    def t_shanken(self) -> pd.Series:
        return self.lambdas / self.se_shanken


def fama_macbeth(excess: pd.DataFrame, factors: pd.DataFrame, constant: bool = True) -> FamaMacBeth:
    """Two-pass regressions; ``factors`` may be traded or not (macro innovations)."""
    data = pd.concat([excess, factors], axis=1).dropna()
    y = data[excess.columns]
    f = data[factors.columns]
    b = betas(y, f)
    x = b.to_numpy()
    if constant:
        x = np.column_stack([np.ones(len(b)), x])
    names = (["const"] if constant else []) + list(factors.columns)
    lam = np.linalg.lstsq(x, y.to_numpy().T, rcond=None)[0].T  # (T, K+1)
    t = lam.shape[0]
    mean = lam.mean(axis=0)
    se = lam.std(axis=0, ddof=1) / np.sqrt(t)
    # Shanken: scale the variance by (1 + l' O^-1 l) and add the factor covariance to the factor lambdas
    omega = np.atleast_2d(np.cov(f.to_numpy(), rowvar=False))
    lf = mean[1:] if constant else mean
    c = float(lf @ np.linalg.solve(omega, lf))
    var = lam.var(axis=0, ddof=1) / t * (1.0 + c)
    add = np.diag(omega) / t
    if constant:
        var[1:] += add
    else:
        var += add
    realised = y.mean()
    fitted = pd.Series(x @ mean, index=b.index)
    r2 = 1.0 - float(((realised - fitted) ** 2).sum()) / float(((realised - realised.mean()) ** 2).sum())
    return FamaMacBeth(
        pd.Series(mean, index=names), pd.Series(se, index=names), pd.Series(np.sqrt(var), index=names), r2, fitted, realised, t
    )


def macro(rf_monthly: pd.Series, gilt: pd.Series, gbpusd: pd.Series) -> pd.DataFrame:
    """Monthly innovations in percentage points: the change in the three-month rate and in the term spread, and sterling's % return.

    ``rf_monthly`` is the monthly return implied by the three-month rate (``fred.uk_rate``); it is
    turned back into an annual rate before the spread to the (annual) gilt yield is taken.
    """
    short = 100.0 * ((1.0 + rf_monthly) ** 12 - 1.0)
    term = 100.0 * gilt - short
    return pd.DataFrame({"D_SHORT": short.diff(), "D_TERM": term.diff(), "GBP": 100.0 * gbpusd.pct_change()}).dropna()


def exposures(factor: pd.Series, x: pd.DataFrame) -> analysis.Regression:
    """Newey-West regression of a factor's return on contemporaneous macro innovations (and anything else in ``x``)."""
    return analysis.regress(factor, x)


def publication(series: pd.Series, date: str) -> dict[str, float]:
    """Annualised mean before and after ``date``, and the change with its Newey-West t-statistic."""
    s = series.dropna()
    post = (s.index > pd.Timestamp(date)).astype(float)
    r = analysis.regress(s, pd.DataFrame({"POST": post}, index=s.index))
    pre_v = s[post == 0].to_numpy(dtype=np.float64)
    post_v = s[post == 1].to_numpy(dtype=np.float64)
    return {
        "before": 12.0 * float(pre_v.mean()),
        "after": 12.0 * float(post_v.mean()),
        "change": 12.0 * float(r.coef[1]),
        "t_change": float(r.tstat[1]),
        "months_before": float(pre_v.size),
        "months_after": float(post_v.size),
        "sharpe_before": stats.annual_sharpe(pre_v),
        "sharpe_after": stats.annual_sharpe(post_v),
    }


def spread_by_size(ports: pd.DataFrame, groups: int = 5) -> pd.DataFrame:
    """High-minus-low return within each size group of a size x characteristic sort.

    Exeter's columns run row by row from the smallest size group to the biggest, with ``groups``
    characteristic portfolios in each row (5 for the 5x5 sorts, 3 for the 2x3 sorts).
    """
    if ports.shape[1] % groups:
        raise ValueError("the number of portfolios is not a multiple of groups")
    cols = list(ports.columns)
    rows = ports.shape[1] // groups
    return pd.DataFrame({f"Q{r + 1}": ports[cols[groups * r + groups - 1]] - ports[cols[groups * r]] for r in range(rows)})


def rolling_alpha(excess: pd.DataFrame, factors: pd.DataFrame, window: int = 120) -> pd.Series:
    """Mean absolute annualised alpha of the test assets over rolling ``window``-month regressions."""
    data = pd.concat([excess, factors], axis=1).dropna()
    y = data[excess.columns].to_numpy(dtype=np.float64)
    x = np.column_stack([np.ones(len(data)), data[factors.columns].to_numpy(dtype=np.float64)])
    out = np.full(len(data), np.nan)
    for t in range(window, len(data) + 1):
        b = np.linalg.lstsq(x[t - window : t], y[t - window : t], rcond=None)[0]
        out[t - 1] = 12.0 * float(np.abs(b[0]).mean())
    return pd.Series(out, index=data.index).dropna()
