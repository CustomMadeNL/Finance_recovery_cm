"""Datamodel voor de CM Finance Recovery pipeline.

`Document` is de centrale entiteit die door alle stappen (import -> analyse ->
ledger-matching -> confidence -> routing -> review) heen wordt verrijkt.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# Documenttypes zoals de analyzer ze herkent.
class DocType:
    VAT_RETURN = "vat_return"          # aangifte omzetbelasting / btw
    VAT_SUPPLETION = "vat_suppletion"  # suppletie omzetbelasting (correctie)
    PAYROLL_TAX = "payroll_tax"        # loonaangifte
    INCOME_TAX = "income_tax"          # inkomsten-/vennootschapsbelasting
    PURCHASE_INVOICE = "purchase_invoice"
    LEGAL = "legal"                    # vonnis / brief advocaat / notaris
    REPORT = "report"                  # herstelrapport e.d.
    UNKNOWN = "unknown"


# Routebestemmingen.
class Route:
    AUTO = "AUTO"
    MANUAL = "MANUAL"


# Flags die tijdens analyse/matching gezet kunnen worden.
class Flag:
    MISSING_DATE = "missing_date"
    MISSING_AMOUNT = "missing_amount"
    MISSING_CONTACT = "missing_contact"
    UNKNOWN_TYPE = "unknown_type"
    AMBIGUOUS = "ambiguous"
    DUPLICATE_SUFFIX = "duplicate_suffix"
    NO_LEDGER = "no_ledger"


@dataclass
class Document:
    """Eén financieel document dat door de pipeline stroomt."""

    id: str
    reference: str
    date: Optional[str] = None
    due_date: Optional[str] = None
    contact: Optional[str] = None
    contact_number: Optional[str] = None
    amount: Optional[float] = None

    # Verrijking (analyzer)
    doc_type: str = DocType.UNKNOWN
    supplier: Optional[str] = None
    period: Optional[str] = None
    parsed_date: Optional[str] = None

    # Ledger-matching
    ledger_code: Optional[str] = None
    ledger_name: Optional[str] = None
    ledger_score: float = 0.0

    # Confidence & routing
    confidence: float = 0.0
    route: Optional[str] = None
    review_reason: Optional[str] = None

    flags: list[str] = field(default_factory=list)

    def add_flag(self, flag: str) -> None:
        if flag not in self.flags:
            self.flags.append(flag)

    @property
    def has_amount(self) -> bool:
        return self.amount is not None and self.amount != 0

    @property
    def has_contact(self) -> bool:
        return bool(self.contact and str(self.contact).strip())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_sync(cls, record: dict[str, Any]) -> "Document":
        """Bouw een Document uit een record in de Moneybird sync-JSON."""
        return cls(
            id=str(record.get("id") or "").strip(),
            reference=str(record.get("reference") or "").strip(),
            date=record.get("date"),
            due_date=record.get("due_date"),
            contact=record.get("contact"),
            contact_number=record.get("contact_number"),
            amount=record.get("amount"),
        )


# SQLite-schema voor de repository-laag.
SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id             TEXT PRIMARY KEY,
    reference      TEXT,
    date           TEXT,
    due_date       TEXT,
    contact        TEXT,
    contact_number TEXT,
    amount         REAL,
    doc_type       TEXT,
    supplier       TEXT,
    period         TEXT,
    parsed_date    TEXT,
    ledger_code    TEXT,
    ledger_name    TEXT,
    ledger_score   REAL,
    confidence     REAL,
    route          TEXT,
    review_reason  TEXT,
    flags          TEXT
);
"""
