"""The anatomy of UK momentum: formation and holding periods, what the signal is made of, when it pays.

Stock-level strategies are built on the survivor sample of today's FTSE 350 (ADR 0003): its
level is biased, so it is used for *comparisons* - one formation window against another, raw
against residual momentum - and each headline is checked against AQR's and Exeter's
survivorship-free factors (ADR 0009).

Conventions (ADR 0010). A strategy is held from the start of month ``h``. Its signal uses only
returns up to the end of month ``h - 1 - skip``:

* the **formation return** over ``j`` months is the compounded return from month ``h - j - skip``
  to ``h - 1 - skip``; the classic "12-1" signal is ``j = 11, skip = 1`` (months ``h - 12`` to
  ``h - 2``);
* stocks are ranked each month; the top and bottom ``share`` (a decile by default) are the
  winners and losers, equally weighted;
* a **Jegadeesh-Titman** strategy holding for ``k`` months owns ``k`` overlapping cohorts, those
  formed in the last ``k`` months, each with weight ``1 / k``; its return in month ``m`` is the
  average of the cohorts' winner-minus-loser returns that month.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from . import analysis, stats
from .data import aqr, exeter, fred

Array = NDArray[np.float64]


# ------------------------------------------------------------------ signals


def formation_return(returns: pd.DataFrame, j: int, skip: int = 1) -> pd.DataFrame:
    """Compounded return over months ``h - j - skip`` to ``h - 1 - skip``, in row ``h`` (NaN unless all ``j`` months exist)."""
    log = pd.DataFrame(np.log1p(returns), index=returns.index, columns=returns.columns)
    window = log.rolling(j, min_periods=j).sum().shift(skip + 1)
    return pd.DataFrame(np.expm1(window), index=returns.index, columns=returns.columns)


def high_ratio(returns: pd.DataFrame, months: int = 12) -> pd.DataFrame:
    """George and Hwang's (2004) nearness to the high: price at the end of ``h - 1`` over its highest recent month-end.

    Prices are rebuilt from returns (any scale works: the ratio is scale-free) and only month-end
    closes are seen, so this is the 12-month high of month-end prices, not of daily prices.
    """
    level = (1.0 + returns.fillna(0.0)).cumprod().where(returns.notna())
    ratio = level / level.rolling(months, min_periods=months).max()
    return ratio.shift(1)


def residual_signal(returns: pd.DataFrame, factors: pd.DataFrame, window: int = 36, j: int = 11, skip: int = 1) -> pd.DataFrame:
    """Blitz, Huij and Martens's (2011) residual momentum.

    For each formation month ``h``, every stock with a complete ``window`` of returns to the end of
    ``h - 1`` is regressed on the factors over that window. The signal is the sum of its residuals
    over the formation months ``h - j - skip`` to ``h - 1 - skip``, divided by their standard
    deviation. One least-squares solve per month covers every stock, since all share the factors.
    """
    data = returns.join(factors, how="inner")
    r = data[returns.columns].to_numpy(dtype=np.float64)
    f = data[factors.columns].to_numpy(dtype=np.float64)
    out = np.full_like(r, np.nan)
    for h in range(window, r.shape[0]):
        rows = slice(h - window, h)  # months h - window .. h - 1
        y = r[rows]
        x = np.column_stack([np.ones(window), f[rows]])
        if not np.isfinite(x).all():
            continue
        ok = np.isfinite(y).all(axis=0)
        if ok.sum() < 2:
            continue
        beta, *_ = np.linalg.lstsq(x, y[:, ok], rcond=None)
        resid = y[:, ok] - x @ beta
        form = resid[window - j - skip : window - skip]  # the formation months inside the window
        sd = form.std(axis=0, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[h, ok] = form.sum(axis=0) / sd
    return pd.DataFrame(out, index=data.index, columns=returns.columns).reindex(returns.index)


# ------------------------------------------------------------------ portfolios


@dataclass(frozen=True)
class Strategy:
    wml: pd.Series  # winners minus losers, monthly
    winners: pd.Series
    losers: pd.Series
    universe: pd.Series  # equal-weighted average of the stocks with a signal
    turnover: pd.Series  # one-sided turnover of the long side, monthly
    long: pd.DataFrame  # winners at each formation month (bool)
    short: pd.DataFrame  # losers at each formation month (bool)
    spread: pd.Series  # mean signal of winners minus losers at formation


def ranks(
    signal: pd.DataFrame, share: float = 0.1, min_stocks: int = 30, count: int | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Winners (top ``share``) and losers (bottom ``share``) at each formation month; rows with too few stocks are empty.

    ``count``, if given, takes exactly that many names in each leg (ties broken by column order), which
    small cross-sections such as twelve industries need: a share like 3/12 sits on a floating-point
    boundary of the percentile ranks.
    """
    n = signal.notna().sum(axis=1)
    enough = (n >= min_stocks).to_numpy()[:, None]
    if count is not None:
        top = signal.rank(axis=1, ascending=False, method="first") <= count
        bottom = signal.rank(axis=1, ascending=True, method="first") <= count
        return top & enough, bottom & enough
    pct = signal.rank(axis=1, pct=True)
    return (pct > 1.0 - share) & enough, (pct <= share) & enough


