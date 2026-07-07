"""Confidence-scoring: bereken hoe zeker de pipeline is van een document.

De score (0..1) combineert de ledger-zekerheid, of het type herkend is, en de
volledigheid (datum/periode/bedrag). Flags trekken de score omlaag. De router
gebruikt deze score om AUTO vs. MANUAL te bepalen.
"""

from __future__ import annotations

from database.models import DocType, Flag, Document

# Gewichten (tellen op tot 1.0 in het ideale, volledig gevulde geval).
W_LEDGER = 0.45
W_TYPE = 0.20
W_DATE = 0.10
W_PERIOD = 0.10
W_AMOUNT = 0.15

# Strafpunten.
P_AMBIGUOUS = 0.25
P_DUPLICATE = 0.20
P_UNKNOWN = 0.40


def score(doc: Document) -> float:
    """Bereken en zet `doc.confidence`; geef de score terug."""
    value = 0.0
    value += W_LEDGER * float(doc.ledger_score or 0.0)
    if doc.doc_type != DocType.UNKNOWN:
        value += W_TYPE
    if doc.parsed_date:
        value += W_DATE
    if doc.period:
        value += W_PERIOD
    if doc.has_amount:
        value += W_AMOUNT

    if Flag.AMBIGUOUS in doc.flags:
        value -= P_AMBIGUOUS
    if Flag.DUPLICATE_SUFFIX in doc.flags:
        value -= P_DUPLICATE
    if Flag.UNKNOWN_TYPE in doc.flags:
        value -= P_UNKNOWN

    value = max(0.0, min(1.0, value))
    doc.confidence = round(value, 3)
    return doc.confidence


def score_all(documents: list[Document]) -> list[Document]:
    for doc in documents:
        score(doc)
    return documents
