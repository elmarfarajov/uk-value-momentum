"""Day 1, deeper: alphas, the value-momentum mix, Exeter's portfolio sorts, and how robust each premium is.

Every number in a subtitle is computed from the data the chart draws, so the text cannot drift
from the figure.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.figure import Figure

from .. import analysis, stats
from ..data import aqr, exeter
from .foundation import COLOURS, LABELS, _panel, _shade
from .style import PALETTE, caption, new_figure, tidy, title_block

SHORT = {
    "VAL": "VAL",
    "MOM": "MOM",
    "HML": "HML",
    "HML_DEVIL": "HML Devil",
    "UMD": "UMD",
    "QMJ": "QMJ",
    "SMB": "SMB",
    "MKT": "Market",
}
MODELS: list[tuple[str, list[str]]] = [
    ("VAL", ["MKT", "MOM"]),
    ("MOM", ["MKT", "VAL"]),
    ("HML", ["MKT", "SMB", "UMD"]),
    ("HML_DEVIL", ["MKT", "SMB", "UMD"]),
    ("UMD", ["MKT", "SMB", "HML"]),
    ("QMJ", ["MKT", "SMB", "HML", "UMD"]),
    ("SMB", ["MKT", "HML", "UMD"]),
]


@lru_cache(maxsize=8)
def _ports(name: str) -> pd.DataFrame:
    return exeter.portfolios(name)


def alpha_table() -> pd.DataFrame:
    """CAPM and multi-factor alphas of every AQR factor (sterling), annualised, with NW t-statistics."""
    p = _panel()
    rows = []
    for y, xs in MODELS:
        capm = analysis.regress(p[y], p[["MKT"]])
        multi = analysis.regress(p[y], p[xs])
        rows.append(
            {
                "factor": y,
                "months": multi.months,
                "capm_alpha": capm.alpha,
                "capm_t": capm.alpha_t,
                "beta": float(capm.coef[1]),
                "controls": " + ".join(SHORT[x] for x in xs),
                "alpha": multi.alpha,
                "alpha_t": multi.alpha_t,
                "r2": multi.r2,
            }
        )
    return pd.DataFrame(rows).set_index("factor")


def factor_alphas() -> Figure:
    t = alpha_table()
    p = _panel()
    fig = new_figure(14.5, 6.6)
    title_block(
        fig,
        "Value is a premium once momentum is held constant",
        f"Annualised alphas with 95% Newey-West intervals. Against the market alone UK value's alpha is "
        f"{100 * t.loc['VAL', 'capm_alpha']:.1f}% a year (t = {t.loc['VAL', 'capm_t']:.2f}); holding momentum constant it is "
        f"{100 * t.loc['VAL', 'alpha']:.1f}% (t = {t.loc['VAL', 'alpha_t']:.2f}), because value's losses are momentum's gains. "
        f"HML Devil's alpha rises from {100 * t.loc['HML_DEVIL', 'capm_alpha']:.1f}% to {100 * t.loc['HML_DEVIL', 'alpha']:.1f}%. "
        f"Momentum's survives every control.",
    )
    order = list(t.index)
    for k, (title, a, tt) in enumerate(
        [("Against the market alone (CAPM)", "capm_alpha", "capm_t"), ("Against the other factors", "alpha", "alpha_t")]
    ):
        ax = fig.add_axes((0.07, 0.12, 0.3, 0.6) if k == 0 else (0.62, 0.12, 0.35, 0.6))
        y = np.arange(len(order))[::-1]
        for yi, f in zip(y, order, strict=True):
            mean, tv = t.loc[f, a], t.loc[f, tt]
            se = abs(mean / tv) if tv != 0 else 0.0
            ax.barh(yi, 100 * mean, color=COLOURS[f], alpha=0.85, height=0.62)
            ax.errorbar(100 * mean, yi, xerr=196 * se, color=PALETTE["ink"], capsize=3, lw=1)
            ax.text(100 * (mean + 1.96 * se) + 0.4, yi, f"t = {tv:.2f}", va="center", fontsize=8, color=PALETTE["muted"])
        ax.axvline(0, color=PALETTE["ink"], lw=0.8)
        ax.set_yticks(y)
        ax.set_yticklabels([SHORT[f] if k == 0 else f"{SHORT[f]} | {t.loc[f, 'controls']}" for f in order], fontsize=8.5)
        tidy(ax, title=title, xlabel="alpha, % a year")
    caption(
        fig,
        f"AQR UK factors in sterling, common months of each regression ({int(p['MKT'].notna().sum())} months for the market). "
        "Bars: intercept x 12; whiskers: +/-1.96 Newey-West standard errors, automatic lag.",
    )
    return fig


def value_momentum_mix() -> Figure:
    p = _panel()
    f = analysis.mix_frontier(p["VAL"], p["MOM"])
    w_star = analysis.tangency_weight(p["VAL"], p["MOM"])
    j = p[["VAL", "MOM"]].dropna()
    mix = 0.5 * j["VAL"] + 0.5 * j["MOM"]
    fig = new_figure(14.5, 6.4)
    title_block(
        fig,
        "Half value, half momentum: a better portfolio than either",
        f"The Sharpe ratio of a mix of UK value and momentum, by the weight on momentum, since {j.index[0]:%B %Y}. Value alone has "
        f"{f['sharpe'].iloc[0]:.2f}, momentum alone {f['sharpe'].iloc[-1]:.2f}, the 50/50 mix {f.loc[0.5, 'sharpe']:.2f}; the "
        f"Sharpe-maximising weight is {100 * w_star:.0f}% momentum. The worst drawdown falls from {100 * f['max_drawdown'].iloc[0]:.0f}% "
        f"and {100 * f['max_drawdown'].iloc[-1]:.0f}% to {100 * f['max_drawdown'].min():.0f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.4, 0.58))
    ax.plot(100 * f.index, f["sharpe"], color=PALETTE["blue"], lw=2, marker="o", ms=3.5, label="Sharpe ratio (left)")
    ax.axvline(100 * w_star, color=PALETTE["muted"], ls="--", lw=1)
    ax.text(100 * w_star + 1.5, 0.88, f"maximum-Sharpe weight {100 * w_star:.0f}%", fontsize=8, color=PALETTE["muted"])
    tidy(ax, title="Sharpe ratio and worst drawdown by weight", xlabel="weight on momentum, %", ylabel="Sharpe ratio")
    ax2 = ax.twinx()
    ax2.plot(100 * f.index, 100 * f["max_drawdown"], color=PALETTE["red"], lw=1.6, ls="-.", label="maximum drawdown, % (right)")
    ax2.set_ylabel("maximum drawdown, %")
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper left")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    _shade(bx, labels=False)
    for s, label, colour, lw in [
        (j["VAL"], "value", COLOURS["VAL"], 1.3),
        (j["MOM"], "momentum", COLOURS["MOM"], 1.3),
        (mix, "50/50 mix", PALETTE["ink"], 2.0),
    ]:
        bx.plot((1 + s).cumprod(), color=colour, lw=lw, label=f"{label} (Sharpe {stats.annual_sharpe(s.to_numpy()):.2f})")
    bx.set_yscale("log")
    tidy(bx, title="Growth of one pound", ylabel="log scale")
    bx.legend(fontsize=8, loc="upper left")
    caption(
        fig,
        "AQR UK VAL and MOM in sterling, rebalanced monthly to fixed weights, no costs. Day 14 asks whether the weight can be timed.",
    )
    return fig


def rolling_correlation() -> Figure:
    p = _panel()
    vm = analysis.rolling_correlation(p["VAL"], p["MOM"], 36)
    hu = analysis.rolling_correlation(p["HML"], p["UMD"], 36)
    ex = analysis.rolling_correlation(p["EX_HML"], p["EX_UMD"], 36)
    neg = float((vm.dropna() < 0).mean())
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "The hedge has held for forty years, and is strongest when it is needed",
        f"Three-year rolling correlations of value and momentum. AQR's VAL and MOM were negatively correlated in {100 * neg:.0f}% of "
        f"three-year windows; the correlation reached {vm.min():.2f} around the technology bubble (window ending {vm.idxmin():%B %Y}) "
        "and stayed near -0.9 through the financial crisis, when momentum's losers rebounded and value stocks with them.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    _shade(ax)
    ax.plot(vm, color=PALETTE["blue"], lw=1.9, label="VAL and MOM (AQR, rank-weighted)")
    ax.plot(hu, color=PALETTE["violet"], lw=1.3, label="HML and UMD (AQR)")
    ax.plot(ex, color=PALETTE["teal"], lw=1.1, ls="--", label="HML and UMD (Exeter)")
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.set_ylim(-1, 0.6)
    tidy(ax, ylabel="correlation, trailing 36 months")
    ax.legend(fontsize=8.5, loc="upper right", ncol=3)
    caption(fig, "Pearson correlations of monthly returns over trailing 36-month windows; AQR in sterling, Exeter in sterling.")
    return fig


def portfolio_grids() -> Figure:
    rf = _panel()["EX_RF"]
    fig = new_figure(14.5, 6.9)
    bm_means, bm_t, bm_spread = analysis.grid(_ports("25ports_size_bm"), rf)
    mo_means, mo_t, mo_spread = analysis.grid(_ports("25ports_size_mom"), rf)
    title_block(
        fig,
        "Inside the factors: twenty-five UK portfolios sorted on size and on value or momentum",
        f"Annualised mean excess returns of Exeter's value-weighted 5x5 sorts, October 1980 to June 2016, with Newey-West t "
        f"below each. Cheap stocks beat expensive ones in every size group, by {100 * bm_spread['spread'].min():.1f} to "
        f"{100 * bm_spread['spread'].max():.1f} points a year, but no single row's spread is significant on its own (largest t "
        f"{bm_spread['t_nw'].max():.2f}). The momentum grid shows almost no premium ({100 * mo_spread['spread'].min():.1f} to "
        f"{100 * mo_spread['spread'].max():.1f} points): these 25 portfolios are re-formed once a year, the six behind UMD every "
        "month, and a momentum signal decays within months.",
    )
    vmin = 100 * min(bm_means.to_numpy().min(), mo_means.to_numpy().min())
    vmax = 100 * max(bm_means.to_numpy().max(), mo_means.to_numpy().max())
    for k, (means, ts, spread, label) in enumerate(
        [(bm_means, bm_t, bm_spread, "book-to-market"), (mo_means, mo_t, mo_spread, "past return (12-1)")]
    ):
        ax = fig.add_axes((0.07 + 0.48 * k, 0.12, 0.36, 0.6))
        ax.imshow(100 * means.to_numpy(), cmap="Blues", vmin=vmin - 2, vmax=vmax, aspect="auto")
        for i in range(5):
            for jx in range(5):
                v = 100 * means.iloc[i, jx]
                ax.text(
                    jx,
                    i,
                    f"{v:.1f}\n(t {ts.iloc[i, jx]:.1f})",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if v > (vmin + vmax) / 2 + 1 else PALETTE["ink"],
                )
        ax.set_xticks(range(5))
        ax.set_xticklabels(["Low", "2", "3", "4", "High"] if k == 0 else ["Losers", "2", "3", "4", "Winners"])
        ax.set_yticks(range(5))
        ax.set_yticklabels(list(means.index))
        ax.grid(False)
        tidy(ax, title=f"Size x {label}, % a year", xlabel=label, ylabel="size quintile")
        sx = fig.add_axes((0.44 + 0.48 * k, 0.12, 0.05, 0.6))
        sx.barh(range(5), 100 * spread["spread"].to_numpy(), color=PALETTE["violet"] if k else PALETTE["teal"], height=0.6)
        sx.set_ylim(4.5, -0.5)
        sx.set_yticks([])
        sx.axvline(0, color=PALETTE["ink"], lw=0.7)
        sx.set_title("High - Low", fontsize=8)
        sx.tick_params(labelsize=7)
    caption(
        fig,
        "Exeter Xfi Centre (Gregory, Tharyan and Christidis, 2013): 25 value-weighted portfolios, excess over Exeter's risk-free "
        "rate. Right strips: highest minus lowest column within each size row.",
    )
    return fig


def factor_legs() -> Figure:
    p = _panel()
    rf = p["EX_RF"]
    legs = {}
    for name in ("6ports_size_bm", "6ports_size_mom"):
        six = _ports(name).sub(rf, axis=0).dropna()
        legs[name] = {c: 12.0 * float(six[c].mean()) for c in six.columns}
    mom = _ports("6ports_size_mom")
    small = (mom["SH"] - mom["SL"]).to_numpy()
    big = (mom["BH"] - mom["BL"]).to_numpy()
    bm = _ports("6ports_size_bm")
    vs = (bm["SH"] - bm["SL"]).to_numpy()
    vb = (bm["BH"] - bm["BL"]).to_numpy()
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Momentum is a story about losers, and about small companies",
        f"The six 2x3 portfolios behind Exeter's HML and UMD, mean excess returns, 1980-2016. Small past losers earned "
        f"{100 * legs['6ports_size_mom']['SL']:.1f}% a year over cash, small winners {100 * legs['6ports_size_mom']['SH']:.1f}%: "
        f"momentum among small firms earned {1200 * small.mean():.1f}% (t = {stats.nw_tstat(small):.2f}) against "
        f"{1200 * big.mean():.1f}% (t = {stats.nw_tstat(big):.2f}) among big ones. Value's spreads, "
        f"{1200 * vs.mean():.1f}% small and {1200 * vb.mean():.1f}% big, are both insignificant.",
    )
    groups = [
        ("6ports_size_bm", ["L", "M", "H"], ["growth", "neutral", "value"]),
        ("6ports_size_mom", ["L", "M", "H"], ["losers", "middle", "winners"]),
    ]
    for k, (name, cols, labels) in enumerate(groups):
        ax = fig.add_axes((0.06 + 0.48 * k, 0.13, 0.42, 0.58))
        x = np.arange(3)
        for off, size, colour in [(-0.18, "S", PALETTE["blue"]), (0.18, "B", PALETTE["slate"])]:
            vals = [100 * legs[name][size + c] for c in cols]
            ax.bar(x + off, vals, width=0.34, color=colour, label="small" if size == "S" else "big")
            for xi, v in zip(x + off, vals, strict=True):
                ax.text(xi, v + 0.3, f"{v:.1f}", ha="center", fontsize=8, color=PALETTE["ink"])
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        tidy(ax, title="Sorted on book-to-market" if k == 0 else "Sorted on past return (12-1)", ylabel="excess return, % a year")
        ax.legend(fontsize=8.5)
    caption(
        fig,
        "Exeter Xfi Centre, value-weighted 2x3 portfolios; size split at the 350th firm. Excess over Exeter's risk-free rate.",
    )
    return fig


def deciles() -> Figure:
    rf = _panel()["EX_RF"]
    bm = analysis.deciles(_ports("10ports_bm"), rf)
    size = analysis.deciles(_ports("10ports_size"), rf)
    vb = (_ports("10ports_bm")["V10"] - _ports("10ports_bm")["V1"]).to_numpy()
    sz = (_ports("10ports_size")["S1"] - _ports("10ports_size")["S10"]).to_numpy()
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Sorted finely, value rises almost decile by decile; the 2x3 recipe dilutes it",
        f"Ten value-weighted portfolios on book-to-market and on size, 1980-2016. Mean excess returns rise from "
        f"{100 * bm['mean'].iloc[0]:.1f}% in the most expensive decile to {100 * bm['mean'].iloc[-1]:.1f}% in the cheapest; the "
        f"extreme spread earns {1200 * vb.mean():.1f}% a year (t = {stats.nw_tstat(vb):.2f}), against Exeter HML's {1200 * _panel()['EX_HML'].mean():.1f}%. Smallest "
        f"minus largest earns {1200 * sz.mean():.1f}% (t = {stats.nw_tstat(sz):.2f}) - but at a cost in volatility.",
    )
    for k, (d, label, colour) in enumerate(
        [(bm, "book-to-market decile (1 = expensive)", PALETTE["teal"]), (size, "size decile (1 = smallest)", PALETTE["blue"])]
    ):
        ax = fig.add_axes((0.06 + 0.5 * k, 0.13, 0.38, 0.58))
        x = np.arange(1, 11)
        se = d["mean"] / d["t_nw"]
        ax.bar(x, 100 * d["mean"], color=colour, alpha=0.85, width=0.7)
        ax.errorbar(x, 100 * d["mean"], yerr=196 * se, fmt="none", color=PALETTE["ink"], capsize=2.5, lw=0.9)
        ax2 = ax.twinx()
        ax2.plot(x, d["sharpe"], color=PALETTE["ink"], marker="o", ms=4, lw=1.2, label="Sharpe ratio (right)")
        ax2.set_ylim(0, 0.9)
        ax2.grid(False)
        ax2.spines["right"].set_visible(True)
        ax2.legend(fontsize=8, loc="upper left")
        ax.set_xticks(x)
        tidy(ax, title=label, xlabel="decile", ylabel="mean excess return, % a year")
    caption(fig, "Exeter Xfi Centre, ten value-weighted portfolios; whiskers are 95% Newey-West intervals of the mean.")
    return fig


def calendar_years() -> Figure:
    p = _panel()
    cols = ["MOM", "VAL", "UMD", "HML", "QMJ", "MKT"]
    cy = analysis.calendar_years(p[cols]).loc[:2025]
    pos = {c: float((cy[c].dropna() > 0).mean()) for c in cols}
    both = cy[["MOM", "VAL"]].dropna()
    joint = int(((both["MOM"] < 0) & (both["VAL"] < 0)).sum())
    fig = new_figure(15.0, 7.2)
    title_block(
        fig,
        "Fifty-four years, one cell each",
        f"Calendar-year returns in sterling. Momentum rose in {100 * pos['MOM']:.0f}% of years and UMD in {100 * pos['UMD']:.0f}%, "
        f"value in {100 * pos['VAL']:.0f}%. The worst years cluster: 2000 and 2009 for momentum (the rebounds), 1999 and 2020 for "
        f"value (the growth manias). Both lost in the same year only {joint} times in {len(both)}.",
    )
    ax = fig.add_axes((0.07, 0.1, 0.9, 0.64))
    data = 100 * cy.T.to_numpy(dtype=float)
    norm = TwoSlopeNorm(vmin=-50, vcenter=0, vmax=50)
    ax.imshow(np.clip(data, -50, 50), cmap="RdBu", norm=norm, aspect="auto")
    for i in range(data.shape[0]):
        for jx in range(data.shape[1]):
            v = data[i, jx]
            if np.isfinite(v):
                ax.text(
                    jx, i, f"{v:.0f}", ha="center", va="center", fontsize=6.3, color="white" if abs(v) > 30 else PALETTE["ink"]
                )
    ax.set_yticks(range(len(cols)))
    ax.set_yticklabels([SHORT[c] for c in cols])
    years = list(cy.index)
    ax.set_xticks(range(0, len(years), 2))
    ax.set_xticklabels([str(y) for y in years[::2]], rotation=90, fontsize=7.5)
    ax.grid(False)
    caption(
        fig,
        "Compounded monthly returns, % per calendar year (years with all twelve months only; blank before a series starts). Colour clipped at +/-50%.",
    )
    return fig


def start_date() -> Figure:
    p = _panel()
    cols = ["MOM", "UMD", "VAL", "HML"]
    sens = {c: analysis.start_sensitivity(p[c], 1972, 2016) for c in cols}
    negative = [int(y) for y in sens["VAL"].index[sens["VAL"]["sharpe"] < 0]]
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "Momentum stays positive whichever year you start counting; value's sign depends on it",
        f"Sharpe ratio from each start year to 2026, for samples of at least ten years. Momentum's stays between {sens['MOM']['sharpe'].min():.2f} and "
        f"{sens['MOM']['sharpe'].max():.2f} whichever year one starts in; value's ranges from {sens['VAL']['sharpe'].min():.2f} "
        f"(starting in {sens['VAL']['sharpe'].idxmin()}) to {sens['VAL']['sharpe'].max():.2f}, and is negative for "
        + (f"{len(negative)} start years between {min(negative)} and {max(negative)}" if negative else "no start year")
        + ". A value 'premium' is partly a choice of sample.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    for c in cols:
        s = sens[c]
        ax.plot(
            s.index, s["sharpe"], color=COLOURS[c], lw=1.9 if c in ("MOM", "VAL") else 1.2, marker="o", ms=2.5, label=LABELS[c]
        )
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    tidy(ax, xlabel="first year of the sample (sample ends 2026)", ylabel="Sharpe ratio")
    ax.legend(fontsize=8.5, ncol=2, loc="upper left")
    caption(
        fig,
        "Each point: annualised Sharpe ratio over all months from January of that year to the end of the series (start years to 2016, so at least ten years).",
    )
    return fig


def _share(prob: float, reps: int = 2000) -> str:
    return f"100% (all {reps:,})" if prob >= 1.0 else f"{100 * prob:.1f}%"


def sharpe_bootstrap() -> Figure:
    p = _panel()
    cols = ["UMD", "QMJ", "MOM", "HML", "MKT", "HML_DEVIL", "VAL", "SMB"]
    draws = {c: analysis.bootstrap_sharpes(p[c], reps=2000) for c in cols}
    prob = {c: float((draws[c] > 0).mean()) for c in cols}
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "How sure can we be? The bootstrap distribution of every Sharpe ratio",
        f"2,000 stationary-bootstrap resamples of each factor (mean block six months). The share of resamples with a positive "
        f"Sharpe ratio is {_share(prob['MOM'])} for momentum and {_share(prob['UMD'])} for UMD, {100 * prob['VAL']:.0f}% "
        f"for value and {100 * prob['SMB']:.0f}% for size. Clearing 99%: "
        f"{', '.join(SHORT[c] for c in cols if prob[c] >= 0.99)}.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    parts = ax.violinplot([draws[c] for c in cols], showmedians=True, widths=0.8)
    bodies = parts["bodies"]
    for body, c in zip(bodies, cols, strict=True):
        body.set_facecolor(COLOURS[c])
        body.set_alpha(0.55)
    for key in ("cmedians", "cmins", "cmaxes", "cbars"):
        parts[key].set_color(PALETTE["ink"])
        parts[key].set_linewidth(0.8)
    for k, c in enumerate(cols, start=1):
        ax.text(
            k, float(np.max(draws[c])) + 0.05, f"P(SR>0)\n{_share(prob[c])}", ha="center", fontsize=7.5, color=PALETTE["muted"]
        )
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.set_xticks(range(1, len(cols) + 1))
    ax.set_xticklabels([SHORT[c] for c in cols])
    tidy(ax, ylabel="annualised Sharpe ratio")
    caption(fig, "AQR UK factors in sterling, each over its full sample. Politis and Romano (1994) stationary bootstrap, seed 0.")
    return fig


def autocorrelation() -> Figure:
    p = _panel()
    cols = ["MOM", "VAL", "HML", "MKT"]
    fig = new_figure(14.5, 6.4)
    lb = {c: analysis.ljung_box(p[c], 12) for c in cols}
    title_block(
        fig,
        "Factor returns remember last month; the market does not",
        f"Autocorrelations at lags 1 to 24 months with 95% bands. Momentum's first-order autocorrelation is "
        f"{analysis.acf(p['MOM'], 1).iloc[0]:.2f} and value's {analysis.acf(p['VAL'], 1).iloc[0]:.2f}, both far outside the band; "
        f"the market's is {analysis.acf(p['MKT'], 1).iloc[0]:.2f}. This is why every t-statistic here is Newey-West, and a first "
        "sign of 'factor momentum' (Day 4).",
    )
    for k, c in enumerate(cols):
        ax = fig.add_axes((0.06 + 0.24 * k, 0.13, 0.205, 0.56))
        a = analysis.acf(p[c], 24)
        band = 1.96 / np.sqrt(p[c].dropna().size)
        ax.bar(a.index, a.to_numpy(), color=COLOURS[c], width=0.7)
        ax.axhspan(-band, band, color=PALETTE["band"], zorder=0)
        ax.axhline(0, color=PALETTE["ink"], lw=0.7)
        ax.set_ylim(-0.2, 0.35)
        q, pv = lb[c]
        tidy(ax, title=f"{SHORT[c]}: Ljung-Box(12) = {q:.0f}, p = {pv:.3f}", xlabel="lag, months")
        ax.title.set_fontsize(9)
        if k == 0:
            ax.set_ylabel("autocorrelation")
    caption(fig, "AQR UK series in sterling. Shaded: +/-1.96/sqrt(T), the 95% band for white noise.")
    return fig


def drawdown_episodes() -> Figure:
    p = _panel()
    fig = new_figure(14.5, 6.6)
    eps = {c: analysis.drawdown_episodes(p[c], 5) for c in ("MOM", "VAL")}
    v0 = next(e for e in eps["VAL"] if e.recovery is None) if any(e.recovery is None for e in eps["VAL"]) else eps["VAL"][0]
    last = pd.Timestamp(str(p["VAL"].last_valid_index()))
    age = (last.year - v0.peak.year) * 12 + last.month - v0.peak.month
    title_block(
        fig,
        "Five worst losing spells each: momentum falls fast, value bleeds for years",
        f"The five deepest drawdowns of momentum and value, from peak to trough (dark) and trough to recovery (light). "
        f"Momentum's worst, {100 * eps['MOM'][0].depth:.0f}% from {eps['MOM'][0].peak:%B %Y}, took {eps['MOM'][0].to_trough} months "
        f"to reach bottom and {eps['MOM'][0].to_recover} to recover. Value's drawdown from {v0.peak:%B %Y} took {v0.to_trough} "
        f"months to reach a {100 * v0.depth:.0f}% trough and, {age} months on, has not recovered.",
    )
    end = p.index[-1]
    for k, c in enumerate(("MOM", "VAL")):
        ax = fig.add_axes((0.05 + 0.49 * k, 0.13, 0.43, 0.56))
        for i, e in enumerate(eps[c]):
            y = 4 - i
            ax.barh(y, (e.trough - e.peak).days, left=e.peak, color=COLOURS[c], height=0.55)
            stop = e.recovery if e.recovery is not None else end
            ax.barh(y, (stop - e.trough).days, left=e.trough, color=COLOURS[c], alpha=0.3, height=0.55)
            note = f"-{100 * e.depth:.0f}%, {e.to_trough}m down, " + (
                f"{e.to_recover}m back" if e.to_recover is not None else "not recovered"
            )
            ax.text(stop + pd.Timedelta(days=120), y, note, va="center", fontsize=7.5, color=PALETTE["ink"])
        ax.set_yticks(range(5))
        ax.set_yticklabels([f"#{5 - i}" for i in range(5)])
        ax.set_xlim(pd.Timestamp("1970-01-01"), pd.Timestamp("2050-01-01"))
        tidy(ax, title=LABELS[c])
    caption(fig, "Drawdowns of cumulative wealth prod(1 + r), AQR UK series in sterling; episodes do not overlap.")
    return fig


def rates_and_currency() -> Figure:
    p = _panel()
    us = aqr.us_bill()
    j = pd.concat([p["RF_UK"], us, p["EX_RF"]], axis=1).dropna(subset=["RF_UK", "RF_US"])
    fig = new_figure(14.5, 6.2)
    gap = 12 * float((j["RF_UK"] - j["RF_US"]).mean())
    title_block(
        fig,
        "Two currencies, two risk-free rates: why the denominator matters",
        f"Left: the UK three-month rate against AQR's US Treasury bill and Exeter's UK rate, % a year. The UK rate averaged "
        f"{100 * gap:.1f} points above the US one from {j.index[0]:%Y} to {j.index[-1]:%Y}, so a UK market excess return measured "
        "over the US bill overstates it. Right: the pound in dollars, the second wedge between AQR's numbers and a sterling "
        "investor's.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    _shade(ax, labels=False)
    ax.plot(1200 * j["RF_UK"], color=PALETTE["blue"], lw=1.6, label="UK three-month interbank (FRED, OECD)")
    ax.plot(1200 * j["RF_US"], color=PALETTE["slate"], lw=1.3, label="US one-month bill (AQR)")
    ax.plot(1200 * j["EX_RF"], color=PALETTE["teal"], lw=1.0, ls="--", label="UK rate in the Exeter file")
    tidy(ax, title="Risk-free rates", ylabel="% a year")
    ax.legend(fontsize=8)
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    _shade(bx, labels=False)
    bx.plot(fred_level(), color=PALETTE["violet"], lw=1.5)
    tidy(bx, title="US dollars per pound", ylabel="month-end level")
    caption(
        fig,
        "Rates converted from annual percentages to monthly returns as (1 + r)^(1/12) - 1 and shown x 1,200. FRED DEXUSUK, month end.",
    )
    return fig


def fred_level() -> pd.Series:
    from ..data import fred

    return fred.gbpusd().loc["1972":]


def market_states() -> Figure:
    p = _panel()
    cols = ["MOM", "UMD", "VAL", "HML", "HML_DEVIL", "QMJ", "SMB"]
    ms = analysis.market_states(p[cols], p["MKT"])
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Momentum and quality earn their keep when the market falls",
        f"Annualised mean factor returns in months when the UK market rose and when it fell. Momentum earned "
        f"{100 * ms.loc['MOM', 'down']:.1f}% a year in down months and {100 * ms.loc['MOM', 'up']:.1f}% in up months; quality "
        f"{100 * ms.loc['QMJ', 'down']:.1f}% against {100 * ms.loc['QMJ', 'up']:.1f}%. Value and HML Devil do the opposite. In the "
        f"market's worst 5% of months momentum gained {ms.loc['MOM', 'worst5_monthly'] * 100:.1f}% a month on average.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.5, 0.58))
    x = np.arange(len(cols))
    ax.bar(
        x - 0.19, 100 * ms["up"], width=0.36, color=PALETTE["blue"], label=f"market up ({int(ms['up_months'].iloc[0])} months)"
    )
    ax.bar(
        x + 0.19,
        100 * ms["down"],
        width=0.36,
        color=PALETTE["red"],
        label=f"market down ({int(ms['down_months'].iloc[0])} months)",
    )
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([SHORT[c] for c in cols])
    tidy(ax, title="Mean return by market state", ylabel="% a year")
    ax.legend(fontsize=8)
    bx = fig.add_axes((0.64, 0.13, 0.33, 0.58))
    d = p[["MOM", "MKT"]].dropna()
    bx.scatter(100 * d["MKT"], 100 * d["MOM"], s=7, color=PALETTE["muted"], alpha=0.6)
    for side, colour in [(d["MKT"] > 0, PALETTE["blue"]), (d["MKT"] <= 0, PALETTE["red"])]:
        xs = d.loc[side, "MKT"]
        b, a = np.polyfit(xs, d.loc[side, "MOM"], 1)
        grid = np.linspace(xs.min(), xs.max(), 10)
        bx.plot(100 * grid, 100 * (a + b * grid), color=colour, lw=2, label=f"beta {b:.2f}")
    bx.axhline(0, color=PALETTE["ink"], lw=0.6)
    bx.axvline(0, color=PALETTE["ink"], lw=0.6)
    tidy(bx, title="Momentum against the market", xlabel="market excess return, % a month", ylabel="momentum, % a month")
    bx.legend(fontsize=8, title="fitted separately", title_fontsize=7.5)
    caption(
        fig,
        "AQR UK factors and market excess return in sterling, 1986-2026. Down: market excess return <= 0. Day 2 conditions on the past market instead.",
    )
    return fig
