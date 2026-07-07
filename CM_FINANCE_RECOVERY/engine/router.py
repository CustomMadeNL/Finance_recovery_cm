<<<<<<< HEAD
"""Routing: bepaal per document AUTO (straight-through) of MANUAL (review).

Een document gaat alleen AUTO als:
  1. de confidence de auto-drempel haalt,
  2. er een grootboekrekening is gekoppeld,
  3. er geen blokkerende flags staan, en
  4. het document uit het lopende boekjaar komt.

De vierde regel is bewust voor een recovery-traject: alleen actuele, schone
aangiftes worden straight-through verwerkt; historische backlog (oudere jaren)
en documenten zonder af te leiden boekjaar gaan naar de review-queue. Het
lopende boekjaar staat in `config.fiscal_year` (env `CM_FISCAL_YEAR`).
"""

from __future__ import annotations

from database.models import DocType, Flag, Route, Document

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


def _tag_fiscal_year(doc: Document, fiscal_year: int) -> None:
    """Zet HISTORICAL / NO_FISCAL_YEAR op basis van het boekjaar."""
    if doc.ref_year is None:
        doc.add_flag(Flag.NO_FISCAL_YEAR)
    elif doc.ref_year < fiscal_year:
        doc.add_flag(Flag.HISTORICAL)


def _invoice_incomplete(doc: Document) -> bool:
    """Een inkoopfactuur is niet te boeken zonder bedrag én (referentie-)leverancier."""
    return doc.doc_type == DocType.PURCHASE_INVOICE and (
        Flag.MISSING_AMOUNT in doc.flags or Flag.MISSING_SUPPLIER in doc.flags
    )


def _review_reason(doc: Document, fiscal_year: int, auto_threshold: float) -> str:
    if Flag.HISTORICAL in doc.flags:
        return f"historisch boekjaar {doc.ref_year} (< {fiscal_year})"
    for flag in (Flag.UNKNOWN_TYPE, Flag.AMBIGUOUS, Flag.NO_LEDGER,
                 Flag.DUPLICATE_SUFFIX, Flag.MISSING_DATE):
        if flag in doc.flags:
            return _REASON_BY_FLAG[flag]
    if _invoice_incomplete(doc):
        missing = "bedrag" if Flag.MISSING_AMOUNT in doc.flags else "leverancier (in referentie)"
        return f"inkoopfactuur zonder {missing}"
    if Flag.NO_FISCAL_YEAR in doc.flags:
        return "geen boekjaar af te leiden uit de referentie"
    if doc.confidence < auto_threshold:
        return f"confidence {doc.confidence:.2f} < drempel {auto_threshold:.2f}"
    return "handmatige controle vereist"


def route(doc: Document, fiscal_year: int, auto_threshold: float) -> Document:
    _tag_fiscal_year(doc, fiscal_year)

    blocked = any(flag in doc.flags for flag in _BLOCKING_FLAGS) or _invoice_incomplete(doc)
    current_year = doc.ref_year == fiscal_year

    if (
        not blocked
        and current_year
        and doc.ledger_code is not None
        and doc.confidence >= auto_threshold
    ):
        doc.route = Route.AUTO
        doc.review_reason = None
    else:
        doc.route = Route.MANUAL
        doc.review_reason = _review_reason(doc, fiscal_year, auto_threshold)
    return doc


def route_all(documents: list[Document], fiscal_year: int, auto_threshold: float) -> list[Document]:
    return [route(doc, fiscal_year, auto_threshold) for doc in documents]
=======
import pandas as pd
from config import DOCUMENT_LEDGERS, DOCUMENT_ROUTED
from engine.confidence import score_match
from engine.review_queue import add_review_item

def run():
    df = pd.read_csv(DOCUMENT_LEDGERS).fillna("")

    scores, actions, reasons_col = [], [], []

    for _, row in df.iterrows():
        result = score_match(row)
        scores.append(result["score"])
        actions.append(result["action"])
        reasons = "; ".join(result["reasons"])
        reasons_col.append(reasons)

        if result["action"] != "AUTO":
            add_review_item(result["action"], str(row.get("id", "UNKNOWN")), reasons)

    df["confidence_score"] = scores
    df["route_action"] = actions
    df["route_reasons"] = reasons_col

    df.to_csv(DOCUMENT_ROUTED, index=False)

    print("ROUTING OK")
    print(df["route_action"].value_counts())
    print(f"Output: {DOCUMENT_ROUTED}")

if __name__ == "__main__":
    run()
>>>>>>> 06917c4 (Build CM Finance Recovery v1.0 pipeline)
