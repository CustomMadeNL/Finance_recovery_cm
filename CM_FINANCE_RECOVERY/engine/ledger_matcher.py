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
