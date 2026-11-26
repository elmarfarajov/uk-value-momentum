"""Momentum crashes and tail risk in the UK: when momentum crashes, whether scaling helps, how fat the tail is.

* **When** (Daniel and Moskowitz 2016): momentum crashes in panic states, after the market has
  fallen and while it is volatile, when the market rebounds. In bear markets the loser portfolio
  holds high-beta stocks, so the long/short factor is short a call on the market. :func:`optionality`
  estimates that asymmetry; :func:`state_table` the returns by state.
* **Scaling** (Barroso and Santa-Clara 2015): momentum's own recent volatility forecasts its
  future volatility but not its mean, so holding it at constant volatility (:func:`constant_vol`)
  avoids much of the crash risk. Daniel and Moskowitz's dynamic weight (:func:`dynamic`) also
  forecasts the mean from the bear-market and volatility state, out of sample.
* **How fat** (extreme value theory): a generalised Pareto distribution fitted to the losses
  beyond a high threshold (:func:`pot`), the Hill estimator of the tail index (:func:`hill`), and
  value at risk and expected shortfall from the normal, the empirical and the fitted tail
  (:func:`risk_table`).

Monthly data throughout: AQR's UK factors in sterling, and the UK market's total return.
Barroso and Santa-Clara estimate volatility from daily returns; free UK factor data is monthly, so
volatility here comes from the past six months (ADR 0017).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as sps

from . import analysis, stats


def bear(market: pd.Series, lookback: int = 24) -> pd.Series:
    """1 when the market's return over the past ``lookback`` months, to the end of ``t - 1``, was negative."""
    past = np.log1p(market).rolling(lookback, min_periods=lookback).sum().shift(1)
    return (past < 0).astype(float).where(past.notna()).rename("BEAR")


def market_variance(market: pd.Series, window: int = 6) -> pd.Series:
    """Annualised variance of the market over the past ``window`` months, known at the end of ``t - 1``."""
    return (12.0 * market.rolling(window, min_periods=window).var().shift(1)).rename("MVAR")


def realised_vol(x: pd.Series, window: int = 6) -> pd.Series:
    """Annualised volatility of ``x`` over the past ``window`` months, known at the end of ``t - 1``."""
    return (np.sqrt(12.0) * x.rolling(window, min_periods=window).std().shift(1)).rename("VOL")


# ------------------------------------------------------------------ when


def optionality(strategy: pd.Series, market: pd.Series, lookback: int = 24) -> analysis.Regression:
    """Daniel-Moskowitz: ``R = a + aB B + (b0 + bB B + bBU B U) Rm``; ``U`` = market up this month.

    A negative ``bBU`` means that in bear markets the strategy loses more when the market rises
    than it gains when the market falls: it is short a call.
    """
    b = bear(market, lookback)
    u = (market > 0).astype(float)
    x = pd.DataFrame({"B": b, "Rm": market, "B_Rm": b * market, "B_U_Rm": b * u * market})
    return analysis.regress(strategy, x)


def state_table(strategy: pd.Series, market: pd.Series, lookback: int = 24, window: int = 6) -> pd.DataFrame:
    """The strategy's record in bull markets, bear markets, and panic states (bear and market variance above its median)."""
    b = bear(market, lookback)
    v = market_variance(market, window)
    j = pd.concat([strategy.rename("s"), b, v, market.rename("m")], axis=1).dropna()
    panic = (j["BEAR"] == 1) & (j["MVAR"] > j["MVAR"].median())
    rows = {}
    for name, mask in (
        ("all", pd.Series(True, index=j.index)),
        ("bull", j["BEAR"] == 0),
        ("bear", j["BEAR"] == 1),
        ("panic", panic),
        ("panic, market up", panic & (j["m"] > 0)),
    ):
        s = j.loc[mask, "s"].to_numpy(dtype=np.float64)
        rows[name] = {
            "months": int(s.size),
            "mean": 12.0 * float(s.mean()) if s.size else np.nan,
            "vol": float(np.sqrt(12.0) * s.std(ddof=1)) if s.size > 1 else np.nan,
            "skew": float(sps.skew(s)) if s.size > 2 else np.nan,
            "worst": float(s.min()) if s.size else np.nan,
        }
    return pd.DataFrame(rows).T


# ------------------------------------------------------------------ scaling


def constant_vol(strategy: pd.Series, target: float | None = None, window: int = 6, cap: float | None = None) -> pd.Series:
    """Barroso-Santa-Clara: hold ``target / forecast`` of the strategy, the forecast its past ``window``-month volatility.

    ``target`` defaults to the strategy's full-sample volatility. That choice scales the whole series
    by one number, so it changes no Sharpe ratio, skewness or kurtosis. ``cap`` bounds the weight.
    """
    s = strategy.dropna()
    tgt = float(np.sqrt(12.0) * s.std(ddof=1)) if target is None else target
    w = tgt / realised_vol(s, window)
    if cap is not None:
        w = w.clip(upper=cap)
    return (w * s).dropna().rename(f"{s.name}_CV")


