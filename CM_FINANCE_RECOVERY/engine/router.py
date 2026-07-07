"""Routing: bepaal per document AUTO (straight-through) of MANUAL (review).

Een document gaat alleen AUTO als de confidence de auto-drempel haalt, er een
grootboekrekening is gekoppeld, en er geen blokkerende flags staan. Al het
andere gaat naar de review-queue met een leesbare reden.
"""

from __future__ import annotations

from database.models import Flag, Route, Document

# Flags die AUTO altijd blokkeren (menselijke beoordeling vereist).
_BLOCKING_FLAGS = {Flag.UNKNOWN_TYPE, Flag.AMBIGUOUS, Flag.NO_LEDGER}

_REASON_BY_FLAG = {
    Flag.UNKNOWN_TYPE: "onbekend documenttype",
    Flag.AMBIGUOUS: "dubbelzinnig (bv. suppletie/correctie)",
    Flag.NO_LEDGER: "geen grootboekrekening gevonden",
    Flag.DUPLICATE_SUFFIX: "mogelijk duplicaat (volgnummer in referentie)",
    Flag.MISSING_DATE: "datum ontbreekt",
    Flag.MISSING_AMOUNT: "bedrag ontbreekt",
    Flag.MISSING_CONTACT: "leverancier/contact ontbreekt",
}


def _review_reason(doc: Document, auto_threshold: float) -> str:
    for flag in (Flag.UNKNOWN_TYPE, Flag.AMBIGUOUS, Flag.NO_LEDGER,
                 Flag.DUPLICATE_SUFFIX, Flag.MISSING_DATE):
        if flag in doc.flags:
            return _REASON_BY_FLAG[flag]
    if doc.confidence < auto_threshold:
        return f"confidence {doc.confidence:.2f} < drempel {auto_threshold:.2f}"
    return "handmatige controle vereist"


def route(doc: Document, auto_threshold: float) -> Document:
    blocked = any(flag in doc.flags for flag in _BLOCKING_FLAGS)
    if (
        not blocked
        and doc.ledger_code is not None
        and doc.confidence >= auto_threshold
    ):
        doc.route = Route.AUTO
        doc.review_reason = None
    else:
        doc.route = Route.MANUAL
        doc.review_reason = _review_reason(doc, auto_threshold)
    return doc


def route_all(documents: list[Document], auto_threshold: float) -> list[Document]:
    return [route(doc, auto_threshold) for doc in documents]
