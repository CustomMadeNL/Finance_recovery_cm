"""Sync de Moneybird 'Inkomend'-inbox — zodra de juiste endpoint bekend is.

Dit script leunt op `inbox_probe.py`: dat bepaalt welke endpoint de ~1400
inkomende documenten bevat (`likely_inbox_endpoint` in
`reports/inbox_probe_results.json`). Deze sync haalt vervolgens álle records van
die endpoint op en schrijft ze naar `data/moneybird_inbox_sync.json`.

    python moneybird/inbox_sync.py                       # gebruikt de gevonden endpoint
    python moneybird/inbox_sync.py --endpoint /documents/xyz.json   # forceer endpoint
    python moneybird/inbox_sync.py --probe               # draai eerst de probe

Belangrijk: op dit moment stelt de publieke Moneybird v2-API de inbox
("nieuwe inkomende documenten klaar om toe te voegen") niet beschikbaar — de
probe vindt geen endpoint met ~1400 records. In dat geval stopt dit script met
een duidelijke melding i.p.v. te crashen. Zodra een endpoint wél gevonden wordt
(bv. na een API-uitbreiding) werkt de sync automatisch.

Vereist MONEYBIRD_ADMINISTRATION_ID + MONEYBIRD_API_TOKEN (env of .env).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent      # CM_FINANCE_RECOVERY
sys.path.insert(0, str(BASE_DIR))

from config import Config  # noqa: E402
from moneybird import inbox_probe  # noqa: E402


def _resolve_endpoint(config: Config, explicit: str | None, run_probe: bool) -> str | None:
    if explicit:
        return explicit
    results_path = config.reports_dir / "inbox_probe_results.json"
    if run_probe or not results_path.exists():
        inbox_probe.run(config)
    if results_path.exists():
        data = json.loads(results_path.read_text(encoding="utf-8"))
        # Alleen een endpoint dat daadwerkelijk ~1400 records had (likely) telt.
        # Niet terugvallen op 'highest' — dat kan een lege endpoint (0 records)
        # zijn en zou een misleidende "0 gesynct" opleveren.
        return data.get("likely_inbox_endpoint")
    return None


def _fetch_all(session, url: str) -> list:
    """Haal alle records op. Sommige endpoints negeren per_page (alles in één
    respons); anders pagineren we door."""
    first = session.get(url, params={"per_page": 100}, timeout=30)
    first.raise_for_status()
    batch = first.json()
    if not isinstance(batch, list):
        return [batch]
    records = list(batch)
    if len(batch) <= 100 and len(batch) != 100:
        return records
    if len(batch) > 100:               # per_page genegeerd -> was al alles
        return records
    page = 2
    while True:
        r = session.get(url, params={"page": page, "per_page": 100}, timeout=30)
        r.raise_for_status()
        b = r.json()
        if not b:
            break
        records.extend(b)
        if len(b) < 100:
            break
        page += 1
        time.sleep(0.2)
    return records


def run(config: Config | None = None, endpoint: str | None = None, run_probe: bool = False) -> int:
    config = config or Config()
    if not config.has_api_credentials():
        raise SystemExit(
            "Moneybird-credentials ontbreken. Zet MONEYBIRD_ADMINISTRATION_ID en "
            "MONEYBIRD_API_TOKEN in je omgeving of .env."
        )

    print("=" * 70)
    print("MONEYBIRD INBOX-SYNC")
    print("=" * 70)

    ep = _resolve_endpoint(config, endpoint, run_probe)
    if not ep:
        print(
            "GEEN inbox-endpoint gevonden.\n"
            "De publieke Moneybird v2-API stelt de 'Inkomend'-inbox (de ~1436\n"
            "nieuwe inkomende documenten) niet beschikbaar. De documenten worden\n"
            "pas via de API zichtbaar nadat ze in Moneybird zijn 'toegevoegd'\n"
            "(dan worden het purchase_invoices/receipts). Zie\n"
            f"{config.reports_dir / 'inbox_probe_results.json'} voor de probe-details."
        )
        return 1

    import requests
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {config.api_token}",
                            "Accept": "application/json"})
    url = f"{config.api_base_url}/{config.administration_id}{ep}"

    print(f"Endpoint : {ep}")
    records = _fetch_all(session, url)
    out = config.data_dir / "moneybird_inbox_sync.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "moneybird-inbox",
        "endpoint": ep,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "count": len(records),
        "documents": records,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"KLAAR: {len(records)} inkomende documenten -> {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sync de Moneybird inbox")
    p.add_argument("--endpoint", help="Forceer een specifiek inbox-endpoint (pad met leading /).")
    p.add_argument("--probe", action="store_true", help="Draai eerst inbox_probe om de endpoint te bepalen.")
    return p


if __name__ == "__main__":
    a = build_parser().parse_args()
    raise SystemExit(run(endpoint=a.endpoint, run_probe=a.probe))
