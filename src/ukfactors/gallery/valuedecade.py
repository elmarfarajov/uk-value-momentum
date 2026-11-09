"""Day 5 charts: value's lost decade in the UK, 2007-2020.

AQR's UK HML, HML Devil and multi-measure value (VAL), in sterling; AQR's value in the US, Europe
and Japan (dollars, long/short); Exeter's book-to-market deciles and size-value portfolios (to
2016); the OECD ten-year gilt yield (FRED). Every number in a subtitle is computed.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from .. import lostdecade as L
from .. import panel, stats
from ..data import exeter, fred
from .foundation import _panel, _shade
from .style import PALETTE, caption, new_figure, tidy, title_block

DRAWS = 200  # bootstrap draws for the break test and the loss probability; the tests lower it
A, B = L.LOST
SRC = "AQR UK factors in sterling (ADR 0004); value = long/short. Lost decade: January 2007 to September 2020."
COL = {"HML": PALETTE["blue"], "HML_DEVIL": PALETTE["violet"], "VAL": PALETTE["green"], "EX_HML": PALETTE["slate"]}
NAMES = {
    "HML": "HML (book-to-market)",
    "HML_DEVIL": "HML Devil (timely prices)",
    "VAL": "AQR VAL (several measures)",
    "EX_HML": "Exeter HML",
}


def _shade_lost(ax) -> None:  # type: ignore[no-untyped-def]
    ax.axvspan(pd.Timestamp(A), pd.Timestamp(B), color=PALETTE["band"], zorder=0)


def _index(s: pd.Series) -> pd.Series:
    return (1 + s.dropna()).cumprod()


@lru_cache(maxsize=1)
def _intl() -> pd.DataFrame:
    return panel.international()


@lru_cache(maxsize=1)
def _deciles() -> pd.DataFrame:
    return exeter.portfolios("10ports_bm")


@lru_cache(maxsize=1)
def _break() -> tuple[pd.Series, pd.Timestamp, float, float]:
    h = _panel()["HML"]
    path, date, stat = L.sup_wald(h)
    _, p = L.sup_wald_pvalue(h, reps=max(19, DRAWS // 2), seed=3)
    return path, date, stat, p


# ------------------------------------------------------------------ 1-4. the episode


def cumulative() -> Figure:
    p = _panel()
    eps = {c: L.episode(p[c].rename(c)) for c in ("HML", "HML_DEVIL", "VAL")}
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "UK value lost money for fourteen years; how much depends on how value is measured",
        f"Growth of £1 in each value factor. From January 2007 to September 2020: HML {100 * eps['HML'].cumulative:+.0f}%, HML Devil "
        f"{100 * eps['HML_DEVIL'].cumulative:+.0f}%, AQR's multi-measure VAL {100 * eps['VAL'].cumulative:+.0f}%. Sharpe ratios before, during and after: HML "
        f"{eps['HML'].sharpe_before:.2f}, {eps['HML'].sharpe_during:.2f}, {eps['HML'].sharpe_after:.2f}.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    for c in ("HML", "HML_DEVIL", "VAL"):
        ax.plot(_index(p[c].loc["1988-07":]), color=COL[c], lw=1.8, label=NAMES[c])
    ax.set_yscale("log")
    _shade_lost(ax)
    ax.legend(frameon=False, loc="upper left")
    ax.set_xlim(pd.Timestamp("1988-07-01"), p["HML"].dropna().index[-1])
    tidy(ax, ylabel="growth of £1 (log)")
    caption(fig, SRC)
    return fig


def international() -> Figure:
    i = _intl()
    cols = {
        "VAL_UK": ("UK", PALETTE["blue"]),
        "VAL_US": ("US", PALETTE["slate"]),
        "VAL_EU": ("Europe", PALETTE["green"]),
        "VAL_JP": ("Japan", PALETTE["violet"]),
    }
    eps = {c: L.episode(i[c].rename(c)) for c in cols}
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "The lost decade was shared by the UK, the US and Europe, but not Japan",
        "AQR's value factor in four markets, growth of $1 from January 2007. Cumulative to September 2020: "
        + ", ".join(f"{cols[c][0]} {100 * eps[c].cumulative:+.0f}%" for c in cols)
        + ". Since then: "
        + ", ".join(
            f"{cols[c][0]} {100 * L.cumulative(i[c].loc[pd.Timestamp(B) + pd.offsets.MonthEnd(1) :]):+.0f}%" for c in cols
        )
        + ".",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    for c, (lab, col) in cols.items():
        ax.plot(_index(i[c].loc[A:]), color=col, lw=1.8, label=lab)
    ax.axvline(pd.Timestamp(B), color=PALETTE["muted"], ls=":", lw=1)
    ax.set_yscale("log")
    ax.legend(frameon=False)
    tidy(ax, ylabel="growth of $1 since 2007 (log)")
    caption(fig, "AQR value (VAL) in each market, long/short, US dollars.")
    return fig


def drawdowns() -> Figure:
    p = _panel()
    fig = new_figure(14.5, 6.0)
    dd = {c: _index(p[c]) / _index(p[c]).cummax() - 1 for c in ("HML", "HML_DEVIL", "VAL")}
    title_block(
        fig,
        "The deepest drawdowns: the dot-com boom and the lost decade",
        f"Drawdown of each value factor from its previous peak. Worst points: HML {100 * dd['HML'].min():.0f}% ({dd['HML'].idxmin():%b %Y}), HML Devil "
        f"{100 * dd['HML_DEVIL'].min():.0f}% ({dd['HML_DEVIL'].idxmin():%b %Y}), VAL {100 * dd['VAL'].min():.0f}% ({dd['VAL'].idxmin():%b %Y}). In {p['VAL'].dropna().index[-1]:%B %Y} "
        f"VAL was still {100 * -dd['VAL'].iloc[-1]:.0f}% below its 2007 peak.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    for c, s in dd.items():
        ax.plot(100 * s.loc["1988-07":], color=COL[c], lw=1.5, label=NAMES[c])
    _shade_lost(ax)
    ax.legend(frameon=False, loc="lower left")
    tidy(ax, ylabel="drawdown, %")
    caption(fig, SRC)
    return fig


def recovery() -> Figure:
    p, i = _panel(), _intl()
    series = {
        "HML": p["HML"],
        "HML Devil": p["HML_DEVIL"],
        "VAL": p["VAL"],
        "US VAL": i["VAL_US"],
        "Europe VAL": i["VAL_EU"],
        "Japan VAL": i["VAL_JP"],
    }
    eps = {k: L.episode(s.rename(k)) for k, s in series.items()}
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Since late 2020 value has done well; whether it is back depends on the measure",
        f"Sharpe ratios before 2007, during the lost decade and after September 2020. UK HML: {eps['HML'].sharpe_before:.2f}, {eps['HML'].sharpe_during:.2f}, "
        f"{eps['HML'].sharpe_after:.2f}. The after-period is under six years, so that last Sharpe ratio has a standard error of "
        f"{stats.sharpe_se(p['HML'].loc[pd.Timestamp(B) + pd.offsets.MonthEnd(1) :].dropna().to_numpy()):.2f}.",
    )
    ax = fig.add_axes((0.06, 0.15, 0.9, 0.56))
    x = np.arange(len(series))
    for k, (attr, col, lab) in enumerate(
        (
            ("sharpe_before", PALETTE["slate"], "before 2007"),
            ("sharpe_during", PALETTE["red"], "2007-2020"),
            ("sharpe_after", PALETTE["blue"], "after 2020"),
        )
    ):
        ax.bar(x + (k - 1) * 0.27, [getattr(e, attr) for e in eps.values()], 0.27, color=col, label=lab)
    ax.set_xticks(x, list(series))
    ax.axhline(0, color=PALETTE["ink"], lw=0.6)
    ax.legend(frameon=False)
    tidy(ax, ylabel="Sharpe ratio")
    caption(fig, SRC + " International: AQR VAL in dollars.")
    return fig


# ------------------------------------------------------------------ 5-7. was it unusual


def break_test() -> Figure:
    path, date, stat, pval = _break()
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "No significant break in value's average return",
        f"Wald statistic for a change in HML's mean at each date (Andrews 1993), Newey-West errors. The largest, {stat:.1f}, is at {date:%B %Y}: the end of the lost "
        f"decade, not its start. A block bootstrap with no break gives a statistic this large with probability {pval:.2f}.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(path, color=PALETTE["blue"], lw=1.6)
    ax.axhline(8.85, color=PALETTE["muted"], ls="--", lw=1)
    ax.text(path.index[0], 9.1, "Andrews' 5% critical value (15% trimming): 8.85", fontsize=8, color=PALETTE["muted"])
    _shade_lost(ax)
    tidy(ax, ylabel="Wald statistic")
    caption(fig, SRC + " Bootstrap: stationary blocks of mean length 12 months on the demeaned series.")
    return fig


def unusual() -> Figure:
    p = _panel()
    n = len(p["HML"].loc[A:B])
    fig = new_figure(14.5, 6.0)
    out = {}
    rng = np.random.default_rng(5)
    for c in ("HML", "VAL"):
        hist = p[c].loc[: pd.Timestamp(A) - pd.offsets.MonthEnd(1)].dropna().to_numpy()
        sims = []
        for _ in range(max(200, DRAWS * 5)):
            idx = L._block_indices(len(hist), 12.0, rng, length=n)
            sims.append(np.prod(1 + hist[idx]) - 1)
        out[c] = (np.array(sims), L.episode(p[c].rename(c)).cumulative)
    title_block(
        fig,
        "A loss this long and deep was rare, but not impossible, by the earlier record",
        f"Cumulative return of {n}-month stretches resampled in blocks from each factor's own history before 2007, against what happened. HML's "
        f"{100 * out['HML'][1]:+.0f}% is worse than {100 * (1 - np.mean(out['HML'][0] <= out['HML'][1])):.1f}% of draws; VAL's {100 * out['VAL'][1]:+.0f}% "
        f"worse than {100 * (1 - np.mean(out['VAL'][0] <= out['VAL'][1])):.1f}%.",
    )
    for k, c in enumerate(("HML", "VAL")):
        ax = fig.add_axes((0.06 + 0.48 * k, 0.13, 0.42, 0.58))
        sims, act = out[c]
        ax.hist(100 * np.clip(sims, -1, 9), bins=50, color=PALETTE["band"], edgecolor=PALETTE["slate"])
        ax.axvline(100 * act, color=PALETTE["accent"], lw=2)
        tidy(ax, title=NAMES[c], xlabel="cumulative return over the stretch, %")
    caption(fig, SRC + " Stationary block bootstrap, mean block 12 months.")
    return fig


def learning() -> Figure:
    em = L.expanding_mean(_panel()["HML"])
    pick = [pd.Timestamp("2006-12-31"), pd.Timestamp("2020-09-30"), em.index[-1]]
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "What an investor would have estimated the value premium to be",
        f"HML's average return from 1988 to each date, with a 95% Newey-West band. In December 2006: {100 * em.loc[pick[0], 'mean']:.1f}% a year; in September 2020: "
        f"{100 * em.loc[pick[1], 'mean']:.1f}% (band {100 * em.loc[pick[1], 'lo']:.1f}% to {100 * em.loc[pick[1], 'hi']:.1f}%); in {pick[2]:%B %Y}: "
        f"{100 * em.loc[pick[2], 'mean']:.1f}%. In September 2020 the band still contained both zero and the 2006 estimate.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.fill_between(em.index, 100 * em["lo"], 100 * em["hi"], color=PALETTE["blue"], alpha=0.15, lw=0)
    ax.plot(100 * em["mean"], color=PALETTE["blue"], lw=1.8)
    ax.axhline(0, color=PALETTE["ink"], lw=0.6)
    _shade_lost(ax)
    tidy(ax, ylabel="estimated premium, % a year")
    caption(fig, SRC)
    return fig


# ------------------------------------------------------------------ 8-11. what lines up with it


def attribution() -> Figure:
    p = _panel()
    a3 = L.attribution(p["HML"], p[["MKT", "SMB", "UMD"]], None)
    a4 = L.attribution(p["HML"], p[["MKT", "SMB", "UMD", "QMJ"]], None)
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Value's short positions in momentum and quality explain part of the loss",
        f"HML's summed monthly return over the lost decade ({100 * a3['total']:+.0f} points), split into factor loadings (full-sample regression) times factor returns, "
        f"the full-sample alpha and what is left. With quality in the model the residual is {100 * a4['residual']:+.0f} points against {100 * a3['residual']:+.0f} without: "
        f"quality contributed {100 * a4['QMJ']:+.0f} and momentum {100 * a4['UMD']:+.0f}.",
    )
    for k, (a, ttl) in enumerate(((a3, "Market, size, momentum"), (a4, "... and quality"))):
        ax = fig.add_axes((0.06 + 0.48 * k, 0.13, 0.42, 0.58))
        keys = [x for x in a.index if x != "total"]
        ax.bar(
            range(len(keys)), [100 * a[x] for x in keys], color=[PALETTE["blue"] if a[x] > 0 else PALETTE["red"] for x in keys]
        )
        ax.set_xticks(range(len(keys)), keys)
        ax.axhline(0, color=PALETTE["ink"], lw=0.6)
        tidy(ax, title=ttl, ylabel="percentage points" if k == 0 else None)
    caption(fig, SRC + " Arithmetic sums of monthly returns, so the parts add up exactly.")
    return fig


def rates() -> Figure:
    p = _panel()
    g = fred.gilt_yield()
    before = L.rate_beta(p["HML"], g, ("1988", "2006"))
    during = L.rate_beta(p["HML"], g, L.LOST)
    after = L.rate_beta(p["HML"], g, (pd.Timestamp(B) + pd.offsets.MonthEnd(1), "2026-12"))
    dy = 100 * g.diff()
    fall = float(dy.loc[A:B].sum())
    dyf = dy.rename("d")
    roll = pd.concat([p["HML"].rename("y"), dyf], axis=1).dropna()
    beta = roll["y"].rolling(60).cov(roll["d"]) / roll["d"].rolling(60).var()
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "During the lost decade value became a bet on gilt yields",
        f"HML's return per percentage point rise in the ten-year gilt yield. Before 2007: {100 * before.coef[1]:+.1f}% (t = {before.tstat[1]:.1f}); 2007-2020: "
        f"{100 * during.coef[1]:+.1f}% (t = {during.tstat[1]:.1f}); since: {100 * after.coef[1]:+.1f}% (t = {after.tstat[1]:.1f}). Yields fell {-fall:.1f} points in the decade, "
        f"which at the decade's beta is {100 * during.coef[1] * fall:+.0f} points of return.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    ax.plot(100 * beta, color=PALETTE["blue"], lw=1.6)
    ax.axhline(0, color=PALETTE["ink"], lw=0.6)
    _shade_lost(ax)
    tidy(ax, title="Rolling 5-year beta to yield changes", ylabel="% return per point")
    ax2 = fig.add_axes((0.68, 0.13, 0.29, 0.58))
    ax2.plot(100 * g.loc["1988":], color=PALETTE["green"], lw=1.4)
    _shade_lost(ax2)
    tidy(ax2, title="Ten-year gilt yield, %")
    caption(fig, SRC + " Gilt yield: OECD via FRED, monthly average (ADR 0014).")
    return fig


def legs() -> Figure:
    p = _panel()
    lg = L.legs(_deciles(), p["EX_RMRF"], p["EX_RF"])
    w = lg.loc["2007":]
    cum = w.apply(L.cumulative)
    pre = 12 * lg.loc[:"2006"].mean()
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Growth stocks won, rather than value stocks losing",
        f"Exeter's top and bottom book-to-market deciles against the UK market, 2007 to June 2016. The value decile beat the market by {100 * cum['value_vs_market']:+.0f}% "
        f"in total; the growth decile by {100 * cum['growth_vs_market']:+.0f}%. Before 2007 the value decile beat the market by {100 * pre['value_vs_market']:.1f}% a year and "
        f"growth trailed it by {100 * -pre['growth_vs_market']:.1f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    for c, col, lab in (
        ("value_vs_market", PALETTE["green"], "value decile minus market"),
        ("growth_vs_market", PALETTE["violet"], "growth decile minus market"),
        ("value_minus_growth", PALETTE["ink"], "value minus growth"),
    ):
        ax.plot(_index(lg[c].loc["2000":]), color=col, lw=1.8, label=lab)
    ax.axvline(pd.Timestamp(A), color=PALETTE["muted"], ls=":", lw=1)
    ax.legend(frameon=False)
    tidy(ax, ylabel="growth of £1 since 2000")
    caption(fig, "Exeter value-weighted book-to-market deciles and market (Gregory, Tharyan and Christidis 2013), to June 2016.")
    return fig


def devil() -> Figure:
    p = _panel()
    d = (p["HML_DEVIL"] - p["HML"]).dropna()
    corr = d.corr(p["UMD"])
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Measuring value with timely prices made the decade worse",
        f"HML Devil minus HML (Asness and Frazzini 2013). Devil uses today's price with last year's book value, so it holds the stocks that are cheap now. "
        f"The difference lost {100 * -L.cumulative(d.loc[A:B]):.0f}% over the decade; it correlates {corr:.2f} with momentum, so it is a bet against recent winners.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(_index(d), color=PALETTE["violet"], lw=1.8)
    _shade_lost(ax)
    tidy(ax, ylabel="growth of £1, Devil minus HML")
    caption(fig, SRC)
    return fig


def size() -> Figure:
    six = exeter.portfolios("6ports_size_bm")
    small, big = (six["SH"] - six["SL"]).rename("small"), (six["BH"] - six["BL"]).rename("big")
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "Small and large value lost alike",
        f"Exeter's value-minus-growth among small and among large UK companies. 2007 to June 2016: small {100 * L.cumulative(small.loc['2007':]):+.0f}%, large "
        f"{100 * L.cumulative(big.loc['2007':]):+.0f}%. Before 2007 small value earned {100 * 12 * small.loc[:'2006'].mean():.1f}% a year and large value "
        f"{100 * 12 * big.loc[:'2006'].mean():.1f}%. The loss was not a small-company problem.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    ax.plot(_index(small), color=PALETTE["teal"], lw=1.8, label="small: high minus low book-to-market")
    ax.plot(_index(big), color=PALETTE["blue"], lw=1.8, label="large: high minus low")
    ax.set_yscale("log")
    _shade(ax, labels=False)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="growth of £1 (log)")
    caption(fig, "Exeter 2 x 3 size and book-to-market portfolios, value-weighted, to June 2016.")
    return fig
