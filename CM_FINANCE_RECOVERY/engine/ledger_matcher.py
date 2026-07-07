<<<<<<< HEAD
"""Ledger-matching: koppel elk document aan een grootboekrekening.

De koppelregels staan centraal in `engine/ledger_schema.py`:
* statutaire documenttypes -> vaste controlerekening;
* inkoopfacturen -> kostenrekening op basis van de (uit de referentie afgeleide)
  leveranciersnaam, via expliciete mapping of keyword-regels.

Onbekende leveranciers krijgen een defaultrekening met lage zekerheid, zodat ze
naar review gaan i.p.v. verkeerd auto-geboekt te worden.
"""

from __future__ import annotations

from database.models import DocType, Flag, Document
from engine import ledger_schema


def match(doc: Document) -> Document:
    """Koppel een grootboekrekening en zet `ledger_score`."""
    if doc.doc_type in ledger_schema.LEDGER_BY_TYPE:
        code, score = ledger_schema.LEDGER_BY_TYPE[doc.doc_type]
        doc.ledger_code = code
        doc.ledger_name = ledger_schema.account_name(code)
        doc.ledger_score = score
        return doc

    if doc.doc_type == DocType.PURCHASE_INVOICE:
        code, name, score = ledger_schema.resolve_supplier(doc.supplier)
        doc.ledger_code, doc.ledger_name, doc.ledger_score = code, name, score
        return doc

    # Onbekend type: geen betrouwbare rekening.
    doc.ledger_code, doc.ledger_name, doc.ledger_score = None, None, 0.0
    doc.add_flag(Flag.NO_LEDGER)
    return doc


def match_all(documents: list[Document]) -> list[Document]:
    return [match(doc) for doc in documents]
=======
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from config import DOCUMENT_ANALYSIS, DOCUMENT_LEDGERS

RULES = {
    "moneybird": "Software",
    "google": "Software",
    "transip": "Hosting",
    "one.com": "Hosting",
    "yellowbrick": "Autokosten",
    "shell": "Autokosten",
    "bp": "Autokosten",
    "athlon": "Autokosten",
    "jumbo": "Kantoorbenodigdheden",
    "albert heijn": "Kantoorbenodigdheden",
    "dekamarkt": "Kantoorbenodigdheden",
    "ikea": "Inventaris",
    "bennett": "Accountantskosten",
}

def match_ledger(contact_name, reference=""):
    text = f"{contact_name} {reference}".lower()
    for key, ledger in RULES.items():
        if key in text:
            return ledger
    return "REVIEW"

def run():
    df = pd.read_csv(DOCUMENT_ANALYSIS).fillna("")
    df["ledger"] = df.apply(
        lambda r: match_ledger(r.get("contact_name", ""), r.get("reference", "")),
        axis=1
    )
    df.to_csv(DOCUMENT_LEDGERS, index=False)

    print("LEDGER MATCHING OK")
    print(df["ledger"].value_counts())
    print(f"Output: {DOCUMENT_LEDGERS}")

if __name__ == "__main__":
    run()
>>>>>>> 06917c4 (Build CM Finance Recovery v1.0 pipeline)
