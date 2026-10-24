"""Day 2 charts: the anatomy of UK momentum.

Stock-level charts use the survivor sample of today's FTSE 350 (ADR 0009) and say so; factor-level
charts use AQR's and Exeter's survivorship-free series. Every number in a subtitle is computed.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.figure import Figure

from .. import momentum as M
from .. import sectors, stats, survivorship
from ..data import exeter, yahoo
from .foundation import _panel, _shade
from .style import PALETTE, caption, new_figure, tidy, title_block

LAST_COMPLETE = pd.Timestamp("2026-09-30")
START = "2001-01"  # first month every J x K strategy exists
SURV = "Survivor sample: today's FTSE 350 with clean price histories (ADR 0003, 0011), equal-weighted deciles."
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@lru_cache(maxsize=1)
def _returns() -> pd.DataFrame:
    return survivorship.clean(yahoo.prices(), LAST_COMPLETE).returns


@lru_cache(maxsize=1)
def _market() -> pd.Series:
    return M.market_total()


@lru_cache(maxsize=1)
def _factors() -> pd.DataFrame:
    p = _panel()
    return pd.concat([_market(), p[["SMB", "HML"]]], axis=1).dropna()


@lru_cache(maxsize=16)
def _jt(j: int, k: int, skip: int = 1, share: float = 0.1) -> M.Strategy:
    return M.jt(_returns(), j, k, skip, share)


@lru_cache(maxsize=1)
def _std() -> M.Strategy:
    return _jt(11, 1)


@lru_cache(maxsize=1)
def _residual() -> M.Strategy:
    return M.overlapping(_returns(), M.residual_signal(_returns(), _factors()), 1)


@lru_cache(maxsize=1)
def _grid() -> pd.DataFrame:
    return M.grid(_returns(), [1, 3, 6, 9, 12], [1, 3, 6, 9, 12], start=START)


def _window(ax, start: object, end: object = LAST_COMPLETE) -> None:  # type: ignore[no-untyped-def]
    """Limit a time axis to the data: the crisis shading would otherwise stretch it back to 1973."""
    ax.set_xlim(pd.Timestamp(str(start)), pd.Timestamp(str(end)))


def _ci(v: np.ndarray) -> float:
    return 1.96 * float(np.sqrt(stats.long_run_variance(v) / v.size))


# ------------------------------------------------------------------ 1. the J x K grid


def jt_grid() -> Figure:
    g = _grid()
    mean = g.pivot(index="J", columns="K", values="mean")
    tval = g.pivot(index="J", columns="K", values="t_nw")
    sharpe = g.pivot(index="J", columns="K", values="sharpe")
    best = g.loc[g["sharpe"].idxmax()]
    fig = new_figure(14.5, 6.6)
    title_block(
        fig,
        "Jegadeesh and Titman in London: short holding periods pay, long ones give it back",
        f"Winner-minus-loser returns for every formation period J and holding period K (months), one-month skip, {START[:4]} to 2026. "
        f"The best cell is J = {int(best['J'])}, K = {int(best['K'])} ({100 * best['mean']:.1f}% a year, Sharpe {best['sharpe']:.2f}); "
        f"holding for a year after a twelve-month formation earns {100 * mean.loc[12, 12]:.1f}%. In this sample few cells clear "
        "t = 2: survivor-based momentum since 2001 is weaker than the long factor histories of Day 1.",
    )
    for k_, (data, label, fmt) in enumerate(
        [(100 * mean, "Mean, % a year (NW t)", "{:.1f}"), (sharpe, "Sharpe ratio", "{:.2f}")]
    ):
        ax = fig.add_axes((0.06 + 0.48 * k_, 0.12, 0.38, 0.58))
        lim = float(np.nanmax(np.abs(data.to_numpy())))
        ax.imshow(data.to_numpy(), cmap="RdBu", norm=TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim), aspect="auto")
        for i in range(data.shape[0]):
            for jx in range(data.shape[1]):
                txt = fmt.format(data.iloc[i, jx]) + (f"\n(t {tval.iloc[i, jx]:.1f})" if k_ == 0 else "")
                ax.text(
                    jx,
                    i,
                    txt,
                    ha="center",
                    va="center",
                    fontsize=8.5,
                    color="white" if abs(data.iloc[i, jx]) > 0.6 * lim else PALETTE["ink"],
                )
        ax.set_xticks(range(data.shape[1]))
        ax.set_xticklabels([str(c) for c in data.columns])
        ax.set_yticks(range(data.shape[0]))
        ax.set_yticklabels([str(r) for r in data.index])
        ax.grid(False)
        tidy(ax, title=label, xlabel="holding period K, months", ylabel="formation period J, months")
    caption(fig, SURV + " Overlapping Jegadeesh-Titman cohorts; decile winners minus losers; Newey-West t.")
    return fig


# ------------------------------------------------------------------ 2. the skip month and short-term reversal


def skip_and_reversal() -> Figure:
    r = _returns()
    skips = {s: M.summary(_jt(11, 1, s).wml.loc[START:]) for s in (0, 1, 2)}
    dec = M.deciles(r, M.formation_return(r, 1, 0)).loc[START:]
    means = 1200 * dec.mean()
    spread = (dec[10] - dec[1]).dropna().to_numpy()
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Why momentum skips a month: last month's winners lose the next",
        f"Left: twelve-month momentum with no skip, a one-month skip and a two-month skip. Skipping the latest month lifts the Sharpe "
        f"ratio from {skips[0]['sharpe']:.2f} to {skips[1]['sharpe']:.2f}. Right: sorted on last month's return alone, the top decile "
        f"earns {abs(1200 * spread.mean()):.1f}% a year less than the bottom next month (t = {stats.nw_tstat(spread):.1f}): short-term "
        "reversal, which a skip keeps out of the momentum signal.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.36, 0.58))
    labels = ["no skip\n(months t-12 to t-1)", "skip one\n(t-12 to t-2)", "skip two\n(t-13 to t-3)"]
    vals = [skips[s]["sharpe"] for s in (0, 1, 2)]
    ax.bar(range(3), vals, color=[PALETTE["slate"], PALETTE["red"], PALETTE["slate"]], width=0.6)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.01, f"{v:.2f}", ha="center", fontsize=9)
    ax.set_xticks(range(3))
    ax.set_xticklabels(labels, fontsize=8.5)
    tidy(ax, title="Twelve months of formation, Sharpe ratio", ylabel="Sharpe ratio")
    bx = fig.add_axes((0.52, 0.13, 0.45, 0.58))
    bx.bar(range(1, 11), means.to_numpy(), color=[PALETTE["blue"]] * 9 + [PALETTE["red"]], width=0.7)
    bx.bar([1], [means.iloc[0]], color=PALETTE["green"], width=0.7)
    bx.axhline(0, color=PALETTE["ink"], lw=0.7)
    bx.set_xticks(range(1, 11))
    tidy(
        bx,
        title="Sorted on last month's return: next month",
        xlabel="decile of last month's return (1 = worst)",
        ylabel="mean return, % a year",
    )
    caption(
        fig,
        SURV
        + f" Skip variants: 11-month formation windows ending one, two or three months before the holding month; {START[:4]}-2026.",
    )
    return fig


# ------------------------------------------------------------------ 3. event time: five years after formation


@lru_cache(maxsize=1)
def _event() -> pd.DataFrame:
    r = _returns()
    return M.event_time(r, M.formation_return(r, 11, 1), 60)


def event_time() -> Figure:
    e = _event()
    peak = int(e["cumulative"].idxmax())
    fig = new_figure(14.5, 6.0)
    first = e.loc[: min(6, len(e)), "mean"].sum()
    title_block(
        fig,
        "Momentum is a few good months followed by years of giving back",
        f"Winners minus losers in each month after formation, cohorts held without rebalancing. The cumulative spread peaks after "
        f"{peak} months at {100 * e['cumulative'].max():.1f}%, earning {100 * first:.1f}% in the first six; by month 60 it is "
        f"{100 * e['cumulative'].iloc[-1]:.1f}%. This is the long-run reversal of De Bondt and Thaler (1985) and Jegadeesh and "
        "Titman (2001): part of momentum is overreaction that later corrects.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    colours = np.where(e["mean"] > 0, PALETTE["blue"], PALETTE["red"])
    ax.bar(e.index, 100 * e["mean"], color=colours, width=0.8, alpha=0.75, label="monthly spread (left)")
    ax.errorbar(e.index, 100 * e["mean"], yerr=196 * e["se"], fmt="none", color=PALETTE["muted"], lw=0.7)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    tidy(ax, xlabel="months after formation", ylabel="winners minus losers, % a month")
    cx = ax.twinx()
    cx.plot(e.index, 100 * e["cumulative"], color=PALETTE["ink"], lw=2, label="cumulative (right)")
    cx.axhline(0, color=PALETTE["muted"], lw=0.6, ls=":")
    cx.set_ylabel("cumulative, %")
    cx.grid(False)
    cx.spines["right"].set_visible(True)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = cx.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8.5, loc="lower left")
    caption(
        fig,
        SURV + " 12-1 decile cohorts formed each month from 2000; whiskers are 95% Newey-West intervals over formation months.",
    )
    return fig


# ------------------------------------------------------------------ 4. intermediate against recent momentum


def intermediate_vs_recent() -> Figure:
    r = _returns()
    inter = M.overlapping(r, M.formation_return(r, 6, 6), 1).wml.loc[START:]
    recent = M.overlapping(r, M.formation_return(r, 5, 1), 1).wml.loc[START:]
    std = _std().wml.loc[START:]
    si, sr, ss = M.summary(inter), M.summary(recent), M.summary(std)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "In the UK the recent half of the year carries momentum, not the distant half",
        f"Novy-Marx (2012) found US momentum driven by returns seven to twelve months ago. Splitting the UK signal: months t-12 to "
        f"t-7 earn {100 * si['mean']:.1f}% a year (Sharpe {si['sharpe']:.2f}), months t-6 to t-2 {100 * sr['mean']:.1f}% "
        f"(Sharpe {sr['sharpe']:.2f}), and the full 12-1 signal {100 * ss['mean']:.1f}% (Sharpe {ss['sharpe']:.2f}). The US "
        "finding does not carry over to this sample.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    _shade(ax, labels=False)
    for s, label, colour in [
        (std, "12-1 (t-12 to t-2)", PALETTE["red"]),
        (recent, "recent (t-6 to t-2)", PALETTE["blue"]),
        (inter, "intermediate (t-12 to t-7)", PALETTE["green"]),
    ]:
        ax.plot((1 + s.fillna(0)).cumprod(), color=colour, lw=1.8, label=label)
    ax.set_yscale("log")
    ax.set_xlim(pd.Timestamp(START), _returns().index[-1])
    tidy(ax, ylabel="growth of one pound (log scale)")
    ax.legend(fontsize=8.5, loc="upper left")
    caption(fig, SURV + " Decile winners minus losers, rebalanced monthly.")
    return fig


# ------------------------------------------------------------------ 5-6. residual momentum


def residual_momentum() -> Figure:
    raw = _std().wml
    res = _residual().wml
    common = raw.dropna().index.intersection(res.dropna().index)
    raw, res = raw.loc[common], res.loc[common]
    m = _market()
    a, b = M.summary(raw, m), M.summary(res, m)
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Residual momentum: the same idea with half the risk",
        f"Blitz, Huij and Martens (2011) rank stocks on returns unexplained by the market, size and value over the past three years. "
        f"Against raw 12-1 momentum over the same months: Sharpe {b['sharpe']:.2f} against {a['sharpe']:.2f}, volatility "
        f"{100 * b['vol']:.0f}% against {100 * a['vol']:.0f}%, worst drawdown {100 * b['max_drawdown']:.0f}% against "
        f"{100 * a['max_drawdown']:.0f}%, and a market beta of {b['beta']:.2f} instead of {a['beta']:.2f}.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    _shade(ax, labels=False)
    ax.plot((1 + raw).cumprod(), color=PALETTE["red"], lw=1.8, label=f"raw 12-1 (Sharpe {a['sharpe']:.2f})")
    ax.plot((1 + res).cumprod(), color=PALETTE["violet"], lw=1.8, label=f"residual (Sharpe {b['sharpe']:.2f})")
    ax.set_yscale("log")
    tidy(ax, title="Growth of one pound", ylabel="log scale")
    ax.legend(fontsize=8.5, loc="upper left")
    bx = fig.add_axes((0.69, 0.13, 0.28, 0.58))
    for s, colour in [(raw, PALETTE["red"]), (res, PALETTE["violet"])]:
        bx.fill_between(s.index, 100 * stats.drawdown_path(s), 0, color=colour, alpha=0.45)
    tidy(bx, title="Drawdowns", ylabel="% below peak")
    _window(ax, raw.index[0], raw.index[-1])
    _window(bx, raw.index[0], raw.index[-1])
    caption(
        fig,
        SURV
        + " Residuals from 36-month regressions on the UK market (sterling total return), AQR's SMB and HML; signal scaled by residual volatility.",
    )
    return fig


def residual_exposures() -> Figure:
    raw, res, m = _std().wml, _residual().wml, _market()
    j = pd.concat([raw.rename("raw"), res.rename("res"), m.rename("m")], axis=1).dropna()
    beta = {c: j[c].rolling(36).cov(j["m"]) / j["m"].rolling(36).var() for c in ("raw", "res")}
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Raw momentum bets on the market's direction; residual momentum much less",
        f"Left: three-year rolling market beta. Raw momentum's swings from {beta['raw'].min():.1f} to {beta['raw'].max():.1f}: after a "
        f"crash the losers are high-beta stocks, so the strategy is short the market just as it rebounds. Residual momentum stays "
        f"between {beta['res'].min():.1f} and {beta['res'].max():.1f}. Right: monthly returns against the market.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.55, 0.58))
    _shade(ax, labels=False)
    ax.plot(beta["raw"], color=PALETTE["red"], lw=1.6, label="raw 12-1")
    ax.plot(beta["res"], color=PALETTE["violet"], lw=1.6, label="residual")
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    tidy(ax, title="Rolling 36-month market beta", ylabel="beta")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.69, 0.13, 0.28, 0.58))
    bx.scatter(100 * j["m"], 100 * j["raw"], s=8, color=PALETTE["red"], alpha=0.5, label="raw")
    bx.scatter(100 * j["m"], 100 * j["res"], s=8, color=PALETTE["violet"], alpha=0.5, label="residual")
    bx.axhline(0, color=PALETTE["ink"], lw=0.6)
    bx.axvline(0, color=PALETTE["ink"], lw=0.6)
    tidy(bx, title="Monthly returns", xlabel="UK market, %", ylabel="strategy, %")
    bx.legend(fontsize=8)
    _window(ax, j.index[0], j.index[-1])
    caption(fig, SURV + " Market: UK total return in sterling (AQR converted from dollars).")
    return fig


# ------------------------------------------------------------------ 7. the 52-week high


@lru_cache(maxsize=1)
def _high() -> M.Strategy:
    r = _returns()
    ratio = M.high_ratio(r)
    tie = M.formation_return(r, 11, 1).rank(axis=1, pct=True)  # stocks at their high are separated by 12-1 momentum
    return M.overlapping(r, ratio + 1e-6 * tie, 1, share=0.3)


def high_vs_momentum() -> Figure:
    hi = _high().wml.loc[START:]
    mo = _jt(11, 1, 1, 0.3).wml.loc[START:]
    sh, sm = M.summary(hi, _market()), M.summary(mo, _market())
    at_high = float(
        (M.high_ratio(_returns()).loc[START:] >= 0.9999)
        .sum(axis=1)
        .div(M.high_ratio(_returns()).loc[START:].notna().sum(axis=1))
        .mean()
    )
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Nearness to the 52-week high does not work on month-end prices",
        f"George and Hwang (2004) buy stocks near their 52-week high and sell those far from it. Measured with month-end prices it earns "
        f"{100 * sh['mean']:.1f}% a year (Sharpe {sh['sharpe']:.2f}, worst drawdown {100 * sh['max_drawdown']:.0f}%) against "
        f"{100 * sm['mean']:.1f}% for 12-1 momentum with the same 30% legs (Sharpe {sm['sharpe']:.2f}, drawdown "
        f"{100 * sm['max_drawdown']:.0f}%); the two correlate {hi.corr(mo):.2f}. On average {100 * at_high:.0f}% of stocks sit at "
        "their high in any month (ties broken by 12-1). The US evidence uses daily highs; a monthly approximation loses what makes the signal work.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    _shade(ax, labels=False)
    ax.plot((1 + hi.fillna(0)).cumprod(), color=PALETTE["teal"], lw=1.8, label="52-week high (top 30% minus bottom 30%)")
    ax.plot((1 + mo.fillna(0)).cumprod(), color=PALETTE["red"], lw=1.8, label="12-1 momentum (same legs)")
    ax.set_yscale("log")
    tidy(ax, ylabel="growth of one pound (log scale)")
    ax.legend(fontsize=8.5, loc="upper left")
    _window(ax, START)
    caption(fig, SURV + " Nearness = month-end price / highest month-end price in the past 12 months, known at formation.")
    return fig


# ------------------------------------------------------------------ 8-9. market states


def _state_series() -> list[tuple[str, pd.Series]]:
    p = _panel()
    return [
        ("AQR MOM (1982-2026)", p["MOM"]),
        ("AQR UMD (1987-2026)", p["UMD"]),
        ("Exeter UMD (1982-2016)", p["EX_UMD"]),
        ("survivors 12-1 (2001-2026)", _std().wml.loc[START:]),
    ]


def market_states() -> Figure:
    rows = [(name, M.market_states(s, _market())) for name, s in _state_series()]
    umd = rows[1][1]
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "UMD pays after rising markets and stalls after falling ones; rank-weighted MOM does not",
        f"Mean return in months following a 24-month rise in the UK market (UP) and a 24-month fall (DOWN), Cooper, Gutierrez and "
        f"Hameed (2004). AQR's UMD earns {100 * umd.loc['UP', 'mean']:.1f}% a year after UP markets (t = {umd.loc['UP', 't_nw']:.1f}) "
        f"and {100 * umd.loc['DOWN', 'mean']:.1f}% after DOWN ones. Only {int(umd.loc['DOWN', 'months'])} months of the sample follow "
        f"a falling market, and none of the differences is significant; AQR's rank-weighted MOM even earns more after falls "
        f"({100 * rows[0][1].loc['DOWN', 'mean']:.1f}% against {100 * rows[0][1].loc['UP', 'mean']:.1f}%). The evidence is thin.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.62, 0.58))
    x = np.arange(len(rows))
    for off, state, colour in [(-0.18, "UP", PALETTE["blue"]), (0.18, "DOWN", PALETTE["red"])]:
        vals, errs = [], []
        for _name, t in rows:
            vals.append(100 * t.loc[state, "mean"])
            errs.append(
                196 * abs(t.loc[state, "mean"] / t.loc[state, "t_nw"])
                if np.isfinite(t.loc[state, "t_nw"]) and t.loc[state, "t_nw"] != 0
                else 0
            )
        ax.bar(
            x + off,
            vals,
            width=0.34,
            color=colour,
            alpha=0.85,
            label="after a rising market" if state == "UP" else "after a falling market",
        )
        ax.errorbar(x + off, vals, yerr=errs, fmt="none", color=PALETTE["ink"], capsize=3, lw=0.9)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels([n for n, _ in rows], fontsize=8.5)
    tidy(ax, title="Mean return by prior market state", ylabel="% a year (95% NW interval)")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.75, 0.13, 0.22, 0.58))
    past = np.log1p(_market()).rolling(24).sum().shift(1).dropna()
    bx.hist(100 * np.expm1(past), bins=40, color=PALETTE["slate"], alpha=0.8)
    bx.axvline(0, color=PALETTE["red"], lw=1.2)
    tidy(bx, title="Past 24-month market return", xlabel="%", ylabel="months")
    caption(
        fig,
        "UK market: sterling total return, Exeter to 1985 and AQR (converted from dollars) after. State known at the start of each month.",
    )
    return fig


def conditional_beta() -> Figure:
    p = _panel()
    cb = M.conditional_beta(p["UMD"], _market(), 24)
    slope, icpt = np.polyfit(cb["market_past"], cb["beta"], 1)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Momentum's market beta follows the market's past: negative after crashes",
        f"Rolling 24-month beta of AQR's UMD on the UK market against the market's return over the same 24 months (Grundy and "
        f"Martin, 2001). After a 30% fall the fitted beta is {icpt + slope * -0.3:.2f}, after a 30% rise {icpt + slope * 0.3:.2f}: "
        "past losers in a falling market are the stocks that fell most, high-beta stocks, so momentum ends up short the market - "
        "the set-up for the crashes of Day 7.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.scatter(100 * cb["market_past"], cb["beta"], s=8, color=PALETTE["violet"], alpha=0.5)
    grid = np.linspace(cb["market_past"].min(), cb["market_past"].max(), 20)
    ax.plot(100 * grid, icpt + slope * grid, color=PALETTE["ink"], lw=1.8)
    ax.axhline(0, color=PALETTE["muted"], lw=0.7)
    tidy(ax, title="Beta against the market's past", xlabel="market return over the 24 months, %", ylabel="UMD beta, 24 months")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    _shade(bx, labels=False)
    bx.plot(cb["beta"], color=PALETTE["violet"], lw=1.5)
    bx.axhline(0, color=PALETTE["ink"], lw=0.7)
    tidy(bx, title="UMD's rolling beta", ylabel="beta")
    _window(bx, cb.index[0], cb.index[-1])
    caption(fig, "AQR UK UMD in sterling; UK market sterling total return. Overlapping 24-month windows.")
    return fig


# ------------------------------------------------------------------ 10-11. seasons: the April effect


def calendar_chart() -> Figure:
    p = _panel()
    cal = M.calendar(p["MOM"])
    reg = M.seasonal_regression(p["EX_UMD"])
    reg_m = M.seasonal_regression(p["MOM"])
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "UK momentum loses in April, the month the tax year ends",
        f"Mean return of AQR's UK momentum in each calendar month, 1972-2026, with 95% intervals. April averages "
        f"{100 * cal.loc[4, 'mean']:.2f}% against {100 * cal.drop(4)['mean'].mean():.2f}% in the other months; regression on calendar "
        f"dummies puts April {100 * reg_m.coef[2]:.1f} points below the rest (t = {reg_m.tstat[2]:.1f}), and Exeter's UMD "
        f"{100 * reg.coef[2]:.1f} points (t = {reg.tstat[2]:.1f}). January, the US tax-loss month, shows nothing (t = "
        f"{reg_m.tstat[1]:.1f}).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    colours = [PALETTE["accent"] if m == 4 else (PALETTE["slate"] if m == 1 else PALETTE["blue"]) for m in range(1, 13)]
    se = cal["mean"] / cal["t"]
    ax.bar(range(1, 13), 100 * cal["mean"], color=colours, width=0.7)
    ax.errorbar(range(1, 13), 100 * cal["mean"], yerr=196 * se, fmt="none", color=PALETTE["ink"], capsize=3, lw=0.9)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MONTHS)
    tidy(ax, ylabel="mean momentum return, % a month")
    caption(
        fig,
        "AQR UK momentum (rank-weighted, sterling), 1972-2026. The UK tax year ends on 5 April; tax-loss selling falls in March and early April.",
    )
    return fig


def april_legs() -> Figure:
    six = exeter.portfolios("6ports_size_mom")
    rf = _panel()["EX_RF"]
    ex = six.sub(rf.reindex(six.index), axis=0).dropna()
    win = (ex["SH"] + ex["BH"]) / 2
    lose = (ex["SL"] + ex["BL"]) / 2
    month = pd.DatetimeIndex(ex.index).month
    stats_rows = {}
    for name, s in [("winners", win), ("losers", lose), ("winners - losers", win - lose)]:
        stats_rows[name] = (100 * s[month == 4].mean(), 100 * s[month != 4].mean())
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "In April the losers rebound: tax-loss selling unwinds",
        f"Exeter's momentum portfolios in April and in other months, 1980-2016. Past losers earn {stats_rows['losers'][0]:.1f}% over "
        f"cash in an average April against {stats_rows['losers'][1]:.1f}% in other months, while winners are little changed "
        f"({stats_rows['winners'][0]:.1f}% against {stats_rows['winners'][1]:.1f}%). It is the losers' bounce, not the winners' "
        "fall, that costs momentum its April.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    names = list(stats_rows)
    x = np.arange(3)
    ax.bar(x - 0.18, [stats_rows[n][0] for n in names], width=0.34, color=PALETTE["accent"], label="April")
    ax.bar(x + 0.18, [stats_rows[n][1] for n in names], width=0.34, color=PALETTE["blue"], label="other months")
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    tidy(ax, title="Mean excess return, % a month", ylabel="% a month")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    wml = win - lose
    by_decade = []
    for start in (1980, 1990, 2000, 2010):
        part = wml.loc[str(start) : str(start + 9)]
        pm = pd.DatetimeIndex(part.index).month
        by_decade.append((f"{start}s", 100 * part[pm == 4].mean(), 100 * part[pm != 4].mean()))
    xd = np.arange(len(by_decade))
    bx.bar(xd - 0.18, [b[1] for b in by_decade], width=0.34, color=PALETTE["accent"], label="April")
    bx.bar(xd + 0.18, [b[2] for b in by_decade], width=0.34, color=PALETTE["blue"], label="other months")
    bx.axhline(0, color=PALETTE["ink"], lw=0.7)
    bx.set_xticks(xd)
    bx.set_xticklabels([b[0] for b in by_decade])
    tidy(bx, title="Winners minus losers by decade", ylabel="% a month")
    bx.legend(fontsize=8.5)
    caption(
        fig, "Exeter Xfi Centre six size x momentum portfolios, value-weighted, monthly re-formation; legs average small and big."
    )
    return fig


def calendar_sources() -> Figure:
    p = _panel()
    srcs = [
        ("AQR MOM", p["MOM"]),
        ("AQR UMD", p["UMD"]),
        ("Exeter UMD", p["EX_UMD"]),
        ("survivors 12-1", _std().wml.loc[START:]),
        ("survivors residual", _residual().wml),
    ]
    data = np.array([[100 * M.calendar(s).loc[m, "mean"] for m in range(1, 13)] for _, s in srcs])
    tv = np.array([[M.calendar(s).loc[m, "t"] for m in range(1, 13)] for _, s in srcs])
    neg = sum(1 for row in data if row[3] < 0)
    fig = new_figure(14.5, 5.6)
    title_block(
        fig,
        "April is the weakest month in four of five sources, and residual momentum is the exception",
        f"Mean monthly return of five UK momentum series by calendar month (t in brackets). April is negative in {neg} of the "
        f"{len(srcs)}, and the lowest month in each of those four. The sources differ in data, construction and period, so the "
        "effect is not an artefact of one of them. Residual momentum, which hedges market, size and value exposure, shows no April "
        "loss, which suggests the April rebound works through factor exposures rather than stock-specific returns.",
    )
    ax = fig.add_axes((0.12, 0.12, 0.85, 0.58))
    lim = float(np.nanmax(np.abs(data)))
    ax.imshow(data, cmap="RdBu", norm=TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim), aspect="auto")
    for i in range(data.shape[0]):
        for jx in range(12):
            ax.text(
                jx,
                i,
                f"{data[i, jx]:.1f}\n({tv[i, jx]:.1f})",
                ha="center",
                va="center",
                fontsize=7.5,
                color="white" if abs(data[i, jx]) > 0.6 * lim else PALETTE["ink"],
            )
    ax.set_xticks(range(12))
    ax.set_xticklabels(MONTHS)
    ax.set_yticks(range(len(srcs)))
    ax.set_yticklabels([n for n, _ in srcs])
    ax.grid(False)
    caption(
        fig,
        "Means in % a month; t from the month's own standard error. Samples: AQR MOM 1972-, UMD 1987-, Exeter 1980-2016, survivors 2001-2026.",
    )
    return fig


# ------------------------------------------------------------------ 12. size


def size_chart() -> Figure:
    six = exeter.portfolios("6ports_size_mom")
    small = six["SH"] - six["SL"]
    big = six["BH"] - six["BL"]
    ss, sb = M.summary(small), M.summary(big)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Momentum is stronger among smaller companies, and has been for decades",
        f"Winners minus losers within the smaller and larger halves of the UK market (Exeter, split at the 350th company). Small: "
        f"{100 * ss['mean']:.1f}% a year, Sharpe {ss['sharpe']:.2f}; big: {100 * sb['mean']:.1f}%, Sharpe {sb['sharpe']:.2f}. The "
        "ten-year rolling mean shows the gap in every decade, consistent with momentum as slow diffusion of news in stocks that "
        "fewer analysts follow (Hong, Lim and Stein, 2000).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    _shade(ax, labels=False)
    ax.plot((1 + small).cumprod(), color=PALETTE["blue"], lw=1.8, label="small")
    ax.plot((1 + big).cumprod(), color=PALETTE["slate"], lw=1.8, label="big")
    ax.set_yscale("log")
    tidy(ax, title="Growth of one pound", ylabel="log scale")
    ax.legend(fontsize=8.5)
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    bx.plot(1200 * small.rolling(120).mean(), color=PALETTE["blue"], lw=1.6, label="small")
    bx.plot(1200 * big.rolling(120).mean(), color=PALETTE["slate"], lw=1.6, label="big")
    bx.axhline(0, color=PALETTE["ink"], lw=0.7)
    tidy(bx, title="Ten-year rolling mean", ylabel="% a year")
    bx.legend(fontsize=8.5)
    _window(ax, small.index[0], small.index[-1])
    _window(bx, small.index[0], small.index[-1])
    caption(fig, "Exeter Xfi Centre six size x momentum portfolios (value-weighted, monthly), October 1980 to June 2016.")
    return fig


# ------------------------------------------------------------------ 13-14. deciles and legs


def decile_returns() -> Figure:
    r = _returns()
    dec = M.deciles(r, M.formation_return(r, 11, 1)).loc[START:]
    uni = r.loc[START:].mean(axis=1)
    rows = []
    for g in dec.columns:
        v = dec[g].dropna().to_numpy()
        rows.append((g, 1200 * v.mean(), stats.annual_sharpe(v), np.sqrt(12) * v.std(ddof=1)))
    fig = new_figure(14.5, 6.0)
    sp = (dec[10] - dec[1]).dropna().to_numpy()
    title_block(
        fig,
        "Among survivors the winners carry the spread; the losers, having survived, do not lose",
        f"Next-month return of each 12-1 momentum decile. The worst decile earns {rows[0][1]:.1f}% a year with volatility "
        f"{100 * rows[0][3]:.0f}%, the best {rows[-1][1]:.1f}% with {100 * rows[-1][3]:.0f}%; the universe averages "
        f"{1200 * uni.mean():.1f}%. The spread, {1200 * sp.mean():.1f}% a year (t = {stats.nw_tstat(sp):.1f}), comes from the winners: "
        "past losers that later failed are missing from today's FTSE 350, so the losers left are the ones that recovered.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    cols = [PALETTE["red"]] + [PALETTE["blue"]] * 8 + [PALETTE["green"]]
    ax.bar(range(1, 11), [x[1] for x in rows], color=cols, width=0.7)
    ax.axhline(1200 * uni.mean(), color=PALETTE["ink"], ls="--", lw=0.9)
    ax.text(10.4, 1200 * uni.mean(), "universe", fontsize=8, color=PALETTE["muted"], va="bottom")
    cx = ax.twinx()
    cx.plot(range(1, 11), [x[2] for x in rows], color=PALETTE["ink"], marker="o", lw=1.2, label="Sharpe ratio (right)")
    cx.grid(False)
    cx.spines["right"].set_visible(True)
    cx.legend(fontsize=8.5, loc="upper left")
    ax.set_xticks(range(1, 11))
    tidy(ax, xlabel="12-1 momentum decile (1 = losers)", ylabel="mean return, % a year")
    caption(fig, SURV + f" {START[:4]}-2026; total returns, not excess.")
    return fig


def legs_chart() -> Figure:
    s = _std()
    long_leg = (s.winners - s.universe).loc[START:]
    short_leg = (s.universe - s.losers).loc[START:]
    six = exeter.portfolios("6ports_size_mom")
    mkt = exeter.factors()["RM"]
    ex_long = ((six["SH"] + six["BH"]) / 2 - mkt).dropna()
    ex_short = (mkt - (six["SL"] + six["BL"]) / 2).dropna()
    fig = new_figure(14.5, 6.2)
    title_block(
        fig,
        "Which leg earns the premium? Survivorship hides the short leg",
        f"Winners over the average stock (long leg) and the average stock over losers (short leg). Survivors, 2001-2026: long "
        f"{1200 * long_leg.mean():.1f}% a year, short {1200 * short_leg.mean():.1f}%. Exeter, 1980-2016: long "
        f"{1200 * ex_long.mean():.1f}%, short {1200 * ex_short.mean():.1f}%. With failed companies included both legs earn; among "
        "survivors the short leg loses, because the losers that went under are not there to be shorted. Day 11 measures the short "
        "leg directly, with disclosed short positions.",
    )
    for k_, (lg, sg, title) in enumerate(
        [
            (long_leg, short_leg, "Survivors (equal-weighted deciles)"),
            (ex_long, ex_short, "Exeter (value-weighted, against the market)"),
        ]
    ):
        ax = fig.add_axes((0.06 + 0.48 * k_, 0.13, 0.42, 0.58))
        _shade(ax, labels=False)
        ax.plot((1 + lg.fillna(0)).cumprod(), color=PALETTE["green"], lw=1.8, label="long leg: winners - average")
        ax.plot((1 + sg.fillna(0)).cumprod(), color=PALETTE["red"], lw=1.8, label="short leg: average - losers")
        ax.set_yscale("log")
        tidy(ax, title=title, ylabel="growth of one pound (log)")
        ax.legend(fontsize=8.5, loc="upper left")
        _window(ax, lg.dropna().index[0], lg.dropna().index[-1])
    caption(fig, SURV + " Exeter legs: average of small and big winner (loser) portfolios against Exeter's market return.")
    return fig


# ------------------------------------------------------------------ 15-17. turnover, persistence, spells


def turnover_chart() -> Figure:
    ks = [1, 3, 6, 12]
    rows = []
    for k in ks:
        s = _jt(11, k)
        v = s.wml.loc[START:].dropna()
        to = s.turnover.loc[START:].dropna().mean()
        mean = 12 * v.mean()
        rows.append((k, to, mean, mean / (2 * 12 * to) if to > 0 else np.nan))
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Momentum trades a lot: a quarter of each leg turns over every month",
        f"One-sided monthly turnover of the winner portfolio and the trading cost that would wipe out the premium. Rebalanced "
        f"monthly (K = 1), {100 * rows[0][1]:.0f}% of the long leg is replaced each month; held twelve months in overlapping "
        f"cohorts, {100 * rows[-1][1]:.0f}%. The break-even round-trip cost is {100 * rows[0][3]:.2f}% for K = 1 - before the 0.5% "
        "UK stamp duty on every purchase (Day 9).",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.bar(range(len(ks)), [100 * r[1] for r in rows], color=PALETTE["blue"], width=0.6)
    for i, r in enumerate(rows):
        ax.text(i, 100 * r[1] + 0.5, f"{100 * r[1]:.0f}%", ha="center", fontsize=9)
    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels([f"K = {k}" for k in ks])
    tidy(ax, title="Monthly turnover of the long leg", ylabel="% of the portfolio")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    be = [100 * r[3] for r in rows]
    bx.bar(range(len(ks)), be, color=[PALETTE["green"] if b > 0 else PALETTE["red"] for b in be], width=0.6)
    bx.axhline(0.5, color=PALETTE["accent"], ls="--", lw=1)
    bx.text(len(ks) - 0.5, 0.52, "UK stamp duty 0.5%", fontsize=8, color=PALETTE["accent"], ha="right", va="bottom")
    bx.set_xticks(range(len(ks)))
    bx.set_xticklabels([f"K = {k}" for k in ks])
    tidy(bx, title="Break-even round-trip cost", ylabel="% of value traded")
    caption(
        fig,
        SURV
        + " 12-1 deciles; turnover = half the sum of absolute weight changes, before price drift; break-even = mean / (2 x 12 x turnover).",
    )
    return fig


def persistence() -> Figure:
    sig = M.formation_return(_returns(), 11, 1)
    t1 = M.transitions(sig, 1, 5)
    t12 = M.transitions(sig, 12, 5)
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Winners stay winners for months, not years",
        f"Probability that a stock in each 12-1 quintile is in each quintile one month and twelve months later. A month on, "
        f"{100 * t1.loc[5, 5]:.0f}% of top-quintile stocks are still there; a year on, {100 * t12.loc[5, 5]:.0f}% - barely more "
        f"than the {100 * t12.loc[1, 5]:.0f}% of former losers who have become winners. Momentum signals decay within a year, which "
        "is why long holding periods give the premium back.",
    )
    for k_, (t, title) in enumerate([(t1, "One month later"), (t12, "Twelve months later")]):
        ax = fig.add_axes((0.07 + 0.48 * k_, 0.12, 0.36, 0.58))
        ax.imshow(100 * t.to_numpy(), cmap="Blues", vmin=0, vmax=100, aspect="auto")
        for i in range(5):
            for jx in range(5):
                v = 100 * t.iloc[i, jx]
                ax.text(jx, i, f"{v:.0f}", ha="center", va="center", fontsize=9, color="white" if v > 50 else PALETTE["ink"])
        ax.set_xticks(range(5))
        ax.set_xticklabels([f"Q{c}" for c in t.columns])
        ax.set_yticks(range(5))
        ax.set_yticklabels([f"Q{c}" for c in t.index])
        ax.grid(False)
        tidy(ax, title=title + ", % of stocks", xlabel="quintile later (Q5 = winners)", ylabel="quintile now")
    caption(fig, SURV + " Quintiles of the 12-1 formation return each month, 2000-2026.")
    return fig


def spells_chart() -> Figure:
    s = _std()
    win = M.spells(s.long.loc[START:])
    lose = M.spells(s.short.loc[START:])
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "How long a stock stays a winner",
        f"Lengths of unbroken spells in the top and bottom 12-1 deciles, re-sorted monthly. Winners' spells last {win.mean():.1f} "
        f"months on average (median {win.median():.0f}), losers' {lose.mean():.1f} (median {lose.median():.0f}); "
        f"{100 * (win >= 12).mean():.0f}% of winner spells last a year or more. The signal moves slowly - it is built from a year "
        "of returns - but the portfolio still changes every month.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    bins = np.arange(1, 40)
    ax.hist(win.clip(upper=38), bins=bins, color=PALETTE["green"], alpha=0.6, label=f"winner spells ({len(win):,})")
    ax.hist(lose.clip(upper=38), bins=bins, color=PALETTE["red"], alpha=0.5, label=f"loser spells ({len(lose):,})")
    tidy(ax, xlabel="consecutive months in the decile (38 = 38 or more)", ylabel="spells")
    ax.legend(fontsize=8.5)
    caption(fig, SURV + f" {START[:4]}-2026.")
    return fig


# ------------------------------------------------------------------ 18. sectors


@lru_cache(maxsize=1)
def _industry() -> pd.Series:
    return sectors.by_ticker(yahoo.constituents())


def sector_composition() -> Figure:
    s = _std()
    ind = _industry()
    win = M.composition(s.long.loc[START:], ind).rolling(12).mean()
    lose = M.composition(s.short.loc[START:], ind).rolling(12).mean()
    has = M.formation_return(_returns(), 11, 1).loc[START:].notna()
    uni = M.composition(has, ind).mean()
    order = list(uni.sort_values(ascending=False).index)
    tilt = (M.composition(s.long.loc[START:], ind).mean() - M.composition(s.short.loc[START:], ind).mean()).reindex(order)
    top = tilt.idxmax()
    peak_ind = win.max().idxmax()
    peak_date = win[peak_ind].idxmax()
    bottom = tilt.idxmin()
    fig = new_figure(14.5, 6.6)
    title_block(
        fig,
        "Momentum is partly an industry bet that rotates over time",
        f"Industry shares of the winner and loser deciles, twelve-month averages. On average winners hold {100 * tilt[top]:.0f} points "
        f"more {top} than losers and {100 * -tilt[bottom]:.0f} points less {bottom}: small average tilts. But the mix rotates; at its "
        f"peak {peak_ind} was {100 * win[peak_ind].max():.0f}% of the winners ({peak_date:%Y}). Day 3 asks how much of momentum is "
        "industry momentum.",
    )
    colours = {
        n: c
        for n, c in zip(
            order,
            [
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
            ],
            strict=False,
        )
    }
    for k_, (comp, title) in enumerate([(win, "Winner decile"), (lose, "Loser decile")]):
        ax = fig.add_axes((0.05 + 0.4 * k_, 0.12, 0.36, 0.58))
        c = comp.reindex(columns=order).fillna(0).dropna(how="all")
        ax.stackplot(
            c.index, (100 * c.T).to_numpy(), colors=[colours.get(n, PALETTE["muted"]) for n in order], labels=order, alpha=0.9
        )
        ax.set_ylim(0, 100)
        tidy(ax, title=title, ylabel="% of names")
    ax.legend(fontsize=7.5, loc="upper left", bbox_to_anchor=(1.02, 1.0))
    caption(
        fig, SURV + " Industries: ICB, mapped from today's Wikipedia sector labels (a company's industry is taken as constant)."
    )
    return fig


# ------------------------------------------------------------------ 19. the formation spread


def spread_timing() -> Figure:
    s = _std()
    j = pd.concat([s.wml.rename("w"), s.spread.rename("sp")], axis=1).loc[START:].dropna()
    reg = M.predictive(j["w"], j["sp"])
    q = pd.qcut(j["sp"], 5, labels=False)
    means = [1200 * j["w"][q == i].mean() for i in range(5)]
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "A wider gap between winners and losers does not promise a bigger payoff",
        f"Next month's momentum return against the formation-period gap between winners' and losers' past returns. Sorted into "
        f"quintiles of the gap, the strategy earns {means[0]:.1f}% a year in the narrowest and {means[-1]:.1f}% in the widest; a "
        f"one-standard-deviation wider gap changes next month's return by {100 * reg.coef[1]:.2f} points (t = {reg.tstat[1]:.1f}). "
        "The widest gaps came in 2004 and 2010, after the market's recoveries, when the losers had fallen furthest.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.42, 0.58))
    ax.bar(range(1, 6), means, color=PALETTE["blue"], width=0.6)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    ax.set_xticks(range(1, 6))
    tidy(ax, title="By quintile of the formation gap", xlabel="quintile (5 = widest)", ylabel="next-month return, % a year")
    bx = fig.add_axes((0.56, 0.13, 0.41, 0.58))
    _shade(bx, labels=False)
    bx.plot(100 * j["sp"], color=PALETTE["violet"], lw=1.2)
    tidy(bx, title="Winners' minus losers' formation return", ylabel="percentage points")
    _window(bx, j.index[0], j.index[-1])
    caption(fig, SURV + " 12-1 deciles; gap = mean formation return of winners minus losers at formation; Newey-West t.")
    return fig


# ------------------------------------------------------------------ 20-21. sources and stability


def sources_compared() -> Figure:
    p = _panel()
    s = _std().wml.loc[START:]
    srcs = [
        ("survivors 12-1 decile", s, PALETTE["red"]),
        ("AQR MOM", p["MOM"].loc[START:], PALETTE["blue"]),
        ("AQR UMD", p["UMD"].loc[START:], PALETTE["violet"]),
        ("Exeter UMD", p["EX_UMD"].loc[START:], PALETTE["teal"]),
    ]
    sm = {n: M.summary(x) for n, x, _ in srcs}
    corr = s.corr(p["UMD"])
    fig = new_figure(14.5, 6.0)
    title_block(
        fig,
        "Survivor-built momentum tracks the survivorship-free factors, with more noise",
        f"The 12-1 decile strategy on today's FTSE 350 against AQR's and Exeter's momentum factors since 2001. It correlates "
        f"{corr:.2f} with AQR's UMD; Sharpe ratios: survivors {sm['survivors 12-1 decile']['sharpe']:.2f}, AQR MOM "
        f"{sm['AQR MOM']['sharpe']:.2f}, UMD {sm['AQR UMD']['sharpe']:.2f}. The decile strategy holds about 30 names a leg and "
        "is far more volatile: its level is noisy, its shape is not.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    _shade(ax, labels=False)
    for n, x, c in srcs:
        ax.plot(
            (1 + x.dropna()).cumprod(),
            color=c,
            lw=1.7,
            label=f"{n} (Sharpe {sm[n]['sharpe']:.2f}, vol {100 * sm[n]['vol']:.0f}%)",
        )
    ax.set_yscale("log")
    tidy(ax, ylabel="growth of one pound (log scale)")
    ax.legend(fontsize=8.5, loc="upper left")
    _window(ax, START)
    caption(fig, "AQR series converted to sterling (ADR 0002); Exeter ends June 2016. " + SURV)
    return fig


def rolling_stability() -> Figure:
    strategies = [
        ("12-1, K = 1", _std().wml, PALETTE["red"]),
        ("3-month formation, K = 3", _jt(3, 3).wml, PALETTE["green"]),
        ("residual 12-1", _residual().wml, PALETTE["violet"]),
        ("AQR UMD", _panel()["UMD"], PALETTE["slate"]),
    ]
    roll = {
        n: s.loc[START:].dropna().rolling(60).apply(lambda v: np.sqrt(12) * v.mean() / v.std(), raw=True)
        for n, s, _ in strategies
    }
    neg = {n: float((r.dropna() < 0).mean()) for n, r in roll.items()}
    fig = new_figure(14.5, 5.8)
    title_block(
        fig,
        "Every momentum variant has had five years with nothing to show",
        f"Five-year rolling Sharpe ratios. The share of five-year windows with a negative Sharpe ratio: 12-1 "
        f"{100 * neg['12-1, K = 1']:.0f}%, residual {100 * neg['residual 12-1']:.0f}%, AQR UMD {100 * neg['AQR UMD']:.0f}%. "
        "The hardest stretches were 2011-2013 and 2021-2025.",
    )
    ax = fig.add_axes((0.06, 0.13, 0.9, 0.58))
    _shade(ax, labels=False)
    for n, _, c in strategies:
        ax.plot(roll[n], color=c, lw=1.6, label=n)
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    tidy(ax, ylabel="Sharpe ratio, trailing 60 months")
    ax.legend(fontsize=8.5, ncol=4, loc="lower left")
    _window(ax, roll["12-1, K = 1"].dropna().index[0])
    caption(fig, SURV + " AQR UMD in sterling.")
    return fig
