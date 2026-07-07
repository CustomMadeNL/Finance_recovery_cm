"""Haal de door Moneybird herkende leverancier + bedrag per inkoopdocument op.

Dekt de volledige Inkoop-backlog: inkoopfacturen, bonnetjes (receipts) én
algemene documenten — samen de ~1500 documenten die Moneybird onder "Inkoop"
toont, niet alleen de openstaande todo's.

Genereert `data/moneybird_recognition.json` in het formaat dat de
verrijkingsstap (`importers/loader.enrich`) verwacht. Draai dit één keer zodra
de Moneybird-API bereikbaar is:

    python fetch_recognition.py            # schrijft data/moneybird_recognition.json
    python fetch_recognition.py --raw      # dumpt ook 1 ruwe respons per endpoint

Iedere run print een VELD-VERIFICATIE-blok: welke veldnaam de leverancier en het
bedrag daadwerkelijk leverde (met een voorbeeldwaarde), plus een waarschuwing als
geen enkele herkende-OCR-sleutel matchte. Zo bevestig je in één oogopslag of de
gegokte OCR-veldnamen kloppen — of dat `_SUPPLIER_KEYS` / `_AMOUNT_KEYS` moet
worden bijgesteld.

Vereist `MONEYBIRD_ADMINISTRATION_ID` en `MONEYBIRD_API_TOKEN` in de omgeving of
`.env`. Werkt alleen met netwerktoegang tot moneybird.com; in een afgeschermde
omgeving (403 policy-denial) geeft het een duidelijke melding i.p.v. te crashen.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

# Mogelijke velden waarin de leverancier kan zitten, op prioriteit. De publieke
# API levert doorgaans het toegewezen contact; als Moneybird herkende (OCR) data
# in de respons meestuurt, pakken we die eerst.
_SUPPLIER_KEYS = ("recognized_contact_name", "recognition_contact_name", "suggested_contact_name")
# Contact-fallbacks (geen OCR): alleen gebruikt als geen enkele herkende sleutel
# een waarde had. De verificatie-samenvatting laat expliciet zien wanneer we
# hierop terugvallen — dat betekent dat de OCR-sleutels (nog) niet matchen.
_CONTACT_KEYS = ("company_name", "full_name")
_AMOUNT_KEYS = (
    "total_price_incl_tax_base",
    "total_price_incl_tax",
    "total_price_excl_tax_base",
)

# Marker in de verificatie-tellers voor "geen enkele kandidaat-sleutel matchte".
_NO_MATCH = "—geen match—"


def _supplier_from(payload: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Geef (leverancier, bronsleutel) terug. Bronsleutel is None bij geen match."""
    for key in _SUPPLIER_KEYS:
        val = payload.get(key)
        if val:
            return str(val).strip(), key
    contact = payload.get("contact") or {}
    for key in _CONTACT_KEYS:
        val = contact.get(key)
        if val:
            return str(val).strip(), f"contact.{key}"
    return None, None


