"""Import-/sync-stap voor de CM Finance Recovery pipeline.

Standaard leest deze loader de meegeleverde Moneybird sync-JSON
(`data/moneybird_sync.json`) — die wordt uitsluitend gelezen, nooit
overschreven. Optioneel kan met geldige credentials + netwerk een live-sync
worden gedraaid; die schrijft alleen bij succes een nieuwe snapshot weg.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import Config
from database.models import Document


@dataclass
class SyncResult:
    documents: list[Document]
    source: str          # "sync-file" of "moneybird-api"
    sync_file: Path
    raw_count: int
    deduped_count: int


def _dedupe(documents: list[Document]) -> list[Document]:
    """Verwijder documenten met een exact dubbele referentie (behoud eerste)."""
    seen: set[str] = set()
    unique: list[Document] = []
    for doc in documents:
        key = (doc.reference or "").strip().lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique.append(doc)
    return unique


def load_sync_file(path: Path | str) -> list[Document]:
    """Lees documenten uit de Moneybird sync-JSON."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Moneybird sync-JSON niet gevonden: {path}. "
            "Draai eerst een sync of plaats het bestand terug."
        )
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    records = payload.get("documents", payload if isinstance(payload, list) else [])
    return [Document.from_sync(rec) for rec in records]


def _try_live_sync(config: Config) -> Optional[list[Document]]:
    """Probeer een live Moneybird-sync. Geeft None terug als dat niet kan."""
    if not config.has_api_credentials():
        return None
    try:  # requests is optioneel en het netwerk kan geblokkeerd zijn
        import requests
    except Exception:
        return None
    try:
        base = f"{config.api_base_url}/{config.administration_id}"
        headers = {"Authorization": f"Bearer {config.api_token}"}
        resp = requests.get(
            f"{base}/documents/general_documents.json",
            headers=headers,
            params={"per_page": 200},
            timeout=30,
        )
        resp.raise_for_status()
        docs = [
            Document(
                id=str(rec.get("id") or ""),
                reference=str(rec.get("reference") or rec.get("filename") or ""),
                date=rec.get("date"),
            )
            for rec in resp.json()
        ]
        return docs
    except Exception:
        # Netwerk geblokkeerd / policy-denial / API-fout: val stil terug op de sync-file.
        return None


def sync(config: Config) -> SyncResult:
    """Voer de import-/sync-stap uit en geef de documenten terug."""
    live = _try_live_sync(config)
    if live is not None:
        source = "moneybird-api"
        documents = live
        # Live succes: snapshot bijwerken (bestaande blijft behouden bij falen).
        _write_snapshot(config.sync_file, documents)
    else:
        source = "sync-file"
        documents = load_sync_file(config.sync_file)

    raw_count = len(documents)
    documents = _dedupe(documents)
    return SyncResult(
        documents=documents,
        source=source,
        sync_file=config.sync_file,
        raw_count=raw_count,
        deduped_count=len(documents),
    )


def _write_snapshot(path: Path, documents: list[Document]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "moneybird",
        "object": "documents/general_documents",
        "synced_documents": len(documents),
        "documents": [
            {
                "id": d.id,
                "reference": d.reference,
                "date": d.date,
                "due_date": d.due_date,
                "contact": d.contact,
                "contact_number": d.contact_number,
            }
            for d in documents
        ],
    }
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
