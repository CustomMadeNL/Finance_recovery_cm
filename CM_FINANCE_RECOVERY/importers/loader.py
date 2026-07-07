"""Import-/sync-stap voor de CM Finance Recovery pipeline.

Twee datasets:
  * "documents" — algemene Moneybird-documenten (`data/moneybird_sync.json`)
  * "inkoop"    — inkoopfacturen met bedragen (`data/moneybird_inkoop.json`)

De JSON-bestanden worden alleen gelezen, nooit overschreven. Optioneel kan met
geldige credentials + netwerk een live-sync van de documenten worden gedraaid;
die schrijft alleen bij succes een nieuwe snapshot weg.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import Config
from database.models import Document

DATASETS = ("documents", "inkoop", "all")


@dataclass
class SyncResult:
    documents: list[Document]
    source: str
    raw_count: int
    deduped_count: int
    per_dataset: dict[str, int] = field(default_factory=dict)
    enriched_count: int = 0


def _dedupe(documents: list[Document]) -> list[Document]:
    """Ontdubbel per dataset.

    Documenten worden op referentie (de titel) ontdubbeld — daar zijn exacte
    dubbele titels re-uploads. Inkoopfacturen worden op hun unieke Moneybird-id
    ontdubbeld: verschillende facturen kunnen hetzelfde referentienummer dragen,
    dus op referentie ontdubbelen zou echte facturen weggooien.
    """
    seen: set[tuple[str, str]] = set()
    unique: list[Document] = []
    for doc in documents:
        if doc.dataset == "inkoop":
            key = (doc.dataset, doc.id)
        else:
            key = (doc.dataset, (doc.reference or "").strip().lower())
        if key[1] and key in seen:
            continue
        if key[1]:
            seen.add(key)
        unique.append(doc)
    return unique


def _load_file(path: Path, dataset: str) -> list[Document]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    records = payload.get("documents", payload if isinstance(payload, list) else [])
    docs = [Document.from_sync(rec) for rec in records]
    for doc in docs:
        doc.dataset = dataset
    return docs


def _load_recognition(path: Path) -> dict[str, dict]:
    """Lees de door Moneybird herkende (OCR) data: document-id -> {supplier, amount}.

    Ondersteunt zowel een dict (id -> record) als een lijst van records met een
    `id`-veld. Ontbreekt het bestand, dan is er simpelweg geen verrijking.
    """
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    records = payload.get("documents", payload) if isinstance(payload, dict) else payload
    if isinstance(records, dict):
        return {str(k): v for k, v in records.items()}
    return {str(r.get("id")): r for r in records if r.get("id")}


def enrich(documents: list[Document], config: Config) -> int:
    """Verrijk documenten met de door Moneybird herkende leverancier/bedrag.

    Zet `recognized_supplier` (de betrouwbare bron) en vult een ontbrekend bedrag
    aan. Geeft het aantal verrijkte documenten terug. Zonder herkende data (geen
    bestand) is dit een no-op, zodat de pipeline altijd blijft draaien.
    """
    recognition = _load_recognition(config.recognition_file)
    if not recognition:
        return 0
    enriched = 0
    for doc in documents:
        rec = recognition.get(doc.id)
        if not rec:
            continue
        supplier = rec.get("supplier") or rec.get("recognized_supplier")
        if supplier:
            doc.recognized_supplier = str(supplier).strip()
            enriched += 1
        if not doc.has_amount and rec.get("amount") is not None:
            doc.amount = rec.get("amount")
    return enriched


def load_documents(config: Config) -> list[Document]:
    return _load_file(config.sync_file, "documents")


def load_inkoop(config: Config) -> list[Document]:
    return _load_file(config.inkoop_file, "inkoop")


def _try_live_sync(config: Config) -> Optional[list[Document]]:
    """Probeer een live Moneybird-sync van de documenten. None als dat niet kan."""
    if not config.has_api_credentials():
        return None
    try:
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
                dataset="documents",
            )
            for rec in resp.json()
        ]
        _write_snapshot(config.sync_file, docs)
        return docs
    except Exception:
        return None


def sync(config: Config, dataset: str = "all") -> SyncResult:
    """Voer de import-/sync-stap uit voor de gekozen dataset(s)."""
    if dataset not in DATASETS:
        raise ValueError(f"onbekende dataset {dataset!r}; kies uit {DATASETS}")

    documents: list[Document] = []
    per_dataset: dict[str, int] = {}
    source_parts: list[str] = []

    if dataset in ("documents", "all"):
        live = _try_live_sync(config)
        docs = live if live is not None else load_documents(config)
        source_parts.append("moneybird-api" if live is not None else "sync-file")
        per_dataset["documents"] = len(docs)
        documents += docs

    if dataset in ("inkoop", "all"):
        inkoop = load_inkoop(config)
        source_parts.append("inkoop-file")
        per_dataset["inkoop"] = len(inkoop)
        documents += inkoop

    raw_count = len(documents)
    documents = _dedupe(documents)
    enriched = enrich(documents, config)
    return SyncResult(
        documents=documents,
        source="+".join(source_parts),
        raw_count=raw_count,
        deduped_count=len(documents),
        per_dataset=per_dataset,
        enriched_count=enriched,
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
