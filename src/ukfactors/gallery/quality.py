"""Day 6 charts: quality and value traps in the UK.

AQR's UK QMJ (from July 1993), HML, HML Devil and VAL in sterling; AQR's QMJ and HML for every
country (dollars, long/short); FTSE 350 survivors from Yahoo for the stock-level test. Every
number in a subtitle is computed.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from .. import analysis, survivorship
from .. import lostdecade as L
from .. import quality as Q
from ..data import aqr, yahoo
from .anatomy import LAST_COMPLETE
from .foundation import _panel
from .style import PALETTE, caption, new_figure, tidy, title_block

DRAWS = 1000  # bootstrap draws for the Sharpe gain; the tests lower it
A, B = L.LOST
SRC = "AQR UK factors in sterling (ADR 0004), long/short, July 1993 onwards. QMJ: Asness, Frazzini and Pedersen (2019)."
COL = {
    "HML": PALETTE["blue"],
    "HML_DEVIL": PALETTE["violet"],
    "VAL": PALETTE["slate"],
    "QMJ": PALETTE["green"],
    "MIX50": PALETTE["ink"],
}
NAMES = {
    "HML": "HML (value)",
    "HML_DEVIL": "HML Devil",
    "VAL": "AQR VAL",
    "QMJ": "QMJ (quality)",
    "MIX50": "50/50 value + quality",
}
WINDOWS: dict[str, tuple[str | None, str | None]] = {
    "1993-2006": (None, "2006-12"),
    "Lost decade 2007-2020": (A, B),
    "Since October 2020": ("2020-10", None),
}


@lru_cache(maxsize=1)
def _d() -> pd.DataFrame:
    return Q.sample(_panel())


@lru_cache(maxsize=1)
def _traps() -> tuple[pd.DataFrame, pd.DataFrame]:
    return Q.trap_buckets(survivorship.clean(yahoo.prices(), LAST_COMPLETE).returns)


@lru_cache(maxsize=1)
def _intl() -> pd.DataFrame:
    return Q.international(aqr.country("QMJ"), aqr.country("HML"))


@lru_cache(maxsize=1)
def _gain() -> np.ndarray:
    d = _d()
    return Q.sharpe_gain(d["HML"], d["QMJ"], reps=DRAWS, seed=6)


def _index(s: pd.Series) -> pd.Series:
    return (1 + s.dropna()).cumprod()


def _log_pounds(ax) -> None:  # type: ignore[no-untyped-def]
    """A log axis labelled in plain pounds, without matplotlib's minor-tick mathtext."""
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter

    lo, hi = ax.get_ylim()
    ticks = [t for t in (0.5, 1, 2, 3, 5, 10, 20, 30, 50, 100) if lo <= t <= hi]
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"£{y:g}"))
    ax.yaxis.set_minor_formatter(NullFormatter())


def _shade_lost(ax) -> None:  # type: ignore[no-untyped-def]
    ax.axvspan(pd.Timestamp(A), pd.Timestamp(B), color=PALETTE["band"], zorder=0)


# ------------------------------------------------------------------ 1-3. the hedge


def cumulative() -> Figure:
    d = _d()
    m = Q.mix(d["HML"], d["QMJ"])
    s = {k: Q.summary(v) for k, v in {"HML": d["HML"], "QMJ": d["QMJ"], "MIX50": m}.items()}
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Value and quality took turns; holding both earned value's return with half the risk",
        f"Growth of £1, July 1993 to {d.index[-1]:%B %Y}. Sharpe ratio: HML {s['HML']['sharpe']:.2f}, QMJ {s['QMJ']['sharpe']:.2f}, the 50/50 mix "
        f"{s['MIX50']['sharpe']:.2f}. Volatility {100 * s['HML']['vol']:.0f}%, {100 * s['QMJ']['vol']:.0f}% and {100 * s['MIX50']['vol']:.0f}%; "
        f"worst fall {100 * s['HML']['maxdd']:.0f}%, {100 * s['QMJ']['maxdd']:.0f}% and {100 * s['MIX50']['maxdd']:.0f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    for k, v in {"HML": d["HML"], "QMJ": d["QMJ"], "MIX50": m}.items():
        ax.plot(_index(v), color=COL[k], lw=2.2 if k == "MIX50" else 1.6, label=NAMES[k])
    ax.set_yscale("log")
    _log_pounds(ax)
    _shade_lost(ax)
    ax.text(
        pd.Timestamp(A),
        1.0,
        " value's lost decade",
        transform=ax.get_xaxis_transform(),
        va="bottom",
        fontsize=8,
        color=PALETTE["muted"],
    )
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="growth of £1 (log scale)")
    caption(fig, SRC + " The mix holds half in each, rebalanced monthly.")
    return fig


