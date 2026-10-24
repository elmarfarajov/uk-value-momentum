"""Day 1 charts: fifty-four years of UK factors, two sources checked against each other, and the biases in free data.

Every chart is drawn from the local raw files (``ukf data fetch``) and is skipped where they
are absent.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from scipy import stats as sps

from .. import panel, stats, survivorship
from ..data import aqr, exeter, fred, yahoo
from .style import PALETTE, SERIES, caption, new_figure, tidy, title_block

LABELS = {
    "VAL": "value (AQR, rank-weighted)",
    "MOM": "momentum (AQR, rank-weighted)",
    "HML": "HML (AQR, Fama-French)",
    "UMD": "UMD (AQR)",
    "QMJ": "quality minus junk (AQR)",
    "MKT": "market excess return",
    "SMB": "SMB (AQR)",
    "HML_DEVIL": "HML Devil (AQR, current prices)",
}
COLOURS = {
    "VAL": PALETTE["blue"],
    "MOM": PALETTE["red"],
    "HML": PALETTE["teal"],
    "UMD": PALETTE["violet"],
    "QMJ": PALETTE["green"],
    "MKT": PALETTE["slate"],
    "SMB": PALETTE["muted"],
    "HML_DEVIL": PALETTE["accent"],
}
CRISES = [
    ("1973-05", "1974-12", "1973-74"),
    ("1987-09", "1987-12", "1987"),
    ("1990-07", "1992-09", "ERM"),
    ("2000-09", "2003-03", "dot-com"),
    ("2007-10", "2009-03", "GFC"),
    ("2020-02", "2020-04", "COVID"),
    ("2022-01", "2022-10", "2022"),
]
LAST_COMPLETE = pd.Timestamp("2026-09-30")


@lru_cache(maxsize=1)
def _panel() -> pd.DataFrame:
    return panel.build()


def _shade(ax: Axes, labels: bool = True) -> None:
    for lo, hi, name in CRISES:
        ax.axvspan(pd.Timestamp(lo), pd.Timestamp(hi), color=PALETTE["band"], zorder=0)
        if labels:
            ax.text(
                pd.Timestamp(lo), 1.0, name, transform=ax.get_xaxis_transform(), fontsize=7, color=PALETTE["muted"], va="bottom"
            )


def long_history() -> Figure:
    p = _panel()
    cols = ["MOM", "VAL", "UMD", "HML", "MKT"]
    sharpe = {c: stats.annual_sharpe(p[c].dropna().to_numpy()) for c in cols}
    fig = new_figure(14.5, 6.6)
    title_block(
        fig,
        "Fifty-four years of UK value and momentum",
        f"Growth of one pound in each zero-cost factor, in sterling, from AQR's survivorship-free UK series. Momentum has the "
        f"longest record and the best: a Sharpe ratio of {sharpe['MOM']:.2f} since 1972 ({sharpe['UMD']:.2f} for the Fama-French-"
        f"style UMD since 1987), against {sharpe['VAL']:.2f} for value and {sharpe['MKT']:.2f} for the market itself - with "
        "momentum's worst years in the rebounds after crashes.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.62))
    _shade(ax)
    for c in cols:
        s = p[c].dropna()
        ax.plot(
            (1 + s).cumprod(),
            color=COLOURS[c],
            lw=1.9 if c in ("MOM", "VAL") else 1.3,
            label=f"{LABELS[c]}, from {s.index[0]:%Y} (Sharpe {sharpe[c]:.2f})",
        )
    ax.set_yscale("log")
    tidy(ax, ylabel="growth of one pound (log scale)")
    ax.legend(fontsize=8.5, loc="upper left")
    caption(
        fig,
        "AQR Capital Management, LLC; dollar series converted to sterling (ADR 0002). Shaded: UK bear markets and crises. Excess returns: no financing cost added.",
    )
    return fig


def rolling_sharpe() -> Figure:
    p = _panel()
    fig = new_figure(14.0, 5.8)
    cols = ["MOM", "VAL", "UMD", "HML", "QMJ"]
    roll = {c: p[c].dropna().rolling(60).apply(lambda v: np.sqrt(12) * v.mean() / v.std(), raw=True) for c in cols}
    neg = {c: float((roll[c].dropna() < 0).mean()) for c in cols}
    title_block(
        fig,
        "A premium is an average over decades, not a promise for any five years",
        f"Five-year rolling Sharpe ratios. Momentum's was negative in {100 * neg['MOM']:.0f}% of five-year windows and value's in "
        f"{100 * neg['VAL']:.0f}%, and quality's in {100 * neg['QMJ']:.0f}%; value spent most of 2010-2020 below zero, the 'lost "
        "decade' Day 5 decomposes. Even momentum's record holds stretches of five years with nothing to show.",
    )
    ax = fig.add_axes((0.06, 0.14, 0.9, 0.6))
    _shade(ax, labels=False)
    for c in cols:
        ax.plot(roll[c], color=COLOURS[c], lw=1.6 if c in ("MOM", "VAL") else 1.1, label=LABELS[c])
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    tidy(ax, ylabel="Sharpe ratio, trailing 60 months")
    ax.legend(fontsize=8, ncol=3, loc="lower left")
    caption(
        fig,
        "Annualised: sqrt(12) x monthly mean / monthly standard deviation over the trailing 60 months. AQR series in sterling.",
    )
    return fig


def two_sources() -> Figure:
    p = _panel()
    pairs = [("HML", "EX_HML", "value: HML"), ("UMD", "EX_UMD", "momentum: UMD"), ("SMB", "EX_SMB", "size: SMB")]
    fig = new_figure(14.5, 6.0)
    corr = {a: p[[a, b]].dropna().corr().iloc[0, 1] for a, b, _ in pairs}
    title_block(
        fig,
        "Two independent sources tell the same story about momentum, less so about value and size",
        f"AQR (built from Datastream and Compustat) against the Exeter Xfi Centre (built from the London Share Price Database), "
        f"month by month over their common years. Momentum agrees closely (correlation {corr['UMD']:.2f}); value ({corr['HML']:.2f}) "
        f"and size ({corr['SMB']:.2f}) less, and their averages differ: the breakpoints and the universe matter for both.",
    )
    for k, (a, b, name) in enumerate(pairs):
        j = p[[a, b]].dropna()
        ax = fig.add_axes((0.05 + 0.325 * k, 0.15, 0.27, 0.58))
        ax.scatter(100 * j[b], 100 * j[a], s=8, color=SERIES[k], alpha=0.5)
        lim = float(100 * max(j.abs().max()))
        ax.plot([-lim, lim], [-lim, lim], color=PALETTE["ink"], lw=0.8)
        tidy(ax, title=name, xlabel="Exeter, % a month", ylabel="AQR, % a month" if k == 0 else None)
        ax.text(
            0.03,
            0.97,
            f"{j.index[0]:%Y-%m} to {j.index[-1]:%Y-%m}\ncorrelation {j[a].corr(j[b]):.3f}\n"
            f"mean AQR {1200 * j[a].mean():.1f}% a year\nmean Exeter {1200 * j[b].mean():.1f}% a year",
            transform=ax.transAxes,
            va="top",
            fontsize=8,
        )
    caption(
        fig,
        "Both in sterling. AQR: Asness and Frazzini's UK factors; Exeter: Gregory, Tharyan and Christidis (2013), files ending June 2016.",
    )
    return fig


PUBLISHED = {  # Gregory, Tharyan and Christidis (2013), Table 1, October 1980 to December 2010, monthly %
    "RMRF": (0.51, 4.67, -1.00, 6.50),
    "SMB": (0.09, 3.23, 0.41, 6.36),
    "HML": (0.31, 3.40, -0.67, 10.04),
    "UMD": (0.77, 4.16, -1.26, 10.87),
}


def exeter_moments() -> dict[str, tuple[float, float, float, float]]:
    e = exeter.factors().loc["1980-10":"2010-12"]
    return {
        c: (100 * float(e[c].mean()), 100 * float(e[c].std()), float(sps.skew(e[c])), float(sps.kurtosis(e[c], fisher=False)))
        for c in PUBLISHED
    }


def exeter_vs_paper() -> Figure:
    ours = exeter_moments()
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "The files are not the paper: Exeter's factors were rebuilt after publication",
        f"Moments of Exeter's downloadable factors over October 1980 to December 2010, against the same statistics printed in "
        f"Gregory, Tharyan and Christidis (2013), Table 1. The market reproduces exactly; momentum averages {ours['UMD'][0]:.2f}% a "
        f"month in the files against {PUBLISHED['UMD'][0]:.2f}% in the paper, and HML {ours['HML'][0]:.2f}% against "
        f"{PUBLISHED['HML'][0]:.2f}%. Any study citing the paper while using the files reports different numbers.",
    )
    names = list(PUBLISHED)
    stats_names = ("mean, % a month", "standard deviation, %", "skewness", "kurtosis")
    for k, label in enumerate(stats_names):
        ax = fig.add_axes((0.045 + 0.243 * k, 0.15, 0.2, 0.58))
        x = np.arange(len(names))
        ax.bar(x - 0.2, [PUBLISHED[n][k] for n in names], width=0.38, color=PALETTE["slate"], label="paper (2013)")
        ax.bar(x + 0.2, [ours[n][k] for n in names], width=0.38, color=PALETTE["blue"], label="files (2016)")
        ax.set_xticks(x, names)
        ax.axhline(0, color=PALETTE["ink"], lw=0.6)
        tidy(ax, title=label)
        if k == 0:
            ax.legend(fontsize=8)
    caption(
        fig,
        "Kurtosis is raw (normal = 3), as in the paper. The Exeter page dates the files' coverage to December 2017; the files end in June 2016.",
    )
    return fig


def currency() -> Figure:
    usd = aqr.uk()
    ex = exeter.factors()
    fx = fred.gbpusd().pct_change().rename("FX")
    rf_us = aqr.us_bill()
    j = pd.concat([usd["MKT"], ex["RM"], ex["RF"], ex["RMRF"], fx, rf_us], axis=1, sort=True).dropna()
    in_usd = (1 + j["RM"]) * (1 + j["FX"]) - 1 - j["RF_US"]
    gap = j["MKT"] - j["RMRF"]
    slope, intercept = np.polyfit(j["FX"], gap, 1)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "AQR's UK factors are in dollars, and a sterling study must say so",
        f"AQR's UK market excess return correlates {j['MKT'].corr(in_usd):.4f} with Exeter's sterling market converted to dollars, "
        f"and only {j['MKT'].corr(j['RMRF']):.3f} with the sterling series itself. The gap between AQR and sterling moves "
        f"{slope:.2f}-for-one with the pound against the dollar: it is the exchange rate. Every AQR series is converted to sterling "
        "before it meets a sterling one.",
    )
    ax = fig.add_axes((0.05, 0.15, 0.27, 0.58))
    ax.scatter(100 * j["RMRF"], 100 * j["MKT"], s=7, color=PALETTE["slate"], alpha=0.5)
    tidy(ax, title="AQR against the sterling market", xlabel="Exeter excess return, %", ylabel="AQR UK MKT, %")
    ax2 = fig.add_axes((0.375, 0.15, 0.27, 0.58))
    ax2.scatter(100 * in_usd, 100 * j["MKT"], s=7, color=PALETTE["blue"], alpha=0.5)
    tidy(ax2, title="AQR against the same market in dollars", xlabel="Exeter converted to dollars, %")
    ax3 = fig.add_axes((0.7, 0.15, 0.27, 0.58))
    ax3.scatter(100 * j["FX"], 100 * gap, s=7, color=PALETTE["violet"], alpha=0.5)
    xs = np.linspace(float(j["FX"].min()), float(j["FX"].max()), 2)
    ax3.plot(100 * xs, 100 * (intercept + slope * xs), color=PALETTE["accent"], lw=1.5, label=f"slope {slope:.3f}")
    ax3.legend(fontsize=8)
    tidy(ax3, title="the gap is the exchange rate", xlabel="pound against the dollar, % a month", ylabel="AQR minus sterling, %")
    caption(
        fig,
        f"{j.index[0]:%Y-%m} to {j.index[-1]:%Y-%m}; FRED DEXUSUK month-end rates. Long/short factors are converted by dividing by (1 + the pound's change).",
    )
    return fig


def distributions() -> Figure:
    p = _panel()
    cols = ["MOM", "UMD", "VAL", "HML", "QMJ", "MKT"]
    fig = new_figure(14.5, 7.4)
    title_block(
        fig,
        "Fat tails, and momentum's on the wrong side",
        "Monthly returns of each factor against a normal distribution with the same mean and volatility. Every series has "
        "excess kurtosis. The Fama-French-style momentum factor UMD has the most negative skew (-1.71) and the worst month "
        "(-33%): steady gains, rare large losses, which is why a Sharpe ratio flatters it and Day 7 studies its crashes.",
    )
    for k, c in enumerate(cols):
        s = 100 * p[c].dropna()
        row, col = divmod(k, 3)
        ax = fig.add_axes((0.05 + 0.325 * col, 0.53 - 0.42 * row, 0.27, 0.3))
        ax.hist(s, bins=60, density=True, color=COLOURS[c], alpha=0.55)
        grid = np.linspace(float(s.min()), float(s.max()), 300)
        ax.plot(grid, sps.norm.pdf(grid, s.mean(), s.std()), color=PALETTE["ink"], lw=1.0)
        ax.set_yscale("log")
        ax.set_ylim(1e-4, None)
        tidy(ax, title=LABELS[c], xlabel="% a month" if row == 1 else None)
        ax.text(
            0.03,
            0.95,
            f"skew {sps.skew(s):.2f}\nexcess kurtosis {sps.kurtosis(s):.1f}\nworst {s.min():.1f}%",
            transform=ax.transAxes,
            va="top",
            fontsize=8,
        )
    caption(
        fig,
        "Log density scale, so the tails are visible. AQR UK series in sterling; black: the normal distribution with the same mean and volatility.",
    )
    return fig


def drawdowns() -> Figure:
    p = _panel()
    cols = ["MOM", "VAL", "QMJ", "MKT"]
    fig = new_figure(14.5, 6.4)
    worst = {c: stats.max_drawdown(p[c].dropna().to_numpy()) for c in cols}
    title_block(
        fig,
        "The pain behind the premium: drawdowns",
        f"Fall of each factor's cumulative return from its previous peak. Value's worst drawdown was {100 * worst['VAL']:.0f}%, "
        f"momentum's {100 * worst['MOM']:.0f}% and the market's {100 * worst['MKT']:.0f}% - and value has still not regained its "
        "2007 peak in 2026. A strategy has to be survivable before it can be profitable.",
    )
    for k, c in enumerate(cols):
        ax = fig.add_axes((0.06, 0.66 - 0.17 * k, 0.9, 0.13))
        dd = stats.drawdown_path(p[c].dropna())
        ax.fill_between(dd.index, 100 * dd, 0, color=COLOURS[c], alpha=0.6)
        ax.set_ylim(-80, 2)
        ax.set_xlim(pd.Timestamp("1972-01"), pd.Timestamp("2026-12"))
        tidy(ax, ylabel="%")
        ax.text(0.005, 0.12, f"{LABELS[c]}: worst {100 * worst[c]:.0f}%", transform=ax.transAxes, fontsize=8.5)
        if k < len(cols) - 1:
            ax.set_xticklabels([])
    caption(fig, "Drawdown = cumulative return / running maximum - 1, on excess returns in sterling.")
    return fig


def world_correlations() -> Figure:
    v = panel.international()
    p = _panel()
    frame = pd.concat(
        [
            v[["VAL_UK", "MOM_UK", "VAL_US", "MOM_US", "VAL_EU", "MOM_EU", "VAL_JP", "MOM_JP"]],
            p[["QMJ", "MKT", "SMB"]].rename(columns={"QMJ": "QMJ_UK", "MKT": "MKT_UK", "SMB": "SMB_UK"}),
        ],
        axis=1,
        sort=True,
    ).dropna()
    c = frame.corr()
    vm = float(c.loc["VAL_UK", "MOM_UK"])
    fig = new_figure(12.5, 8.2)
    title_block(
        fig,
        "Value and momentum hedge each other, in the UK and everywhere",
        f"Correlations of monthly returns, {frame.index[0]:%Y} to {frame.index[-1]:%Y}. UK value and UK momentum correlate "
        f"{vm:.2f}: the negative link Asness, Moskowitz and Pedersen (2013) found in every market, and the reason a combination "
        "of the two (Day 14) is steadier than either. Both styles correlate 0.5 to 0.8 across countries: each has a strong "
        "global component, so diversifying across markets helps less than diversifying across styles.",
    )
    ax = fig.add_axes((0.18, 0.14, 0.68, 0.66))
    im = ax.imshow(c.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(c)), c.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(c)), c.index)
    for i in range(len(c)):
        for k in range(len(c)):
            ax.text(
                k,
                i,
                f"{c.iloc[i, k]:.2f}",
                ha="center",
                va="center",
                fontsize=7,
                color="white" if abs(c.iloc[i, k]) > 0.6 else PALETTE["ink"],
            )
    ax.grid(False)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    caption(fig, "AQR rank-weighted value and momentum by market (dollars, long/short), UK QMJ, market and SMB in sterling.")
    return fig


@lru_cache(maxsize=1)
def _bias() -> survivorship.Bias:
    p = _panel()
    return survivorship.measure(yahoo.prices(), p["MOM"], p["MKT"] + p["RF_UK"], LAST_COMPLETE)


def survivorship_bias() -> Figure:
    p = _panel()
    cleaning = survivorship.clean(yahoo.prices(), LAST_COMPLETE)
    ret = cleaning.returns
    average = ret.mean(axis=1)
    market = p["MKT"] + p["RF_UK"]
    j = pd.concat([average.rename("survivors"), market.rename("market")], axis=1, sort=True).dropna()
    b = _bias()
    periods = [("1999", "2007"), ("2008", "2015"), ("2016", "2026")]
    gaps = [12 * float((j.loc[lo:hi, "survivors"] - j.loc[lo:hi, "market"]).mean()) for lo, hi in periods]
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Free data remembers only the winners",
        f"Today's FTSE 350 companies, followed back to 1999, beat the UK market by {100 * b.survivors_premium:.1f}% a year on "
        f"average - by {100 * gaps[0]:.1f}% a year in 1999-2007 and {100 * gaps[-1]:.1f}% since 2016: the further back, the "
        f"bigger the bias. A momentum strategy on the same survivors earns {100 * b.momentum_survivors.mean() * 12:.1f}% a year "
        f"against {100 * b.momentum_clean.mean() * 12:.1f}% for AQR's survivorship-free momentum: the losers that survived "
        "rebounded, so survivorship makes momentum look weaker, not stronger.",
    )
    ax = fig.add_axes((0.05, 0.15, 0.42, 0.58))
    ax.plot((1 + j["survivors"]).cumprod(), color=PALETTE["accent"], lw=1.8, label="today's FTSE 350, equal-weighted")
    ax.plot((1 + j["market"]).cumprod(), color=PALETTE["slate"], lw=1.8, label="the UK market (AQR, sterling)")
    ax.set_yscale("log")
    tidy(ax, title="survivors against the market", ylabel="growth of one pound")
    ax.legend(fontsize=8)
    ax2 = fig.add_axes((0.55, 0.15, 0.42, 0.58))
    ax2.plot((1 + b.momentum_survivors).cumprod(), color=PALETTE["accent"], lw=1.8, label="momentum on today's FTSE 350")
    ax2.plot((1 + b.momentum_clean).cumprod(), color=PALETTE["blue"], lw=1.8, label="AQR UK momentum (survivorship-free)")
    tidy(ax2, title=f"momentum, correlation {b.correlation:.2f}", ylabel="growth of one pound")
    ax2.legend(fontsize=8)
    caption(
        fig,
        f"Yahoo Finance daily adjusted closes at month end, {cleaning.kept} companies; {len(cleaning.excluded)} series excluded for "
        "impossible moves and unit flips (ADR 0011). Equal weights tilt the survivors towards smaller firms, which adds a size effect to the bias.",
    )
    return fig


def decades() -> Figure:
    p = _panel()
    cols = ["MOM", "VAL", "HML", "UMD", "QMJ", "MKT"]
    edges = ["1972", "1980", "1990", "2000", "2010", "2020", "2027"]
    fig = new_figure(14.5, 6.2)
    tables = {c: stats.by_period(p[c], edges) for c in cols}
    mom = tables["MOM"].set_index("period")["mean"]
    title_block(
        fig,
        "Decade by decade: momentum in every decade since 1980, value in some",
        f"Annualised mean returns per decade with 95% Newey-West confidence intervals. Momentum lost a little in the 1970s "
        f"({100 * mom.iloc[0]:.1f}% a year) and was positive in every decade since, {100 * mom.iloc[1:].min():.0f}% to "
        f"{100 * mom.iloc[1:].max():.0f}% a year; value was strongly positive in the 1980s and 2000s and negative in the 1990s and "
        "2010s. Intervals this wide are why a decade proves little on its own.",
    )
    ax = fig.add_axes((0.06, 0.15, 0.9, 0.58))
    periods = sorted({row for t in tables.values() for row in t["period"]})
    x = np.arange(len(periods))
    width = 0.13
    for k, c in enumerate(cols):
        t = tables[c].set_index("period").reindex(periods)
        ax.bar(x + (k - 2.5) * width, 100 * t["mean"], width=width * 0.95, color=COLOURS[c], label=LABELS[c])
        ax.errorbar(x + (k - 2.5) * width, 100 * t["mean"], yerr=196 * t["se"], fmt="none", ecolor=PALETTE["ink"], lw=0.7)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    ax.set_xticks(x, periods)
    tidy(ax, ylabel="% a year")
    ax.legend(fontsize=7.5, ncol=3)
    caption(
        fig, "A decade is shown when a series has at least 24 months in it; AQR series in sterling. The 2020s run to July 2026."
    )
    return fig


def uk_vs_world() -> Figure:
    v = panel.international()
    markets = [("UK", "UK"), ("US", "US"), ("EU", "continental Europe"), ("JP", "Japan")]
    rows = []
    for code, name in markets:
        for style in ("VAL", "MOM"):
            s = v[f"{style}_{code}"].dropna().loc["1982":]
            boot = stats.stationary_bootstrap(s.to_numpy(), stats.annual_sharpe, reps=800, seed=1)
            rows.append((name, style, stats.annual_sharpe(s.to_numpy()), *np.percentile(boot, [2.5, 97.5])))
    fig = new_figure(14.0, 5.8)
    uk_mom = next(r[2] for r in rows if r[0] == "UK" and r[1] == "MOM")
    us_mom = next(r[2] for r in rows if r[0] == "US" and r[1] == "MOM")
    title_block(
        fig,
        "Momentum works in the UK and Europe, value in Japan",
        f"Sharpe ratios of AQR's value and momentum in four stock markets, 1982 to 2026, with 95% stationary-bootstrap intervals. "
        f"UK momentum's Sharpe ratio is {uk_mom:.2f}, against {us_mom:.2f} in the US and about the same as continental Europe's; "
        "UK value's interval includes zero. Japan is the mirror image: value works and momentum does not.",
    )
    ax = fig.add_axes((0.08, 0.15, 0.88, 0.58))
    x = np.arange(len(markets))
    for k, (style, colour) in enumerate((("VAL", PALETTE["blue"]), ("MOM", PALETTE["red"]))):
        sel = [r for r in rows if r[1] == style]
        sr = np.array([r[2] for r in sel])
        lo = np.array([r[3] for r in sel])
        hi = np.array([r[4] for r in sel])
        ax.bar(x + (k - 0.5) * 0.36, sr, width=0.34, color=colour, label="value" if style == "VAL" else "momentum")
        ax.errorbar(x + (k - 0.5) * 0.36, sr, yerr=[sr - lo, hi - sr], fmt="none", ecolor=PALETTE["ink"], lw=0.8, capsize=3)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    ax.set_xticks(x, [m[1] for m in markets])
    tidy(ax, ylabel="Sharpe ratio")
    ax.legend(fontsize=8.5)
    caption(
        fig,
        "AQR rank-weighted long/short factors in dollars from 1982, when every market's value series exists; mean block length 6 months.",
    )
    return fig
