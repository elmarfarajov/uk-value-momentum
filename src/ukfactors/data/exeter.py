"""The Exeter Xfi Centre's UK factors and portfolios (Gregory, Tharyan and Christidis, 2013).

The UK's equivalent of Kenneth French's library: SMB, HML and UMD built on UK listed firms
with the Fama-French method adapted to the UK (size breakpoints from the largest 350 firms),
with the market return and the risk-free rate, and the sorted portfolios behind them.

The web page states coverage to December 2017; the files themselves, dated November 2016,
end in June 2016. Use is limited to bona fide academic research, and publications must cite
Gregory, A., Tharyan, R. and Christidis, A. (2013), "Constructing and testing alternative
versions of the Fama-French and Carhart models in the UK", *Journal of Business Finance &
Accounting* 40(1-2), 172-214. The files are kept locally and never committed.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from . import store

BASE = "https://business-school.exeter.ac.uk/v8media/facultysites/ese/businessschool/documents/xfi"
FILES = {
    "monthlyfactors": "monthlyfactors.csv",
    "6ports_size_bm": "vw_sizebm_6groups.csv",
    "6ports_size_mom": "vw_sizemom_6groups.csv",
    "25ports_size_bm": "vw_sizebm_25groups.csv",
    "25ports_size_mom": "vw_sizemom_25groups.csv",
    "10ports_bm": "vw_bm_10groups.csv",
    "10ports_size": "vw_size_10groups.csv",
}


def fetch(root: Path | None = None) -> None:  # pragma: no cover - network
    for name in FILES:
        store.download(f"{BASE}/{name}.zip", f"exeter_{name}.zip", root)


def _read(archive: Path, member: str) -> pd.DataFrame:
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        chosen = member if member in names else next(n for n in names if n.endswith(".csv") and n.startswith("vw"))
        raw = z.read(chosen).decode("latin1")
    frame = pd.read_csv(io.StringIO(raw))
    month = frame.columns[0]
    dates = pd.PeriodIndex(frame[month].str.replace("m", "-", regex=False), freq="M").to_timestamp(how="end").normalize()
    return frame.drop(columns=month).set_index(dates).astype(float)


def factors(root: Path | None = None) -> pd.DataFrame:
    """SMB, HML, UMD, the risk-free rate, the market and the market excess return, monthly, in sterling (decimals)."""
    frame = _read(store.path("exeter_monthlyfactors.zip", root), FILES["monthlyfactors"])
    return frame.rename(columns=str.upper)


def portfolios(name: str, root: Path | None = None) -> pd.DataFrame:
    """Value-weighted portfolio returns of one Exeter sort, e.g. ``25ports_size_mom``."""
    return _read(store.path(f"exeter_{name}.zip", root), FILES[name])
