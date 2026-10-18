"""Public-domain UK series from FRED: the short rate and the pound against the dollar.

* ``IR3TIB01GBM156N``: the UK three-month interbank rate (OECD Main Economic Indicators),
  monthly from 1957, in percent a year. It is this project's UK risk-free rate; the UK
  Treasury-bill series stops in 2017.
* ``DEXUSUK``: US dollars per pound, daily from 1971 (Federal Reserve H.10); month-end values
  are used to tell whether a series is in sterling or in dollars.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import store

SERIES = {"uk_rate": "IR3TIB01GBM156N", "gbpusd": "DEXUSUK"}


def fetch(root: Path | None = None) -> None:  # pragma: no cover - network
    for name, code in SERIES.items():
        store.download(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}", f"fred_{name}.csv", root)


def _series(name: str, root: Path | None = None) -> pd.Series:
    frame = pd.read_csv(store.path(f"fred_{name}.csv", root), na_values=".")
    dates = pd.to_datetime(frame.iloc[:, 0])
    return pd.Series(pd.to_numeric(frame.iloc[:, 1], errors="coerce").to_numpy(), index=dates, name=name).dropna()


def uk_rate(root: Path | None = None) -> pd.Series:
    """The monthly UK risk-free return implied by the month's three-month rate (OECD monthly average, decimals)."""
    annual = _series("uk_rate", root) / 100.0
    monthly = (1.0 + annual) ** (1.0 / 12.0) - 1.0
    monthly.index = monthly.index + pd.offsets.MonthEnd(0)
    return monthly.rename("RF_UK")


def gbpusd(root: Path | None = None) -> pd.Series:
    """US dollars per pound at each month end."""
    daily = _series("gbpusd", root)
    return daily.resample("ME").last().rename("GBPUSD")
