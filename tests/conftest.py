"""Synthetic stand-ins for every raw file, in the sources' own formats, so the tests never need the licensed data."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

MONTHS = pd.date_range("1972-01-31", "2026-09-30", freq="ME")
COUNTRIES = ["USA", "GBR", "JPN", "DEU"]


def _aqr_sheet(frame: pd.DataFrame) -> pd.DataFrame:
    """AQR's layout: a few lines of notes, then a row starting DATE, then dates as mm/dd/yyyy."""
    notes = pd.DataFrame([["Synthetic AQR workbook"] + [None] * frame.shape[1], [None] * (frame.shape[1] + 1)])
    header = pd.DataFrame([["DATE", *frame.columns]])
    body = pd.DataFrame([[d.strftime("%m/%d/%Y"), *row] for d, row in zip(frame.index, frame.to_numpy(), strict=True)])
    return pd.concat([notes, header, body], ignore_index=True)


def write_data(root: Path, seed: int = 0) -> dict[str, pd.Series]:
    rng = np.random.default_rng(seed)
    n = MONTHS.size
    fx = pd.Series(np.cumprod(1 + rng.normal(0, 0.025, n)) * 2.4, index=MONTHS)
    rf_uk_annual = pd.Series(np.clip(5 + np.cumsum(rng.normal(0, 0.3, n)), 0.1, 15), index=MONTHS)
    rf_us = pd.Series(np.full(n, 0.003), index=MONTHS)
    x = fx.pct_change()
    sterling = {
        "MKT": pd.Series(rng.normal(0.006, 0.045, n), index=MONTHS),
        "SMB": pd.Series(rng.normal(0.001, 0.03, n), index=MONTHS),
        "HML": pd.Series(rng.normal(0.003, 0.03, n), index=MONTHS),
        "UMD": pd.Series(rng.normal(0.008, 0.04, n), index=MONTHS),
    }
    # AQR reports in dollars: long/short factors times (1 + x); the market as a dollar excess over the US bill
    rf_uk = (1 + rf_uk_annual / 100) ** (1 / 12) - 1
    usd = {c: s * (1 + x) for c, s in sterling.items() if c != "MKT"}
    usd["MKT"] = (1 + sterling["MKT"] + rf_uk) * (1 + x) - 1 - rf_us

    vme = pd.DataFrame(index=MONTHS)
    for code in ("US90", "UK90", "ROE90", "JP90"):
        vme[f"VALLS_VME_{code}"] = rng.normal(0.003, 0.025, n)
        vme[f"MOMLS_VME_{code}"] = rng.normal(0.006, 0.035, n)
    vme["VAL^SS"] = vme.filter(like="VALLS").mean(axis=1)
    vme["MOM^SS"] = vme.filter(like="MOMLS").mean(axis=1)
    vme.loc[:"1981-06", "VALLS_VME_UK90"] = np.nan
    root.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(root / "aqr_vme_monthly.xlsx") as w:
        _aqr_sheet(vme).to_excel(w, sheet_name="VME Factors", header=False, index=False)

    def country(gbr: pd.Series) -> pd.DataFrame:
        frame = pd.DataFrame({c: rng.normal(0.004, 0.04, n) for c in COUNTRIES}, index=MONTHS)
        frame["GBR"] = gbr.to_numpy()
        return frame

    with pd.ExcelWriter(root / "aqr_qmj_monthly.xlsx") as w:
        for sheet, key in (("MKT", "MKT"), ("SMB", "SMB"), ("HML FF", "HML"), ("UMD", "UMD")):
            _aqr_sheet(country(usd[key])).to_excel(w, sheet_name=sheet, header=False, index=False)
        _aqr_sheet(country(usd["HML"] * 0.8)).to_excel(w, sheet_name="HML Devil", header=False, index=False)
        _aqr_sheet(country(pd.Series(rng.normal(0.004, 0.02, n), index=MONTHS))).to_excel(
            w, sheet_name="QMJ Factors", header=False, index=False
        )
        _aqr_sheet(pd.DataFrame({"Risk Free Rate": rf_us})).to_excel(w, sheet_name="RF", header=False, index=False)

    ex = pd.DataFrame(index=MONTHS).loc["1980-10":"2016-06"]
    idx = ex.index
    ex.insert(0, "month", [f"{d.year}m{d.month}" for d in idx])
    for c in ("SMB", "HML", "UMD"):
        ex[c.lower()] = (sterling[c].loc[idx] + rng.normal(0, 0.005, idx.size)).to_numpy()
    ex["rf"] = rf_uk.loc[idx].to_numpy()
    ex["rm"] = (sterling["MKT"].loc[idx] + rf_uk.loc[idx]).to_numpy()
    ex["rmrf"] = sterling["MKT"].loc[idx].to_numpy()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("monthlyfactors.csv", ex.to_csv(index=False))
    (root / "exeter_monthlyfactors.zip").write_bytes(buffer.getvalue())

    # FRED: the rate monthly at the first of each month, the exchange rate daily with "." for holidays
    first = MONTHS - pd.offsets.MonthBegin(1)
    pd.DataFrame({"observation_date": first.strftime("%Y-%m-%d"), "IR3TIB01GBM156N": rf_uk_annual.to_numpy()}).to_csv(
        root / "fred_uk_rate.csv", index=False
    )
    days = pd.bdate_range("1971-12-01", "2026-09-30")
    level = fx.reindex(days, method="bfill").ffill().astype(object)
    last_day = days.to_series().groupby(days.to_period("M")).max()
    holiday = (np.arange(days.size) % 37 == 0) & ~days.isin(last_day)
    level[holiday] = "."
    pd.DataFrame({"observation_date": days.strftime("%Y-%m-%d"), "DEXUSUK": level.to_numpy()}).to_csv(
        root / "fred_gbpusd.csv", index=False
    )

    stocks = pd.DataFrame(
        np.exp(np.cumsum(rng.normal(0.007, 0.08, (MONTHS.size, 60)), axis=0)) * 100.0,
        index=MONTHS,
        columns=[f"S{i:02d}.L" for i in range(60)],
    ).loc["1999-01":]
    stocks.iloc[40:60, 0] /= 100.0  # a pence/pound flip, to be excluded
    stocks.to_csv(root / "yahoo_ftse350_monthly.csv")
    return {"fx": fx, "rf_uk": rf_uk, "rf_us": rf_us, **{f"gbp_{c}": s for c, s in sterling.items()}}


@pytest.fixture(scope="session")
def synthetic(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, pd.Series]]:
    root = tmp_path_factory.mktemp("raw")
    return root, write_data(root)


@pytest.fixture(scope="session")
def data_root(synthetic: tuple[Path, dict[str, pd.Series]]) -> Path:
    return synthetic[0]


@pytest.fixture(scope="session")
def truth(synthetic: tuple[Path, dict[str, pd.Series]]) -> dict[str, pd.Series]:
    return synthetic[1]


@pytest.fixture
def use_data(data_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("UKF_DATA", str(data_root))
    return data_root


@pytest.fixture
def no_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("UKF_DATA", str(tmp_path))
    return tmp_path
