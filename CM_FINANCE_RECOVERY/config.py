"""Configuratie voor de CM Finance Recovery module.

Alle gevoelige instellingen (Moneybird administratie-id en API-token) worden uit
de omgeving / een `.env`-bestand geladen. Er staan bewust geen secrets in de repo.

Maak naast dit bestand een `.env` aan (zie `.env.example`):

    MONEYBIRD_ADMINISTRATION_ID=123456789
    MONEYBIRD_API_TOKEN=xxxxxxxx

De overige waarden hebben verstandige standaarden en kunnen optioneel via de
omgeving worden overschreven.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    # python-dotenv is optioneel: zonder .env draaien we gewoon op os.environ.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is een zachte afhankelijkheid
    pass


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Runtime-configuratie voor de recovery-run."""

    # Moneybird API
    administration_id: str = field(default_factory=lambda: os.getenv("MONEYBIRD_ADMINISTRATION_ID", ""))
    api_token: str = field(default_factory=lambda: os.getenv("MONEYBIRD_API_TOKEN", ""))
    api_base_url: str = field(
        default_factory=lambda: os.getenv("MONEYBIRD_API_BASE_URL", "https://moneybird.com/api/v2")
    )

    # Matching
    # Score (0-100) waarboven een leverancier automatisch wordt gekoppeld.
    match_auto_threshold: float = field(default_factory=lambda: _get_float("CM_MATCH_AUTO_THRESHOLD", 90.0))
    # Score waaronder een match wordt genegeerd; ertussenin = handmatige review.
    match_review_threshold: float = field(default_factory=lambda: _get_float("CM_MATCH_REVIEW_THRESHOLD", 70.0))

    # Uitvoer
    output_dir: Path = field(
        default_factory=lambda: Path(os.getenv("CM_OUTPUT_DIR", "output")).expanduser()
    )

    def has_api_credentials(self) -> bool:
        return bool(self.administration_id and self.api_token)

    def require_api_credentials(self) -> None:
        if not self.has_api_credentials():
            raise RuntimeError(
                "Moneybird-credentials ontbreken. Zet MONEYBIRD_ADMINISTRATION_ID en "
                "MONEYBIRD_API_TOKEN in je omgeving of .env-bestand."
            )


# Kolomnamen zoals ze in de Moneybird Excel-export voorkomen, gemapt naar
# de interne, taal-neutrale veldnamen die de rest van de module gebruikt.
EXCEL_COLUMN_MAP: dict[str, str] = {
    "id": "id",
    "referentie": "reference",
    "status": "status",
    "datum": "date",
    "vervaldatum": "due_date",
    "contact": "contact",
    "contactnummer": "contact_number",
    "valuta": "currency",
    "betaald op": "paid_at",
    "totaalprijs exclusief btw": "amount_ex_vat",
    "totaalprijs inclusief btw": "amount_inc_vat",
    "totaalprijs exclusief btw (EUR)": "amount_ex_vat_eur",
    "totaalprijs inclusief btw (EUR)": "amount_inc_vat_eur",
    "btw": "vat",
}
