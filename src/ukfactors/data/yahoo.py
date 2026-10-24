"""Today's FTSE 350 companies and their price histories: the survivorship-biased sample, kept to measure the bias.

Free price data covers the companies listed *today*. A strategy built on them never holds a
company that later failed, was taken over cheaply or was delisted, and so it looks better than
anything an investor could have held. This module builds that sample on purpose: comparing a
momentum strategy run on it with AQR's survivorship-free UK momentum over the same months
measures how much the bias is worth.

Constituents, with their FTSE Industry Classification Benchmark sector, come from Wikipedia's
FTSE 100 and FTSE 250 pages (CC BY-SA); prices are Yahoo
Finance daily closes adjusted for dividends and splits, sampled at month end. Both are stored locally only.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from . import store

PAGES = {"ftse100": "https://en.wikipedia.org/wiki/FTSE_100_Index", "ftse250": "https://en.wikipedia.org/wiki/FTSE_250_Index"}
PRICES_FILE = "yahoo_ftse350_monthly.csv"
CONSTITUENTS_FILE = "ftse350_constituents.csv"


def _constituents_from(html: str, index: str) -> pd.DataFrame:
    for table in pd.read_html(io.StringIO(html)):
        cols = {str(c).lower(): c for c in table.columns}
        ticker = next((cols[c] for c in cols if c in ("ticker", "epic", "ticker symbol")), None)
        company = next((cols[c] for c in cols if c.startswith("company")), None)
        sector = next((cols[c] for c in cols if "sector" in c), None)
        if ticker is not None and company is not None and len(table) > 50:
            out = pd.DataFrame({"ticker": table[ticker].astype(str).str.strip(), "company": table[company].astype(str)})
            out["index"] = index
            out["sector"] = table[sector].astype(str).str.strip() if sector is not None else ""
            return out
    raise ValueError(f"no constituents table found for {index}")


def fetch_constituents(root: Path | None = None) -> pd.DataFrame:  # pragma: no cover - network
    import requests

    frames = []
    for index, url in PAGES.items():
        html = requests.get(url, headers={"User-Agent": store.USER_AGENT}, timeout=60).text
        frames.append(_constituents_from(html, index))
    out = pd.concat(frames, ignore_index=True)
    out["yahoo"] = out["ticker"].str.replace(".", "", regex=False).str.rstrip(".") + ".L"
    base = root or store.data_root()
    base.mkdir(parents=True, exist_ok=True)
    out.to_csv(base / CONSTITUENTS_FILE, index=False)
    store.record(CONSTITUENTS_FILE, " + ".join(PAGES.values()), base)
    return out


def fetch_prices(root: Path | None = None, start: str = "1999-01-01") -> pd.DataFrame:  # pragma: no cover - network
    import yfinance as yf

    base = root or store.data_root()
    tickers = pd.read_csv(base / CONSTITUENTS_FILE)["yahoo"].tolist()
    # Daily adjusted closes, sampled at each month's last trading day. Yahoo's own monthly bars apply
    # dividend adjustments inconsistently, which shows up as spikes in ex-dividend months that reverse
    # the month after (ADR 0011); daily closes do not have that defect.
    raw = yf.download(tickers, start=start, interval="1d", auto_adjust=True, progress=False, threads=True)
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = close.resample("ME").last().dropna(how="all", axis=1)
    close.to_csv(base / PRICES_FILE)
    store.record(PRICES_FILE, "Yahoo Finance via yfinance, daily adjusted closes sampled at month end", base)
    return close


def constituents(root: Path | None = None) -> pd.DataFrame:
    return pd.read_csv(store.path(CONSTITUENTS_FILE, root))


def prices(root: Path | None = None) -> pd.DataFrame:
    """Month-end adjusted closes of today's FTSE 350 companies (columns: Yahoo tickers)."""
    frame = pd.read_csv(store.path(PRICES_FILE, root), index_col=0, parse_dates=True)
    return frame.astype(float)