def overlapping(
    returns: pd.DataFrame, signal: pd.DataFrame, k: int = 1, share: float = 0.1, min_stocks: int = 30, count: int | None = None
) -> Strategy:
    """A Jegadeesh-Titman strategy: ``k`` overlapping cohorts formed on ``signal``, each held ``k`` months."""
    signal = signal.reindex(index=returns.index, columns=returns.columns)
    win, lose = ranks(signal, share, min_stocks, count)
    r = returns.to_numpy(dtype=np.float64)
    w = win.to_numpy()
    lo = lose.to_numpy()
    valid = w.any(axis=1) & lo.any(axis=1)
    n = r.shape[0]
    wml = np.full(n, np.nan)
    wr = np.full(n, np.nan)
    lr = np.full(n, np.nan)
    uni = np.full(n, np.nan)
    turnover = np.full(n, np.nan)
    has_signal = signal.notna().to_numpy()
    prev_weights: Array | None = None
    for m in range(n):
        cohorts = [c for c in range(m - k + 1, m + 1) if c >= 0 and valid[c]]
        if len(cohorts) < k:
            prev_weights = None
            continue
        rm = r[m]
        win_c = [_mean(rm, w[c]) for c in cohorts]
        lose_c = [_mean(rm, lo[c]) for c in cohorts]
        wr[m] = float(np.nanmean(win_c))
        lr[m] = float(np.nanmean(lose_c))
        wml[m] = wr[m] - lr[m]
        uni[m] = _mean(rm, has_signal[m])
        weights = sum(w[c] / w[c].sum() for c in cohorts) / k
        if prev_weights is not None:
            turnover[m] = 0.5 * float(np.abs(weights - prev_weights).sum())
        prev_weights = weights
    idx = returns.index
    sig = signal.to_numpy(dtype=np.float64)
    spread = np.array([_mean(sig[h], w[h]) - _mean(sig[h], lo[h]) if valid[h] else np.nan for h in range(n)])
    return Strategy(
        pd.Series(wml, idx, name="WML"),
        pd.Series(wr, idx, name="winners"),
        pd.Series(lr, idx, name="losers"),
        pd.Series(uni, idx, name="universe"),
        pd.Series(turnover, idx, name="turnover"),
        win,
        lose,
        pd.Series(spread, idx, name="spread"),
    )


def _mean(values: Array, mask: Array) -> float:
    v = values[mask]
    v = v[np.isfinite(v)]
    return float(v.mean()) if v.size else float("nan")


def jt(returns: pd.DataFrame, j: int, k: int, skip: int = 1, share: float = 0.1) -> Strategy:
    return overlapping(returns, formation_return(returns, j, skip), k, share)


def grid(
    returns: pd.DataFrame, js: list[int], ks: list[int], skip: int = 1, share: float = 0.1, start: str | None = None
) -> pd.DataFrame:
    """Annualised mean, Newey-West t and Sharpe ratio of every J x K strategy, over common months from ``start``."""
    rows = []
    for j in js:
        for k in ks:
            s = jt(returns, j, k, skip, share).wml.dropna()
            if start is not None:
                s = s.loc[start:]
            v = s.to_numpy(dtype=np.float64)
            rows.append(
                {
                    "J": j,
                    "K": k,
                    "months": v.size,
                    "mean": 12 * v.mean(),
                    "t_nw": stats.nw_tstat(v),
                    "sharpe": stats.annual_sharpe(v),
                }
            )
    return pd.DataFrame(rows)


