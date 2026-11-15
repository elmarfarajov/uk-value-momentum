"""Quality and value traps in the UK: does quality separate cheap stocks from value traps?

A value trap is a stock that is cheap for a good reason: its business is getting worse, and
it keeps getting cheaper. Asness, Frazzini and Pedersen (2019) define quality as what an
investor should pay more for (profitable, growing, safe, well-paid-out companies) and build a
quality-minus-junk factor (QMJ). Cheap stocks tend to be junky, so value and QMJ are
negatively correlated, and a value investor who also holds quality avoids the worst of the
traps. Novy-Marx (2013) makes the same point with gross profitability.

Two levels of evidence, both from free data:

* **factor level** (AQR's UK QMJ from July 1993, HML, HML Devil and VAL, in sterling): the
  correlation, value's alpha once quality is controlled for, the value-quality mix, the lost
  decade and the behaviour of quality in market falls;
* **stock level** (FTSE 350 survivors from Yahoo): free UK data has no accounts, so "cheap" is
  the long-term loser signal (returns from months t-60 to t-13, De Bondt and Thaler 1985, which
  tracks book-to-market) and "quality" is its price-based part, safety (low volatility). The
  panel holds today's survivors only, so the worst traps, the companies that failed, are
  missing (ADR 0016).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import analysis, stats
from .lostdecade import _block_indices

START = "1993-07"  # first month of AQR's UK QMJ
VALUE = ("HML", "HML_DEVIL", "VAL")


def sample(p: pd.DataFrame, columns: tuple[str, ...] = ("MKT", "SMB", "HML", "HML_DEVIL", "UMD", "QMJ", "VAL")) -> pd.DataFrame:
    """The factors from the first QMJ month, over the months the core factors share; VAL (which ends earlier) may be missing at the end."""
    core = [c for c in columns if c != "VAL"]
    return p.loc[START:, list(columns)].dropna(subset=core)


def mix(value: pd.Series, quality: pd.Series, w: float = 0.5) -> pd.Series:
    """``(1 - w) value + w quality``, monthly, over their common months."""
    j = pd.concat([value, quality], axis=1).dropna()
    return ((1.0 - w) * j.iloc[:, 0] + w * j.iloc[:, 1]).rename(f"MIX{int(round(100 * w))}")


# ------------------------------------------------------------------ factor level


@dataclass(frozen=True)
class Adjusted:
    """Value's alpha against a base model, with and without quality added."""

    base: analysis.Regression
    with_quality: analysis.Regression

    @property
    def loading(self) -> float:
        return float(self.with_quality.coef[-1])


def adjusted_alpha(value: pd.Series, base: pd.DataFrame, quality: pd.Series) -> Adjusted:
    """Regress value on the base factors, then on the base factors and QMJ, over the same months."""
    data = pd.concat([value.rename("__v__"), base, quality.rename("QMJ")], axis=1).dropna()
    b = analysis.regress(data["__v__"], data[list(base.columns)])
    q = analysis.regress(data["__v__"], data[[*base.columns, "QMJ"]])
    return Adjusted(b, q)


def periods(frame: pd.DataFrame, windows: dict[str, tuple[str | None, str | None]]) -> pd.DataFrame:
    """Compounded return, annualised return and Sharpe ratio of each column in each window."""
    rows = []
    for label, (a, b) in windows.items():
        part = frame.loc[a:b]
        for col in frame.columns:
            v = part[col].dropna().to_numpy(dtype=np.float64)
            if v.size < 12:
                continue
            total = float(np.prod(1.0 + v) - 1.0)
            rows.append(
                {
                    "window": label,
                    "factor": col,
                    "months": int(v.size),
                    "total": total,
                    "annual": (1.0 + total) ** (12.0 / v.size) - 1.0,
                    "sharpe": stats.annual_sharpe(v),
                }
            )
    return pd.DataFrame(rows).set_index(["window", "factor"])


def flight_to_quality(quality: pd.Series, market: pd.Series, share: float = 0.1) -> dict[str, float]:
    """Quality's annualised mean in the worst and best ``share`` of market months, and its quarterly market beta."""
    j = pd.concat([quality.rename("q"), market.rename("m")], axis=1).dropna()
    lo, hi = j["m"].quantile(share), j["m"].quantile(1.0 - share)
    qq = (1.0 + j).resample("QE").prod() - 1.0
    beta = analysis.regress(qq["q"], qq[["m"]])
    return {
        "worst": 12.0 * float(j.loc[j["m"] <= lo, "q"].mean()),
        "middle": 12.0 * float(j.loc[(j["m"] > lo) & (j["m"] < hi), "q"].mean()),
        "best": 12.0 * float(j.loc[j["m"] >= hi, "q"].mean()),
        "beta": float(beta.coef[1]),
        "beta_t": float(beta.tstat[1]),
    }


