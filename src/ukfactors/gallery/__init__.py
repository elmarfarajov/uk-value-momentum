"""The chart gallery: every figure the documentation shows, rebuilt from source with ``ukf gallery``.

Each chart is an :class:`Item` - the file it writes, what it shows, the function that draws
it and the day it belongs to - so the gallery page (``docs/GALLERY.md``) and the images cannot
drift apart. Chart modules are imported only when the charts are listed, so the package imports
without them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from matplotlib.figure import Figure

from ..data import store
from .style import save

DAYS: dict[int, str] = {
    1: "Fifty-four years of UK factors",
    2: "The anatomy of momentum",
    3: "Industry momentum and sector rotation",
}
RAW = ["aqr_vme_monthly.xlsx", "aqr_qmj_monthly.xlsx", "exeter_monthlyfactors.zip", "fred_uk_rate.csv", "fred_gbpusd.csv"]
STOCKS = ["yahoo_ftse350_monthly.csv"]
PORTS = [
    f"exeter_{n}.zip"
    for n in ("6ports_size_bm", "6ports_size_mom", "25ports_size_bm", "25ports_size_mom", "10ports_bm", "10ports_size")
]


@dataclass(frozen=True)
class Item:
    filename: str
    title: str
    description: str
    build: Callable[[], Figure]
    day: int
    requires: tuple[str, ...] = tuple(RAW)

    def available(self) -> bool:
        return store.available(list(self.requires))


S = tuple(RAW + STOCKS)
P = tuple(RAW + PORTS)


def items() -> tuple[Item, ...]:
    from . import anatomy as a
    from . import deepdive as d
    from . import foundation as f
    from . import industries as ind

    return (
        Item(
            "long-history.png",
            "Fifty-four years of UK value and momentum",
            "Growth of one pound in each UK factor, in sterling, 1972-2026.",
            f.long_history,
            1,
        ),
        Item(
            "rolling-sharpe.png",
            "A premium is an average over decades",
            "Five-year rolling Sharpe ratios of value, momentum and quality.",
            f.rolling_sharpe,
            1,
        ),
        Item(
            "two-sources.png",
            "Two independent sources",
            "AQR against Exeter, month by month, for HML, UMD and SMB.",
            f.two_sources,
            1,
        ),
        Item(
            "exeter-vs-paper.png",
            "The files are not the paper",
            "Exeter's downloadable factors against the statistics printed in the 2013 paper.",
            f.exeter_vs_paper,
            1,
        ),
        Item(
            "currency.png",
            "AQR's UK factors are in dollars",
            "AQR's UK market against Exeter's in sterling and in dollars, and the gap against the exchange rate.",
            f.currency,
            1,
        ),
        Item(
            "distributions.png",
            "Fat tails",
            "Monthly return distributions against normal ones with the same mean and volatility.",
            f.distributions,
            1,
        ),
        Item(
            "drawdowns.png",
            "The pain behind the premium",
            "Drawdowns of value, momentum, quality and the market.",
            f.drawdowns,
            1,
        ),
        Item(
            "world-correlations.png",
            "Value and momentum hedge each other",
            "Correlations of value and momentum across four markets and UK factors.",
            f.world_correlations,
            1,
        ),
        Item(
            "survivorship.png",
            "Free data remembers only the winners",
            "Today's FTSE 350 against the market, and momentum on survivors against AQR's.",
            f.survivorship_bias,
            1,
            tuple(RAW + STOCKS),
        ),
        Item("decades.png", "Decade by decade", "Annualised factor returns by decade with Newey-West intervals.", f.decades, 1),
        Item(
            "uk-vs-world.png",
            "Momentum works in the UK and Europe, value in Japan",
            "Sharpe ratios of value and momentum in four stock markets.",
            f.uk_vs_world,
            1,
        ),
        Item(
            "factor-alphas.png",
            "Value is a premium once momentum is held constant",
            "CAPM and multi-factor alphas with Newey-West intervals.",
            d.factor_alphas,
            1,
        ),
        Item(
            "value-momentum-mix.png",
            "Half value, half momentum",
            "Sharpe ratio and drawdown of the value-momentum mix by weight.",
            d.value_momentum_mix,
            1,
        ),
        Item(
            "rolling-correlation.png",
            "The hedge has held for forty years",
            "Three-year rolling correlations of value and momentum.",
            d.rolling_correlation,
            1,
        ),
        Item(
            "portfolio-grids.png",
            "Twenty-five UK portfolios",
            "Exeter's 5x5 sorts on size and value, and on size and momentum.",
            d.portfolio_grids,
            1,
            tuple(RAW + PORTS),
        ),
        Item(
            "factor-legs.png",
            "Momentum is a story about losers",
            "The six 2x3 portfolios behind HML and UMD.",
            d.factor_legs,
            1,
            tuple(RAW + PORTS),
        ),
        Item(
            "deciles.png",
            "Value sorted finely",
            "Ten portfolios on book-to-market and on size.",
            d.deciles,
            1,
            tuple(RAW + PORTS),
        ),
        Item("calendar-years.png", "One cell per year", "Calendar-year returns of every factor, 1972-2025.", d.calendar_years, 1),
        Item("start-date.png", "When you start counting", "Sharpe ratio from each start year to 2026.", d.start_date, 1),
        Item(
            "sharpe-bootstrap.png", "How sure can we be?", "Bootstrap distributions of every Sharpe ratio.", d.sharpe_bootstrap, 1
        ),
        Item(
            "autocorrelation.png",
            "Factor returns remember last month",
            "Autocorrelations and Ljung-Box tests.",
            d.autocorrelation,
            1,
        ),
        Item(
            "drawdown-episodes.png",
            "Five worst losing spells",
            "Peak, trough and recovery of the deepest drawdowns.",
            d.drawdown_episodes,
            1,
        ),
        Item(
            "rates-and-currency.png",
            "Two currencies, two risk-free rates",
            "UK and US risk-free rates, and the pound in dollars.",
            d.rates_and_currency,
            1,
        ),
        Item(
            "market-states.png",
            "Momentum earns its keep when the market falls",
            "Factor returns in up and down markets.",
            d.market_states,
            1,
        ),
        Item(
            "jt-grid.png",
            "Jegadeesh and Titman in London",
            "Mean and Sharpe ratio of every J x K momentum strategy.",
            a.jt_grid,
            2,
            S,
        ),
        Item(
            "skip-and-reversal.png",
            "Why momentum skips a month",
            "The skip month and short-term reversal.",
            a.skip_and_reversal,
            2,
            S,
        ),
        Item(
            "event-time.png",
            "A few good months, then years of giving back",
            "Winners minus losers for 60 months after formation.",
            a.event_time,
            2,
            S,
        ),
        Item(
            "intermediate-vs-recent.png",
            "Recent or intermediate momentum",
            "Months t-12 to t-7 against t-6 to t-2.",
            a.intermediate_vs_recent,
            2,
            S,
        ),
        Item(
            "residual-momentum.png",
            "Residual momentum",
            "Raw against residual momentum: growth and drawdowns.",
            a.residual_momentum,
            2,
            S,
        ),
        Item(
            "residual-exposures.png",
            "Raw momentum bets on the market",
            "Rolling market beta of raw and residual momentum.",
            a.residual_exposures,
            2,
            S,
        ),
        Item(
            "high-vs-momentum.png",
            "Nearness to the 52-week high",
            "The 52-week-high strategy against 12-1 momentum.",
            a.high_vs_momentum,
            2,
            S,
        ),
        Item(
            "momentum-market-states.png",
            "Momentum after rising and falling markets",
            "Momentum returns by the market's past 24 months.",
            a.market_states,
            2,
            S,
        ),
        Item(
            "conditional-beta.png",
            "Momentum's beta follows the market's past",
            "Rolling beta of UMD against the market's past return.",
            a.conditional_beta,
            2,
        ),
        Item(
            "calendar.png",
            "UK momentum loses in April",
            "Mean momentum return by calendar month, 1972-2026.",
            a.calendar_chart,
            2,
        ),
        Item(
            "april-legs.png",
            "In April the losers rebound",
            "Exeter's winners and losers in April and other months.",
            a.april_legs,
            2,
            P,
        ),
        Item(
            "calendar-sources.png",
            "April in every source",
            "Calendar-month means of five momentum series.",
            a.calendar_sources,
            2,
            S,
        ),
        Item(
            "momentum-size.png", "Momentum among small and big companies", "Exeter's small and big momentum.", a.size_chart, 2, P
        ),
        Item("momentum-deciles.png", "Ten momentum deciles", "Next-month returns of 12-1 deciles.", a.decile_returns, 2, S),
        Item(
            "momentum-legs.png",
            "Which leg earns the premium",
            "Long and short legs of momentum.",
            a.legs_chart,
            2,
            tuple(RAW + STOCKS + PORTS),
        ),
        Item(
            "turnover.png",
            "Momentum trades a lot",
            "Turnover and break-even trading costs by holding period.",
            a.turnover_chart,
            2,
            S,
        ),
        Item(
            "persistence.png",
            "Winners stay winners for months",
            "Quintile transition matrices at one and twelve months.",
            a.persistence,
            2,
            S,
        ),
        Item("spells.png", "How long a stock stays a winner", "Spells in the winner and loser deciles.", a.spells_chart, 2, S),
        Item(
            "sector-composition.png",
            "Momentum is partly an industry bet",
            "Industry shares of the winner and loser deciles.",
            a.sector_composition,
            2,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "spread-timing.png",
            "The formation gap",
            "Next-month momentum against the winners-losers formation gap.",
            a.spread_timing,
            2,
            S,
        ),
        Item(
            "sources-compared.png",
            "Survivors against the factors",
            "Survivor-built momentum against AQR and Exeter.",
            a.sources_compared,
            2,
            S,
        ),
        Item(
            "rolling-stability.png",
            "Five years with nothing to show",
            "Rolling five-year Sharpe ratios of momentum variants.",
            a.rolling_stability,
            2,
            S,
        ),
        Item(
            "industry-paths.png",
            "Twelve UK industries",
            "Growth of one pound in each industry, 2000-2026.",
            ind.industry_paths,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "industry-years.png",
            "Industry returns year by year",
            "Calendar-year returns of twelve industries.",
            ind.industry_years,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "industry-risk-return.png",
            "Industries: risk, return and correlation",
            "Mean against volatility, and the correlation matrix.",
            ind.industry_risk_return,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "industry-sizes.png",
            "Stocks behind each industry",
            "Members per industry over time.",
            ind.group_sizes,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "industry-grid.png",
            "Industry momentum by horizon",
            "J x K grid of industry momentum.",
            ind.industry_grid,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "one-month.png",
            "Stocks reverse, industries continue",
            "Fama-MacBeth slopes on last month's returns.",
            ind.one_month,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "industry-vs-stock.png",
            "Industry out of stock momentum",
            "Stock, industry-neutral and industry momentum.",
            ind.industry_vs_stock_paths,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "spanning.png",
            "Spanning tests",
            "Alphas of each momentum strategy on another.",
            ind.spanning_chart,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "fama-macbeth.png",
            "Fama-MacBeth: own against industry",
            "Slopes on own, neutral and industry 12-1 returns.",
            ind.fama_macbeth_chart,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "placebo.png",
            "Real industries against random groups",
            "Industry momentum and dispersion for random groupings.",
            ind.placebo_chart,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "dispersion.png",
            "Industry dispersion",
            "Dispersion of industry returns and next-month industry momentum.",
            ind.dispersion_chart,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "lead-lag.png",
            "Do some industries lead others?",
            "Lagged cross-correlations of industry returns.",
            ind.lead_lag,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "rotation.png",
            "Sector rotation year by year",
            "Long and short legs of industry momentum by year.",
            ind.rotation,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "industry-event-time.png",
            "Industry signals fade",
            "Event-time returns of industry momentum.",
            ind.industry_event_time,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "industry-states.png",
            "Industry momentum and market states",
            "Returns after rising and falling markets.",
            ind.industry_states,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "industry-calendar.png",
            "April and industries",
            "Calendar-month means of industry and neutral momentum.",
            ind.industry_calendar,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "industry-turnover.png",
            "Industry momentum turnover",
            "Monthly turnover of industry and stock momentum.",
            ind.turnover_chart,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "within-industries.png",
            "Momentum within industries",
            "Within-group momentum in the largest groups.",
            ind.within_industries,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "trusts.png",
            "Investment-trust momentum",
            "Trusts against operating companies.",
            ind.trusts_chart,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
        Item(
            "industry-stability.png",
            "Five-year windows",
            "Rolling Sharpe ratios of momentum variants.",
            ind.stability,
            3,
            tuple(RAW + STOCKS + ["ftse350_constituents.csv"]),
        ),
    )


def build(out_dir: str | Path = "docs/images", only: str | None = None) -> list[Path]:
    written = []
    for item in items():
        if only and only not in (item.filename, str(item.day)):
            continue
        if not item.available():
            print(f"skipped {item.filename}: needs the local raw data (ukf data fetch)")
            continue
        written.append(save(item.build(), Path(out_dir) / item.filename))
    return written


def markdown(prefix: str = "images") -> str:
    lines = ["# Gallery", "", "Every chart is rebuilt from source with `ukf gallery` after `ukf data fetch`.", ""]
    for day, title in DAYS.items():
        lines += [f"## Day {day}: {title}", ""]
        for item in items():
            if item.day == day:
                lines += [f"**{item.title}** - {item.description}", "", f"![{item.title}]({prefix}/{item.filename})", ""]
    return "\n".join(lines)