def event_time(
    returns: pd.DataFrame,
    signal: pd.DataFrame,
    horizon: int = 60,
    share: float = 0.1,
    min_stocks: int = 30,
    count: int | None = None,
) -> pd.DataFrame:
    """Winner-minus-loser return in each month ``tau = 1..horizon`` after formation, averaged over formation months.

    Cohorts are formed on ``signal`` and never rebalanced; a stock that stops trading drops out.
    The standard error at each ``tau`` is Newey-West over formation months.
    """
    win, lose = ranks(signal.reindex(index=returns.index, columns=returns.columns), share, min_stocks, count)
    r = returns.to_numpy(dtype=np.float64)
    w, lo = win.to_numpy(), lose.to_numpy()
    forms = np.flatnonzero(w.any(axis=1) & lo.any(axis=1))
    rows = []
    for tau in range(horizon):
        vals = np.array([_mean(r[h + tau], w[h]) - _mean(r[h + tau], lo[h]) for h in forms if h + tau < r.shape[0]])
        vals = vals[np.isfinite(vals)]
        if vals.size < 24:
            break
        se = np.sqrt(stats.long_run_variance(vals) / vals.size)
        rows.append({"tau": tau + 1, "mean": float(vals.mean()), "se": float(se), "cohorts": int(vals.size)})
    out = pd.DataFrame(rows).set_index("tau")
    out["cumulative"] = out["mean"].cumsum()
    return out


def deciles(returns: pd.DataFrame, signal: pd.DataFrame, groups: int = 10, min_stocks: int = 30) -> pd.DataFrame:
    """Next-month equal-weighted return of each signal group (1 = lowest), monthly."""
    sig = signal.reindex(index=returns.index, columns=returns.columns)
    pct = sig.rank(axis=1, pct=True)
    count = sig.notna().sum(axis=1)
    group = np.ceil(pct * groups).clip(1, groups)
    out = {}
    for g in range(1, groups + 1):
        out[g] = returns.where(group == g).mean(axis=1).where(count >= min_stocks)
    return pd.DataFrame(out)


def transitions(signal: pd.DataFrame, lag: int = 1, groups: int = 5) -> pd.DataFrame:
    """Probability of moving from each signal group to each other ``lag`` months later (rows sum to one)."""
    group = np.ceil(signal.rank(axis=1, pct=True) * groups).clip(1, groups)
    later = group.shift(-lag)
    a = group.to_numpy().ravel()
    b = later.to_numpy().ravel()
    ok = np.isfinite(a) & np.isfinite(b)
    m = pd.crosstab(a[ok].astype(int), b[ok].astype(int), normalize="index")
    m.index.name, m.columns.name = "from", "to"
    return m


def spells(long: pd.DataFrame) -> pd.Series:
    """Lengths, in months, of every unbroken spell a stock spends in a portfolio (bool frame of memberships)."""
    lengths: list[int] = []
    for col in long.columns:
        x = long[col].to_numpy().astype(int)
        run = 0
        for v in x:
            if v:
                run += 1
            elif run:
                lengths.append(run)
                run = 0
        if run:
            lengths.append(run)
    return pd.Series(lengths, name="months")


def composition(members: pd.DataFrame, industry: pd.Series) -> pd.DataFrame:
    """Share of each industry in a portfolio at each formation month."""
    ind = industry.reindex(members.columns).fillna("Other")
    counts = members.T.groupby(ind.to_numpy()).sum().T
    total = counts.sum(axis=1)
    return counts.div(total.where(total > 0), axis=0)


# ------------------------------------------------------------------ the market, states and seasons


def market_total() -> pd.Series:
    """The UK stock market's total return in sterling: AQR's (from 1986, converted from dollars), Exeter's before."""
    fx = fred.gbpusd().pct_change()
    usd = aqr.uk()["MKT"] + aqr.us_bill().reindex(aqr.uk().index)
    gbp = ((1.0 + usd) / (1.0 + fx.reindex(usd.index)) - 1.0).dropna()
    ex = exeter.factors()["RM"]
    return gbp.combine_first(ex.loc[: gbp.index[0] - pd.offsets.MonthEnd(1)]).rename("MARKET")


