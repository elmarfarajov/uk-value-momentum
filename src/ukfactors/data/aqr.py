"""AQR's data library: value and momentum everywhere, and quality minus junk with its companion factors.

Two workbooks, both updated monthly and rebuilt in full history at each update:

* **Value and Momentum Everywhere** (Asness, Moskowitz and Pedersen, 2013): rank-weighted
  long/short value (VAL) and momentum (MOM) factors for stock selection in the US, the UK,
  continental Europe and Japan, and for four asset classes, from January 1972.
* **Quality Minus Junk** (Asness, Frazzini and Pedersen, 2019), whose workbook also carries
  each country's market, size (SMB), value (HML in Fama-French's form and in AQR's "Devil"
  form with current prices) and momentum (UMD) factors. For the UK: market from 1986, the
  rest from 1987-1988, QMJ from 1993.

AQR builds the UK factors from Datastream (1981-1989) and Compustat/XpressFeed (1990-), with
delisted companies included: the long history is free of survivorship bias. AQR asks to be
cited as "AQR Capital Management, LLC"; the workbooks are kept locally and never committed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import store

VME_URL = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Value-and-Momentum-Everywhere-Factors-Monthly.xlsx"
QMJ_URL = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Quality-Minus-Junk-Factors-Monthly.xlsx"
VME_FILE = "aqr_vme_monthly.xlsx"
QMJ_FILE = "aqr_qmj_monthly.xlsx"

VME_COLUMNS = {
    "VALLS_VME_US90": "VAL_US",
    "MOMLS_VME_US90": "MOM_US",
    "VALLS_VME_UK90": "VAL_UK",
    "MOMLS_VME_UK90": "MOM_UK",
    "VALLS_VME_ROE90": "VAL_EU",
    "MOMLS_VME_ROE90": "MOM_EU",
    "VALLS_VME_JP90": "VAL_JP",
    "MOMLS_VME_JP90": "MOM_JP",
    "VAL^SS": "VAL_EQ",
    "MOM^SS": "MOM_EQ",
}
COUNTRY_SHEETS = {"MKT": "MKT", "SMB": "SMB", "HML FF": "HML", "HML Devil": "HML_DEVIL", "UMD": "UMD", "QMJ Factors": "QMJ"}


def fetch(root: Path | None = None) -> None:  # pragma: no cover - network
    store.download(VME_URL, VME_FILE, root)
    store.download(QMJ_URL, QMJ_FILE, root)


def _table(path: Path, sheet: str) -> pd.DataFrame:
    """A sheet whose data start under a row beginning ``DATE``; returns a month-end indexed frame."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    header = int(raw.index[raw.iloc[:, 0].astype(str).str.strip().str.upper().eq("DATE")][0])
    names = [str(c).strip() for c in raw.iloc[header]]
    body = raw.iloc[header + 1 :].copy()
    body.columns = names
    body = body.dropna(subset=["DATE"])
    body["DATE"] = pd.to_datetime(body["DATE"], format="%m/%d/%Y", errors="coerce")
    body = body.dropna(subset=["DATE"]).set_index("DATE")
    body.index = body.index + pd.offsets.MonthEnd(0)
    return body.apply(pd.to_numeric, errors="coerce").dropna(how="all")


def vme(root: Path | None = None) -> pd.DataFrame:
    """Monthly excess returns of AQR's value and momentum factors (decimals), renamed ``VAL_UK``, ``MOM_UK`` and so on."""
    frame = _table(store.path(VME_FILE, root), "VME Factors")
    keep = [c for c in VME_COLUMNS if c in frame.columns]
    return frame[keep].rename(columns=VME_COLUMNS).astype(float)


def country(factor: str, root: Path | None = None) -> pd.DataFrame:
    """One AQR factor (``MKT``, ``SMB``, ``HML``, ``HML_DEVIL``, ``UMD`` or ``QMJ``) for every country, monthly."""
    sheet = {v: k for k, v in COUNTRY_SHEETS.items()}[factor]
    return _table(store.path(QMJ_FILE, root), sheet).astype(float)


def uk(root: Path | None = None) -> pd.DataFrame:
    """The UK columns of every AQR series in one frame: VAL, MOM, MKT, SMB, HML, HML_DEVIL, UMD, QMJ."""
    v = vme(root)
    out = pd.DataFrame({"VAL": v["VAL_UK"], "MOM": v["MOM_UK"]})
    for factor in COUNTRY_SHEETS.values():
        out[factor] = country(factor, root)["GBR"]
    return out


def us_bill(root: Path | None = None) -> pd.Series:
    """AQR's risk-free rate (the US one-month Treasury bill), monthly."""
    frame = _table(store.path(QMJ_FILE, root), "RF")
    return frame.iloc[:, 0].astype(float).rename("RF_US")
