"""Day 3 charts: industry momentum and sector rotation in the UK.

All charts use the survivor sample of today's FTSE 350 (ADR 0009) grouped into twelve industries
(ADR 0012); no free survivorship-free UK industry data exists. Every number in a subtitle is
computed from the data the chart draws.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.figure import Figure

from .. import industry as I
from .. import momentum as M
from .. import stats
from ..data import yahoo
from .anatomy import LAST_COMPLETE, START, _market, _returns, _std, _window
from .foundation import _shade
from .style import PALETTE, caption, new_figure, tidy, title_block

SURV = "Survivor sample: today's FTSE 350, twelve industries (ICB, investment trusts separate), equal-weighted (ADR 0009, 0012)."
TWELVE = [
    PALETTE["blue"],
    PALETTE["green"],
    PALETTE["violet"],
    PALETTE["teal"],
    PALETTE["slate"],
    PALETTE["red"],
    "#8fb3e8",
    "#9fd4c2",
    "#c3a6e0",
    "#88c5c5",
    "#b6bfc8",
    "#e3a1a1",
]


@lru_cache(maxsize=1)
def _groups() -> pd.Series:
    return I.groups(yahoo.constituents())


@lru_cache(maxsize=1)
def _ind() -> tuple[pd.DataFrame, pd.DataFrame]:
    return I.industry_returns(_returns(), _groups())


@lru_cache(maxsize=16)
def _imom(j: int = 11, k: int = 1, skip: int = 1) -> M.Strategy:
    return I.industry_momentum(_ind()[0], j, k, skip)


@lru_cache(maxsize=1)
def _decomp() -> pd.DataFrame:
    r, g, ir = _returns(), _groups(), _ind()[0]
    ims = M.overlapping(r, I.industry_signal(r, g, ir), 1).wml
    nms = M.overlapping(r, I.neutral_signal(r, g), 1).wml
    return pd.concat(
        [_std().wml.rename("stock"), ims.rename("industry_stocks"), nms.rename("neutral"), _imom().wml.rename("industry")], axis=1
    ).loc[START:]


@lru_cache(maxsize=1)
def _fm() -> dict[str, I.FamaMacBeth]:
    r, g, ir = _returns(), _groups(), _ind()[0]
    own = M.formation_return(r, 11, 1)
    isig = I.industry_signal(r, g, ir)
    nsig = I.neutral_signal(r, g)
    lag1 = M.formation_return(r, 1, 0)
    ilag = I.industry_signal(r, g, ir, 1, 0)
    rr = r.loc[START:]
    return {
        "own and industry 12-1": I.fama_macbeth(rr, {"own 12-1": own, "industry 12-1": isig}),
        "neutral and industry 12-1": I.fama_macbeth(rr, {"industry-neutral 12-1": nsig, "industry 12-1": isig}),
        "last month": I.fama_macbeth(rr, {"own last month": lag1, "industry last month": ilag, "own 12-1": own}),
    }


@lru_cache(maxsize=1)
def _placebo() -> pd.DataFrame:
    return I.placebo(_returns(), _groups(), draws=200, start=START)


def _s(x: pd.Series) -> dict[str, float]:
    return M.summary(x.loc[START:].dropna())


# ------------------------------------------------------------------ 1-4. the industries


def industry_paths() -> Figure:
    ir = _ind()[0].loc["2000":]
    growth = pd.DataFrame({c: (1 + ir[c].dropna()).cumprod() for c in ir.columns})
    ann = 12 * ir.mean()
    best, worst = ann.idxmax(), ann.idxmin()
    fig = new_figure(14.5, 6.6)
    title_block(
        fig,
        "Twelve UK industries, 2000-2026: a wide spread of fortunes",
        f"Growth of one pound in each industry, equal-weighted across today's members. {best} averaged {100 * ann[best]:.1f}% a year and "
        f"{worst} {100 * ann[worst]:.1f}%; the average monthly gap between the best and worst industry was "
        f"{100 * (ir.max(axis=1) - ir.min(axis=1)).mean():.1f} points. Momentum across industries needs that spread to persist.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.66, 0.6))
    _shade(ax, labels=False)
    order = ann.sort_values(ascending=False).index
    for name, c in zip(order, TWELVE, strict=False):
        ax.plot(growth[name], color=c, lw=1.5, label=f"{name} ({100 * ann[name]:.1f}%)")
    ax.set_yscale("log")
    _window(ax, "2000-01-31")
    tidy(ax, ylabel="growth of one pound (log scale)")
    ax.legend(fontsize=7.5, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    caption(fig, SURV + " Telecommunications and Technology start when they first have three members.")
    return fig


def industry_years() -> Figure:
    ir = _ind()[0].loc["2000":"2025"]
    cy = (
        ir.groupby(pd.DatetimeIndex(ir.index).year)
        .apply(lambda g: (1 + g).prod() - 1)
        .where(ir.groupby(pd.DatetimeIndex(ir.index).year).count() >= 12)
    )
    rank_corr = cy.rank(axis=1).corrwith(cy.rank(axis=1).shift(1), axis=1).dropna()
    fig = new_figure(15.0, 7.0)
    title_block(
        fig,
        "Last year's best industry is no guide to this year's",
        f"Calendar-year returns of each industry, %. The rank correlation between one year's industry returns and the next averages "
        f"{rank_corr.mean():.2f} (positive in {int((rank_corr > 0).sum())} of {len(rank_corr)} years): at an annual horizon industry "
        "leadership does not persist, if anything it mildly reverses.",
    )
    ax = fig.add_axes((0.15, 0.1, 0.82, 0.62))
    data = 100 * cy.T.to_numpy(dtype=float)
    ax.imshow(np.clip(data, -60, 60), cmap="RdBu", norm=TwoSlopeNorm(vmin=-60, vcenter=0, vmax=60), aspect="auto")
    for i in range(data.shape[0]):
        for jx in range(data.shape[1]):
            if np.isfinite(data[i, jx]):
                ax.text(
                    jx,
                    i,
                    f"{data[i, jx]:.0f}",
                    ha="center",
                    va="center",
                    fontsize=6.3,
                    color="white" if abs(data[i, jx]) > 35 else PALETTE["ink"],
                )
    ax.set_yticks(range(len(cy.columns)))
    ax.set_yticklabels(list(cy.columns), fontsize=8)
    ax.set_xticks(range(0, len(cy.index), 2))
    ax.set_xticklabels([str(y) for y in cy.index[::2]], fontsize=8)
    ax.grid(False)
    caption(fig, SURV + " Blank: fewer than three members or an incomplete year. Colour clipped at +/-60%.")
    return fig


def industry_risk_return() -> Figure:
    ir = _ind()[0].loc[START:]
    stats_ = pd.DataFrame({"mean": 12 * ir.mean(), "vol": np.sqrt(12) * ir.std(), "n": _ind()[1].loc[START:].mean()})
    corr = ir.corr()
    off = corr.to_numpy()[np.triu_indices(len(corr), 1)]
    fig = new_figure(14.5, 6.4)
    title_block(
        fig,
        "Industries differ widely in return and risk, and move together",
        f"Left: mean return against volatility for each industry since 2001 (dot size: members). Right: correlations between "
        f"industry returns average {np.nanmean(off):.2f} (range {np.nanmin(off):.2f} to {np.nanmax(off):.2f}). Industry momentum is a bet "
        "on the part that does not move together.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.38, 0.58))
    ax.scatter(100 * stats_["vol"], 100 * stats_["mean"], s=8 * stats_["n"], color=PALETTE["blue"], alpha=0.5)
    for name, row in stats_.iterrows():
        ax.annotate(str(name), (100 * row["vol"], 100 * row["mean"]), fontsize=7.5, xytext=(4, 2), textcoords="offset points")
    tidy(ax, title="Return and risk since 2001", xlabel="volatility, % a year", ylabel="mean return, % a year")
    bx = fig.add_axes((0.55, 0.12, 0.36, 0.6))
    bx.imshow(corr.to_numpy(), cmap="Blues", vmin=0, vmax=1)
    bx.set_xticks(range(len(corr)))
    bx.set_xticklabels([c[:10] for c in corr.columns], rotation=90, fontsize=7)
    bx.set_yticks(range(len(corr)))
    bx.set_yticklabels([c[:14] for c in corr.index], fontsize=7)
    for i in range(len(corr)):
        for jx in range(len(corr)):
            v = corr.iloc[i, jx]
            bx.text(jx, i, f"{v:.1f}", ha="center", va="center", fontsize=6, color="white" if v > 0.7 else PALETTE["ink"])
    bx.grid(False)
    tidy(bx, title="Correlation of industry returns")
    caption(fig, SURV + f" Monthly returns, {START[:4]}-2026.")
    return fig


def group_sizes() -> Figure:
    cnt = _ind()[1].loc["2000":]
    fig = new_figure(14.5, 5.8)
    total = cnt.sum(axis=1)
    title_block(
        fig,
        "How many stocks stand behind each industry",
        f"Members with a return each month. The sample grows from {int(total.iloc[0])} stocks in 2000 to {int(total.iloc[-1])} in 2026 "
        f"because today's companies are followed back to their listing. {cnt.iloc[-1].idxmax()} are the largest group ({int(cnt.iloc[-1].max())} "
        f"today); {cnt.iloc[-1].idxmin()} the smallest ({int(cnt.iloc[-1].min())}).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.7, 0.58))
    order = cnt.iloc[-1].sort_values(ascending=False).index
    ax.stackplot(cnt.index, cnt[order].T.to_numpy(), colors=TWELVE[: len(order)], labels=list(order), alpha=0.9)
    _window(ax, "2000-01-31")
    tidy(ax, ylabel="stocks with a return")
    ax.legend(fontsize=7.5, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    caption(fig, SURV)
    return fig


# ------------------------------------------------------------------ 5-8. industry momentum


def industry_grid() -> Figure:
    ir = _ind()[0]
    js, ks = [1, 3, 6, 9, 12], [1, 3, 6, 12]
    mean = np.zeros((len(js), len(ks)))
    tv = np.zeros_like(mean)
    for a, j in enumerate(js):
        for b, k in enumerate(ks):
            s = I.industry_momentum(ir, j if j == 1 else j - 1, k, 0 if j == 1 else 1).wml.loc[START:].dropna().to_numpy()
            mean[a, b] = 1200 * s.mean()
            tv[a, b] = stats.nw_tstat(s)
    fig = new_figure(14.5, 6.4)
    title_block(
        fig,
        "Industry momentum in the UK lives at one month, not twelve",
        f"Top three minus bottom three industries for each formation period J and holding period K, {START[:4]}-2026. Ranking on last "
        f"month's industry return earns {mean[0, 0]:.1f}% a year held one month (t = {tv[0, 0]:.1f}); the classic twelve-month signal earns "
        f"{mean[-1, 0]:.1f}% (t = {tv[-1, 0]:.1f}). Unlike US industries (Moskowitz and Grinblatt, 1999), UK industries show no "
        "reliable momentum beyond a few months.",
    )
    ax = fig.add_axes((0.15, 0.12, 0.6, 0.6))
    lim = float(np.abs(mean).max())
    ax.imshow(mean, cmap="RdBu", norm=TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim), aspect="auto")
    for a in range(len(js)):
        for b in range(len(ks)):
            ax.text(
                b,
                a,
                f"{mean[a, b]:.1f}\n(t {tv[a, b]:.1f})",
                ha="center",
                va="center",
                fontsize=9,
                color="white" if abs(mean[a, b]) > 0.6 * lim else PALETTE["ink"],
            )
    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels([str(k) for k in ks])
    ax.set_yticks(range(len(js)))
    ax.set_yticklabels([f"{j} (no skip)" if j == 1 else f"{j}" for j in js])
    ax.grid(False)
    tidy(ax, xlabel="holding period K, months", ylabel="formation period J, months")
    caption(fig, SURV + " J = 1 uses last month's return with no skip; longer windows skip the latest month.")
    return fig


def one_month() -> Figure:
    fm = _fm()["last month"].frame()
    s1 = _imom(1, 1, 0).wml.loc[START:].dropna()
    r = _returns()
    dec = M.deciles(r, M.formation_return(r, 1, 0)).loc[START:]
    stock_spread = (dec[10] - dec[1]).dropna()
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Last month: stocks reverse, industries continue",
        f"Fama-MacBeth slopes of next month's stock return on the stock's own last-month return, its industry's last-month return "
        f"and its 12-1 return. A stock's own last month predicts a {abs(100 * fm.loc['own last month', 'mean']):.2f}-point lower return "
        f"per standard deviation (t = {fm.loc['own last month', 't_nw']:.1f}); its industry's predicts a "
        f"{100 * fm.loc['industry last month', 'mean']:.2f}-point higher one (t = {fm.loc['industry last month', 't_nw']:.1f}). "
        "Short-term reversal is a stock effect; at the industry level news keeps diffusing.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    names = list(fm.index)
    vals = 100 * fm["mean"].to_numpy()
    se = np.abs(vals / fm["t_nw"].to_numpy())
    ax.bar(range(len(names)), vals, color=[PALETTE["red"], PALETTE["blue"], PALETTE["slate"]], width=0.55)
    ax.errorbar(range(len(names)), vals, yerr=1.96 * se, fmt="none", color=PALETTE["ink"], capsize=4)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, fontsize=8.5)
    tidy(ax, title="Fama-MacBeth slopes (95% NW intervals)", ylabel="% a month per standard deviation")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    _shade(bx, labels=False)
    bx.plot(
        (1 + s1).cumprod(),
        color=PALETTE["blue"],
        lw=1.8,
        label=f"industries: last month's top 3 minus bottom 3 (Sharpe {stats.annual_sharpe(s1.to_numpy()):.2f})",
    )
    bx.plot(
        (1 + stock_spread).cumprod(),
        color=PALETTE["red"],
        lw=1.8,
        label=f"stocks: last month's top minus bottom decile (Sharpe {stats.annual_sharpe(stock_spread.to_numpy()):.2f})",
    )
    bx.set_yscale("log")
    _window(bx, START)
    tidy(bx, title="One-month strategies", ylabel="growth of one pound (log)")
    bx.legend(fontsize=7.5, loc="upper left")
    caption(fig, SURV + f" Predictors standardised each month; {START[:4]}-2026.")
    return fig


def industry_vs_stock_paths() -> Figure:
    d = _decomp()
    sm = {c: _s(d[c]) for c in d.columns}
    labels = {
        "stock": "stock 12-1 deciles",
        "neutral": "industry-neutral stock 12-1",
        "industry_stocks": "stocks ranked on their industry's 12-1",
        "industry": "industries: top 3 minus bottom 3, 12-1",
    }
    colours = {
        "stock": PALETTE["red"],
        "neutral": PALETTE["violet"],
        "industry_stocks": PALETTE["teal"],
        "industry": PALETTE["blue"],
    }
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Take the industry out of stock momentum and almost nothing changes",
        f"Twelve-month momentum four ways. Stock momentum: Sharpe {sm['stock']['sharpe']:.2f}. Ranking each stock against its own "
        f"industry (industry-neutral): {sm['neutral']['sharpe']:.2f}, correlation {d['stock'].corr(d['neutral']):.2f}. Ranking stocks on "
        f"their industry's return: {sm['industry_stocks']['sharpe']:.2f}; ranking industries themselves: {sm['industry']['sharpe']:.2f}. "
        "UK stock momentum is stock-specific, the opposite of Moskowitz and Grinblatt's US finding.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    _shade(ax, labels=False)
    for c in ["stock", "neutral", "industry_stocks", "industry"]:
        ax.plot((1 + d[c].fillna(0)).cumprod(), color=colours[c], lw=1.8, label=f"{labels[c]} (Sharpe {sm[c]['sharpe']:.2f})")
    ax.set_yscale("log")
    _window(ax, START)
    tidy(ax, ylabel="growth of one pound (log scale)")
    ax.legend(fontsize=8.5, loc="upper left")
    caption(
        fig,
        SURV
        + " Stock strategies: decile winners minus losers; industry-neutral signal = stock 12-1 minus its industry's average 12-1.",
    )
    return fig


def spanning_chart() -> Figure:
    d = _decomp().dropna()
    pairs = [
        ("stock", ["industry"], "stock on industry"),
        ("industry", ["stock"], "industry on stock"),
        ("neutral", ["industry"], "neutral on industry"),
        ("stock", ["neutral"], "stock on neutral"),
    ]
    regs = [(label, I.spanning(d[y], d[x])) for y, x, label in pairs]
    corr = d.corr()
    fig = new_figure(14.5, 6.0)
    r0, r1 = regs[0][1], regs[1][1]
    title_block(
        fig,
        "Spanning: industry momentum adds nothing that stock momentum lacks",
        f"Alphas of each strategy regressed on another. Stock momentum keeps an alpha of {100 * r0.alpha:.1f}% a year over industry momentum "
        f"(t = {r0.alpha_t:.1f}), while industry momentum's alpha over stock momentum is {100 * r1.alpha:.1f}% (t = {r1.alpha_t:.1f}). With "
        "survivors' noisy returns no alpha is significant, but the asymmetry runs the opposite way to the US evidence.",
    )
    ax = fig.add_axes((0.17, 0.13, 0.42, 0.58))
    vals = [100 * r.alpha for _, r in regs]
    se = [abs(100 * r.alpha / r.alpha_t) for _, r in regs]
    ax.barh(
        range(len(regs))[::-1], vals, color=[PALETTE["red"], PALETTE["blue"], PALETTE["violet"], PALETTE["slate"]], height=0.55
    )
    ax.errorbar(vals, range(len(regs))[::-1], xerr=[1.96 * s for s in se], fmt="none", color=PALETTE["ink"], capsize=4)
    ax.set_yticks(range(len(regs))[::-1])
    ax.set_yticklabels([lab for lab, _ in regs])
    ax.axvline(0, color=PALETTE["ink"], lw=0.7)
    tidy(ax, title="Alpha, % a year (95% NW interval)")
    bx = fig.add_axes((0.66, 0.13, 0.3, 0.58))
    names = ["stock", "neutral", "industry_stocks", "industry"]
    short = ["stock", "neutral", "ind. stocks", "industries"]
    bx.imshow(corr.loc[names, names].to_numpy(), cmap="Blues", vmin=0, vmax=1)
    for i in range(4):
        for jx in range(4):
            v = corr.loc[names[i], names[jx]]
            bx.text(jx, i, f"{v:.2f}", ha="center", va="center", fontsize=8.5, color="white" if v > 0.7 else PALETTE["ink"])
    bx.set_xticks(range(4))
    bx.set_xticklabels(short, fontsize=8, rotation=30)
    bx.set_yticks(range(4))
    bx.set_yticklabels(short, fontsize=8)
    bx.grid(False)
    tidy(bx, title="Correlations")
    caption(fig, SURV + " Common months, Newey-West errors.")
    return fig


def fama_macbeth_chart() -> Figure:
    fm = _fm()
    a, b = fm["own and industry 12-1"].frame(), fm["neutral and industry 12-1"].frame()
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Stock by stock, the industry's past return adds nothing over the stock's own",
        f"Fama-MacBeth regressions of next month's return on standardised 12-1 signals. With both in the regression, the stock's own 12-1 "
        f"return earns {100 * a.loc['own 12-1', 'mean']:.2f} points a month per standard deviation (t = {a.loc['own 12-1', 't_nw']:.1f}) and "
        f"its industry's {100 * a.loc['industry 12-1', 'mean']:.2f} (t = {a.loc['industry 12-1', 't_nw']:.1f}). Splitting the stock's return "
        f"into an industry part and an industry-neutral part gives the neutral part {100 * b.loc['industry-neutral 12-1', 'mean']:.2f} "
        f"(t = {b.loc['industry-neutral 12-1', 't_nw']:.1f}).",
    )
    for k, (frame, title) in enumerate([(a, "Own and industry 12-1"), (b, "Industry-neutral and industry 12-1")]):
        ax = fig.add_axes((0.06 + 0.48 * k, 0.13, 0.42, 0.58))
        vals = 100 * frame["mean"].to_numpy()
        se = np.abs(vals / frame["t_nw"].to_numpy())
        ax.bar(range(len(frame)), vals, color=[PALETTE["red"] if k == 0 else PALETTE["violet"], PALETTE["blue"]], width=0.5)
        ax.errorbar(range(len(frame)), vals, yerr=1.96 * se, fmt="none", color=PALETTE["ink"], capsize=4)
        ax.axhline(0, color=PALETTE["ink"], lw=0.7)
        ax.set_xticks(range(len(frame)))
        ax.set_xticklabels(list(frame.index))
        tidy(ax, title=title, ylabel="% a month per standard deviation" if k == 0 else None)
    caption(fig, SURV + f" Monthly cross-sections, {START[:4]}-2026; 95% Newey-West intervals of the mean slope.")
    return fig


# ------------------------------------------------------------------ 9-10. placebo and dispersion


def placebo_chart() -> Figure:
    pl = _placebo()
    real = _imom().wml.loc[START:].dropna()
    real_sr = stats.annual_sharpe(real.to_numpy())
    real_disp = float(I.dispersion(_ind()[0]).loc[START:].mean())
    pct = float((pl["sharpe"] < real_sr).mean())
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Real industries are more distinct than random groups, but no better for momentum",
        f"The same stocks put into {len(pl)} random groupings with the real group sizes. Real industries' returns are far more dispersed "
        f"({100 * real_disp:.2f}% a month against {100 * pl['dispersion'].mean():.2f}% for random groups, above all {len(pl)} draws), yet "
        f"twelve-month industry momentum's Sharpe ratio of {real_sr:.2f} sits at the {100 * pct:.0f}th percentile of the random ones. "
        "Industries are real, their momentum is not distinguishable from chance.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.hist(pl["sharpe"], bins=25, color=PALETTE["slate"], alpha=0.7)
    ax.axvline(real_sr, color=PALETTE["red"], lw=2, label=f"real industries ({real_sr:.2f})")
    tidy(ax, title="Industry momentum Sharpe ratio, random groups", xlabel="Sharpe ratio", ylabel="random groupings")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    bx.hist(100 * pl["dispersion"], bins=25, color=PALETTE["slate"], alpha=0.7)
    bx.axvline(100 * real_disp, color=PALETTE["blue"], lw=2, label=f"real industries ({100 * real_disp:.2f}%)")
    tidy(bx, title="Cross-sectional dispersion of group returns", xlabel="% a month", ylabel="random groupings")
    bx.legend(fontsize=8.5)
    caption(fig, SURV + " Random groupings keep each stock's returns and each group's size; only membership is shuffled.")
    return fig


def dispersion_chart() -> Figure:
    disp = I.dispersion(_ind()[0]).loc[START:]
    w = _imom(1, 1, 0).wml
    j = pd.concat([w.rename("w"), disp.shift(1).rename("d")], axis=1).dropna()
    q = pd.qcut(j["d"], 4, labels=False)
    means = [1200 * j["w"][q == i].mean() for i in range(4)]
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Industry dispersion does not predict industry momentum",
        f"Left: the cross-sectional standard deviation of industry returns each month. Right: next month's one-month industry momentum by "
        f"quartile of this month's dispersion: {means[0]:.1f}% a year in the calmest quartile, {means[-1]:.1f}% in the most dispersed, with no pattern between. "
        "Dispersion rose in 2008-09, 2016 and 2021-22, when sectors moved apart most.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.5, 0.58))
    _shade(ax, labels=False)
    ax.plot(100 * disp, color=PALETTE["violet"], lw=1.2)
    ax.plot(100 * disp.rolling(12).mean(), color=PALETTE["ink"], lw=1.8, label="12-month average")
    _window(ax, START)
    tidy(ax, title="Dispersion of industry returns", ylabel="% a month")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.64, 0.13, 0.33, 0.58))
    bx.bar(range(1, 5), means, color=PALETTE["blue"], width=0.6)
    bx.axhline(0, color=PALETTE["ink"], lw=0.7)
    bx.set_xticks(range(1, 5))
    tidy(bx, title="Next-month industry momentum", xlabel="quartile of dispersion (4 = widest)", ylabel="% a year")
    caption(fig, SURV + " One-month industry momentum: last month's top three minus bottom three industries.")
    return fig


# ------------------------------------------------------------------ 11-12. lead-lag and rotation


def lead_lag() -> Figure:
    rel = I.relative_returns(_ind()[0].loc[START:])
    ca = I.cross_autocorrelation(rel, 1)
    nm = I.pair_months(rel, 1)
    rho = I.own_autocorrelation(_ind()[0].loc[START:])
    bands = 1.96 / np.sqrt(nm.to_numpy())
    big = int((np.abs(ca.to_numpy()) > bands).sum())
    fig = new_figure(14.5, 8.6)
    title_block(
        fig,
        "Do some industries lead others? Not detectably",
        f"Correlation of each industry's relative return this month (rows) with each industry's relative return next month (columns), "
        f"pairwise over {int(nm.to_numpy().min())} to {int(nm.to_numpy().max())} months. {big} of {ca.size} correlations exceed their 95% "
        f"band, against about {0.05 * ca.size:.0f} expected by chance. Own autocorrelations (the diagonal) average {rho.mean():.2f}. No "
        "stable lead-lag network of the kind Menzly and Ozbas (2010) find in US supplier-customer links appears at this level of aggregation.",
    )
    ax = fig.add_axes((0.22, 0.24, 0.55, 0.5))
    lim = float(np.nanmax(np.abs(ca.to_numpy())))
    ax.imshow(ca.to_numpy(), cmap="RdBu", norm=TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim), aspect="auto")
    for i in range(len(ca)):
        for jx in range(len(ca)):
            v = ca.iloc[i, jx]
            out = abs(v) > bands[i, jx]
            ax.text(
                jx,
                i,
                f"{v:.2f}",
                ha="center",
                va="center",
                fontsize=6.5,
                color="white" if abs(v) > 0.6 * lim else PALETTE["ink"],
                fontweight="bold" if out else "normal",
            )
    ax.set_xticks(range(len(ca)))
    ax.set_xticklabels(list(ca.columns), rotation=60, ha="right", fontsize=7.5)
    ax.set_yticks(range(len(ca)))
    ax.set_yticklabels(list(ca.index), fontsize=7.5)
    ax.grid(False)
    tidy(ax, xlabel="next month", ylabel="this month")
    caption(
        fig, SURV + " Relative return = industry minus the average of industries that month. Bold: outside the pair's 95% band."
    )
    return fig


def rotation() -> Figure:
    s = _imom(1, 1, 0)
    net = I.winners_by_year(s).loc[2001:2026]
    order = net.abs().mean().sort_values(ascending=False).index
    fig = new_figure(15.0, 6.8)
    most = net.clip(lower=0).mean().idxmax()
    title_block(
        fig,
        "Sector rotation, year by year",
        f"Share of months each industry spent in the long leg (blue, +) minus the short leg (red, -) of one-month industry momentum. "
        f"Leadership rotates: no industry is long in most years. {most} spent the most time in the long leg overall. Industry momentum "
        "trades sectors in and out every few months.",
    )
    ax = fig.add_axes((0.15, 0.1, 0.82, 0.62))
    data = net[order].T.to_numpy()
    ax.imshow(data, cmap="RdBu", norm=TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1), aspect="auto")
    for i in range(data.shape[0]):
        for jx in range(data.shape[1]):
            if abs(data[i, jx]) >= 0.25:
                ax.text(
                    jx,
                    i,
                    f"{data[i, jx]:+.1f}",
                    ha="center",
                    va="center",
                    fontsize=6.5,
                    color="white" if abs(data[i, jx]) > 0.6 else PALETTE["ink"],
                )
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(list(order), fontsize=8)
    ax.set_xticks(range(0, len(net.index), 2))
    ax.set_xticklabels([str(y) for y in net.index[::2]], fontsize=8)
    ax.grid(False)
    caption(fig, SURV + " +1: long all year; -1: short all year. Values below 0.25 in size are not printed.")
    return fig


# ------------------------------------------------------------------ 13-16. horizons, states, seasons, costs


def industry_event_time() -> Figure:
    ir = _ind()[0]
    e1 = M.event_time(ir, M.formation_return(ir, 1, 0), 36, min_stocks=6, count=3)
    e12 = M.event_time(ir, M.formation_return(ir, 11, 1), 36, min_stocks=6, count=3)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Industry signals fade within months",
        f"Cumulative return of the top three minus bottom three industries in each month after formation, cohorts held without rebalancing. "
        f"Formed on last month's return, the spread gains {100 * e1['cumulative'].iloc[0]:.2f}% in the first month and "
        f"{100 * e1['cumulative'].iloc[2]:.2f}% by month 3, then drifts; formed on the 12-1 return it reaches "
        f"{100 * e12['cumulative'].iloc[11]:.1f}% after a year and {100 * e12['cumulative'].iloc[-1]:.1f}% after three.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    for e, label, c in [
        (e1, "formed on last month's industry return", PALETTE["blue"]),
        (e12, "formed on the industry's 12-1 return", PALETTE["violet"]),
    ]:
        ax.plot(e.index, 100 * e["cumulative"], color=c, lw=2, marker="o", ms=3, label=label)
        band = 196 * np.sqrt((e["se"] ** 2).cumsum())
        ax.fill_between(e.index, 100 * e["cumulative"] - band, 100 * e["cumulative"] + band, color=c, alpha=0.1)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    tidy(ax, xlabel="months after formation", ylabel="cumulative spread, %")
    ax.legend(fontsize=8.5)
    caption(
        fig,
        SURV
        + " Bands: +/-1.96 x the square root of the summed monthly variances (an approximation that ignores covariance across months).",
    )
    return fig


def industry_states() -> Figure:
    rows = [
        ("industries, last month", _imom(1, 1, 0).wml.loc[START:]),
        ("industries, 12-1", _imom().wml.loc[START:]),
        ("stocks, 12-1", _std().wml.loc[START:]),
        ("industry-neutral stocks, 12-1", _decomp()["neutral"]),
    ]
    tabs = [(n, M.market_states(s, _market())) for n, s in rows]
    fig = new_figure(14.5, 6.0)
    t0 = tabs[0][1]
    title_block(
        fig,
        "After falling markets, one-month industry momentum does the opposite of stock momentum",
        f"Mean return after 24-month market rises (UP) and falls (DOWN). One-month industry momentum earns {100 * t0.loc['UP', 'mean']:.1f}% "
        f"after UP markets and {100 * t0.loc['DOWN', 'mean']:.1f}% after DOWN ones. Only {int(t0.loc['DOWN', 'months'])} months follow a "
        "falling market since 2001, so every interval is wide.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    x = np.arange(len(tabs))
    for off, st, c in [(-0.18, "UP", PALETTE["blue"]), (0.18, "DOWN", PALETTE["red"])]:
        vals = [100 * t.loc[st, "mean"] for _, t in tabs]
        errs = [
            196 * abs(t.loc[st, "mean"] / t.loc[st, "t_nw"]) if np.isfinite(t.loc[st, "t_nw"]) and t.loc[st, "t_nw"] != 0 else 0
            for _, t in tabs
        ]
        ax.bar(
            x + off,
            vals,
            width=0.34,
            color=c,
            alpha=0.85,
            label="after a rising market" if st == "UP" else "after a falling market",
        )
        ax.errorbar(x + off, vals, yerr=errs, fmt="none", color=PALETTE["ink"], capsize=3, lw=0.9)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels([n for n, _ in tabs], fontsize=8.5)
    tidy(ax, ylabel="% a year (95% NW interval)")
    ax.legend(fontsize=8.5)
    caption(fig, SURV + " Market state from the UK market's sterling total return over the previous 24 months.")
    return fig


def industry_calendar() -> Figure:
    series = [
        ("industries, last month", _imom(1, 1, 0).wml.loc[START:]),
        ("industries, 12-1", _imom().wml.loc[START:]),
        ("industry-neutral stocks", _decomp()["neutral"]),
    ]
    cals = [(n, M.calendar(s)) for n, s in series]
    reg = M.seasonal_regression(_decomp()["neutral"].dropna())
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "April hurts twelve-month momentum, of stocks and of industries alike",
        f"Mean return by calendar month. Industry-neutral stock momentum loses {abs(100 * cals[2][1].loc[4, 'mean']):.1f}% in an average April "
        f"(regression coefficient {100 * reg.coef[2]:.1f} points, t = {reg.tstat[2]:.1f}); one-month industry momentum averages "
        f"{100 * cals[0][1].loc[4, 'mean']:+.1f}% in April and twelve-month industry momentum {100 * cals[1][1].loc[4, 'mean']:+.1f}%. The April "
        "loss follows the twelve-month signal, whether it ranks stocks or industries; the one-month industry signal is spared.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    w = 0.27
    for k, ((n, c), col) in enumerate(zip(cals, [PALETTE["blue"], PALETTE["slate"], PALETTE["violet"]], strict=True)):
        ax.bar(np.arange(1, 13) + (k - 1) * w, 100 * c["mean"], width=w, color=col, label=n)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    tidy(ax, ylabel="mean return, % a month")
    ax.legend(fontsize=8.5)
    caption(fig, SURV + f" {START[:4]}-2026.")
    return fig


def turnover_chart() -> Figure:
    items = [("industries, last month", _imom(1, 1, 0)), ("industries, 12-1", _imom()), ("stocks, 12-1", _std())]
    to = [(n, float(s.turnover.loc[START:].mean())) for n, s in items]
    means = [12 * float(s.wml.loc[START:].mean()) for _, s in items]
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "Industry momentum trades sectors, and trades them often",
        f"Monthly one-sided turnover of the long leg. One-month industry momentum replaces {100 * to[0][1]:.0f}% of its long leg a month, "
        f"twelve-month industry momentum {100 * to[1][1]:.0f}% and twelve-month stock momentum {100 * to[2][1]:.0f}%. At {means[0] * 100:.1f}% "
        f"a year gross, the one-month industry strategy breaks even at a round-trip cost of {100 * means[0] / (24 * to[0][1]):.2f}% - below "
        "UK stamp duty alone, unless implemented with exchange-traded funds, which are exempt from stamp duty.",
    )
    ax = fig.add_axes((0.25, 0.13, 0.7, 0.58))
    ax.barh(range(3)[::-1], [100 * t for _, t in to], color=[PALETTE["blue"], PALETTE["slate"], PALETTE["red"]], height=0.5)
    for i, (_, t) in enumerate(to):
        ax.text(100 * t + 0.5, 2 - i, f"{100 * t:.0f}%", va="center", fontsize=9)
    ax.set_yticks(range(3)[::-1])
    ax.set_yticklabels([n for n, _ in to])
    tidy(ax, xlabel="monthly turnover of the long leg, %")
    caption(
        fig, SURV + " Turnover = half the sum of absolute changes in target weights (stocks equal-weighted within industries)."
    )
    return fig


# ------------------------------------------------------------------ 17-19. within industries, trusts, stability


@lru_cache(maxsize=1)
def _within() -> pd.DataFrame:
    r, g = _returns(), _groups()
    largest = list(g.reindex(r.columns).value_counts().index[:4])
    rows = []
    for name in largest:
        s = I.within(r, g, name).wml.loc[START:].dropna()
        rows.append({"group": name, **M.summary(s)})
    s = I.within(r, g, largest[0], exclude=True).wml.loc[START:].dropna()
    rows.append({"group": f"all except {largest[0].lower()}", **M.summary(s)})
    return pd.DataFrame(rows).set_index("group")


def within_industries() -> Figure:
    w = _within()
    groups_ = w.iloc[:4]
    best = groups_["sharpe"].idxmax()
    rest = groups_.drop(best)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"Momentum within industries: strongest among {best.lower()}",
        f"Stock momentum run separately inside the four largest groups (quintile legs, 12-1). {best} give the highest Sharpe ratio, "
        f"{groups_.loc[best, 'sharpe']:.2f} (t = {groups_.loc[best, 't_nw']:.1f}); the others range from {rest['sharpe'].min():.2f} to "
        f"{rest['sharpe'].max():.2f}. For investment trusts one possible channel is that strong past performance attracts flows and "
        "narrows a trust's discount to net asset value.",
    )
    ax = fig.add_axes((0.25, 0.13, 0.42, 0.58))
    order = w.index[::-1]
    last = w.index[-1]
    ax.barh(
        range(len(order)),
        w.loc[order, "sharpe"],
        color=[PALETTE["slate"] if o == last else PALETTE["blue"] for o in order],
        height=0.55,
    )
    for i, o in enumerate(order):
        ax.text(max(w.loc[o, "sharpe"], 0) + 0.01, i, f"t = {w.loc[o, 't_nw']:.1f}", va="center", fontsize=8.5)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(list(order))
    ax.axvline(0, color=PALETTE["ink"], lw=0.7)
    tidy(ax, title="Sharpe ratio of within-group momentum")
    bx = fig.add_axes((0.75, 0.13, 0.22, 0.58))
    bx.bar(range(len(w)), 100 * w["vol"], color=PALETTE["slate"], width=0.6)
    bx.set_xticks(range(len(w)))
    bx.set_xticklabels([n.split()[0][:9] for n in w.index], rotation=45, fontsize=7.5)
    tidy(bx, title="Volatility, % a year")
    caption(fig, SURV + " Quintile winners minus losers within each group; at least 15 stocks with a signal.")
    return fig


def trusts_chart() -> Figure:
    r, g = _returns(), _groups()
    name = "Investment Trusts" if (g == "Investment Trusts").sum() >= 20 else str(g.value_counts().index[0])
    t = I.within(r, g, name).wml.loc[START:]
    x = I.within(r, g, name, exclude=True).wml.loc[START:]
    reg = I.spanning(t.dropna(), pd.DataFrame({"x": x}).dropna())
    st, sx = M.summary(t.dropna(), _market()), M.summary(x.dropna(), _market())
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Investment-trust momentum is calmer, and partly independent of company momentum",
        f"Momentum among investment trusts against momentum among operating companies. Trusts: {100 * st['mean']:.1f}% a year, volatility "
        f"{100 * st['vol']:.0f}%, worst drawdown {100 * st['max_drawdown']:.0f}%; companies: {100 * sx['mean']:.1f}%, {100 * sx['vol']:.0f}%, "
        f"{100 * sx['max_drawdown']:.0f}%. They correlate {t.corr(x):.2f}, and trust momentum keeps an alpha of {100 * reg.alpha:.1f}% "
        f"(t = {reg.alpha_t:.1f}) over company momentum.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    _shade(ax, labels=False)
    ax.plot((1 + t.fillna(0)).cumprod(), color=PALETTE["teal"], lw=1.8, label="investment trusts")
    ax.plot((1 + x.fillna(0)).cumprod(), color=PALETTE["red"], lw=1.8, label="operating companies")
    ax.set_yscale("log")
    _window(ax, START)
    tidy(ax, title="Growth of one pound", ylabel="log scale")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.69, 0.13, 0.28, 0.58))
    for s, c in [(t, PALETTE["teal"]), (x, PALETTE["red"])]:
        bx.fill_between(s.index, 100 * stats.drawdown_path(s.fillna(0)), 0, color=c, alpha=0.4)
    _window(bx, START)
    tidy(bx, title="Drawdowns", ylabel="% below peak")
    caption(fig, SURV + " Quintile legs within each set; 12-1 signal.")
    return fig


def stability() -> Figure:
    d = _decomp()
    series = [
        ("stock 12-1", d["stock"], PALETTE["red"]),
        ("industry-neutral 12-1", d["neutral"], PALETTE["violet"]),
        ("industries, last month", _imom(1, 1, 0).wml.loc[START:], PALETTE["blue"]),
        ("industries, 12-1", d["industry"], PALETTE["slate"]),
    ]
    roll = {n: s.dropna().rolling(60).apply(lambda v: np.sqrt(12) * v.mean() / v.std(), raw=True) for n, s, _ in series}
    neg = {n: float((r.dropna() < 0).mean()) for n, r in roll.items()}
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "No variant is reliable over every five years",
        f"Five-year rolling Sharpe ratios. Share of windows below zero: stock 12-1 {100 * neg['stock 12-1']:.0f}%, industry-neutral "
        f"{100 * neg['industry-neutral 12-1']:.0f}%, one-month industry {100 * neg['industries, last month']:.0f}%, twelve-month industry "
        f"{100 * neg['industries, 12-1']:.0f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    _shade(ax, labels=False)
    for n, _, c in series:
        ax.plot(roll[n], color=c, lw=1.6, label=n)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    _window(ax, roll["stock 12-1"].dropna().index[0], LAST_COMPLETE)
    tidy(ax, ylabel="Sharpe ratio, trailing 60 months")
    ax.legend(fontsize=8.5, ncol=4, loc="lower left")
    caption(fig, SURV)
    return fig