def _amount_from(payload: dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
    """Geef (bedrag, bronsleutel) terug. Bronsleutel is None bij geen match."""
    for key in _AMOUNT_KEYS:
        val = payload.get(key)
        if val not in (None, ""):
            try:
                return float(val), key
            except (TypeError, ValueError):
                continue
    return None, None


def _new_stats() -> dict[str, Any]:
    """Lege verzamelbak voor de veld-verificatie."""
    return {
        "total": 0,
        "per_endpoint": Counter(),
        "supplier_keys": Counter(),
        "amount_keys": Counter(),
        "supplier_samples": {},
        "amount_samples": {},
    }


# De Moneybird-"Inkoop"-backlog is verdeeld over meerdere document-typen, elk op
# een eigen endpoint. De UI telt ze samen; het loont dus om ze alle drie op te
# halen (facturen zijn maar ~2/3 van het totaal, de rest zijn bonnetjes).
_DOCUMENT_ENDPOINTS = (
    "documents/purchase_invoices",   # inkoopfacturen
    "documents/receipts",            # bonnetjes / kassabonnen
    "documents/general_documents",   # algemene documenten (aangiftes e.d.)
)


def _iter_documents(session, base: str, endpoint: str, page_size: int = 100):
    # Zonder expliciete filter geeft de Moneybird-API alleen de "todo"-subset
    # terug (openstaande/te-verwerken documenten — bevestigd via de response-header
    # `x-total-count`). Voor een recovery-traject willen we juist de volledige
    # backlog, dus dwingen we `state:all` af.
    page = 1
    while True:
        resp = session.get(
            f"{base}/{endpoint}.json",
            params={"page": page, "per_page": page_size, "filter": "state:all"},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for item in batch:
            yield item
        if len(batch) < page_size:
            break
        page += 1


def fetch(config: Config, dump_raw: bool = False, stats: Optional[dict] = None) -> dict[str, dict]:
    import requests

    if not config.has_api_credentials():
        raise SystemExit(
            "Moneybird-credentials ontbreken. Zet MONEYBIRD_ADMINISTRATION_ID en "
            "MONEYBIRD_API_TOKEN in je omgeving of .env."
        )

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {config.api_token}"})
    base = f"{config.api_base_url}/{config.administration_id}"

    recognition: dict[str, dict] = {}
    dumped: set[str] = set()
    for endpoint in _DOCUMENT_ENDPOINTS:
        for inv in _iter_documents(session, base, endpoint):
            # Dump het eerste document van élk endpoint: de herkende (OCR-)velden
            # kunnen per document-type (factuur vs. bonnetje) verschillen.
            if dump_raw and endpoint not in dumped:
                print(f"--- ruwe API-respons (eerste document, {endpoint}) ---")
                print(json.dumps(inv, indent=2, ensure_ascii=False)[:2000])
                print("--- einde ruwe respons ---\n")
                dumped.add(endpoint)
            if stats is not None:
                stats["total"] += 1
                stats["per_endpoint"][endpoint] += 1
            doc_id = str(inv.get("id") or "").strip()
            if not doc_id:
                continue
            supplier, s_key = _supplier_from(inv)
            amount, a_key = _amount_from(inv)
            if stats is not None:
                _record(stats, "supplier", s_key, supplier)
                _record(stats, "amount", a_key, amount)
            entry: dict[str, Any] = {}
            if supplier:
                entry["supplier"] = supplier
            if amount is not None:
                entry["amount"] = amount
            if entry:
                recognition[doc_id] = entry
    return recognition


def _record(stats: dict, kind: str, key: Optional[str], value: Any) -> None:
    """Tel één veldtreffer en bewaar de eerste voorbeeldwaarde per sleutel."""
    label = key or _NO_MATCH
    stats[f"{kind}_keys"][label] += 1
    samples = stats[f"{kind}_samples"]
    if key and label not in samples and value not in (None, ""):
        samples[label] = value


def _print_verification(stats: dict) -> None:
    """Print welke veldnamen de leverancier/het bedrag leverden — de kern van
    de OCR-veld-verificatie."""
    total = stats["total"]
    print("-" * 60)
    print(f"VELD-VERIFICATIE — {total} documenten bekeken")
    if not total:
        print("  (geen documenten opgehaald)")
        return

    def _dump(title: str, counter: Counter, samples: dict) -> None:
        print(f"  {title}:")
        if not counter:
            print("    (geen)")
            return
        for key, n in counter.most_common():
            sample = samples.get(key)
            suffix = f"   bv. {sample!r}" if sample not in (None, "") else ""
            print(f"    {key:<26} {n:>6}{suffix}")

    _dump("leverancier — brongebruikte veldnaam", stats["supplier_keys"], stats["supplier_samples"])
    _dump("bedrag — brongebruikte veldnaam", stats["amount_keys"], stats["amount_samples"])

    matched_ocr = any(k in _SUPPLIER_KEYS for k in stats["supplier_keys"])
    if not matched_ocr:
        print()
        print("  LET OP: geen enkele herkende-OCR-sleutel matchte in de respons.")
        print(f"          Gezochte OCR-sleutels: {', '.join(_SUPPLIER_KEYS)}")
        print("          De leverancier komt nu (hooguit) uit het contact-veld.")
        print("          Bekijk de ruwe respons (--raw) en stel zo nodig")
        print("          _SUPPLIER_KEYS bij aan de echte veldnaam.")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Moneybird recognition data")
    parser.add_argument("--raw", action="store_true", help="Dump 1 ruwe API-respons per endpoint ter inspectie.")
    parser.add_argument("--output", help="Uitvoerpad (standaard: config.recognition_file).")
    args = parser.parse_args(argv)

    config = Config()
    stats = _new_stats()
    try:
        recognition = fetch(config, dump_raw=args.raw, stats=stats)
    except SystemExit:
        raise
    except Exception as exc:  # netwerk/proxy/API-fout
        msg = str(exc)
        if "403" in msg or "ProxyError" in msg or "Max retries" in msg:
            print(
                "FOUT: kon moneybird.com niet bereiken (waarschijnlijk netwerk-policy/403).\n"
                "Laat een admin moneybird.com op de allowlist zetten en probeer opnieuw.",
                file=sys.stderr,
            )
        else:
            print(f"FOUT bij ophalen: {exc}", file=sys.stderr)
        return 1

    out_path = Path(args.output) if args.output else config.recognition_file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "moneybird-api",
        "objects": list(_DOCUMENT_ENDPOINTS),
        "recognized_documents": len(recognition),
        "documents": recognition,
    }
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    _print_verification(stats)
    print("-" * 60)
    print(f"KLAAR: {len(recognition)} documenten met herkende data -> {out_path}")
    print("Draai nu 'python app.py' om de verrijking toe te passen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