def dynamic(strategy: pd.Series, market: pd.Series, window: int = 6, start: int = 120, lookback: int = 24) -> pd.DataFrame:
    """Daniel-Moskowitz's dynamic weight ``mu_t / sigma_t^2``, with the mean forecast out of sample.

    The mean forecast regresses the strategy on ``B_{t-1} x sigma^2_m`` (the bear indicator times the
    market's recent variance) on data up to ``t - 1`` only, from month ``start`` on. The variance
    forecast is the strategy's past ``window``-month variance. The series is scaled ex post to the
    strategy's volatility, which changes no Sharpe ratio. Returns the weight and the return.
    """
    s = strategy.rename("s")
    z = (bear(market, lookback) * market_variance(market, window)).rename("z")
    var = (realised_vol(s, window) ** 2).rename("v")
    j = pd.concat([s, z, var], axis=1).dropna()
    sv, zv = j["s"].to_numpy(), j["z"].to_numpy()
    mu = np.full(len(j), np.nan)
    for t in range(start, len(j)):
        x = np.column_stack([np.ones(t), zv[:t]])
        g = np.linalg.lstsq(x, sv[:t], rcond=None)[0]
        mu[t] = 12.0 * (g[0] + g[1] * zv[t])  # annualised mean forecast for month t
    w = pd.Series(mu, index=j.index) / j["v"]
    r = (w * j["s"]).dropna()
    scale = float(np.sqrt(12.0) * j["s"].loc[r.index].std(ddof=1)) / float(np.sqrt(12.0) * r.std(ddof=1))
    return pd.DataFrame({"weight": (w * scale).loc[r.index], "return": r * scale})


def distribution(x: pd.Series) -> dict[str, float]:
    v = x.dropna().to_numpy(dtype=np.float64)
    return {
        "mean": 12.0 * float(v.mean()),
        "vol": float(np.sqrt(12.0) * v.std(ddof=1)),
        "sharpe": stats.annual_sharpe(v),
        "skew": float(sps.skew(v)),
        "kurt": float(sps.kurtosis(v)),
        "worst": float(v.min()),
        "maxdd": stats.max_drawdown(v),
        "months": float(v.size),
    }


# ------------------------------------------------------------------ extreme values


@dataclass(frozen=True)
class Tail:
    """A generalised Pareto fit to the losses above ``u``: shape ``xi`` (the tail index), scale ``beta``."""

    xi: float
    beta: float
    u: float
    exceed: int
    n: int

    def var(self, p: float) -> float:
        """Loss exceeded with probability ``1 - p`` (McNeil, Frey and Embrechts 2015, eq. 5.18)."""
        q = (self.n / self.exceed) * (1.0 - p)
        if abs(self.xi) < 1e-9:
            return self.u - self.beta * np.log(q)
        return self.u + self.beta / self.xi * (q ** (-self.xi) - 1.0)

    def es(self, p: float) -> float:
        """Expected loss beyond ``var(p)``; finite only for ``xi < 1``."""
        return (self.var(p) + self.beta - self.xi * self.u) / (1.0 - self.xi)


def pot(returns: pd.Series, quantile: float = 0.9) -> Tail:
    """Peaks over threshold: fit a generalised Pareto to the losses (``-returns``) above their ``quantile``."""
    loss = -returns.dropna().to_numpy(dtype=np.float64)
    u = float(np.quantile(loss, quantile))
    ex = loss[loss > u] - u
    xi, _, beta = sps.genpareto.fit(ex, floc=0.0)
    return Tail(float(xi), float(beta), u, int(ex.size), int(loss.size))


def hill(returns: pd.Series, ks: np.ndarray) -> np.ndarray:
    """Hill estimates of the left tail index ``xi`` using the ``k`` largest losses, for each ``k``."""
    loss = np.sort(-returns.dropna().to_numpy(dtype=np.float64))[::-1]
    out = np.full(len(ks), np.nan)
    for i, k in enumerate(ks):
        top = loss[: k + 1]
        if top[-1] > 0:
            out[i] = float(np.mean(np.log(top[:k])) - np.log(top[k]))
    return out


def risk_table(returns: pd.Series, ps: tuple[float, ...] = (0.99, 0.999), quantile: float = 0.9) -> pd.DataFrame:
    """Monthly VaR and ES (as positive losses) at each level: normal, empirical and generalised Pareto."""
    v = returns.dropna().to_numpy(dtype=np.float64)
    mu, sd = float(v.mean()), float(v.std(ddof=1))
    tail = pot(returns, quantile)
    rows = []
    for p in ps:
        z = sps.norm.ppf(p)
        emp_var = float(-np.quantile(v, 1.0 - p))
        beyond = -v[v <= -emp_var]
        rows.append(
            {
                "p": p,
                "normal_var": -mu + sd * z,
                "normal_es": -mu + sd * sps.norm.pdf(z) / (1.0 - p),
                "empirical_var": emp_var,
                "empirical_es": float(beyond.mean()) if beyond.size else np.nan,
                "evt_var": tail.var(p),
                "evt_es": tail.es(p),
            }
        )
    return pd.DataFrame(rows).set_index("p")
