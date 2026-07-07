"""Centrale configuratie voor de CM Finance Recovery v1.0 pipeline.

Alle paden zijn relatief aan deze map, zodat `python app.py` overal draait.
Gevoelige waarden (Moneybird-token) komen uit de omgeving / `.env` en staan
nooit in de repo. De pipeline draait volledig op de meegeleverde sync-JSON en
heeft geen netwerk of secrets nodig; die zijn alleen voor de optionele
live-sync.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # dotenv is optioneel — zonder .env draaien we op os.environ
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

BASE_DIR = Path(__file__).resolve().parent


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Runtime-configuratie voor één pipeline-run."""

    # Paden
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    reports_dir: Path = BASE_DIR / "reports"
    sync_file: Path = BASE_DIR / "data" / "moneybird_sync.json"
    database_file: Path = BASE_DIR / "data" / "recovery.db"

    # Routing-drempels (0..1)
    auto_threshold: float = field(default_factory=lambda: _get_float("CM_AUTO_THRESHOLD", 0.80))
    review_threshold: float = field(default_factory=lambda: _get_float("CM_REVIEW_THRESHOLD", 0.40))

    # Optionele live Moneybird-sync (standaard uit; werkt alleen met netwerk+token)
    administration_id: str = field(default_factory=lambda: os.getenv("MONEYBIRD_ADMINISTRATION_ID", ""))
    api_token: str = field(default_factory=lambda: os.getenv("MONEYBIRD_API_TOKEN", ""))
    api_base_url: str = field(
        default_factory=lambda: os.getenv("MONEYBIRD_API_BASE_URL", "https://moneybird.com/api/v2")
    )

    def has_api_credentials(self) -> bool:
        return bool(self.administration_id and self.api_token)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
