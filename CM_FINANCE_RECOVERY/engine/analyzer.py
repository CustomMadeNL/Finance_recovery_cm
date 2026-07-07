"""Analysestap: classificeer documenten en extraheer datum/periode/leverancier.

Werkt op de `referentie` van elk document (de titel zoals die in Moneybird
staat). Pure stdlib; geen externe afhankelijkheden.
"""

from __future__ import annotations

import re
from typing import Optional

from database.models import DocType, Flag, Document

# Leidende datum in de referentie: 2021-04-26 of 26-04-2021.
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_NL_DATE = re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b")

# Kwartaal-/maandbereik: "April 2023 - Juni 2023" of "Oktober2022-December2022".
_PERIOD = re.compile(
    r"(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s*"
    r"(\d{4})?\s*[-–]\s*"
    r"(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s*"
    r"(\d{4})",
    re.IGNORECASE,
)

_SUPPLIER = re.compile(r"factuur\s+van\s+(.+?)(?:[_:]|$)", re.IGNORECASE)
_TIMESTAMP_ONLY = re.compile(r"^\d{2}-\d{2}-\d{4}\s*-\s*\d{2}:\d{2}", re.IGNORECASE)


def _classify(reference: str) -> str:
    ref = reference.lower()
    if _SUPPLIER.search(ref) or ref.startswith("factuur"):
        return DocType.PURCHASE_INVOICE
    if "loonaangifte" in ref or "loonheffing" in ref:
        return DocType.PAYROLL_TAX
    if "inkomstenbelasting" in ref or "vennootschapsbelasting" in ref:
        return DocType.INCOME_TAX
    if "suppletie" in ref:
        return DocType.VAT_SUPPLETION
    if "omzetbelasting" in ref or "btw-aangifte" in ref or "btw aangifte" in ref or "btw-aangifte" in ref:
        return DocType.VAT_RETURN
    if "vonnis" in ref or "advocaten" in ref or "notaris" in ref or ("brief" in ref and "custommade" in ref):
        return DocType.LEGAL
    if "herstelrapport" in ref or "rapport" in ref:
        return DocType.REPORT
    return DocType.UNKNOWN


def _parse_date(reference: str, fallback: Optional[str]) -> Optional[str]:
    m = _ISO_DATE.search(reference)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _NL_DATE.search(reference)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return fallback


def _parse_period(reference: str) -> Optional[str]:
    m = _PERIOD.search(reference)
    if not m:
        return None
    start = m.group(1).capitalize()
    start_year = m.group(2) or m.group(4)
    end = m.group(3).capitalize()
    end_year = m.group(4)
    return f"{start} {start_year} - {end} {end_year}"


def _ref_year(reference: str, parsed_date: Optional[str]) -> Optional[int]:
    """Bepaal het boekjaar uit de referentie zelf (niet de sync-datum).

    Prioriteit: leidende datum -> periode-eindjaar -> los jaartal in de titel.
    """
    m = _ISO_DATE.search(reference)
    if m:
        return int(m.group(1))
    m = _NL_DATE.search(reference)
    if m:
        return int(m.group(3))
    m = _PERIOD.search(reference)
    if m and m.group(4):
        return int(m.group(4))
    # Fallback: een los 4-cijferig jaartal-token (19xx/20xx), ook als het met
    # underscores aan andere tekst vastzit (bv. "Loonaangifte_2024_..."). Losse
    # tokens voorkomen dat lange nummers als "20251029" een schijnjaar opleveren.
    candidate: Optional[int] = None
    for tok in re.split(r"[^0-9]+", reference):
        if len(tok) == 4 and tok[:2] in ("19", "20"):
            candidate = int(tok)
    return candidate


def _year_from_date(value: Optional[str]) -> Optional[int]:
    """Jaar uit een ISO-datum (YYYY-MM-DD)."""
    if not value:
        return None
    m = _ISO_DATE.search(value)
    return int(m.group(1)) if m else None


def _extract_supplier(reference: str) -> Optional[str]:
    m = _SUPPLIER.search(reference)
    if not m:
        return None
    name = m.group(1).strip(" -_")
    return name or None


def analyze(doc: Document) -> Document:
    """Verrijk één document met type, datum, periode, leverancier en flags."""
    ref = doc.reference or ""
    is_invoice = doc.dataset == "inkoop"

    doc.parsed_date = _parse_date(ref, doc.date)
    doc.period = _parse_period(ref)

    if is_invoice:
        # Inkoopfacturen: leverancier uit de REFERENTIE ("Factuur van X"). Het
        # Moneybird-contactveld is bij deze onverwerkte documenten onbetrouwbaar
        # (vaak een default-contact) en wordt daarom niet voor boeking gebruikt.
        # Boekjaar uit de factuurdatum.
        doc.doc_type = DocType.PURCHASE_INVOICE
        # Voorrang: door Moneybird herkende leverancier (OCR) > referentie.
        doc.supplier = doc.recognized_supplier or _extract_supplier(ref)
        doc.ref_year = _year_from_date(doc.date) or _ref_year(ref, doc.parsed_date)
    else:
        doc.doc_type = _classify(ref)
        doc.ref_year = _ref_year(ref, doc.parsed_date)
        if doc.doc_type == DocType.PURCHASE_INVOICE:
            doc.supplier = _extract_supplier(ref)

    # Flags
    if not doc.parsed_date:
        doc.add_flag(Flag.MISSING_DATE)
    if not doc.has_amount:
        doc.add_flag(Flag.MISSING_AMOUNT)
    if not doc.has_contact:
        doc.add_flag(Flag.MISSING_CONTACT)
    if is_invoice and not doc.supplier:
        doc.add_flag(Flag.MISSING_SUPPLIER)
    if not is_invoice and (
        doc.doc_type == DocType.UNKNOWN or _TIMESTAMP_ONLY.match(ref) or ref.lower().startswith("file_")
    ):
        doc.add_flag(Flag.UNKNOWN_TYPE)
    if doc.doc_type == DocType.VAT_SUPPLETION:
        doc.add_flag(Flag.AMBIGUOUS)  # correctie-aangifte: vraagt menselijke check
    if re.search(r"\s\d{1,2}$", ref) and doc.doc_type != DocType.UNKNOWN:
        # trailing volgnummer ("... 1", "... 2") duidt op een variant/duplicaat.
        # Bewust \d{1,2} zodat een afsluitend jaartal ("... Juni 2023") niet meetelt.
        doc.add_flag(Flag.DUPLICATE_SUFFIX)

    return doc


def analyze_all(documents: list[Document]) -> list[Document]:
    return [analyze(doc) for doc in documents]
