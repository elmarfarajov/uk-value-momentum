"""Where the raw files live, and the record of what was downloaded.

Every source is downloaded once into ``data/raw`` (``$UKF_DATA`` overrides it) and never
committed: AQR's, Exeter's and Yahoo's files are theirs to license, not this repository's to
republish. Each download is recorded in ``data/raw/manifest.json`` with its URL, time and
SHA-256, so every number in the analysis can be tied to the exact bytes it came from.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (uk-value-momentum research; +https://github.com/elmarfarajov/uk-value-momentum)"


def data_root() -> Path:
    configured = os.environ.get("UKF_DATA")
    return Path(configured) if configured else Path(__file__).resolve().parents[3] / "data" / "raw"


def path(name: str, root: Path | None = None) -> Path:
    return (root or data_root()) / name


def sha256(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def manifest(root: Path | None = None) -> dict[str, dict[str, str]]:
    file = (root or data_root()) / "manifest.json"
    if not file.exists():
        return {}
    data: dict[str, dict[str, str]] = json.loads(file.read_text(encoding="utf-8"))
    return data


def record(name: str, url: str, root: Path | None = None) -> None:
    """Add a downloaded file to the manifest with its URL, time and SHA-256."""
    base = root or data_root()
    entries = manifest(base)
    entries[name] = {
        "url": url,
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha256(base / name),
    }
    (base / "manifest.json").write_text(json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")


def download(url: str, name: str, root: Path | None = None) -> Path:  # pragma: no cover - network
    import requests

    base = root or data_root()
    base.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120)
    response.raise_for_status()
    (base / name).write_bytes(response.content)
    record(name, url, base)
    return base / name


def available(names: list[str], root: Path | None = None) -> bool:
    base = root or data_root()
    return all((base / n).exists() for n in names)
