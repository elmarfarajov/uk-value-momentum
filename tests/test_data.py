from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ukfactors import panel
from ukfactors.data import aqr, exeter, fred, store, yahoo


def test_data_root_follows_the_environment(no_data: Path) -> None:
    assert store.data_root() == no_data
    assert not store.available(["aqr_vme_monthly.xlsx"])


def test_manifest_records_url_time_and_hash(tmp_path: Path) -> None:
    (tmp_path / "f.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    store.record("f.csv", "https://example.org/f.csv", tmp_path)
    entry = store.manifest(tmp_path)["f.csv"]
    assert entry["url"] == "https://example.org/f.csv"
    assert entry["sha256"] == store.sha256(tmp_path / "f.csv")
    assert len(entry["sha256"]) == 64 and "T" in entry["fetched"]
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")).keys() == {"f.csv"}


def test_aqr_vme_finds_the_header_and_renames(use_data: Path) -> None:
    v = aqr.vme()
    assert {"VAL_UK", "MOM_UK", "VAL_JP", "MOM_EQ"} <= set(v.columns)
    assert v.index[0] == pd.Timestamp("1972-01-31") and v.index.is_month_end.all()
    assert v["VAL_UK"].first_valid_index() == pd.Timestamp("1981-07-31")


def test_aqr_uk_takes_the_gbr_column(use_data: Path, truth: dict[str, pd.Series]) -> None:
    u = aqr.uk()
    assert list(u.columns) == ["VAL", "MOM", "MKT", "SMB", "HML", "HML_DEVIL", "UMD", "QMJ"]
    expected = truth["gbp_UMD"] * (1 + truth["fx"].pct_change())
    pd.testing.assert_series_equal(u["UMD"].dropna(), expected.dropna(), check_names=False, check_freq=False)
    assert aqr.us_bill().name == "RF_US"


def test_exeter_parses_stata_months(use_data: Path) -> None:
    f = exeter.factors()
    assert list(f.columns) == ["SMB", "HML", "UMD", "RF", "RM", "RMRF"]
    assert f.index[0] == pd.Timestamp("1980-10-31") and f.index[-1] == pd.Timestamp("2016-06-30")


def test_fred_rate_is_monthly_and_dated_at_month_end(use_data: Path, truth: dict[str, pd.Series]) -> None:
    r = fred.uk_rate()
    assert r.index.is_month_end.all()
    pd.testing.assert_series_equal(r, truth["rf_uk"].rename("RF_UK"), check_freq=False, check_index_type=False, check_names=False)


def test_fred_exchange_rate_skips_holidays(use_data: Path, truth: dict[str, pd.Series]) -> None:
    fx = fred.gbpusd()
    assert fx.notna().all()
    np.testing.assert_allclose(fx.loc["1972":].to_numpy(), truth["fx"].to_numpy())


def test_sterling_conversion_inverts_the_dollar_translation(use_data: Path, truth: dict[str, pd.Series]) -> None:
    p = panel.build()
    for c in ("SMB", "HML", "UMD", "MKT"):
        got = p[c].dropna()
        np.testing.assert_allclose(got.to_numpy(), truth[f"gbp_{c}"].loc[got.index].to_numpy(), atol=1e-12)


def test_to_sterling_by_hand() -> None:
    idx = pd.date_range("2000-01-31", periods=2, freq="ME")
    usd = pd.DataFrame({"VAL": [0.011, -0.02], "MKT": [0.05, 0.0]}, index=idx)
    fx = pd.Series([0.1, -0.5], index=idx)
    rf = pd.Series([0.0, 0.0], index=idx)
    out = panel.to_sterling(usd, fx, rf, rf)
    assert out.loc[idx[0], "VAL"] == pytest.approx(0.01)  # 1.1% in dollars is 1% in sterling when the pound rose 10%
    assert out.loc[idx[0], "MKT"] == pytest.approx(1.05 / 1.1 - 1)
    assert out.loc[idx[1], "MKT"] == pytest.approx(1.0)  # flat in dollars while the pound halved: doubled in sterling


def test_panel_columns_and_start(use_data: Path) -> None:
    p = panel.build()
    assert {"VAL", "MOM", "MKT", "EX_RMRF", "EX_UMD", "RF_UK", "FX"} <= set(p.columns)
    assert "EX_RM" not in p.columns
    assert p.index[0] >= pd.Timestamp("1972-01-31")


def test_yahoo_constituents_table_is_found() -> None:
    rows = "".join(f"<tr><td>Company {i}</td><td>C{i}.</td></tr>" for i in range(60))
    html = f"<table><tr><th>Company</th><th>Ticker</th></tr>{rows}</table>"
    out = yahoo._constituents_from(html, "ftse250")
    assert len(out) == 60 and set(out["index"]) == {"ftse250"}
    with pytest.raises(ValueError):
        yahoo._constituents_from("<table><tr><th>x</th></tr><tr><td>1</td></tr></table>", "ftse100")


def test_yahoo_prices_read_back(use_data: Path) -> None:
    px = yahoo.prices()
    assert px.shape[1] == 60 and isinstance(px.index, pd.DatetimeIndex)
