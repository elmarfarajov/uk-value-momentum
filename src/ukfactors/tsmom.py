"""Time-series momentum on UK assets: each asset is held long or short on the sign of its own past return.

Cross-sectional momentum (Days 2 and 3) ranks assets against each other. Time-series momentum
(Moskowitz, Ooi and Pedersen 2012, "MOP") asks only whether an asset's own excess return over
the past year was positive. Positions are scaled by ex-ante volatility, so each asset contributes
similar risk.

The UK assets are:

* ``EQUITY``: the UK stock market's sterling excess return (AQR, converted; ADR 0004);
* ``GILT``: a constant-maturity ten-year gilt, priced from the OECD long-term yield (FRED), less
  the UK short rate;
* ``GBP``: the pound against the dollar, funded in dollars and earning the UK rate;
* the UK long/short equity factors (value, momentum, size, quality) for factor momentum.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import analysis

FACTORS = ("VAL", "MOM", "SMB", "HML", "UMD", "QMJ")


# ------------------------------------------------------------------ assets


def gilt_returns(yields: pd.Series, maturity: float = 10.0) -> pd.Series:
    """Monthly total return of a constant-maturity par gilt priced from a yield series (decimals, a year).

    Each month a par bond paying a semi-annual coupon ``y_{t-1}`` is bought, and sold a month later
    with ``maturity - 1/12`` years left at the yield ``y_t``. The return is the price change plus a
    month of coupon, ``P(y_t) - 1 + y_{t-1}/12``. An unchanged yield returns exactly ``y/12``.
    """
    y0 = yields.shift(1)
    h = (yields / 2.0).where(yields.abs() > 1e-12, 1e-12)
    disc = (1.0 + h) ** (-2.0 * (maturity - 1.0 / 12.0))
    price = (y0 / 2.0) / h * (1.0 - disc) + disc
    return (price - 1.0 + y0 / 12.0).dropna().rename("GILT_TR")


def gbp_excess(fx: pd.Series, rf_uk: pd.Series, rf_us: pd.Series) -> pd.Series:
    """Long pounds funded in dollars, in dollars: ``(1 + x)(1 + rf_UK) - (1 + rf_US)``."""
    df = pd.concat([fx, rf_uk, rf_us], axis=1).dropna()
    return ((1.0 + df.iloc[:, 0]) * (1.0 + df.iloc[:, 1]) - (1.0 + df.iloc[:, 2])).rename("GBP")


def assets(panel: pd.DataFrame, gilt: pd.Series, rf_us: pd.Series) -> pd.DataFrame:
    """The three UK asset classes as monthly excess returns."""
    eq = panel["MKT"].rename("EQUITY")
    gl = (gilt - panel["RF_UK"]).rename("GILT")
    fx = gbp_excess(panel["FX"], panel["RF_UK"], rf_us)
    return pd.concat([eq, gl, fx], axis=1).dropna(how="all")


# ------------------------------------------------------------------ the strategy


def ex_ante_vol(returns: pd.DataFrame, com: float = 6.0) -> pd.DataFrame:
    """Annualised exponentially weighted volatility known at the end of each month (centre of mass in months)."""
    mean = returns.ewm(com=com, min_periods=12).mean()
    var = ((returns - mean) ** 2).ewm(com=com, min_periods=12).mean()
    return np.sqrt(12.0 * var)


def signal(returns: pd.DataFrame, lookback: int = 12, kind: str = "sign", vol: pd.DataFrame | None = None) -> pd.DataFrame:
    """The trading signal at each month end, from the past ``lookback`` months of excess returns.

    ``sign``: +1 or -1 on the sign of the cumulative excess return (MOP). ``linear``: the return
    divided by its volatility over the window, clipped at +/-1 (a smoother rule). ``ma``: +1 or -1
    on whether the excess-return index is above its ``lookback``-month moving average.
    """
    logs = returns.apply(np.log1p)
    cum = logs.rolling(lookback, min_periods=lookback).sum()
    if kind == "sign":
        return np.sign(cum)
    if kind == "linear":
        v = (vol if vol is not None else ex_ante_vol(returns)) * np.sqrt(lookback / 12.0)
        return (cum / v).clip(-1.0, 1.0)
    if kind == "ma":
        level = logs.cumsum()
        return np.sign(level - level.rolling(lookback, min_periods=lookback).mean())
    raise ValueError(f"unknown signal {kind!r}")


@dataclass(frozen=True)
class Result:
    by_asset: pd.DataFrame  # monthly return of each asset's position
    positions: pd.DataFrame  # position held over each month (weight on the asset's excess return)

    @property
    def portfolio(self) -> pd.Series:
        """Equal weight across the assets available that month (MOP's diversified TSMOM)."""
        return self.by_asset.mean(axis=1, skipna=True).dropna().rename("TSMOM")


def tsmom(
    returns: pd.DataFrame,
    lookback: int = 12,
    hold: int = 1,
    target: float | None = 0.10,
    kind: str = "sign",
    com: float = 6.0,
    skip: int = 0,
) -> Result:
    """Time-series momentum: signal at month end ``t`` scaled by ``target / sigma_t``, held over ``t+1 .. t+hold``.

    With ``hold > 1`` each month holds the average of the last ``hold`` positions (overlapping
    portfolios, as in Jegadeesh-Titman and MOP). ``target=None`` holds one unit, unscaled.
    ``skip=1`` forms the signal from months t-12 .. t-1, leaving out the latest month.
    """
    vol = ex_ante_vol(returns, com)
    sig = signal(returns, lookback, kind, vol).shift(skip)
    weight = sig * (target / vol) if target is not None else sig
    weight = weight.where(vol.notna()) if target is not None else weight
    held = sum(weight.shift(k) for k in range(1, hold + 1)) / hold
    out = held * returns
    out = out.where(held.notna())
    return Result(out.dropna(how="all"), held.dropna(how="all"))


def grid(returns: pd.DataFrame, lookbacks: tuple[int, ...], holds: tuple[int, ...], start: str | None = None) -> pd.DataFrame:
    """Annualised Sharpe ratio of the diversified strategy for each lookback (rows) and holding period (columns)."""
    out = pd.DataFrame(index=list(lookbacks), columns=list(holds), dtype=float)
    for j in lookbacks:
        for k in holds:
            p = tsmom(returns, j, k).portfolio
            p = p.loc[start:] if start else p
            out.loc[j, k] = float(np.sqrt(12) * p.mean() / p.std())
    return out


# ------------------------------------------------------------------ evidence


def predictability(returns: pd.DataFrame, max_lag: int = 24, sign: bool = False, com: float = 6.0) -> pd.DataFrame:
    """MOP's pooled regression of ``r_t / sigma_{t-1}`` on ``r_{t-h} / sigma_{t-h-1}`` (or its sign), h = 1..max_lag.

    t-statistics cluster by month, since the assets' returns in one month are correlated.
    """
    vol = ex_ante_vol(returns, com)
    z = returns / vol.shift(1)
    rows = []
    for h in range(1, max_lag + 1):
        x = np.sign(z.shift(h)) if sign else z.shift(h)
        stack = pd.concat([z.stack().rename("y"), x.stack().rename("x")], axis=1, sort=True).dropna()
        yv, xv = stack["y"].to_numpy(), stack["x"].to_numpy()
        months = stack.index.get_level_values(0)
        xm = np.column_stack([np.ones_like(xv), xv])
        inv = np.linalg.inv(xm.T @ xm)
        b = inv @ xm.T @ yv
        u = yv - xm @ b
        score = pd.DataFrame(xm * u[:, None]).groupby(np.asarray(months)).sum().to_numpy()
        cov = inv @ (score.T @ score) @ inv
        rows.append({"lag": h, "beta": b[1], "t": b[1] / np.sqrt(cov[1, 1]), "n": yv.size})
    return pd.DataFrame(rows).set_index("lag")


def quarterly(strategy: pd.Series, market: pd.Series) -> pd.DataFrame:
    """Compounded quarterly returns of both series, keeping only quarters in which both have all three months."""
    both = pd.concat([strategy.rename("s"), market.rename("m")], axis=1).dropna()
    full = both["s"].resample("QE").count() == 3
    q = (1.0 + both).resample("QE").prod() - 1.0
    return q[full]


def smile(strategy: pd.Series, market: pd.Series) -> analysis.Regression:
    """Regress the strategy's quarterly return on the market's and its square (Fung and Hsieh's straddle shape)."""
    q = quarterly(strategy, market)
    return analysis.regress(q["s"], pd.DataFrame({"market": q["m"], "market_sq": q["m"] ** 2}), lags=0)


def placebo(returns: pd.DataFrame, draws: int = 500, seed: int = 0, lookback: int = 12) -> np.ndarray:
    """Sharpe ratios of the diversified strategy with each asset's signal shifted in time by a random offset.

    The shift keeps each signal's persistence and the share of time long, but breaks its link to the
    returns that follow, so the distribution is what a signal of the same shape earns by chance.
    """
    rng = np.random.default_rng(seed)
    vol = ex_ante_vol(returns)
    sig = signal(returns, lookback, "sign")
    out = np.empty(draws)
    for d in range(draws):
        shifted = pd.DataFrame(index=sig.index, columns=sig.columns, dtype=float)
        for c in sig.columns:
            s = sig[c].dropna()
            k = int(rng.integers(24, max(25, s.size - 24)))
            shifted.loc[s.index, c] = np.roll(s.to_numpy(), k)
        w = (shifted * 0.10 / vol).shift(1)
        p = (w * returns).mean(axis=1).dropna()
        out[d] = np.sqrt(12) * p.mean() / p.std()
    return out


def crisis_table(strategy: pd.Series, market: pd.Series, episodes: dict[str, tuple[str, str]]) -> pd.DataFrame:
    """Cumulative return of the strategy and the market over each named episode."""
    rows = []
    for name, (a, b) in episodes.items():
        s, m = strategy.loc[a:b], market.loc[a:b]
        rows.append(
            {
                "episode": name,
                "months": len(m),
                "market": float(np.prod(1.0 + m.to_numpy()) - 1.0),
                "tsmom": float(np.prod(1.0 + s.to_numpy()) - 1.0),
            }
        )
    return pd.DataFrame(rows).set_index("episode")


# ------------------------------------------------------------------ stocks: time series against cross section


def stock_strategies(returns: pd.DataFrame, rf: pd.Series, j: int = 11, skip: int = 1, min_stocks: int = 30) -> pd.DataFrame:
    """Equal-weighted stock-level strategies from the same 12-1 formation return.

    ``TS``: long each stock whose formation excess return is positive, short each negative one,
    each with weight 1/N (a net position that can be long or short the market). ``XS``: long the
    stocks above the month's mean formation return and short those below, each side summing to
    one half (no net market position). ``NET``: the TS strategy's net weight times the
    equal-weighted market's excess return; TS = XS-like part + NET.
    """
    excess = returns.sub(rf.reindex(returns.index), axis=0)
    form = excess.apply(np.log1p).rolling(j, min_periods=j).sum().shift(skip)
    n = form.notna().sum(axis=1)
    ok = n >= min_stocks
    ts_w = np.sign(form).div(n, axis=0)
    dev = form.sub(form.mean(axis=1), axis=0)
    xs_w = np.sign(dev)
    xs_w = (
        xs_w.where(xs_w > 0).div(xs_w.where(xs_w > 0).sum(axis=1), axis=0).fillna(0) * 0.5
        - xs_w.where(xs_w < 0).abs().div(xs_w.where(xs_w < 0).abs().sum(axis=1), axis=0).fillna(0) * 0.5
    )
    xs_w = xs_w.where(form.notna())
    mkt = excess.where(form.notna()).mean(axis=1)
    ts = (ts_w.shift(1) * excess).sum(axis=1, min_count=1)
    xs = (xs_w.shift(1) * excess).sum(axis=1, min_count=1)
    net = ts_w.shift(1).sum(axis=1) * mkt
    long_share = (form > 0).sum(axis=1) / n
    out = pd.DataFrame({"TS": ts, "XS": xs, "NET": net, "MKT": mkt, "LONG_SHARE": long_share.shift(1)})
    return out[ok.shift(1, fill_value=False)].dropna(subset=["TS", "XS"])


def summary(series: pd.Series) -> dict[str, float]:
    s = series.dropna()
    nav = (1 + s).cumprod()
    return {
        "mean": 12 * float(s.mean()),
        "vol": float(np.sqrt(12) * s.std()),
        "sharpe": float(np.sqrt(12) * s.mean() / s.std()),
        "skew": float(s.skew()),  # type: ignore[arg-type]
        "maxdd": float((nav / nav.cummax() - 1).min()),
        "months": float(s.size),
    }
