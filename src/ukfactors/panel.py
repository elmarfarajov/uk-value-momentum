"""One aligned monthly panel of UK factors, every series in sterling.

**AQR's UK factors are in US dollars.** AQR's UK market return correlates 0.996 with Exeter's
sterling market return converted to dollars, and only 0.82 with the sterling return itself; the
gap between AQR's series and the sterling one loads one-for-one on the pound's move against the
dollar. Every AQR series is therefore converted before it meets a sterling one. With ``x`` the
month's change in dollars per pound:

* a long/short factor, ``r_L - r_S`` in sterling, is ``(r_L - r_S)(1 + x)`` in dollars, so the
  sterling factor is the dollar factor divided by ``1 + x``;
* the market's dollar excess return over the US bill, ``MKT``, gives a dollar return
  ``MKT + rf_US``, a sterling return ``(1 + MKT + rf_US) / (1 + x) - 1``, and a sterling
  excess return over the UK rate.

Columns: ``VAL``, ``MOM``, ``MKT``, ``SMB``, ``HML``, ``HML_DEVIL``, ``UMD``, ``QMJ`` (AQR, in
sterling); ``EX_RMRF``, ``EX_SMB``, ``EX_HML``, ``EX_UMD``, ``EX_RF`` (Exeter, sterling);
``RF_UK`` (FRED); ``FX`` (the pound's monthly change against the dollar).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .data import aqr, exeter, fred

LONG_SHORT = ("VAL", "MOM", "SMB", "HML", "HML_DEVIL", "UMD", "QMJ")


def to_sterling(usd: pd.DataFrame, fx: pd.Series, rf_us: pd.Series, rf_uk: pd.Series) -> pd.DataFrame:
    """Convert AQR's dollar factors to sterling: long/short factors by ``/(1 + x)``, the market as an excess over the UK rate."""
    out = pd.DataFrame(index=usd.index)
    x = fx.reindex(usd.index)
    for c in usd.columns:
        if c in LONG_SHORT:
            out[c] = usd[c] / (1.0 + x)
    if "MKT" in usd.columns:
        dollar = usd["MKT"] + rf_us.reindex(usd.index)
        out["MKT"] = (1.0 + dollar) / (1.0 + x) - 1.0 - rf_uk.reindex(usd.index)
    return out[[c for c in usd.columns if c in out.columns]]


def build(root: Path | None = None) -> pd.DataFrame:
    fx = fred.gbpusd(root).pct_change().rename("FX")
    rf_uk = fred.uk_rate(root)
    usd = aqr.uk(root)
    gbp = to_sterling(usd, fx, aqr.us_bill(root), rf_uk)
    ex = exeter.factors(root)
    ex = ex.rename(columns={c: f"EX_{c}" for c in ex.columns}).drop(columns=["EX_RM"])
    panel = pd.concat([gbp, ex, rf_uk, fx], axis=1, sort=True)
    return panel.loc["1972-01":].dropna(how="all")


def international(root: Path | None = None) -> pd.DataFrame:
    """AQR's value and momentum in the four stock-selection markets and their average (dollars, long/short)."""
    return aqr.vme(root)