def correlation() -> Figure:
    d = _d()
    rc = analysis.rolling_correlation(d["HML"], d["QMJ"], 36)
    rd = analysis.rolling_correlation(d["HML_DEVIL"], d["QMJ"], 36)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Cheap UK stocks are usually junk: value and quality are negatively correlated most of the time",
        f"Correlation with QMJ over rolling 36 months. Full sample: HML {d['HML'].corr(d['QMJ']):.2f}, HML Devil {d['HML_DEVIL'].corr(d['QMJ']):.2f}; "
        f"the HML correlation was below zero in {100 * (rc.dropna() < 0).mean():.0f}% of windows. Devil value uses current prices, so it holds "
        "more recent losers, and recent losers are junkier.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    ax.plot(rc, color=COL["HML"], lw=1.8, label="HML and QMJ")
    ax.plot(rd, color=COL["HML_DEVIL"], lw=1.4, label="HML Devil and QMJ")
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    _shade_lost(ax)
    ax.set_ylim(-1, 1)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="36-month correlation")
    caption(fig, SRC)
    return fig


def frontier() -> Figure:
    d = _d()
    fig = new_figure(14.5, 6.0)
    tw = {v: analysis.tangency_weight(d[v], d["QMJ"]) for v in Q.VALUE}
    best = {v: analysis.mix_frontier(d[v], d["QMJ"])["sharpe"].max() for v in Q.VALUE}
    title_block(
        fig,
        f"Any measure of value gains from adding quality; the best mixes hold {100 * min(tw.values()):.0f}-{100 * max(tw.values()):.0f}% quality",
        "Sharpe ratio and worst fall of (1 - w) value + w QMJ. Maximum-Sharpe weight on QMJ: "
        + ", ".join(f"{NAMES[v]} {100 * tw[v]:.0f}% (Sharpe {best[v]:.2f})" for v in Q.VALUE)
        + f". QMJ alone: {Q.summary(d['QMJ'])['sharpe']:.2f}.",
    )
    a1 = fig.add_axes((0.06, 0.13, 0.42, 0.6))
    a2 = fig.add_axes((0.55, 0.13, 0.42, 0.6))
    for v in Q.VALUE:
        f = analysis.mix_frontier(d[v], d["QMJ"])
        a1.plot(100 * f.index, f["sharpe"], color=COL[v], lw=1.8, label=NAMES[v])
        a1.plot(100 * tw[v], f["sharpe"].max(), "o", color=COL[v], ms=6)
        a2.plot(100 * f.index, -100 * f["max_drawdown"], color=COL[v], lw=1.8, label=NAMES[v])
    a1.legend(frameon=False, loc="lower right")
    tidy(a1, title="Sharpe ratio", xlabel="weight on QMJ, %", ylabel="annualised Sharpe ratio")
    tidy(a2, title="Worst peak-to-trough fall", xlabel="weight on QMJ, %", ylabel="%")
    caption(fig, SRC + " Dots: in-sample maximum-Sharpe weights, which flatter the mix.")
    return fig


# ------------------------------------------------------------------ 4-6. what quality adds to value


