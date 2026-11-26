"""Day 7 charts: momentum crashes and tail risk in the UK.

AQR's UK UMD (from 1987) and VME momentum (MOM, from 1972), HML and the UK market's total return
in sterling, less the UK bill (market excess return); AQR's UMD for every country (dollars). Every
number in a subtitle is computed.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from .. import crashes as C
from .. import momentum as M
from ..data import aqr
from .foundation import _panel, _shade
from .style import PALETTE, caption, new_figure, tidy, title_block

SRC = "AQR UK factors in sterling (ADR 0004); UMD from 1987, MOM from 1972; market = UK total return less the UK bill."
COL = {
    "UMD": PALETTE["blue"],
    "CV": PALETTE["green"],
    "DYN": PALETTE["violet"],
    "MKT": PALETTE["slate"],
    "HML": PALETTE["teal"],
    "MOM": PALETTE["ink"],
}


@lru_cache(maxsize=1)
def _mkt() -> pd.Series:
    p = _panel()
    mt = M.market_total()
    return (mt - p["RF_UK"].reindex(mt.index)).dropna().rename("MKT")


@lru_cache(maxsize=1)
def _umd() -> pd.Series:
    return _panel()["UMD"].dropna().rename("UMD")


@lru_cache(maxsize=1)
def _scaled() -> pd.DataFrame:
    u = _umd()
    dy = C.dynamic(u, _mkt())
    cv = C.constant_vol(u)
    return pd.DataFrame({"UMD": u, "CV": cv, "DYN": dy["return"], "W_DYN": dy["weight"], "W_CV": cv / u}).loc[dy.index]


def _index(s: pd.Series) -> pd.Series:
    return (1 + s.dropna()).cumprod()


def _log_pounds(ax) -> None:  # type: ignore[no-untyped-def]
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter

    lo, hi = ax.get_ylim()
    ticks = [t for t in (0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500) if lo <= t <= hi]
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"£{y:g}"))
    ax.yaxis.set_minor_formatter(NullFormatter())


# ------------------------------------------------------------------ 1-3. when momentum crashes


def worst() -> Figure:
    u, m = _umd(), _mkt()
    b = C.bear(m)
    w = u.nsmallest(12)
    fig = new_figure(14.5, 6.0)
    in_bear = int((b.reindex(w.index) == 1).sum())
    up = int((m.reindex(w.index) > 0).sum())
    title_block(
        fig,
        "UK momentum's worst months came when the market rebounded after a fall",
        f"The 12 worst months of UMD since 1987. {in_bear} came after the market had fallen over the previous two years, and in {up} the market rose. "
        f"The worst, {w.index[0]:%B %Y}, lost {100 * -w.iloc[0]:.0f}% as the market rose {100 * m.get(w.index[0], np.nan):.0f}%; "
        f"{w.index[1]:%B %Y} (vaccine news) lost {100 * -w.iloc[1]:.0f}%.",
    )
    ax = fig.add_axes((0.06, 0.18, 0.9, 0.55))
    x = np.arange(len(w))
    cols = [PALETTE["red"] if b.get(d, 0) == 1 else PALETTE["slate"] for d in w.index]
    ax.bar(x - 0.2, 100 * w.to_numpy(), 0.38, color=cols, label="UMD (red: after a two-year market fall)")
    ax.bar(
        x + 0.2,
        100 * m.reindex(w.index).to_numpy(),
        0.38,
        color=PALETTE["band"],
        edgecolor=PALETTE["muted"],
        label="market excess return",
    )
    ax.set_xticks(x, [f"{d:%b %Y}" for d in w.index], rotation=30, ha="right")
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="upper right")
    tidy(ax, ylabel="return in the month, %")
    caption(fig, SRC + " Bear state: the market's return over the 24 months to the end of the previous month was negative.")
    return fig


def states() -> Figure:
    p = _panel()
    t = {k: C.state_table(p[k].dropna(), _mkt()) for k in ("UMD", "MOM")}
    u = t["UMD"]
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Momentum does well in bear markets on average; it loses when a panic ends with a rally",
        f"Annualised mean of UMD by state. Bull {100 * u.loc['bull', 'mean']:+.0f}%, bear {100 * u.loc['bear', 'mean']:+.0f}%, panic (bear and high market variance) "
        f"{100 * u.loc['panic', 'mean']:+.0f}%, but panic months in which the market rose {100 * u.loc['panic, market up', 'mean']:+.0f}% "
        f"({int(u.loc['panic, market up', 'months'])} months). Skewness in bear months {u.loc['bear', 'skew']:.1f}, in bull months {u.loc['bull', 'skew']:.1f}.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    names = list(u.index)
    x = np.arange(len(names))
    for j, k in enumerate(("UMD", "MOM")):
        ax.bar(
            x + (j - 0.5) * 0.36,
            100 * t[k]["mean"].to_numpy(),
            0.34,
            color=COL[k],
            label={"UMD": "UMD (1987-)", "MOM": "AQR MOM (1980-)"}[k],
        )
    ax.set_xticks(x, [f"{n}\n({int(u.loc[n, 'months'])} months)" for n in names])
    ax.axhline(0, color=PALETTE["ink"], lw=0.8)
    ax.legend(frameon=False, loc="lower left")
    tidy(ax, ylabel="annualised mean, %")
    caption(
        fig,
        SRC
        + " Panic: bear state and the market's six-month variance above its median. MOM's states start when the market series starts (1980).",
    )
    return fig


def optionality() -> Figure:
    u, m = _umd(), _mkt()
    r = C.optionality(u, m)
    b = C.bear(m)
    j = pd.concat([u.rename("u"), m.rename("m"), b], axis=1).dropna()
    fig = new_figure(14.5, 6.2)
    c = dict(zip(r.names, r.coef, strict=True))
    t = dict(zip(r.names, r.tstat, strict=True))
    up_bear = c["Rm"] + c["B_Rm"] + c["B_U_Rm"]
    down_bear = c["Rm"] + c["B_Rm"]
    title_block(
        fig,
        "In bear markets UK momentum is short a call on the market",
        f"Daniel-Moskowitz regression of UMD on the market, {r.months} months. Market beta in bull markets {c['Rm']:.2f}; in bear markets {down_bear:.2f} when the market falls "
        f"and {up_bear:.2f} when it rises (the extra up-market beta {c['B_U_Rm']:.2f}, t = {t['B_U_Rm']:.1f}). Momentum gains little from further falls and loses "
        "heavily in rebounds: the losers it is short are high-beta stocks.",
    )
    for k, (state, lab) in enumerate(((0.0, "Bull markets"), (1.0, "Bear markets"))):
        ax = fig.add_axes((0.06 + 0.49 * k, 0.13, 0.42, 0.58))
        part = j[j["BEAR"] == state]
        ax.scatter(100 * part["m"], 100 * part["u"], s=12, color=PALETTE["red"] if state else PALETTE["slate"], alpha=0.6)
        for side, slope in (("down", c["Rm"] + state * c["B_Rm"]), ("up", c["Rm"] + state * (c["B_Rm"] + c["B_U_Rm"]))):
            xs = np.linspace(part["m"].min(), 0, 20) if side == "down" else np.linspace(0, part["m"].max(), 20)
            ax.plot(100 * xs, 100 * (c["alpha"] + state * c["B"] + slope * xs), color=PALETTE["ink"], lw=1.6)
        ax.axhline(0, color=PALETTE["muted"], lw=0.6)
        ax.axvline(0, color=PALETTE["muted"], lw=0.6)
        tidy(ax, title=f"{lab} ({len(part)} months)", xlabel="market excess return, %", ylabel="UMD, %")
    caption(fig, SRC + " Lines: fitted slopes for falling and rising months; Newey-West errors.")
    return fig


# ------------------------------------------------------------------ 4-6. scaling


def scaled() -> Figure:
    s = _scaled()
    d = {k: C.distribution(s[k]) for k in ("UMD", "CV", "DYN")}
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Holding momentum at constant volatility raised its Sharpe ratio and removed the crashes",
        f"Growth of £1 from {s.index[0]:%B %Y}, the first month of the out-of-sample dynamic strategy. Sharpe ratio: UMD {d['UMD']['sharpe']:.2f}, constant volatility "
        f"{d['CV']['sharpe']:.2f}, dynamic {d['DYN']['sharpe']:.2f}. Worst fall {100 * d['UMD']['maxdd']:.0f}%, {100 * d['CV']['maxdd']:.0f}% and "
        f"{100 * d['DYN']['maxdd']:.0f}%. Volatilities differ: {100 * d['UMD']['vol']:.0f}%, {100 * d['CV']['vol']:.0f}% and {100 * d['DYN']['vol']:.0f}%.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    for k, lab in (
        ("UMD", "UMD"),
        ("CV", "constant volatility (Barroso-Santa-Clara)"),
        ("DYN", "dynamic (Daniel-Moskowitz, out of sample)"),
    ):
        ax.plot(_index(s[k]), color=COL[k], lw=1.8, label=lab)
    ax.set_yscale("log")
    _log_pounds(ax)
    _shade(ax)
    ax.set_xlim(s.index[0], s.index[-1])
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="growth of £1 (log scale)")
    caption(
        fig,
        SRC
        + " Volatility forecast: past six months. The constant-volatility target is UMD's full-sample volatility; it scales the series, not its Sharpe ratio.",
    )
    return fig


def moments() -> Figure:
    s = _scaled()
    keys = ("UMD", "CV", "DYN")
    d = {k: C.distribution(s[k]) for k in keys}
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Constant volatility turned momentum's left skew positive; the dynamic weight has fat tails of its own",
        f"Same months for all three. Skewness: UMD {d['UMD']['skew']:.2f}, constant volatility {d['CV']['skew']:+.2f}, dynamic {d['DYN']['skew']:+.2f}. Excess kurtosis "
        f"{d['UMD']['kurt']:.1f}, {d['CV']['kurt']:.1f} and {d['DYN']['kurt']:.1f}: the dynamic weight is unbounded, so a few months with very large weights dominate. "
        f"Worst month {100 * d['UMD']['worst']:.0f}%, {100 * d['CV']['worst']:.0f}%, {100 * d['DYN']['worst']:.0f}%.",
    )
    metrics = (("sharpe", "Sharpe ratio"), ("skew", "skewness"), ("kurt", "excess kurtosis"), ("maxdd", "worst fall"))
    lab = {"UMD": "UMD", "CV": "constant vol.", "DYN": "dynamic"}
    for i, (m, title) in enumerate(metrics):
        ax = fig.add_axes((0.05 + 0.24 * i, 0.15, 0.19, 0.55))
        vals = [d[k][m] * (100 if m == "maxdd" else 1) for k in keys]
        ax.bar([lab[k] for k in keys], vals, color=[COL[k] for k in keys])
        ax.axhline(0, color=PALETTE["ink"], lw=0.6)
        ax.tick_params(axis="x", labelsize=8)
        tidy(ax, title=title + (" (%)" if m == "maxdd" else ""))
    caption(fig, SRC)
    return fig


def weights() -> Figure:
    s = _scaled()
    fig = new_figure(14.5, 6.0)
    pre = float(s["W_CV"].get(pd.Timestamp("2009-03-31"), np.nan))
    apr = float(s["W_CV"].get(pd.Timestamp("2009-04-30"), np.nan))
    title_block(
        fig,
        "Scaling cut the position before the 2009 crash because volatility had already risen",
        f"Weight on UMD each month. Constant-volatility weight in April 2009: {apr:.2f} (March {pre:.2f}); median {s['W_CV'].median():.2f}. The dynamic weight "
        f"ranges from {s['W_DYN'].min():.1f} to {s['W_DYN'].max():.1f}, peaking in {s['W_DYN'].idxmax():%B %Y}, when momentum's own six-month volatility was "
        f"{100 * C.realised_vol(_umd()).loc[s['W_DYN'].idxmax()]:.0f}%; a handful of such months give the dynamic strategy its fat tails.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    ax.plot(s["W_CV"], color=COL["CV"], lw=1.6, label="constant volatility")
    ax.plot(s["W_DYN"], color=COL["DYN"], lw=1.0, alpha=0.8, label="dynamic")
    ax.axhline(1, color=PALETTE["muted"], lw=0.8, ls="--")
    ax.axhline(0, color=PALETTE["ink"], lw=0.6)
    _shade(ax)
    ax.set_xlim(s.index[0], s.index[-1])
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, ylabel="weight on UMD")
    caption(
        fig,
        SRC
        + " Weights are scaled so that each strategy's volatility matches UMD's over the sample (constant volatility: on average).",
    )
    return fig


# ------------------------------------------------------------------ 7-9. the tail


def _series() -> dict[str, pd.Series]:
    p = _panel()
    return {"UMD": _umd(), "MOM": p["MOM"].dropna(), "MKT": _mkt(), "HML": p["HML"].dropna()}


def gpd() -> Figure:
    ss = _series()
    fig = new_figure(14.5, 6.0)
    tails = {k: C.pot(v) for k, v in ss.items()}
    title_block(
        fig,
        "Beyond the worst tenth of months all four tails are fat, but the fitted index moves with the threshold",
        "Share of months losing more than x, empirical (dots) and fitted (lines), beyond each series' 90th-percentile loss. Tail index xi: "
        + ", ".join(f"{k} {t.xi:.2f}" for k, t in tails.items())
        + ". xi = 0 is a thin (exponential) tail; xi = 0.25 means moments above the fourth do not exist.",
    )
    for i, k in enumerate(("UMD", "MKT")):
        ax = fig.add_axes((0.06 + 0.49 * i, 0.13, 0.42, 0.58))
        t = tails[k]
        loss = np.sort(-ss[k].to_numpy())
        tail = loss[loss > t.u]
        emp = 1.0 - (np.searchsorted(loss, tail, side="right") / loss.size) + 1.0 / loss.size
        ax.semilogy(100 * tail, emp, "o", color=COL[k], ms=4, label="empirical")
        xs = np.linspace(t.u, tail.max() * 1.15, 100)
        fit = (t.exceed / t.n) * (1 + t.xi * (xs - t.u) / t.beta) ** (-1 / t.xi)
        ax.semilogy(100 * xs, fit, color=PALETTE["ink"], lw=1.6, label=f"GPD, xi = {t.xi:.2f}")
        mu, sd = ss[k].mean(), ss[k].std()
        from scipy.stats import norm

        ax.semilogy(100 * xs, norm.sf((xs + mu) / sd), color=PALETTE["red"], lw=1.2, ls="--", label="normal")
        ax.set_ylim(1e-5, 0.3)
        ax.legend(frameon=False)
        tidy(ax, title=k, xlabel="monthly loss, %", ylabel="share of months with a larger loss")
    caption(fig, SRC + " Peaks over threshold, maximum likelihood (scipy genpareto, location fixed at zero).")
    return fig


def hill() -> Figure:
    ss = _series()
    ks = np.arange(10, 121, 2)
    fig = new_figure(14.5, 6.0)
    h = {k: C.hill(v, ks) for k, v in ss.items()}
    title_block(
        fig,
        "The Hill estimator does not settle: the tail index depends on how many months count as the tail",
        "Hill estimate of the left-tail index xi from the k largest monthly losses. At k = 40: "
        + ", ".join(f"{k} {h[k][ks == 40][0]:.2f}" for k in ss)
        + ". The estimate drifts upwards with k for every series; 40-60 months of a 500-month sample is the usual compromise.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.6))
    for k, v in h.items():
        ax.plot(ks, v, color=COL[k], lw=1.8, label=k)
    ax.axvspan(40, 60, color=PALETTE["band"], zorder=0)
    ax.legend(frameon=False, loc="upper left")
    tidy(ax, xlabel="k: number of largest losses used", ylabel="Hill estimate of xi")
    caption(fig, SRC)
    return fig


def var() -> Figure:
    ss = _series()
    t = {k: C.risk_table(ss[k]) for k in ("UMD", "MKT")}
    u = t["UMD"]
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        f"A normal model puts momentum's one-in-a-thousand-month loss at {100 * u.loc[0.999, 'normal_var']:.0f}%; the fitted tail says {100 * u.loc[0.999, 'evt_var']:.0f}%",
        f"Monthly value at risk and expected shortfall. UMD at 99.9%: normal VaR {100 * u.loc[0.999, 'normal_var']:.0f}%, empirical {100 * u.loc[0.999, 'empirical_var']:.0f}%, "
        f"generalised Pareto {100 * u.loc[0.999, 'evt_var']:.0f}% (expected shortfall {100 * u.loc[0.999, 'evt_es']:.0f}%). At 99% the three are "
        f"{100 * u.loc[0.99, 'normal_var']:.0f}%, {100 * u.loc[0.99, 'empirical_var']:.0f}% and {100 * u.loc[0.99, 'evt_var']:.0f}%.",
    )
    cols = [
        ("normal_var", "normal VaR", PALETTE["muted"]),
        ("empirical_var", "empirical VaR", PALETTE["slate"]),
        ("evt_var", "GPD VaR", PALETTE["blue"]),
        ("evt_es", "GPD ES", PALETTE["violet"]),
    ]
    for i, k in enumerate(("UMD", "MKT")):
        ax = fig.add_axes((0.06 + 0.49 * i, 0.13, 0.42, 0.58))
        x = np.arange(2)
        for j, (c, lab, col) in enumerate(cols):
            ax.bar(x + (j - 1.5) * 0.2, 100 * t[k][c].to_numpy(), 0.19, color=col, label=lab)
        ax.set_xticks(x, ["99%", "99.9%"])
        ax.legend(frameon=False, loc="upper left", fontsize=8)
        tidy(ax, title=k, ylabel="monthly loss, %")
    caption(fig, SRC + " The 99.9% empirical figures rest on the single worst month or two.")
    return fig


# ------------------------------------------------------------------ 10. other countries


def international() -> Figure:
    u = aqr.country("UMD")
    rows = {}
    for c in u.columns:
        s = u[c].dropna()
        if len(s) < 240 or c in ("Global", "Global Ex USA", "Europe", "North America", "Pacific"):
            continue
        cv = C.constant_vol(s)
        raw = C.distribution(s.loc[cv.index])
        sc = C.distribution(cv)
        rows[c] = {"sh": raw["sharpe"], "sh_cv": sc["sharpe"], "sk": raw["skew"], "sk_cv": sc["skew"]}
    t = pd.DataFrame(rows).T
    fig = new_figure(14.5, 6.4)
    g = t.loc["GBR"]
    title_block(
        fig,
        "Volatility scaling helped momentum in every country, and the UK gained more than most",
        f"AQR's UMD in {len(t)} countries (dollars). Constant volatility raised the Sharpe ratio in {int((t['sh_cv'] > t['sh']).sum())} and the skewness in "
        f"{int((t['sk_cv'] > t['sk']).sum())}. Median gain {np.median(t['sh_cv'] - t['sh']):+.2f}; UK {g['sh']:.2f} to {g['sh_cv']:.2f} "
        f"({g['sh_cv'] - g['sh']:+.2f}), skewness {g['sk']:.1f} to {g['sk_cv']:+.1f}.",
    )
    cols = [PALETTE["accent"] if c == "GBR" else PALETTE["blue"] for c in t.index]
    a1 = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    a2 = fig.add_axes((0.55, 0.13, 0.42, 0.58))
    for a, (x, y, title) in ((a1, ("sh", "sh_cv", "Sharpe ratio")), (a2, ("sk", "sk_cv", "Skewness"))):
        a.scatter(t[x], t[y], color=cols, s=24)
        for c in t.index:
            a.annotate(
                c, (t.loc[c, x], t.loc[c, y]), fontsize=6.5, color=PALETTE["muted"], xytext=(3, 2), textcoords="offset points"
            )
        lim = (min(t[x].min(), t[y].min()) - 0.1, max(t[x].max(), t[y].max()) + 0.1)
        a.plot(lim, lim, color=PALETTE["muted"], lw=0.8, ls="--")
        tidy(a, title=title, xlabel="UMD", ylabel="constant volatility")
    caption(fig, "AQR country UMD factors, US dollars, long/short. Points above the dashed line improve with scaling.")
    return fig
