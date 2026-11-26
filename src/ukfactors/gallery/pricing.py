"""Day 8 charts: risk or mispricing?

Exeter's 25 size-book-to-market and six size-momentum portfolios and its factors (October 1980 to
June 2016, sterling); AQR UK factors (VAL from 1981, MOM from 1972, in sterling); FRED's three-month rate,
ten-year gilt yield and sterling. Every number in a subtitle is computed.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from .. import pricing as P
from ..data import exeter, fred
from .foundation import _panel
from .style import PALETTE, caption, new_figure, tidy, title_block

SRC = "Exeter UK portfolios and factors (Gregory, Tharyan and Christidis 2013), value-weighted, October 1980 to June 2016."
MODELS = {"CAPM": ["RMRF"], "FF3": ["RMRF", "SMB", "HML"], "C4": ["RMRF", "SMB", "HML", "UMD"]}
COL = {"CAPM": PALETTE["slate"], "FF3": PALETTE["blue"], "C4": PALETTE["green"]}
FCOL = {
    "RMRF": PALETTE["slate"],
    "SMB": PALETTE["teal"],
    "HML": PALETTE["blue"],
    "UMD": PALETTE["violet"],
    "QMJ": PALETTE["green"],
}
PUBLISHED = "1993-12"


@lru_cache(maxsize=1)
def _data() -> dict[str, pd.DataFrame]:
    f = exeter.factors()
    rf = f["RF"]
    bm = exeter.portfolios("25ports_size_bm").sub(rf, axis=0)
    m6 = exeter.portfolios("6ports_size_mom").sub(rf, axis=0)
    m25 = exeter.portfolios("25ports_size_mom").sub(rf, axis=0)
    both = pd.concat([bm.add_prefix("BM "), m6.add_prefix("MOM ")], axis=1)
    return {"f": f, "bm": bm, "m6": m6, "m25": m25, "both": both}


@lru_cache(maxsize=1)
def _macro() -> pd.DataFrame:
    return P.macro(fred.uk_rate(), fred.gilt_yield(), fred.gbpusd())


SETS = {"bm": "25 size-B/M", "m6": "6 size-momentum", "both": "31 together", "m25": "25 size-momentum (annual sort)"}


# ------------------------------------------------------------------ 1-3. time-series tests


def grs() -> Figure:
    d = _data()
    res = {(s, m): P.grs(d[s], d["f"][c]) for s in SETS for m, c in MODELS.items()}
    fig = new_figure(14.5, 6.0)
    b = res[("both", "C4")]
    title_block(
        fig,
        "No model prices UK size, value and momentum portfolios together; four factors come closest",
        f"Gibbons-Ross-Shanken statistic by test set and model (bars), with the 5% critical value (ticks). On the 31 portfolios together: CAPM "
        f"{res[('both', 'CAPM')].stat:.1f}, FF3 {res[('both', 'FF3')].stat:.1f}, C4 {b.stat:.1f} (p = {b.p:.3f}). The 25 size-B/M portfolios reject none of the "
        f"models (CAPM p = {res[('bm', 'CAPM')].p:.2f}): UK value is too weak in this sample to trouble even the CAPM.",
    )
    ax = fig.add_axes((0.06, 0.15, 0.9, 0.56))
    x = np.arange(len(SETS))
    from scipy.stats import f as fdist

    for j, m in enumerate(MODELS):
        vals = [res[(s, m)].stat for s in SETS]
        ax.bar(x + (j - 1) * 0.26, vals, 0.24, color=COL[m], label=m)
        for i, s in enumerate(SETS):
            g = res[(s, m)]
            n = d[s].shape[1]
            crit = fdist.ppf(0.95, n, g.months - n - len(MODELS[m]))
            ax.plot([x[i] + (j - 1) * 0.26 - 0.12, x[i] + (j - 1) * 0.26 + 0.12], [crit, crit], color=PALETTE["red"], lw=1.4)
            ax.text(
                x[i] + (j - 1) * 0.26, vals[i], f"p={g.p:.2f}" if g.p >= 0.005 else "p<.01", ha="center", va="bottom", fontsize=7
            )
    ax.set_xticks(x, list(SETS.values()))
    ax.legend(frameon=False, loc="upper right")
    tidy(ax, ylabel="GRS statistic")
    caption(fig, SRC + " Excess returns over Exeter's risk-free rate; red ticks: 5% critical value of F(N, T - N - K).")
    return fig


def alphas_bm() -> Figure:
    d = _data()
    fig = new_figure(14.5, 6.2)
    a = {m: 12 * P.grs(d["bm"], d["f"][MODELS[m]]).alphas.to_numpy().reshape(5, 5) for m in ("CAPM", "FF3")}
    title_block(
        fig,
        "CAPM alphas rise from growth to value within each size group; three factors flatten most of the pattern",
        f"Annualised alpha of each of the 25 size-book-to-market portfolios, %. Value minus growth corner (small): CAPM {100 * (a['CAPM'][0, 4] - a['CAPM'][0, 0]):+.1f} points, "
        f"FF3 {100 * (a['FF3'][0, 4] - a['FF3'][0, 0]):+.1f}. Mean absolute alpha: CAPM {100 * np.abs(a['CAPM']).mean():.1f}%, FF3 {100 * np.abs(a['FF3']).mean():.1f}%.",
    )
    lim = 100 * max(np.abs(a["CAPM"]).max(), np.abs(a["FF3"]).max())
    for k, m in enumerate(("CAPM", "FF3")):
        ax = fig.add_axes((0.06 + 0.47 * k, 0.13, 0.38, 0.58))
        im = ax.imshow(100 * a[m], cmap="RdBu", vmin=-lim, vmax=lim)
        for i in range(5):
            for j in range(5):
                ax.text(j, i, f"{100 * a[m][i, j]:.1f}", ha="center", va="center", fontsize=8)
        ax.set_xticks(range(5), ["growth", "2", "3", "4", "value"])
        ax.set_yticks(range(5), ["small", "2", "3", "4", "big"])
        ax.grid(False)
        tidy(ax, title=m)
    fig.colorbar(im, ax=fig.axes, shrink=0.6, label="alpha, % a year")
    caption(fig, SRC)
    return fig


def alphas_mom() -> Figure:
    d = _data()
    a = {m: 12 * P.grs(d["m6"], d["f"][c]).alphas for m, c in MODELS.items()}
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"Only a momentum factor removes most of the momentum portfolios' alphas; small winners keep {100 * a['C4']['SH']:.0f}% a year",
        f"Annualised alpha of Exeter's six size-momentum portfolios. Small winners: CAPM {100 * a['CAPM']['SH']:+.1f}%, FF3 {100 * a['FF3']['SH']:+.1f}%, C4 "
        f"{100 * a['C4']['SH']:+.1f}%. Small losers: {100 * a['CAPM']['SL']:+.1f}%, {100 * a['FF3']['SL']:+.1f}%, {100 * a['C4']['SL']:+.1f}%. Adding value makes "
        "the losers' alphas more negative: losers tend to be cheap, so the value factor credits them with a premium they do not earn.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    names = list(d["m6"].columns)
    x = np.arange(len(names))
    for j, m in enumerate(MODELS):
        ax.bar(x + (j - 1) * 0.26, 100 * a[m].to_numpy(), 0.24, color=COL[m], label=m)
    labels = {
        "SL": "small losers",
        "SM": "small middle",
        "SH": "small winners",
        "BL": "big losers",
        "BM": "big middle",
        "BH": "big winners",
    }
    ax.set_xticks(x, [labels.get(n, n) for n in names])
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="alpha, % a year")
    caption(fig, SRC + " Six portfolios: two size groups by three prior-return (months t-12 to t-2) groups, rebalanced monthly.")
    return fig


# ------------------------------------------------------------------ 4-5. cross-section


def fit() -> Figure:
    d = _data()
    fms = {m: P.fama_macbeth(d["both"], d["f"][c]) for m, c in MODELS.items()}
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "In the cross-section, momentum's beta explains average returns; market beta does not",
        "Average excess return of the 31 portfolios against the Fama-MacBeth fitted value. Cross-sectional R-squared: "
        + ", ".join(f"{m} {fms[m].r2:.2f}" for m in MODELS)
        + ". Under the CAPM the fitted values hardly vary: market betas are all close to one.",
    )
    for k, m in enumerate(MODELS):
        ax = fig.add_axes((0.05 + 0.32 * k, 0.13, 0.27, 0.58))
        fm = fms[m]
        is_mom = fm.realised.index.str.startswith("MOM")
        ax.scatter(1200 * fm.fitted[~is_mom], 1200 * fm.realised[~is_mom], s=18, color=PALETTE["blue"], label="size-B/M")
        ax.scatter(
            1200 * fm.fitted[is_mom], 1200 * fm.realised[is_mom], s=26, marker="s", color=PALETTE["violet"], label="size-momentum"
        )
        lo, hi = 1200 * min(fm.fitted.min(), fm.realised.min()), 1200 * max(fm.fitted.max(), fm.realised.max())
        ax.plot([lo, hi], [lo, hi], color=PALETTE["muted"], lw=0.8, ls="--")
        if k == 0:
            ax.legend(frameon=False, loc="upper left", fontsize=8)
        tidy(ax, title=f"{m} (R² {fm.r2:.2f})", xlabel="fitted, % a year", ylabel="realised, % a year")
    caption(fig, SRC + " Betas from full-sample time-series regressions; a constant in the cross-sectional regressions.")
    return fig


def lambdas() -> Figure:
    d = _data()
    c = MODELS["C4"]
    fm = P.fama_macbeth(d["both"], d["f"][c])
    mean = 12 * d["f"][c].loc[d["both"].dropna().index].mean()
    fig = new_figure(14.5, 6.0)
    t = fm.t_shanken
    title_block(
        fig,
        "Momentum carries a priced premium close to its own mean; the market's premium is not identified",
        f"Fama-MacBeth prices of risk, four-factor model, 31 portfolios, with Shanken-corrected 95% intervals, against each factor's average return. UMD: lambda "
        f"{100 * 12 * fm.lambdas['UMD']:.1f}% (t = {t['UMD']:.1f}) against a mean of {100 * mean['UMD']:.1f}%. HML: {100 * 12 * fm.lambdas['HML']:.1f}% (t = {t['HML']:.1f}). "
        f"The intercept is {100 * 12 * fm.lambdas['const']:.1f}% a year (t = {t['const']:.1f}): a zero-beta rate far above the bill rate.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    names = ["const", *c]
    x = np.arange(len(names))
    lam = 1200 * fm.lambdas[names].to_numpy()
    err = 1200 * 1.96 * fm.se_shanken[names].to_numpy()
    ax.bar(
        x - 0.18,
        lam,
        0.34,
        yerr=err,
        color=PALETTE["blue"],
        capsize=3,
        ecolor=PALETTE["muted"],
        label="Fama-MacBeth price of risk",
    )
    ax.bar(
        x[1:] + 0.18,
        100 * mean.to_numpy(),
        0.34,
        color=PALETTE["band"],
        edgecolor=PALETTE["muted"],
        label="factor's average return",
    )
    ax.set_xticks(x, ["intercept", *c])
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="% a year")
    caption(
        fig, SRC + " For a traded factor that prices the assets, lambda should equal the factor's mean and the intercept zero."
    )
    return fig


# ------------------------------------------------------------------ 6-7. macro risk


def macro() -> Figure:
    d = _data()
    m = _macro()
    p = _panel()
    series = {"RMRF": d["f"]["RMRF"], "SMB": d["f"]["SMB"], "HML": d["f"]["HML"], "UMD": d["f"]["UMD"], "QMJ": p["QMJ"].dropna()}
    reg = {k: P.exposures(v, m) for k, v in series.items()}
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Macro news moves the market, not value or momentum",
        "Monthly factor returns on the change in the three-month rate, the change in the term spread (per percentage point) and sterling's return (per 1%), with "
        "Newey-West 95% intervals. R-squared: "
        + ", ".join(f"{k} {r.r2:.3f}" for k, r in reg.items())
        + ". A risk story for UMD would need large, "
        "significant exposures; it has none.",
    )
    names = list(m.columns)
    titles = {"D_SHORT": "three-month rate, +1 point", "D_TERM": "term spread, +1 point", "GBP": "sterling, +1%"}
    for i, n in enumerate(names):
        ax = fig.add_axes((0.06 + 0.32 * i, 0.13, 0.27, 0.58))
        ks = list(series)
        coef = [100 * reg[k].coef[reg[k].names.index(n)] for k in ks]
        se = [100 * 1.96 * reg[k].se[reg[k].names.index(n)] for k in ks]
        ax.bar(ks, coef, yerr=se, color=[FCOL[k] for k in ks], capsize=3, ecolor=PALETTE["muted"])
        ax.axhline(0, color=PALETTE["ink"], lw=0.8)
        tidy(ax, title=titles[n], ylabel="factor return, % a month" if i == 0 else None)
    caption(fig, SRC + " Rates and the gilt yield from FRED (OECD monthly averages); QMJ from AQR, 1993 onwards.")
    return fig


def macro_fm() -> Figure:
    d = _data()
    m = _macro()
    mac = P.fama_macbeth(d["both"], pd.concat([d["f"][["RMRF"]], m], axis=1))
    c4 = P.fama_macbeth(d["both"], d["f"][MODELS["C4"]])
    fig = new_figure(14.5, 6.0)
    t = mac.t_shanken
    title_block(
        fig,
        f"Macro betas fit {100 * mac.r2:.0f}% of the cross-section, but only with a zero-beta rate of {100 * 12 * mac.lambdas['const']:.0f}% a year",
        f"Fama-MacBeth with betas on the market and three macro innovations, 31 portfolios. Shanken t-statistics: three-month rate {t['D_SHORT']:.1f}, term spread "
        f"{t['D_TERM']:.1f}, sterling {t['GBP']:.1f}; intercept {100 * 12 * mac.lambdas['const']:.1f}% a year (t = {t['const']:.1f}). Cross-sectional R-squared "
        f"{mac.r2:.2f}, against {c4.r2:.2f} for the four-factor model. An intercept that large means the betas do not explain the level of returns, only part of their spread.",
    )
    a1 = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    a2 = fig.add_axes((0.55, 0.13, 0.42, 0.58))
    names = list(mac.lambdas.index)
    a1.bar(names, t.to_numpy(), color=[PALETTE["slate"] if abs(v) < 1.96 else PALETTE["blue"] for v in t.to_numpy()])
    a1.axhline(1.96, color=PALETTE["red"], lw=0.8, ls="--")
    a1.axhline(-1.96, color=PALETTE["red"], lw=0.8, ls="--")
    a1.axhline(0, color=PALETTE["ink"], lw=0.6)
    tidy(a1, title="Shanken t-statistics, macro model", ylabel="t")
    is_mom = mac.realised.index.str.startswith("MOM")
    a2.scatter(1200 * mac.fitted[~is_mom], 1200 * mac.realised[~is_mom], s=18, color=PALETTE["blue"], label="size-B/M")
    a2.scatter(
        1200 * mac.fitted[is_mom], 1200 * mac.realised[is_mom], s=26, marker="s", color=PALETTE["violet"], label="size-momentum"
    )
    lo, hi = 1200 * min(mac.fitted.min(), mac.realised.min()), 1200 * max(mac.fitted.max(), mac.realised.max())
    a2.plot([lo, hi], [lo, hi], color=PALETTE["muted"], lw=0.8, ls="--")
    a2.legend(frameon=False, loc="upper left", fontsize=8)
    tidy(a2, title=f"Fitted against realised (R² {mac.r2:.2f})", xlabel="fitted, % a year", ylabel="realised, % a year")
    caption(fig, SRC + " Macro innovations: monthly changes, FRED.")
    return fig


# ------------------------------------------------------------------ 8-10. signs of mispricing


def publication() -> Figure:
    p = _panel()
    f = _data()["f"]
    series = {"AQR VAL": p["VAL"], "AQR MOM": p["MOM"], "Exeter HML": f["HML"], "Exeter UMD": f["UMD"], "Exeter SMB": f["SMB"]}
    r = {k: P.publication(v, PUBLISHED) for k, v in series.items()}
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Value shrank after it was published; momentum did not",
        f"Annualised mean before and after December 1993 (Fama and French 1993, Jegadeesh and Titman 1993). AQR VAL {100 * r['AQR VAL']['before']:.1f}% to "
        f"{100 * r['AQR VAL']['after']:.1f}% (t of the change {r['AQR VAL']['t_change']:.1f}); Exeter HML {100 * r['Exeter HML']['before']:.1f}% to "
        f"{100 * r['Exeter HML']['after']:.1f}% (t {r['Exeter HML']['t_change']:.1f}); AQR MOM {100 * r['AQR MOM']['before']:.1f}% to {100 * r['AQR MOM']['after']:.1f}%; "
        f"Exeter UMD {100 * r['Exeter UMD']['before']:.1f}% to {100 * r['Exeter UMD']['after']:.1f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    x = np.arange(len(series))
    ax.bar(x - 0.18, [100 * r[k]["before"] for k in series], 0.34, color=PALETTE["slate"], label="before 1994")
    ax.bar(x + 0.18, [100 * r[k]["after"] for k in series], 0.34, color=PALETTE["blue"], label="1994 onwards")
    ax.set_xticks(x, [f"{k}\n(t of change {r[k]['t_change']:+.1f})" for k in series])
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="annualised mean, %")
    caption(
        fig,
        "AQR VAL from July 1981, MOM from 1972 (sterling); Exeter from October 1980. The UK papers came later (Liu, Strong and Xu 1999; Gregory et al. 2001), so 1993 is a lower bound on awareness.",
    )
    return fig


def size() -> Figure:
    f6 = {k: exeter.portfolios(n) for k, n in (("momentum", "6ports_size_mom"), ("value", "6ports_size_bm"))}
    sp = {k: P.spread_by_size(v, 3) for k, v in f6.items()}
    from .. import stats as S

    fig = new_figure(14.5, 6.0)
    dm = sp["momentum"]["Q1"] - sp["momentum"]["Q2"]
    dv = sp["value"]["Q1"] - sp["value"]["Q2"]
    title_block(
        fig,
        "Momentum is far stronger among small stocks, where arbitrage is costly; value is not",
        f"High-minus-low return within small and big stocks, % a year, with Newey-West 95% intervals. Momentum: small {100 * 12 * sp['momentum']['Q1'].mean():.1f}%, big "
        f"{100 * 12 * sp['momentum']['Q2'].mean():.1f}% (difference t = {S.nw_tstat(dm.to_numpy()):.1f}). Value: small {100 * 12 * sp['value']['Q1'].mean():.1f}%, big "
        f"{100 * 12 * sp['value']['Q2'].mean():.1f}% (t = {S.nw_tstat(dv.to_numpy()):.1f}). A larger premium where trading is harder points to mispricing.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    x = np.arange(2)
    for j, (k, col) in enumerate((("momentum", PALETTE["violet"]), ("value", PALETTE["blue"]))):
        means = [1200 * sp[k][q].mean() for q in ("Q1", "Q2")]
        errs = [1200 * 1.96 * sp[k][q].mean() / S.nw_tstat(sp[k][q].to_numpy()) for q in ("Q1", "Q2")]
        ax.bar(x + (j - 0.5) * 0.36, means, 0.34, yerr=errs, color=col, capsize=3, ecolor=PALETTE["muted"], label=k)
    ax.set_xticks(x, ["small stocks", "big stocks"])
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="upper right")
    tidy(ax, ylabel="high minus low, % a year")
    caption(fig, SRC + " Six portfolios each: two size groups by three characteristic groups.")
    return fig


def rolling() -> Figure:
    d = _data()
    r = {m: P.rolling_alpha(d["both"], d["f"][c]) for m, c in MODELS.items()}
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "The four-factor model's pricing errors have been smaller than the CAPM's in every ten-year window",
        f"Mean absolute annualised alpha of the 31 portfolios over rolling 120-month regressions. C4 below CAPM in {100 * (r['C4'] < r['CAPM'].reindex(r['C4'].index)).mean():.0f}% "
        f"of windows; last window (to June 2016): CAPM {100 * r['CAPM'].iloc[-1]:.1f}%, FF3 {100 * r['FF3'].iloc[-1]:.1f}%, C4 {100 * r['C4'].iloc[-1]:.1f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    for m in MODELS:
        ax.plot(100 * r[m], color=COL[m], lw=1.8, label=m)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, xlabel="end of the 120-month window", ylabel="mean |alpha|, % a year")
    caption(fig, SRC)
    return fig
