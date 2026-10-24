"""Today's FTSE 350 companies grouped into the eleven ICB industries.

Wikipedia lists each company's ICB *sector* in free text that varies between pages and over
time ("Travel & Leisure", "travel and leisure", "Banking services"). The sectors are mapped to
the eleven ICB industries by ordered keyword rules: the first rule whose keyword appears in the
lower-cased sector name wins, so "gas, water & multiutilities" is a utility before "gas" can make
it energy. Every sector seen so far maps; an unseen one falls to "Other" and is reported.
"""

from __future__ import annotations

import pandas as pd

INDUSTRIES = (
    "Financials",
    "Real Estate",
    "Industrials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Health Care",
    "Basic Materials",
    "Energy",
    "Utilities",
    "Telecommunications",
    "Technology",
)

RULES: tuple[tuple[str, str], ...] = (
    ("real estate", "Real Estate"),
    ("utilit", "Utilities"),
    ("gas, water", "Utilities"),
    ("electricity", "Utilities"),
    ("electrical utilities", "Utilities"),
    ("telecom", "Telecommunications"),
    ("mobile", "Telecommunications"),
    ("pharma", "Health Care"),  # before "technology", which "biotechnology" contains
    ("health", "Health Care"),
    ("software", "Technology"),
    ("technology", "Technology"),
    ("mining", "Basic Materials"),
    ("metals", "Basic Materials"),
    ("chemical", "Basic Materials"),
    ("basic resources", "Basic Materials"),
    ("oil", "Energy"),
    ("energy", "Energy"),
    ("food", "Consumer Staples"),
    ("beverage", "Consumer Staples"),
    ("tobacco", "Consumer Staples"),
    ("personal products", "Consumer Staples"),
    ("consumer staples", "Consumer Staples"),
    ("household goods", "Consumer Discretionary"),
    ("home construction", "Consumer Discretionary"),
    ("homebuilding", "Consumer Discretionary"),
    ("retail", "Consumer Discretionary"),
    ("media", "Consumer Discretionary"),
    ("travel", "Consumer Discretionary"),
    ("leisure", "Consumer Discretionary"),
    ("personal goods", "Consumer Discretionary"),
    ("consumer digital", "Consumer Discretionary"),
    ("aerospace", "Industrials"),
    ("construction", "Industrials"),
    ("industrial", "Industrials"),
    ("support services", "Industrials"),
    ("electronic", "Industrials"),
    ("engineering", "Industrials"),
    ("containers", "Industrials"),
    ("bank", "Financials"),
    ("insurance", "Financials"),
    ("financ", "Financials"),
    ("invest", "Financials"),
    ("hedge fund", "Financials"),
)


def industry(sector: str) -> str:
    """The ICB industry of a free-text ICB sector name ("Other" if no rule matches)."""
    s = str(sector).lower()
    for key, name in RULES:
        if key in s:
            return name
    return "Other"


def by_ticker(constituents: pd.DataFrame) -> pd.Series:
    """Industry of each Yahoo ticker, from a constituents table with ``yahoo`` and ``sector`` columns."""
    return pd.Series([industry(s) for s in constituents["sector"]], index=constituents["yahoo"], name="industry")
