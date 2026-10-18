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
}
RAW = ["aqr_vme_monthly.xlsx", "aqr_qmj_monthly.xlsx", "exeter_monthlyfactors.zip", "fred_uk_rate.csv", "fred_gbpusd.csv"]
STOCKS = ["yahoo_ftse350_monthly.csv"]


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


def items() -> tuple[Item, ...]:
    from . import foundation as f

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
