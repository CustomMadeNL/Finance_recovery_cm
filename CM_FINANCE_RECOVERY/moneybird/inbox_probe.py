"""Probe kandidaat-endpoints om de Moneybird 'Inkomend'-inbox te vinden.

Het dashboard toont "±1436 nieuwe inkomende documenten klaar om toe te voegen",
maar de bekende endpoints (purchase_invoices/receipts/general_documents) leveren
die inbox niet. Dit script test een reeks kandidaat-endpoints, telt de records,
toont de eerste 3, en schrijft alles naar `reports/inbox_probe_results.json`.

    python moneybird/inbox_probe.py

Crasht niet op een enkele fout: elke endpoint wordt los afgehandeld. Aan het eind
rapporteert het welke endpoint (indien enige) ~1400 records bevat.

Vereist MONEYBIRD_ADMINISTRATION_ID + MONEYBIRD_API_TOKEN (env of .env).
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent      # CM_FINANCE_RECOVERY
sys.path.insert(0, str(BASE_DIR))

from config import Config  # noqa: E402

# De te testen kandidaat-endpoints (paden t.o.v. .../api/v2/{administration_id}).
CANDIDATE_ENDPOINTS = [
    "/documents.json",
    "/documents/synchronization.json",
    "/documents/typeless_documents.json",
    "/documents/typeless_documents/synchronization.json",
    "/documents/incoming_documents.json",
    "/documents/incoming_documents/synchronization.json",
    "/documents/source_documents.json",
    "/documents/source_documents/synchronization.json",
    "/uploads.json",
    "/uploads/synchronization.json",
]

# Verwacht aantal inkomende documenten (dashboard), met marge.
_EXPECTED_MIN, _EXPECTED_MAX = 1200, 1700
_PAGE_CAP = 40  # veiligheidslimiet tegen eindeloze paginatie


def _count_records(session, url: str, first_batch: list) -> tuple[int, bool]:
    """Tel records. Sommige endpoints (synchronization) negeren per_page en geven
    alles in één respons; dan is de eerste batch al de volledige lijst."""
    n = len(first_batch)
    if n < 100:
        return n, False               # één pagina, volledig
    if n > 100:
        return n, False               # per_page genegeerd -> alles in eerste respons
    # precies 100 -> waarschijnlijk gepagineerd; verder tellen
    total = n
    page = 2
    capped = False
    while page <= _PAGE_CAP:
        r = session.get(url, params={"page": page, "per_page": 100}, timeout=30)
        if r.status_code != 200:
            break
        batch = r.json()
        if not isinstance(batch, list) or not batch:
            break
        total += len(batch)
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.2)
    else:
        capped = True
    return total, capped


def probe_endpoint(session, base: str, ep: str) -> dict:
    """Test één endpoint; vang alle fouten af."""
    url = base + ep
    result = {"endpoint": ep, "status": None, "count": None,
              "records_sample": [], "error": None, "note": None}
    try:
        r = session.get(url, params={"per_page": 100}, timeout=30)
        result["status"] = r.status_code
        if r.status_code != 200:
            result["error"] = f"{r.status_code}: {r.text[:200].strip()}"
            return result
        data = r.json()
        if isinstance(data, list):
            count, capped = _count_records(session, url, data)
            result["count"] = count
            if capped:
                result["note"] = f">= {count} (paginatie-cap bereikt)"
            result["records_sample"] = data[:3]
        elif isinstance(data, dict):
            result["note"] = f"object, geen lijst; keys={sorted(data.keys())[:10]}"
            result["records_sample"] = [data]
        else:
            result["note"] = f"onverwacht type: {type(data).__name__}"
    except Exception as exc:  # netwerk/JSON/policy-fout — nooit crashen
        result["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return result


def run(config: Config | None = None) -> int:
    config = config or Config()
    if not config.has_api_credentials():
        raise SystemExit(
            "Moneybird-credentials ontbreken. Zet MONEYBIRD_ADMINISTRATION_ID en "
            "MONEYBIRD_API_TOKEN in je omgeving of .env."
        )

    import requests
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {config.api_token}",
                            "Accept": "application/json"})
    base = f"{config.api_base_url}/{config.administration_id}"

    print("=" * 70)
    print("MONEYBIRD INBOX-PROBE")
    print(f"administration_id: {config.administration_id}")
    print("=" * 70)

    results = []
    for ep in CANDIDATE_ENDPOINTS:
        res = probe_endpoint(session, base, ep)
        results.append(res)
        status = res["status"]
        if res["count"] is not None:
            tail = res["note"] or f"{res['count']} records"
            print(f"  {str(status):>4}  {ep:<52} {tail}")
        elif res["error"]:
            print(f"  {str(status or 'ERR'):>4}  {ep:<52} {res['error'][:60]}")
        else:
            print(f"  {str(status):>4}  {ep:<52} {res['note']}")
        time.sleep(0.2)

    # Welke endpoint bevat ~1400 records?
    candidates = [r for r in results
                  if isinstance(r["count"], int) and _EXPECTED_MIN <= r["count"] <= _EXPECTED_MAX]
    # Fallback: de endpoint met het hoogste aantal records (los van bekende endpoints).
    best = max((r for r in results if isinstance(r["count"], int)),
               key=lambda r: r["count"], default=None)
    likely = candidates[0]["endpoint"] if candidates else None

    payload = {
        "administration_id": config.administration_id,
        "base_url": base,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expected_incoming_range": [_EXPECTED_MIN, _EXPECTED_MAX],
        "likely_inbox_endpoint": likely,
        "highest_count_endpoint": best["endpoint"] if best else None,
        "endpoints": results,
    }
    out = config.reports_dir / "inbox_probe_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("-" * 70)
    if likely:
        print(f"GEVONDEN: endpoint met ~1400 inkomende documenten -> {likely}")
    else:
        print("GEEN endpoint met ~1400 records gevonden onder de geteste kandidaten.")
        if best and isinstance(best["count"], int) and best["count"] > 0:
            print(f"  (hoogste telling: {best['endpoint']} = {best['count']} records)")
    print(f"Resultaten -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
