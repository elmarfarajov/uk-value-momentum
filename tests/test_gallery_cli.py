from __future__ import annotations

from pathlib import Path

import pytest

from ukfactors import cli, gallery
from ukfactors.validation import run_validation, to_markdown


def test_gallery_registry_is_complete_and_unique() -> None:
    items = gallery.items()
    assert len(items) == 11
    assert len({i.filename for i in items}) == len(items)
    assert all(i.day in gallery.DAYS for i in items)
    assert all(i.filename.endswith(".png") and i.title and i.description for i in items)


def test_gallery_markdown_links_every_image() -> None:
    md = gallery.markdown()
    assert md.startswith("# Gallery")
    for item in gallery.items():
        assert f"(images/{item.filename})" in md


def test_gallery_skips_without_data(no_data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gallery.build(no_data / "out") == []
    assert "skipped long-history.png" in capsys.readouterr().out


def test_every_chart_draws_from_synthetic_data(use_data: Path, tmp_path: Path) -> None:
    from ukfactors.gallery import foundation

    foundation._panel.cache_clear()
    written = gallery.build(tmp_path)
    foundation._panel.cache_clear()
    assert len(written) == 11
    assert all(p.stat().st_size > 20_000 for p in written)


def test_validation_without_data_skips_rather_than_fails(no_data: Path) -> None:
    results = run_validation(fast=True)
    assert set(results["status"]) <= {"PASS", "SKIP"}
    assert (results["status"] == "SKIP").sum() == 3
    assert (results["status"] == "PASS").sum() == 6
    md = to_markdown(results)
    assert md.count("\n") == len(results) + 1


def test_validation_with_synthetic_data_runs_the_data_checks(use_data: Path) -> None:
    results = run_validation(fast=True).set_index("check")
    assert results.loc["AQR converted to sterling", "status"] == "PASS"
    assert results.loc["Two sources agree on momentum", "status"] == "PASS"
    assert results.loc["Exeter market reproduces the published table", "status"] in {"PASS", "FAIL"}  # synthetic numbers


def test_cli_parser() -> None:
    args = cli.build_parser().parse_args(["validate", "--fast", "--out", "x.md"])
    assert args.fast and args.out == "x.md" and args.func is cli.cmd_validate
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["data", "delete"])


def test_cli_data_list_without_data(no_data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["data", "list"])
    assert "nothing stored" in capsys.readouterr().out


def test_cli_validate_writes_the_report(no_data: Path, tmp_path: Path) -> None:
    out = tmp_path / "VALIDATION.md"
    cli.main(["validate", "--fast", "--out", str(out)])
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Validation report") and "SKIP" in text and "FAIL" not in text


def test_cli_stats(use_data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["stats", "--reps", "50"])
    out = capsys.readouterr().out
    assert "VAL" in out and "EX_UMD" in out and "sharpe" in out
