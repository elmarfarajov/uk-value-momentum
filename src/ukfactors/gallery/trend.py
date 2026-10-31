"""Day 4 charts: time-series momentum on UK assets, UK factors and UK stocks.

Assets: the UK equity market (AQR, in sterling), a constant-maturity ten-year gilt priced from the
OECD yield, and the pound against the dollar. Every number in a subtitle is computed from the data
the chart draws.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.figure import Figure

from .. import tsmom as T
from ..data import aqr, fred
from .anatomy import _returns
from .foundation import _panel, _shade
from .style import PALETTE, SERIES, caption, new_figure, tidy, title_block

DRAWS = 500  # placebo draws; the tests lower it
SRC = "UK equity (AQR, in sterling), 10-year gilt from the OECD yield (FRED), pound vs dollar; excess returns."
RULE = "12-month sign rule, 10% ex-ante volatility per asset, equal weights (ADR 0013)."
COL = {"EQUITY": PALETTE["blue"], "GILT": PALETTE["green"], "GBP": PALETTE["violet"], "TSMOM": PALETTE["ink"]}
EPISODES = {
    "1987 crash": ("1987-10", "1987-11"),
    "ERM exit 1992": ("1992-08", "1992-12"),
    "Dot-com bust": ("2000-09", "2003-03"),
    "Financial crisis": ("2007-11", "2009-02"),
    "Euro crisis 2011": ("2011-05", "2011-09"),
    "Covid 2020": ("2020-01", "2020-03"),
    "2022 gilt crisis": ("2022-01", "2022-10"),
}


@lru_cache(maxsize=1)
def _assets() -> pd.DataFrame:
    p = _panel()
    return T.assets(p, T.gilt_returns(fred.gilt_yield()), aqr.us_bill())


@lru_cache(maxsize=1)
def _factors() -> pd.DataFrame:
    return _panel()[list(T.FACTORS)].dropna(how="all")


@lru_cache(maxsize=1)
def _base() -> T.Result:
    return T.tsmom(_assets())


@lru_cache(maxsize=1)
def _fbase() -> T.Result:
    return T.tsmom(_factors())


@lru_cache(maxsize=1)
def _stocks() -> pd.DataFrame:
    return T.stock_strategies(_returns(), _panel()["RF_UK"].dropna())


@lru_cache(maxsize=1)
def _placebo() -> np.ndarray:
    return T.placebo(_assets(), DRAWS, seed=4)


def _sr(s: pd.Series) -> float:
    return T.summary(s)["sharpe"]


def _cum(ax, s: pd.Series, **kw) -> None:  # type: ignore[no-untyped-def]
    ax.plot((1 + s.dropna()).cumprod(), **kw)


# ------------------------------------------------------------------ 1. the assets


def assets() -> Figure:
    a = _assets()
    y = fred.gilt_yield().loc["1972":]
    fig = new_figure(14.5, 6.4)
    s = {c: T.summary(a[c]) for c in a}
    title_block(
        fig,
        "Three UK asset classes, three different paths",
        f"Growth of one pound of excess return. Equity earned {100 * s['EQUITY']['mean']:.1f}% a year over cash since 1986 (Sharpe {s['EQUITY']['sharpe']:.2f}); "
        f"the ten-year gilt {100 * s['GILT']['mean']:.1f}% since 1972 (Sharpe {s['GILT']['sharpe']:.2f}), most of it in the long fall of yields from "
        f"{100 * y.max():.1f}% in {y.idxmax():%Y} to {100 * y.min():.1f}% in {y.idxmin():%Y}; the pound {100 * s['GBP']['mean']:.1f}% (Sharpe {s['GBP']['sharpe']:.2f}).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.6))
    for c in a:
        _cum(ax, a[c], color=COL[c], lw=1.6, label=str(c).title() if c != "GBP" else "Pound vs dollar")
    ax.set_yscale("log")
    _shade(ax, labels=False)
    ax.set_xlim(pd.Timestamp("1972-01-01"), a.index[-1])
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, title="Cumulative excess return", ylabel="growth of £1 (log)")
    ax2 = fig.add_axes((0.68, 0.13, 0.3, 0.6))
    ax2.plot(100 * y, color=PALETTE["green"], lw=1.4)
    tidy(ax2, title="Ten-year gilt yield", ylabel="% a year")
    caption(fig, SRC)
    return fig


# ------------------------------------------------------------------ 2. predictability


def predictability() -> Figure:
    pa = T.predictability(_assets(), 24)
    pf = T.predictability(_factors(), 24)
    fig = new_figure(14.5, 6.0)
    sig_a = int((pa["t"].iloc[:12] > 1.96).sum())
    sig_f = int((pf["t"].iloc[:12] > 1.96).sum())
    title_block(
        fig,
        "Past returns predict future returns weakly for assets and clearly for factors",
        f"Pooled regression of each month's volatility-scaled excess return on the same asset's return h months earlier (Moskowitz, Ooi and Pedersen 2012). "
        f"Assets: {sig_a} of the first 12 lags have t above 1.96, lag 1 (t = {pa['t'].iloc[0]:.1f}), and it comes from gilts, whose yield is a monthly average "
        f"(ADR 0014); without gilts lag 1 has t = {T.predictability(_assets()[['EQUITY', 'GBP']], 1)['t'].iloc[0]:.1f}. Factors: {sig_f} of 12, lag-12 t = {pf['t'].iloc[11]:.1f}. Clustered by month.",
    )
    for k, (df, name) in enumerate(((pa, "Three asset classes"), (pf, "Six UK equity factors"))):
        ax = fig.add_axes((0.06 + 0.48 * k, 0.13, 0.42, 0.58))
        cols = [PALETTE["blue"] if t > 0 else PALETTE["red"] for t in df["t"]]
        ax.bar(df.index, df["t"], color=cols, width=0.7)
        for lvl in (1.96, -1.96):
            ax.axhline(lvl, color=PALETTE["muted"], ls="--", lw=0.8)
        ax.axhline(0, color=PALETTE["ink"], lw=0.6)
        tidy(ax, title=name, xlabel="lag h, months", ylabel="t-statistic" if k == 0 else None)
    caption(fig, SRC + " Factors: AQR UK value, momentum, SMB, HML, UMD, QMJ in sterling.")
    return fig


# ------------------------------------------------------------------ 3. the strategy


def cumulative() -> Figure:
    r = _base()
    port = r.portfolio
    fig = new_figure(14.5, 6.2)
    s = {c: _sr(r.by_asset[c]) for c in r.by_asset}
    ps = T.summary(port)
    title_block(
        fig,
        "Following the trend paid in every UK asset class, and best in gilts",
        f"Time-series momentum in each asset and the equal-weighted portfolio. Sharpe ratios: gilts {s['GILT']:.2f}, equity {s['EQUITY']:.2f}, the pound {s['GBP']:.2f}; "
        f"the portfolio {ps['sharpe']:.2f} with {100 * ps['vol']:.1f}% volatility, worst drawdown {100 * ps['maxdd']:.0f}%, {port.index[0]:%Y}-{port.index[-1]:%Y}. "
        "Three assets give little diversification; MOP's 58 futures gave a Sharpe above 1.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    for c in r.by_asset:
        _cum(
            ax, r.by_asset[c], color=COL[c], lw=1.2, alpha=0.85, label=f"{str(c).title() if c != 'GBP' else 'Pound'} ({s[c]:.2f})"
        )
    _cum(ax, port, color=COL["TSMOM"], lw=2.2, label=f"Portfolio ({ps['sharpe']:.2f})")
    ax.set_yscale("log")
    _shade(ax)
    ax.set_xlim(port.index[0], port.index[-1])
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="growth of £1 (log)")
    caption(fig, SRC + " " + RULE)
    return fig


def lookback_grid() -> Figure:
    g = T.grid(_assets(), (1, 3, 6, 9, 12, 18, 24), (1, 3, 6, 12), start="1975-01")
    fig = new_figure(12.0, 6.4)
    best = g.stack().idxmax()
    title_block(
        fig,
        "Most lookback and holding choices earn a positive Sharpe ratio",
        f"Sharpe ratio of the diversified strategy for each lookback (rows) and holding period (columns), common sample from 1975. All {g.size} cells are "
        f"positive; the best is a {best[0]}-month lookback held {best[1]} month(s) ({g.max().max():.2f}), the standard 12/1 gives {g.loc[12, 1]:.2f}. "
        "The one-month cell rests on the averaged gilt yield's autocorrelation (ADR 0014) and should be discounted.",
    )
    ax = fig.add_axes((0.12, 0.12, 0.8, 0.58))
    im = ax.imshow(g.to_numpy(float), cmap="RdBu", norm=TwoSlopeNorm(0.0, -0.8, 0.8), aspect="auto")
    for i in range(g.shape[0]):
        for j in range(g.shape[1]):
            ax.text(j, i, f"{g.iat[i, j]:.2f}", ha="center", va="center", fontsize=10)
    ax.set_xticks(range(g.shape[1]), [f"{k}" for k in g.columns])
    ax.set_yticks(range(g.shape[0]), [f"{k}" for k in g.index])
    fig.colorbar(im, ax=ax, fraction=0.03)
    tidy(ax, xlabel="holding period, months", ylabel="lookback, months")
    ax.grid(False)
    caption(fig, SRC + " Each cell: sign rule, 10% volatility target, overlapping portfolios.")
    return fig


# ------------------------------------------------------------------ 4. the smile and crises


def smile() -> Figure:
    port = _base().portfolio
    mkt = _assets()["EQUITY"]
    reg = T.smile(port, mkt)
    df = T.quarterly(port, mkt)
    fig = new_figure(12.5, 6.6)
    title_block(
        fig,
        "Trend following pays most when the stock market moves most, in either direction",
        f"Quarterly portfolio return against the UK market's quarterly excess return, {len(df)} quarters. The fitted curve has a slope of {reg.coef[1]:.2f} "
        f"(t = {reg.tstat[1]:.1f}) and a curvature of {reg.coef[2]:.2f} (t = {reg.tstat[2]:.1f}): the shape of a long straddle on the market (Fung and Hsieh 2001).",
    )
    ax = fig.add_axes((0.08, 0.13, 0.86, 0.58))
    ax.scatter(100 * df["m"], 100 * df["s"], s=14, color=PALETTE["blue"], alpha=0.6)
    xs = np.linspace(df["m"].min(), df["m"].max(), 200)
    ax.plot(100 * xs, 100 * (reg.coef[0] + reg.coef[1] * xs + reg.coef[2] * xs**2), color=PALETTE["ink"], lw=2)
    ax.axhline(0, color=PALETTE["muted"], lw=0.6)
    ax.axvline(0, color=PALETTE["muted"], lw=0.6)
    tidy(ax, xlabel="UK market excess return in the quarter, %", ylabel="TSMOM portfolio return, %")
    caption(fig, SRC + " " + RULE)
    return fig


def crises() -> Figure:
    port = _base().portfolio
    mkt = _assets()["EQUITY"]
    t = T.crisis_table(port, mkt, EPISODES)
    fig = new_figure(14.5, 6.0)
    wins = int((t["tsmom"] > 0).sum())
    title_block(
        fig,
        f"Trend following made money in {wins} of {len(t)} UK stress episodes",
        f"Cumulative return over seven episodes. In the financial crisis the portfolio gained {100 * t.loc['Financial crisis', 'tsmom']:.0f}% while the market fell "
        f"{100 * -t.loc['Financial crisis', 'market']:.0f}%; in the dot-com bust {100 * t.loc['Dot-com bust', 'tsmom']:+.0f}% against {100 * t.loc['Dot-com bust', 'market']:+.0f}%; "
        f"in 2022 {100 * t.loc['2022 gilt crisis', 'tsmom']:+.0f}%, mostly from being short gilts. The one loss: {100 * t['tsmom'].min():+.0f}% around the {t['tsmom'].idxmin()}. "
        "Episodes are few, and two (1987, Covid) last under four months.",
    )
    ax = fig.add_axes((0.06, 0.2, 0.9, 0.5))
    x = np.arange(len(t))
    ax.bar(x - 0.2, 100 * t["market"], 0.4, color=PALETTE["slate"], label="UK equity")
    ax.bar(x + 0.2, 100 * t["tsmom"], 0.4, color=PALETTE["blue"], label="TSMOM portfolio")
    ax.axhline(0, color=PALETTE["ink"], lw=0.6)
    ax.set_xticks(x, t.index, fontsize=9)
    ax.legend(frameon=False)
    tidy(ax, ylabel="cumulative return, %")
    caption(fig, SRC + " " + RULE)
    return fig


def positions() -> Figure:
    pos = _base().positions.apply(np.sign)
    fig = new_figure(14.5, 4.8)
    share = (pos > 0).mean()
    title_block(
        fig,
        "Long a little more often than short, and never for long",
        f"Direction of each position, month by month (blue long, red short). Long equity {100 * share['EQUITY']:.0f}% of months, long gilts {100 * share['GILT']:.0f}%, "
        f"long the pound {100 * share['GBP']:.0f}%. Gilts: long {100 * (pos['GILT'].loc['1972':'1981'] > 0).mean():.0f}% of months in 1972-1981, while yields rose, "
        f"and {100 * (pos['GILT'].loc['1982':'2020'] > 0).mean():.0f}% in 1982-2020, while they fell.",
    )
    ax = fig.add_axes((0.08, 0.15, 0.9, 0.5))
    for i, c in enumerate(pos.columns):
        s = pos[c].dropna()
        ax.scatter(s.index, np.full(s.size, i), c=[PALETTE["blue"] if v > 0 else PALETTE["red"] for v in s], marker="|", s=140)
    ax.set_yticks(range(pos.shape[1]), ["Equity", "Gilt", "Pound"])
    ax.set_ylim(-0.6, pos.shape[1] - 0.4)
    tidy(ax)
    caption(fig, RULE)
    return fig


# ------------------------------------------------------------------ 5. design choices


def design() -> Figure:
    a = _assets()
    variants = {
        "sign, scaled": T.tsmom(a).portfolio,
        "sign, unscaled": T.tsmom(a, target=None).portfolio,
        "linear, scaled": T.tsmom(a, kind="linear").portfolio,
        "moving average, scaled": T.tsmom(a, kind="ma").portfolio,
        "sign, 6-month lookback": T.tsmom(a, lookback=6).portfolio,
        "sign, skip latest month": T.tsmom(a, skip=1).portfolio,
    }
    start = max(v.index[0] for v in variants.values())
    rows = {k: T.summary(v.loc[start:]) for k, v in variants.items()}
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Volatility scaling and the exact rule matter less than the idea",
        f"Sharpe ratio and worst drawdown of {len(rows)} versions of the strategy over a common sample from {start:%Y}. Sharpe ratios range from "
        f"{min(r['sharpe'] for r in rows.values()):.2f} to {max(r['sharpe'] for r in rows.values()):.2f}. Without volatility scaling the portfolio is "
        f"dominated by the most volatile asset; Kim, Tse and Wald (2016) argue scaling explains much of TSMOM's record.",
    )
    names = list(rows)
    for k, (key, label) in enumerate((("sharpe", "Sharpe ratio"), ("maxdd", "worst drawdown, %"))):
        ax = fig.add_axes((0.18 + 0.43 * k, 0.13, 0.33, 0.58))
        vals = [rows[n][key] * (100 if key == "maxdd" else 1) for n in names]
        ax.barh(range(len(names)), vals, color=[*SERIES, "#8fb3e8"][: len(names)])
        ax.set_yticks(range(len(names)), names if k == 0 else [""] * len(names))
        ax.invert_yaxis()
        tidy(ax, title=label)
    caption(fig, SRC)
    return fig


def placebo() -> Figure:
    pl = _placebo()
    act = _sr(_base().portfolio)
    p = float((pl >= act).mean())
    fig = new_figure(12.5, 6.0)
    title_block(
        fig,
        "Random timing with the same persistence rarely does as well",
        f"Sharpe ratios of {pl.size} portfolios whose signals are each asset's own signal shifted by a random number of months: same share of time long, same "
        f"persistence, no link to what follows. The actual {act:.2f} beats {100 * (1 - p):.1f}% of them (one-sided p = {p:.3f}); the placebo median is {np.median(pl):.2f}.",
    )
    ax = fig.add_axes((0.08, 0.13, 0.86, 0.58))
    ax.hist(pl, bins=40, color=PALETTE["band"], edgecolor=PALETTE["slate"])
    ax.axvline(act, color=PALETTE["accent"], lw=2)
    tidy(ax, xlabel="annualised Sharpe ratio", ylabel="placebo portfolios")
    caption(fig, SRC + " " + RULE)
    return fig


def rolling() -> Figure:
    a, f = _base().portfolio, _fbase().portfolio
    w = 60
    ra = np.sqrt(12) * a.rolling(w).mean() / a.rolling(w).std()
    rf = np.sqrt(12) * f.rolling(w).mean() / f.rolling(w).std()
    fig = new_figure(14.5, 5.6)
    title_block(
        fig,
        "Trend following comes and goes",
        f"Rolling five-year Sharpe ratios. The asset portfolio's runs from {ra.min():.1f} to {ra.max():.1f} and has been below zero in {100 * (ra < 0).mean():.0f}% of "
        f"windows; factor momentum's from {rf.min():.1f} to {rf.max():.1f}. Their correlation is {a.corr(f):.2f}, so the two diversify each other.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(ra, color=PALETTE["blue"], lw=1.6, label="Asset TSMOM")
    ax.plot(rf, color=PALETTE["green"], lw=1.6, label="Factor TSMOM")
    ax.axhline(0, color=PALETTE["ink"], lw=0.6)
    _shade(ax, labels=False)
    ax.set_xlim(ra.dropna().index[0], ra.index[-1])
    ax.legend(frameon=False)
    tidy(ax, ylabel="Sharpe ratio, 60 months")
    caption(fig, RULE)
    return fig


# ------------------------------------------------------------------ 6. factor momentum


def factor_momentum() -> Figure:
    r = _fbase()
    f = _factors()
    fig = new_figure(14.5, 6.2)
    held = {c: _sr(f[c].loc[r.by_asset[c].dropna().index]) for c in f}
    timed = {c: _sr(r.by_asset[c]) for c in f}
    ps = T.summary(r.portfolio)
    better = sum(timed[c] > held[c] for c in f)
    title_block(
        fig,
        "Timing UK factors by their own past return beats holding them",
        f"Sharpe ratio of each UK factor held passively and timed by the 12-month sign rule, over the same months. Timing wins for {better} of 6; the "
        f"timed portfolio has a Sharpe of {ps['sharpe']:.2f} and {100 * ps['vol']:.0f}% volatility. Factor momentum (Ehsani and Linnainmaa 2022) "
        "is the time-series version of momentum applied to factors.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    x = np.arange(len(f.columns))
    ax.bar(x - 0.2, [held[c] for c in f], 0.4, color=PALETTE["slate"], label="held")
    ax.bar(x + 0.2, [timed[c] for c in f], 0.4, color=PALETTE["green"], label="timed")
    ax.set_xticks(x, f.columns)
    ax.axhline(0, color=PALETTE["ink"], lw=0.6)
    ax.legend(frameon=False)
    tidy(ax, title="Sharpe ratio")
    ax2 = fig.add_axes((0.56, 0.13, 0.4, 0.58))
    _cum(ax2, r.portfolio, color=PALETTE["green"], lw=2, label="Factor TSMOM")
    _cum(ax2, _base().portfolio, color=PALETTE["blue"], lw=1.4, label="Asset TSMOM")
    ax2.set_yscale("log")
    ax2.legend(frameon=False)
    tidy(ax2, title="Growth of £1 (log)")
    caption(fig, "AQR UK factors in sterling (ADR 0004). " + RULE)
    return fig


# ------------------------------------------------------------------ 7. stocks


def stocks() -> Figure:
    s = _stocks()
    fig = new_figure(14.5, 6.2)
    ss = {c: T.summary(s[c]) for c in ("TS", "XS", "NET")}
    corr = s["TS"].corr(s["XS"])
    title_block(
        fig,
        "Among stocks, time-series momentum is cross-sectional momentum plus a market bet",
        f"Survivor FTSE 350 stocks, equal weights, 12-1 formation. The time-series strategy earned {100 * ss['TS']['mean']:.1f}% a year (Sharpe {ss['TS']['sharpe']:.2f}), "
        f"the cross-sectional {100 * ss['XS']['mean']:.1f}% ({ss['XS']['sharpe']:.2f}); they correlate {corr:.2f}. The time-series version's net market position "
        f"earned {100 * ss['NET']['mean']:.1f}% a year (Goyal and Jegadeesh 2018).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    for c, col, lab in (
        ("TS", PALETTE["blue"], "time series"),
        ("XS", PALETTE["green"], "cross section"),
        ("NET", PALETTE["slate"], "net market part"),
    ):
        _cum(ax, s[c], color=col, lw=1.6, label=lab)
    ax.set_yscale("log")
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, title="Growth of £1 (log)")
    ax2 = fig.add_axes((0.68, 0.13, 0.29, 0.58))
    ax2.plot(100 * s["LONG_SHARE"], color=PALETTE["violet"], lw=1.2)
    ax2.axhline(50, color=PALETTE["muted"], ls="--", lw=0.8)
    tidy(ax2, title="Stocks with a positive formation return, %")
    caption(fig, "Survivor sample: today's FTSE 350 (ADR 0009, 0011); excess returns over the UK rate.")
    return fig
