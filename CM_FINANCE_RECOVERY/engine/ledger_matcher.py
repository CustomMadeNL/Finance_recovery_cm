"""Ledger-matching: koppel elk document aan een grootboekrekening.

Statutaire documenten (btw, loonheffing, inkomstenbelasting) mappen
deterministisch op een controlerekening. Inkoopfacturen worden op
leveranciersnaam fuzzy gematcht aan een kostenrekening met `difflib` (stdlib).
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Optional

from database.models import DocType, Flag, Document

# Vast grootboekschema per documenttype: (code, naam, basiszekerheid 0..1).
LEDGER_BY_TYPE: dict[str, tuple[str, str, float]] = {
    DocType.VAT_RETURN: ("1520", "Af te dragen omzetbelasting", 1.0),
    DocType.VAT_SUPPLETION: ("1520", "Af te dragen omzetbelasting (suppletie)", 0.7),
    DocType.PAYROLL_TAX: ("1530", "Af te dragen loonheffing", 1.0),
    DocType.INCOME_TAX: ("0510", "Te betalen inkomsten-/vennootschapsbelasting", 0.9),
    DocType.LEGAL: ("4400", "Juridische kosten", 0.6),
    DocType.REPORT: ("4510", "Advies- en administratiekosten", 0.6),
}

# Bekende leveranciers -> kostenrekening (voor inkoopfacturen).
SUPPLIER_LEDGERS: dict[str, tuple[str, str]] = {
    "nordic nest": ("4600", "Kantoorbenodigdheden"),
    "het catshuis": ("4610", "Inkoop artikelgroep"),
    "bol.com": ("4600", "Kantoorbenodigdheden"),
    "blokker": ("4600", "Kantoorbenodigdheden"),
}

_PURCHASE_DEFAULT = ("4000", "Inkoop / directe kosten")


def _best_supplier_ledger(supplier: str) -> tuple[Optional[str], Optional[str], float]:
    best_key, best_score = None, 0.0
    target = supplier.lower()
    for key in SUPPLIER_LEDGERS:
        score = SequenceMatcher(None, target, key).ratio()
        if score > best_score:
            best_key, best_score = key, score
    if best_key and best_score >= 0.6:
        code, name = SUPPLIER_LEDGERS[best_key]
        return code, name, round(best_score, 3)
    return _PURCHASE_DEFAULT[0], _PURCHASE_DEFAULT[1], round(best_score, 3)


def match(doc: Document) -> Document:
    """Koppel een grootboekrekening en zet `ledger_score`."""
    if doc.doc_type in LEDGER_BY_TYPE:
        code, name, score = LEDGER_BY_TYPE[doc.doc_type]
        doc.ledger_code, doc.ledger_name, doc.ledger_score = code, name, score
        return doc

    if doc.doc_type == DocType.PURCHASE_INVOICE:
        if doc.supplier:
            code, name, score = _best_supplier_ledger(doc.supplier)
            # Onbekende leverancier -> defaultrekening met lage zekerheid.
            doc.ledger_score = max(0.4, score) if code != _PURCHASE_DEFAULT[0] else 0.4
            doc.ledger_code, doc.ledger_name = code, name
        else:
            doc.ledger_code, doc.ledger_name, doc.ledger_score = (*_PURCHASE_DEFAULT, 0.3)
        return doc

    # Onbekend type: geen betrouwbare rekening.
    doc.ledger_code, doc.ledger_name, doc.ledger_score = None, None, 0.0
    doc.add_flag(Flag.NO_LEDGER)
    return doc


def match_all(documents: list[Document]) -> list[Document]:
    return [match(doc) for doc in documents]
