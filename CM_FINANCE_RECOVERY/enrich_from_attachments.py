"""OCR-verrijking: haal leverancier + bedrag + datum uit de PDF/foto-bijlagen
van onverwerkte Moneybird-documenten, zodat ze alsnog auto-boekbaar worden.

Onverwerkte documenten (state `new`, 0 detailregels) hebben in Moneybird géén
bedrag/leverancier in de gestructureerde data — die staan alleen in de bijlage
(meestal een foto/scan). Dit script downloadt die bijlage en laat een
Claude-vision-model per document `supplier`, `amount` en `date` extraheren. Het
resultaat wordt samengevoegd in `data/moneybird_recognition.json`, precies het
formaat dat `importers/loader.enrich` verwacht — waarna de pipeline en
`book_to_moneybird.py` de documenten oppakken.

    python enrich_from_attachments.py --list-only        # toon kandidaten, geen netwerk-download
    python enrich_from_attachments.py --limit 3          # PREVIEW: extraheer 3, schrijf niets
    python enrich_from_attachments.py --limit 3 --write  # schrijf resultaat naar recognition-json

Vereist:
  - MONEYBIRD_ADMINISTRATION_ID + MONEYBIRD_API_TOKEN  (bijlage-download)
  - ANTHROPIC_API_KEY                                   (vision-extractie)
  - netwerktoegang tot moneybird.com **en moneybirdstorage.com** (bijlagen
    worden vanaf de storage-host geserveerd; laat een admin die allowlisten).
  - pip install anthropic
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Iterator, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

# Endpoints waarvan we onverwerkte documenten OCR'en.
_ENDPOINTS = ("documents/purchase_invoices", "documents/receipts")
_OCR_MODEL = os.getenv("CM_OCR_MODEL", "claude-sonnet-5")

_PROMPT = (
    "Dit is een inkoopfactuur of bon. Geef UITSLUITEND JSON terug met exact deze "
    "sleutels: supplier (naam van de leverancier/winkel als string), amount "
    "(totaalbedrag inclusief btw als getal, punt als decimaalteken), date "
    "(factuur-/bondatum als YYYY-MM-DD), confidence (0-1, hoe zeker je bent). "
    "Gebruik null als een veld echt niet leesbaar is. Geen uitleg, alleen JSON."
)


def _session(config: Config):
    import requests
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {config.api_token}"})
    return s


def iter_unprocessed(session, base: str) -> Iterator[tuple[str, dict]]:
    """Yield (endpoint, document) voor documenten zonder detailregels + met bijlage."""
    for ep in _ENDPOINTS:
        page = 1
        while True:
            r = session.get(f"{base}/{ep}.json",
                            params={"page": page, "per_page": 100, "filter": "state:all"},
                            timeout=30)
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for doc in batch:
                if not doc.get("details") and doc.get("attachments"):
                    yield ep, doc
            if len(batch) < 100:
                break
            page += 1


def _sniff_media_type(data: bytes, declared: str) -> str:
    """Bepaal het echte type; octet-stream/onbekend -> herken via magic bytes."""
    if declared and declared not in ("application/octet-stream", ""):
        return declared.split(";")[0]
    if data[:5] == b"%PDF-":
        return "application/pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "application/pdf"  # veilige default: meeste bijlagen zijn PDF


def download_attachment(session, base: str, ep: str, doc_id: str, att: dict) -> tuple[bytes, str]:
    """Download de bijlage-bytes + media-type (volgt redirect naar storage-host)."""
    url = f"{base}/{ep}/{doc_id}/attachments/{att['id']}/download"
    r = session.get(url, timeout=60, allow_redirects=True)
    r.raise_for_status()
    return r.content, _sniff_media_type(r.content, att.get("content_type") or "")


def _content_block(data: bytes, media_type: str) -> dict:
    """PDF -> document-block, afbeelding -> image-block (Claude-vision API)."""
    b64 = base64.standard_b64encode(data).decode("ascii")
    kind = "document" if media_type == "application/pdf" else "image"
    return {"type": kind, "source": {"type": "base64", "media_type": media_type, "data": b64}}


def extract_fields(data: bytes, media_type: str) -> dict:
    """Laat het vision-model supplier/amount/date extraheren. Vereist ANTHROPIC_API_KEY."""
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=_OCR_MODEL,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": [
                _content_block(data, media_type),
                {"type": "text", "text": _PROMPT},
            ],
        }],
    )
    text = "".join(block.text for block in msg.content if block.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    return json.loads(text)


def _load_recognition(path: Path) -> dict:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("documents", payload) if isinstance(payload, dict) else {}
    return {}


def _save_recognition(path: Path, documents: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "moneybird-attachments-ocr",
        "objects": list(_ENDPOINTS),
        "recognized_documents": len(documents),
        "documents": documents,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(config: Config | None = None, limit: Optional[int] = None,
        write: bool = False, list_only: bool = False) -> int:
    config = config or Config()
    if not config.has_api_credentials():
        raise SystemExit("Moneybird-credentials ontbreken (MONEYBIRD_ADMINISTRATION_ID / _API_TOKEN).")

    session = _session(config)
    base = f"{config.api_base_url}/{config.administration_id}"

    print("=" * 68)
    print("OCR-VERRIJKING UIT BIJLAGEN  ", "(LIST-ONLY)" if list_only else
          ("(WRITE)" if write else "(PREVIEW — schrijft niets)"))
    print("=" * 68)

    recognition = _load_recognition(config.recognition_file)
    processed = 0
    updated = 0

    for ep, doc in iter_unprocessed(session, base):
        doc_id = str(doc["id"])
        existing = recognition.get(doc_id) or {}
        # Sla over wat al een leverancier én bedrag heeft.
        if existing.get("supplier") and existing.get("amount"):
            continue
        att = doc["attachments"][0]
        label = f"[{ep.split('/')[-1]:<17}] {doc_id}  {att.get('content_type','?'):<12} ref={doc.get('reference') or '—'}"

        if list_only:
            print("  KANDIDAAT ", label)
            processed += 1
            if limit and processed >= limit:
                break
            continue

        try:
            image, media = download_attachment(session, base, ep, doc_id, att)
            fields = extract_fields(image, media)
        except Exception as exc:
            print(f"  FOUT      {label}  -> {type(exc).__name__}: {str(exc)[:100]}")
            processed += 1
            if limit and processed >= limit:
                break
            continue

        supplier = fields.get("supplier")
        amount = fields.get("amount")
        conf = fields.get("confidence")
        print(f"  OCR       {label}\n            -> leverancier={supplier!r} bedrag={amount} "
              f"datum={fields.get('date')} conf={conf}")

        entry = dict(existing)
        if supplier:
            entry["supplier"] = str(supplier).strip()
        if isinstance(amount, (int, float)) and amount > 0:
            entry["amount"] = float(amount)
        if fields.get("date"):
            entry["date"] = fields["date"]
        if entry:
            recognition[doc_id] = entry
            updated += 1

        processed += 1
        if limit and processed >= limit:
            break

    print("-" * 68)
    if list_only:
        print(f"LIST-ONLY: {processed} kandidaten getoond (nog te OCR'en). Geen download/AI.")
        return 0

    if write and updated:
        _save_recognition(config.recognition_file, recognition)
        print(f"KLAAR: {updated} document(en) verrijkt -> {config.recognition_file}")
        print("Draai nu 'python app.py' en daarna 'python book_to_moneybird.py' (preview).")
    else:
        print(f"PREVIEW: {processed} verwerkt, {updated} zouden verrijkt worden. "
              f"Er is NIETS weggeschreven. Voeg --write toe om op te slaan.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="OCR-verrijking van onverwerkte Moneybird-bijlagen")
    p.add_argument("--limit", type=int, default=5, help="Max aantal documenten (standaard 5).")
    p.add_argument("--write", action="store_true", help="Schrijf resultaat naar recognition-json.")
    p.add_argument("--list-only", action="store_true", dest="list_only",
                   help="Toon alleen kandidaten; geen download/AI-call.")
    return p


if __name__ == "__main__":
    a = build_parser().parse_args()
    raise SystemExit(run(limit=a.limit, write=a.write, list_only=a.list_only))
