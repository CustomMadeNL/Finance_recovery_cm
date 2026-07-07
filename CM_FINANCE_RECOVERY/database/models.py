<<<<<<< HEAD
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
    HISTORICAL = "historical"        # ouder dan het lopende boekjaar (recovery-backlog)
    NO_FISCAL_YEAR = "no_fiscal_year"  # geen boekjaar af te leiden uit de referentie
    MISSING_SUPPLIER = "missing_supplier"  # geen leverancier af te leiden uit de referentie


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
    status: Optional[str] = None      # Moneybird-status (bv. "new")
    paid_at: Optional[str] = None     # betaaldatum, indien betaald
    dataset: str = "documents"        # herkomst: "documents" of "inkoop"

    # Verrijking (analyzer)
    doc_type: str = DocType.UNKNOWN
    supplier: Optional[str] = None
    # Door Moneybird herkende leverancier (OCR). Betrouwbaarder dan de referentie;
    # gevuld door de verrijkingsstap zodra die data beschikbaar is.
    recognized_supplier: Optional[str] = None
    period: Optional[str] = None
    parsed_date: Optional[str] = None
    ref_year: Optional[int] = None  # expliciet boekjaar uit de referentie (niet de sync-datum)

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
            status=record.get("status"),
            paid_at=record.get("paid_at"),
            recognized_supplier=record.get("recognized_supplier"),
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
    status         TEXT,
    paid_at        TEXT,
    dataset        TEXT,
    doc_type       TEXT,
    supplier       TEXT,
    recognized_supplier TEXT,
    period         TEXT,
    parsed_date    TEXT,
    ref_year       INTEGER,
    ledger_code    TEXT,
    ledger_name    TEXT,
    ledger_score   REAL,
    confidence     REAL,
    route          TEXT,
    review_reason  TEXT,
    flags          TEXT
);
"""
=======
import sqlite3
from config import DB_PATH

def connect():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = connect()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id TEXT PRIMARY KEY, name TEXT, company_name TEXT, email TEXT, data TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ledger_accounts (
        id TEXT PRIMARY KEY, name TEXT, account_type TEXT, data TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS tax_rates (
        id TEXT PRIMARY KEY, name TEXT, percentage REAL, data TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS purchase_invoices (
        id TEXT PRIMARY KEY, contact_id TEXT, state TEXT, total_price REAL,
        invoice_date TEXT, data TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS receipts (
        id TEXT PRIMARY KEY, contact_id TEXT, total_price REAL, receipt_date TEXT, data TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS review_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type TEXT, object_id TEXT, reason TEXT, status TEXT DEFAULT 'OPEN'
    )""")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("DATABASE OK")
>>>>>>> 06917c4 (Build CM Finance Recovery v1.0 pipeline)