def market_states(strategy: pd.Series, market: pd.Series, lookback: int = 24) -> pd.DataFrame:
    """Cooper, Gutierrez and Hameed (2004): the strategy's return after markets that rose or fell over ``lookback`` months.

    The state for month ``h`` uses market returns up to the end of ``h - 1`` only. The difference
    is the coefficient on a DOWN dummy, with a Newey-West t-statistic.
    """
    past = np.log1p(market).rolling(lookback, min_periods=lookback).sum().shift(1)
    j = pd.concat([strategy.rename("s"), past.rename("past")], axis=1).dropna()
    down = (j["past"] < 0).astype(float)
    rows = []
    for name, part in (("UP", j[down == 0]), ("DOWN", j[down == 1])):
        v = part["s"].to_numpy(dtype=np.float64)
        rows.append(
            {"state": name, "months": v.size, "mean": 12 * v.mean(), "t_nw": stats.nw_tstat(v) if v.size > 12 else np.nan}
        )
    reg = analysis.regress(j["s"], pd.DataFrame({"DOWN": down}, index=j.index))
    rows.append({"state": "DOWN - UP", "months": len(j), "mean": 12 * float(reg.coef[1]), "t_nw": float(reg.tstat[1])})
    return pd.DataFrame(rows).set_index("state")


def conditional_beta(strategy: pd.Series, market: pd.Series, window: int = 24) -> pd.DataFrame:
    """Rolling beta of the strategy on the market, against the market's return over the same window (Grundy and Martin, 2001)."""
    j = pd.concat([strategy.rename("s"), market.rename("m")], axis=1).dropna()
    cov = j["s"].rolling(window).cov(j["m"])
    var = j["m"].rolling(window).var()
    past = np.log1p(j["m"]).rolling(window).sum()
    return pd.DataFrame({"beta": cov / var, "market_past": np.expm1(past)}).dropna()


def calendar(series: pd.Series) -> pd.DataFrame:
    """Mean return in each calendar month (annualised x 12 is not applied: monthly means), with Newey-West t."""
    s = series.dropna()
    months = pd.DatetimeIndex(s.index).month
    rows = []
    for m in range(1, 13):
        v = s[months == m].to_numpy(dtype=np.float64)
        se = v.std(ddof=1) / np.sqrt(v.size)
        rows.append(
            {
                "month": m,
                "years": v.size,
                "mean": float(v.mean()),
                "t": float(v.mean() / se),
                "share_positive": float((v > 0).mean()),
            }
        )
    return pd.DataFrame(rows).set_index("month")


def seasonal_regression(series: pd.Series, months: tuple[int, ...] = (1, 4)) -> analysis.Regression:
    """The strategy's monthly return on dummies for the given calendar months, with Newey-West errors."""
    s = series.dropna()
    m = pd.DatetimeIndex(s.index).month
    x = pd.DataFrame({f"m{k}": (m == k).astype(float) for k in months}, index=s.index)
    return analysis.regress(s, x)


def predictive(strategy: pd.Series, predictor: pd.Series) -> analysis.Regression:
    """Next month's strategy return on this month's (standardised) predictor, both known at formation."""
    z = (predictor - predictor.mean()) / predictor.std()
    return analysis.regress(strategy, pd.DataFrame({"z": z}))


def summary(series: pd.Series, market: pd.Series | None = None) -> dict[str, float]:
    """Annualised mean, volatility, Sharpe, NW t, maximum drawdown, skew and (optionally) market beta of a monthly series."""
    s = series.dropna()
    v = s.to_numpy(dtype=np.float64)
    out = {
        "months": float(v.size),
        "mean": 12 * float(v.mean()),
        "vol": float(np.sqrt(12) * v.std(ddof=1)),
        "sharpe": stats.annual_sharpe(v),
        "t_nw": stats.nw_tstat(v),
        "max_drawdown": stats.max_drawdown(v),
        "skew": float(pd.Series(v).skew()),
    }
    if market is not None:
        reg = analysis.regress(s, pd.DataFrame({"m": market}))
        out["beta"] = float(reg.coef[1])
        out["alpha"] = reg.alpha
    return out