def international(quality: pd.DataFrame, value: pd.DataFrame, start: str = START, min_months: int = 120) -> pd.DataFrame:
    """For each country: the QMJ-HML correlation and the Sharpe ratios of value, quality and the 50/50 mix."""
    rows = {}
    for c in quality.columns.intersection(value.columns):
        j = pd.concat([value[c].rename("v"), quality[c].rename("q")], axis=1, sort=True).loc[start:].dropna()
        if len(j) < min_months:
            continue
        m = (0.5 * (j["v"] + j["q"])).to_numpy(dtype=np.float64)
        rows[c] = {
            "corr": float(j["v"].corr(j["q"])),
            "value": stats.annual_sharpe(j["v"].to_numpy(dtype=np.float64)),
            "quality": stats.annual_sharpe(j["q"].to_numpy(dtype=np.float64)),
            "mix": stats.annual_sharpe(m),
            "months": len(j),
        }
    out = pd.DataFrame(rows).T
    out["gain"] = out["mix"] - out[["value", "quality"]].max(axis=1)
    return out


def sharpe_gain(value: pd.Series, quality: pd.Series, reps: int = 1000, block: float = 12.0, seed: int = 0) -> np.ndarray:
    """Stationary-bootstrap draws of Sharpe(50/50 mix) - Sharpe(value), resampling months jointly."""
    j = pd.concat([value, quality], axis=1).dropna().to_numpy(dtype=np.float64)
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for i in range(reps):
        x = j[_block_indices(len(j), block, rng)]
        out[i] = stats.annual_sharpe(0.5 * (x[:, 0] + x[:, 1])) - stats.annual_sharpe(x[:, 0])
    return out


# ------------------------------------------------------------------ stock level


def cheapness(returns: pd.DataFrame, start: int = 60, end: int = 13) -> pd.DataFrame:
    """Long-term past return from month ``t - start`` to ``t - end``, known at the end of month ``t - 1``; low means cheap."""
    log = pd.DataFrame(np.log1p(returns), index=returns.index, columns=returns.columns)
    n = start - end + 1
    return log.rolling(n, min_periods=n).sum().shift(end).apply(np.expm1)


def volatility(returns: pd.DataFrame, window: int = 36) -> pd.DataFrame:
    """Annualised volatility over the past ``window`` months, known at the end of month ``t - 1``."""
    return returns.rolling(window, min_periods=window - 6).std().shift(1) * np.sqrt(12.0)


def trap_buckets(
    returns: pd.DataFrame, cheap_share: float = 0.3, groups: int = 3, min_stocks: int = 30, horizon: int = 12, trap: float = -0.3
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Equal-weighted returns of the cheapest stocks split by volatility, and a per-bucket trap table.

    Each month, the stocks with both signals are ranked on cheapness; the cheapest ``cheap_share``
    are split into ``groups`` by past volatility (1 = safest). Returns (monthly bucket returns with
    ``ALL`` for every ranked stock and ``CHEAP`` for all cheap stocks; a table of the mean
    next-``horizon``-month return and the share of stock-months that lose ``trap`` or more over it).
    """
    cheap = cheapness(returns)
    vol = volatility(returns)
    ok = cheap.notna() & vol.notna() & returns.notna()
    fwd = returns.apply(np.log1p).rolling(horizon, min_periods=horizon).sum().shift(-(horizon - 1)).apply(np.expm1)
    labels = pd.DataFrame(np.nan, index=returns.index, columns=returns.columns)
    for t in returns.index:
        row = ok.loc[t]
        if row.sum() < min_stocks:
            continue
        c = cheap.loc[t, row]
        sel = c[c.rank(pct=True) <= cheap_share].index
        v = vol.loc[t, sel]
        labels.loc[t, sel] = np.ceil(v.rank(pct=True) * groups).clip(1, groups)
    ranked = ok & (ok.sum(axis=1) >= min_stocks).to_numpy()[:, None]
    out = {f"V{g}": returns.where(labels == g).mean(axis=1) for g in range(1, groups + 1)}
    out["CHEAP"] = returns.where(labels.notna()).mean(axis=1)
    out["ALL"] = returns.where(ranked).mean(axis=1)
    buckets = pd.DataFrame(out).dropna()
    rows = {}
    for name, mask in [*((f"V{g}", labels == g) for g in range(1, groups + 1)), ("CHEAP", labels.notna()), ("ALL", ranked)]:
        f = fwd.where(mask).stack().dropna()
        v = vol.where(mask).stack().dropna()
        rows[name] = {
            "forward": float(f.mean()),
            "trap_rate": float((f <= trap).mean()),
            "volatility": float(v.mean()),
            "obs": int(f.size),
        }
    return buckets, pd.DataFrame(rows).T


def summary(series: pd.Series) -> dict[str, float]:
    v = series.dropna().to_numpy(dtype=np.float64)
    return {
        "mean": 12.0 * float(v.mean()),
        "vol": float(np.sqrt(12.0) * v.std(ddof=1)),
        "sharpe": stats.annual_sharpe(v),
        "t": stats.nw_tstat(v),
        "maxdd": stats.max_drawdown(v),
    }