def lost_decade() -> Figure:
    d = _d()
    t = Q.periods(d[["HML", "QMJ"]].assign(MIX50=Q.mix(d["HML"], d["QMJ"])), WINDOWS)
    fig = new_figure(14.5, 6.0)
    lost = t.loc["Lost decade 2007-2020"]
    title_block(
        fig,
        "Quality paid for value's lost decade, then gave some back as value recovered",
        f"Annualised return in each window. In 2007-2020 HML returned {100 * lost.loc['HML', 'annual']:+.1f}% a year and QMJ "
        f"{100 * lost.loc['QMJ', 'annual']:+.1f}%; the mix compounded {100 * lost.loc['MIX50', 'total']:+.0f}% in all. Since October 2020 value has "
        f"returned {100 * t.loc[('Since October 2020', 'HML'), 'annual']:+.0f}% a year and quality {100 * t.loc[('Since October 2020', 'QMJ'), 'annual']:+.1f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    keys = ["HML", "QMJ", "MIX50"]
    x = np.arange(len(WINDOWS))
    for i, k in enumerate(keys):
        vals = [100 * t.loc[(w, k), "annual"] for w in WINDOWS]
        bars = ax.bar(x + (i - 1) * 0.26, vals, 0.24, color=COL[k], label=NAMES[k])
        for b_, v in zip(bars, vals, strict=True):
            ax.text(b_.get_x() + b_.get_width() / 2, v, f"{v:+.1f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
    ax.set_xticks(x, list(WINDOWS))
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="annualised return, %")
    caption(fig, SRC + " The last window is short (about five years).")
    return fig


def alpha() -> Figure:
    d = _d()
    base = d[["MKT", "SMB", "UMD"]]
    fits = {v: Q.adjusted_alpha(d[v], base, d["QMJ"]) for v in Q.VALUE}
    fig = new_figure(14.5, 6.0)
    h = fits["HML"]
    title_block(
        fig,
        "Controlling for quality raises value's alpha: value is cheap and junky, and junk costs money",
        f"Annualised alpha of each value factor against market, size and momentum, then with QMJ added. HML: {100 * h.base.alpha:.1f}% (t = {h.base.alpha_t:.1f}) "
        f"rising to {100 * h.with_quality.alpha:.1f}% (t = {h.with_quality.alpha_t:.1f}); its QMJ loading is {h.loading:.2f}. "
        "A negative loading means value holds junk, so removing the junk exposure leaves more alpha.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.6))
    x = np.arange(len(Q.VALUE))
    for j, (lab, attr, col) in enumerate(
        [("market, size, momentum", "base", PALETTE["slate"]), ("plus QMJ", "with_quality", PALETTE["green"])]
    ):
        a = [100 * getattr(fits[v], attr).alpha for v in Q.VALUE]
        se = [100 * 12 * getattr(fits[v], attr).se[0] * 1.96 for v in Q.VALUE]
        ax.bar(x + (j - 0.5) * 0.36, a, 0.34, yerr=se, color=col, label=lab, capsize=3, ecolor=PALETTE["muted"])
    ax.set_xticks(x, [NAMES[v] for v in Q.VALUE])
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="upper right")
    tidy(ax, ylabel="annualised alpha, % (95% interval)")
    a2 = fig.add_axes((0.69, 0.13, 0.28, 0.6))
    a2.barh([NAMES[v] for v in Q.VALUE][::-1], [fits[v].loading for v in Q.VALUE][::-1], color=PALETTE["blue"])
    a2.axvline(0, color=PALETTE["ink"], lw=0.8)
    tidy(a2, title="Loading on QMJ", xlabel="coefficient")
    caption(fig, SRC + " Newey-West errors.")
    return fig


def crisis() -> Figure:
    d = _d()
    f = Q.flight_to_quality(d["QMJ"], d["MKT"])
    qq = (1 + d[["QMJ", "MKT"]]).resample("QE").prod() - 1
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Quality is a hedge: it gains when the UK market falls, which is when cheap junk falls hardest",
        f"Quarterly QMJ against the market. Beta {f['beta']:.2f} (t = {f['beta_t']:.1f}). In the worst tenth of market months QMJ earned "
        f"{100 * f['worst']:+.0f}% a year; in the best tenth {100 * f['best']:+.0f}%. A value portfolio that adds quality inherits the hedge.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.6))
    ax.scatter(100 * qq["MKT"], 100 * qq["QMJ"], s=14, color=PALETTE["green"], alpha=0.7)
    fit = np.polyfit(qq["MKT"], qq["QMJ"], 1)
    xs = np.linspace(qq["MKT"].min(), qq["MKT"].max(), 50)
    ax.plot(100 * xs, 100 * np.polyval(fit, xs), color=PALETTE["ink"], lw=1.2)
    ax.axhline(0, color=PALETTE["muted"], lw=0.6)
    ax.axvline(0, color=PALETTE["muted"], lw=0.6)
    tidy(ax, xlabel="UK market excess return in the quarter, %", ylabel="QMJ in the quarter, %")
    a2 = fig.add_axes((0.69, 0.13, 0.28, 0.6))
    vals = [100 * f["worst"], 100 * f["middle"], 100 * f["best"]]
    a2.bar(["worst 10%", "middle 80%", "best 10%"], vals, color=[PALETTE["green"], PALETTE["slate"], PALETTE["red"]])
    a2.axhline(0, color=PALETTE["ink"], lw=0.8)
    tidy(a2, title="QMJ by market month", ylabel="annualised, %")
    caption(fig, SRC)
    return fig


# ------------------------------------------------------------------ 7-8. how sure, and is it British


def bootstrap() -> Figure:
    g = _gain()
    d = _d()
    obs = Q.summary(Q.mix(d["HML"], d["QMJ"]))["sharpe"] - Q.summary(d["HML"])["sharpe"]
    fig = new_figure(14.5, 6.0)
    lo, hi = np.percentile(g, [5, 95])
    title_block(
        fig,
        "The gain from adding quality to value is too large to be luck",
        f"Sharpe ratio of the 50/50 mix minus that of HML, in {len(g):,} stationary-bootstrap histories (12-month mean blocks, months drawn jointly). "
        f"Observed gain {obs:+.2f}; 90% interval {lo:+.2f} to {hi:+.2f}; {100 * (g <= 0).mean():.1f}% of draws show no gain.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    ax.hist(g, bins=50, color=PALETTE["green"], alpha=0.8)
    ax.axvline(0, color=PALETTE["red"], lw=1.2)
    ax.axvline(obs, color=PALETTE["ink"], lw=1.4)
    ax.text(obs, ax.get_ylim()[1] * 0.95, " observed", fontsize=8)
    tidy(ax, xlabel="Sharpe(mix) - Sharpe(HML)", ylabel="histories")
    caption(fig, SRC + " The bootstrap keeps the joint distribution and short-run dependence of the two factors.")
    return fig


def international() -> Figure:
    t = _intl()
    t = t.drop(index=[c for c in t.index if c in ("Global", "Global Ex USA", "Europe", "North America", "Pacific")]).sort_values(
        "corr"
    )
    fig = new_figure(14.5, 6.6)
    gbr = t.loc["GBR"]
    title_block(
        fig,
        "The value-quality hedge is international; the UK sits at the median correlation and gains more than most",
        f"AQR's QMJ and HML in {len(t)} countries, July 1993 onwards (dollars). Correlation below zero in {int((t['corr'] < 0).sum())}; the 50/50 mix beats "
        f"the better of the two in {int((t['gain'] > 0).sum())}. UK: correlation {gbr['corr']:.2f}, Sharpe {gbr['value']:.2f} value, {gbr['quality']:.2f} quality, "
        f"{gbr['mix']:.2f} mix. The US is an exception: correlation {t.loc['USA', 'corr']:+.2f}.",
    )
    a1 = fig.add_axes((0.06, 0.16, 0.42, 0.56))
    a2 = fig.add_axes((0.55, 0.16, 0.42, 0.56))
    cols = [PALETTE["accent"] if c == "GBR" else PALETTE["blue"] for c in t.index]
    a1.bar(t.index, t["corr"], color=cols)
    a1.axhline(0, color=PALETTE["ink"], lw=0.8)
    a1.tick_params(axis="x", rotation=90, labelsize=7.5)
    tidy(a1, title="Correlation of QMJ with HML", ylabel="correlation")
    a2.scatter(t[["value", "quality"]].max(axis=1), t["mix"], color=cols, s=24)
    for c in t.index:
        a2.annotate(
            c,
            (max(t.loc[c, "value"], t.loc[c, "quality"]), t.loc[c, "mix"]),
            fontsize=6.5,
            color=PALETTE["muted"],
            xytext=(3, 2),
            textcoords="offset points",
        )
    lim = (min(0, t["mix"].min()) - 0.05, t["mix"].max() + 0.1)
    a2.plot(lim, lim, color=PALETTE["muted"], lw=0.8, ls="--")
    tidy(
        a2,
        title="Mix against the better single factor",
        xlabel="Sharpe ratio of the better of value and quality",
        ylabel="Sharpe ratio of the 50/50 mix",
    )
    caption(fig, "AQR country QMJ and HML factors, US dollars, long/short. Points above the dashed line gain from mixing.")
    return fig


# ------------------------------------------------------------------ 9-10. stocks


def traps() -> Figure:
    _, tab = _traps()
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Among cheap FTSE 350 survivors, the safest are the least likely to keep falling, but the riskiest earned most",
        f"The cheapest 30% on returns from five years to one year ago, split into thirds by volatility. Share of stock-years losing 30% or more over the next "
        f"12 months: {100 * tab.loc['V1', 'trap_rate']:.0f}% for the safest third, {100 * tab.loc['V3', 'trap_rate']:.0f}% for the riskiest "
        f"({100 * tab.loc['ALL', 'trap_rate']:.0f}% for all stocks). Mean next-12-month return: {100 * tab.loc['V1', 'forward']:.0f}% against "
        f"{100 * tab.loc['V3', 'forward']:.0f}%. The panel holds survivors only, which flatters the risky cheap stocks most.",
    )
    keys = ["V1", "V2", "V3", "CHEAP", "ALL"]
    lab = ["cheap, safest", "cheap, middle", "cheap, riskiest", "all cheap", "all stocks"]
    cols = [PALETTE["green"], PALETTE["teal"], PALETTE["red"], PALETTE["slate"], PALETTE["muted"]]
    a1 = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    a2 = fig.add_axes((0.55, 0.13, 0.42, 0.58))
    a1.bar(lab, 100 * tab.loc[keys, "trap_rate"], color=cols)
    a2.bar(lab, 100 * tab.loc[keys, "forward"], color=cols)
    for a in (a1, a2):
        a.tick_params(axis="x", labelsize=8)
    tidy(a1, title="Trap rate: lose 30% or more in the next year", ylabel="% of stock-years")
    tidy(a2, title="Mean return over the next year", ylabel="%")
    caption(
        fig,
        "Yahoo month-end prices of current FTSE 350 members, cleaned (ADR 0003, 0011); overlapping 12-month windows; equal weights. Survivors only (ADR 0016).",
    )
    return fig


def trap_paths() -> Figure:
    b, _ = _traps()
    s = {k: Q.summary(b[k]) for k in ("V1", "V3", "ALL")}
    crash = (1 + b.loc["2007-06":"2009-02"]).prod() - 1
    covid = (1 + b.loc["2020-01":"2020-03"]).prod() - 1
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Safe cheap stocks fell least in 2008 but not in 2020; risky cheap survivors earned most overall",
        f"Growth of £1, equal-weighted, rebalanced monthly. June 2007 to February 2009: safest {100 * crash.loc['V1']:.0f}%, riskiest {100 * crash.loc['V3']:.0f}%, "
        f"all {100 * crash.loc['ALL']:.0f}%; January-March 2020: {100 * covid.loc['V1']:.0f}%, {100 * covid.loc['V3']:.0f}% and {100 * covid.loc['ALL']:.0f}%. Safest cheap third: {100 * s['V1']['mean']:.0f}% a year, volatility {100 * s['V1']['vol']:.0f}%, "
        f"worst fall {100 * s['V1']['maxdd']:.0f}%. Riskiest cheap third: {100 * s['V3']['mean']:.0f}%, {100 * s['V3']['vol']:.0f}%, {100 * s['V3']['maxdd']:.0f}%. "
        f"All stocks: {100 * s['ALL']['mean']:.0f}%, {100 * s['ALL']['vol']:.0f}%, {100 * s['ALL']['maxdd']:.0f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    for k, lab, col in (
        ("V1", "cheap, safest third", PALETTE["green"]),
        ("V3", "cheap, riskiest third", PALETTE["red"]),
        ("ALL", "all stocks", PALETTE["slate"]),
    ):
        ax.plot(_index(b[k]), color=col, lw=1.8, label=lab)
    ax.set_yscale("log")
    _log_pounds(ax)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="growth of £1 (log scale)")
    caption(
        fig,
        "Yahoo prices of current FTSE 350 members, total-return proxy from adjusted closes. A survivor panel cannot show the traps that failed (ADR 0016).",
    )
    return fig
