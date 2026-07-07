"""Write-back: boek AUTO-inkoopfacturen in Moneybird.

Boekt elke AUTO-inkoopfactuur op de categorie **Ongecategoriseerde uitgaven**
met **21% btw** (conform de afgesproken default) door via de API een
detailregel toe te voegen. Later herverdelen naar de juiste grootboekrekening
kan altijd in Moneybird.

VEILIGHEID — dit script schrijft alleen met expliciete vlaggen:

    python book_to_moneybird.py                      # PREVIEW: toont plan, schrijft niets
    python book_to_moneybird.py --id <doc_id>        # PREVIEW van één factuur (before + payload)
    python book_to_moneybird.py --id <doc_id> --commit   # boekt DIE ene factuur echt
    python book_to_moneybird.py --commit --max 5     # boekt max 5 facturen echt
    python book_to_moneybird.py --commit --all       # boekt alle AUTO-facturen echt

Zonder `--commit` gebeurt er niets onomkeerbaars. `--commit` vereist `--id`,
`--max` of `--all` (nooit per ongeluk alles). Reeds geboekte documenten (met
detailregels) worden overgeslagen (idempotent). Elke boeking wordt geverifieerd
en gelogd naar `reports/booked_log.csv`.

Vereist `MONEYBIRD_ADMINISTRATION_ID` + `MONEYBIRD_API_TOKEN`.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database.models import DocType, Route, Document
from book_dry_run import plan_bookings

# Afgesproken boekingsdefaults (namen; id's worden bij runtime opgezocht).
TARGET_LEDGER_NAME = "Ongecategoriseerde uitgaven"
TARGET_TAX_NAME = "21% btw"
TARGET_TAX_PERCENTAGE = 21.0


def _session(config: Config):
    import requests
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {config.api_token}"})
    return s


def _lookup_ids(session, base: str) -> tuple[str, str]:
    """Zoek ledger_account_id (Ongecategoriseerde uitgaven) + tax_rate_id (21% btw)."""
    la = session.get(f"{base}/ledger_accounts.json", params={"per_page": 100}, timeout=30)
    la.raise_for_status()
    ledger = next((a for a in la.json() if a.get("name") == TARGET_LEDGER_NAME), None)
    if not ledger:
        raise SystemExit(f"Grootboekrekening '{TARGET_LEDGER_NAME}' niet gevonden in Moneybird.")

    tr = session.get(f"{base}/tax_rates.json", params={"per_page": 100}, timeout=30)
    tr.raise_for_status()
    tax = next(
        (t for t in tr.json()
         if t.get("name") == TARGET_TAX_NAME
         and str(t.get("tax_rate_type")) == "purchase_invoice"
         and float(t.get("percentage") or 0) == TARGET_TAX_PERCENTAGE),
        None,
    )
    if not tax:
        raise SystemExit(f"Btw-tarief '{TARGET_TAX_NAME}' (purchase) niet gevonden in Moneybird.")
    return str(ledger["id"]), str(tax["id"])


def _bookable(docs: list[Document]) -> list[Document]:
    """AUTO-inkoopfacturen met een boekbaar bedrag."""
    return [
        d for d in docs
        if d.route == Route.AUTO
        and d.doc_type == DocType.PURCHASE_INVOICE
        and d.amount is not None and d.amount > 0
    ]


def _payload(doc: Document, ledger_id: str, tax_id: str) -> dict:
    """Bouw de PATCH-payload. Ons bedrag is incl. btw; reken terug naar excl.
    zodat Moneybird met 21% btw exact op het factuurtotaal uitkomt."""
    price_excl = round(doc.amount / (1 + TARGET_TAX_PERCENTAGE / 100), 2)
    supplier = doc.recognized_supplier or doc.supplier or doc.contact or "Onbekende leverancier"
    return {
        "purchase_invoice": {
            "details_attributes": {
                "0": {
                    "description": f"{supplier} — {doc.reference}".strip(" —"),
                    "price": price_excl,
                    "amount": "1",
                    "tax_rate_id": tax_id,
                    "ledger_account_id": ledger_id,
                }
            }
        }
    }


def _fetch_current(session, base: str, doc_id: str) -> dict | None:
    r = session.get(f"{base}/documents/purchase_invoices/{doc_id}.json", timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def _log(path: Path, rows: list[list]) -> None:
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["id", "leverancier", "bedrag_incl", "prijs_excl", "resultaat", "state", "entry_number"])
        w.writerows(rows)


def run(config: Config | None = None, doc_id: str | None = None,
        commit: bool = False, max_n: int | None = None, book_all: bool = False) -> int:
    config = config or Config()
    if not config.has_api_credentials():
        raise SystemExit("Moneybird-credentials ontbreken (MONEYBIRD_ADMINISTRATION_ID / _API_TOKEN).")

    session = _session(config)
    base = f"{config.api_base_url}/{config.administration_id}"
    ledger_id, tax_id = _lookup_ids(session, base)

    auto_docs, _ = plan_bookings(config, "all")
    bookable = _bookable(auto_docs)
    if doc_id:
        bookable = [d for d in bookable if d.id == doc_id]
        if not bookable:
            raise SystemExit(f"Document {doc_id} zit niet in de boekbare AUTO-set.")

    print("=" * 68)
    print("MONEYBIRD WRITE-BACK  ", "(COMMIT)" if commit else "(PREVIEW — schrijft niets)")
    print("=" * 68)
    print(f"Categorie   : {TARGET_LEDGER_NAME}  (id {ledger_id})")
    print(f"Btw         : {TARGET_TAX_NAME}  (id {tax_id})")
    print(f"Boekbaar    : {len(bookable)} AUTO-inkoopfacturen\n")

    # Selecteer de te verwerken set.
    if commit and not (doc_id or book_all or max_n):
        raise SystemExit("Weiger te boeken zonder --id, --max of --all (veiligheid).")
    todo = bookable if (doc_id or book_all) else bookable[: (max_n or 0)]
    if not commit and not doc_id:
        todo = bookable[: (max_n or 5)]  # preview toont een paar regels

    log_rows: list[list] = []
    booked = skipped = failed = 0

    for d in todo:
        payload = _payload(d, ledger_id, tax_id)
        line = payload["purchase_invoice"]["details_attributes"]["0"]
        supplier = d.recognized_supplier or d.supplier or d.contact or "—"
        header = f"[{d.id}] {supplier[:30]:<30} incl EUR {d.amount:>10,.2f} -> excl EUR {line['price']:>10,.2f}"

        current = _fetch_current(session, base, d.id)
        if current is None:
            print(f"  OVERSLAAN {header}  (niet gevonden in Moneybird)")
            skipped += 1
            continue
        if current.get("details"):
            print(f"  OVERSLAAN {header}  (heeft al detailregels — reeds geboekt)")
            skipped += 1
            continue

        if not commit:
            print(f"  PREVIEW   {header}")
            print(f"            state nu: {current.get('state')} | payload.details: "
                  f"{line['description'][:40]!r} @21% -> {TARGET_LEDGER_NAME}")
            continue

        # Echt boeken.
        r = session.patch(f"{base}/documents/purchase_invoices/{d.id}.json", json=payload, timeout=30)
        if r.status_code in (200, 201):
            res = r.json()
            state = res.get("state")
            entry = res.get("entry_number")
            print(f"  GEBOEKT   {header}  -> state={state} entry={entry}")
            log_rows.append([d.id, supplier, f"{d.amount:.2f}", f"{line['price']:.2f}", "OK", state, entry])
            booked += 1
        else:
            print(f"  MISLUKT   {header}  -> HTTP {r.status_code}: {r.text[:160]}")
            log_rows.append([d.id, supplier, f"{d.amount:.2f}", f"{line['price']:.2f}", f"HTTP {r.status_code}", "", ""])
            failed += 1

    print("-" * 68)
    if commit:
        _log(config.reports_dir / "booked_log.csv", log_rows)
        print(f"KLAAR: geboekt {booked}, overgeslagen {skipped}, mislukt {failed}.")
        print(f"Log -> {config.reports_dir / 'booked_log.csv'}")
    else:
        print(f"PREVIEW: {len(todo)} regel(s) getoond, {len(bookable)} boekbaar totaal. "
              f"Er is NIETS geschreven. Voeg --commit toe om te boeken.")
    return 0 if failed == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Boek AUTO-inkoopfacturen in Moneybird")
    p.add_argument("--id", help="Boek/preview alleen dit document-id.")
    p.add_argument("--commit", action="store_true", help="Schrijf echt naar Moneybird (anders preview).")
    p.add_argument("--max", type=int, default=None, help="Maximaal aantal facturen om te boeken.")
    p.add_argument("--all", action="store_true", dest="book_all", help="Boek alle boekbare AUTO-facturen.")
    return p


if __name__ == "__main__":
    a = build_parser().parse_args()
    raise SystemExit(run(doc_id=a.id, commit=a.commit, max_n=a.max, book_all=a.book_all))
