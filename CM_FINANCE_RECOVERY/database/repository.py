<<<<<<< HEAD
"""Persistentielaag voor de CM Finance Recovery pipeline.

Gebruikt uitsluitend de Python-stdlib (`sqlite3`), zodat de pipeline zonder
externe database of afhankelijkheden draait. De database (`data/recovery.db`)
is een wegwerp-cache van de laatste run en staat in `.gitignore`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from database.models import SCHEMA, Document

_COLUMNS = [
    "id", "reference", "date", "due_date", "contact", "contact_number",
    "amount", "status", "paid_at", "dataset", "doc_type", "supplier",
    "recognized_supplier", "period", "parsed_date", "ref_year", "ledger_code", "ledger_name",
    "ledger_score", "confidence", "route", "review_reason", "flags",
]


class DocumentRepository:
    """CRUD rond de `documents`-tabel."""

    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        # Wegwerp-cache: schema vers opbouwen zodat schemawijzigingen tussen
        # runs nooit een oude tabel achterlaten.
        self._conn.execute("DROP TABLE IF EXISTS documents")
        self._conn.executescript(SCHEMA)

    def reset(self) -> None:
        """Leeg de tabel voor een verse run (idempotent)."""
        self._conn.execute("DELETE FROM documents")
        self._conn.commit()

    @staticmethod
    def _to_row(doc: Document) -> tuple:
        return (
            doc.id, doc.reference, doc.date, doc.due_date, doc.contact,
            doc.contact_number, doc.amount, doc.status, doc.paid_at,
            doc.dataset, doc.doc_type, doc.supplier, doc.recognized_supplier,
            doc.period, doc.parsed_date, doc.ref_year, doc.ledger_code, doc.ledger_name,
            doc.ledger_score, doc.confidence, doc.route, doc.review_reason,
            json.dumps(doc.flags, ensure_ascii=False),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Document:
        data = dict(row)
        data["flags"] = json.loads(data.get("flags") or "[]")
        return Document(**data)

    def save(self, doc: Document) -> None:
        placeholders = ",".join(["?"] * len(_COLUMNS))
        self._conn.execute(
            f"INSERT OR REPLACE INTO documents ({','.join(_COLUMNS)}) VALUES ({placeholders})",
            self._to_row(doc),
        )
        self._conn.commit()

    def save_many(self, docs: Iterable[Document]) -> int:
        rows = [self._to_row(d) for d in docs]
        placeholders = ",".join(["?"] * len(_COLUMNS))
        self._conn.executemany(
            f"INSERT OR REPLACE INTO documents ({','.join(_COLUMNS)}) VALUES ({placeholders})",
            rows,
        )
        self._conn.commit()
        return len(rows)

    def all(self) -> list[Document]:
        cur = self._conn.execute(f"SELECT {','.join(_COLUMNS)} FROM documents ORDER BY id")
        return [self._from_row(r) for r in cur.fetchall()]

    def by_route(self, route: str) -> list[Document]:
        cur = self._conn.execute(
            f"SELECT {','.join(_COLUMNS)} FROM documents WHERE route = ? ORDER BY id",
            (route,),
        )
        return [self._from_row(r) for r in cur.fetchall()]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "DocumentRepository":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
=======
import json
from database.models import connect

class Repository:
    def __init__(self):
        self.conn = connect()
        self.cur = self.conn.cursor()

    def save_many(self, table, rows):
        if not rows:
            return

        for row in rows:
            record = {"data": json.dumps(row, ensure_ascii=False)}

            if table == "contacts":
                record.update({
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "company_name": row.get("company_name"),
                    "email": row.get("email"),
                })
            elif table == "ledger_accounts":
                record.update({
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "account_type": row.get("account_type"),
                })
            elif table == "tax_rates":
                record.update({
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "percentage": row.get("percentage"),
                })
            elif table == "purchase_invoices":
                record.update({
                    "id": row.get("id"),
                    "contact_id": row.get("contact_id"),
                    "state": row.get("state"),
                    "total_price": row.get("total_price"),
                    "invoice_date": row.get("invoice_date"),
                })
            elif table == "receipts":
                record.update({
                    "id": row.get("id"),
                    "contact_id": row.get("contact_id"),
                    "total_price": row.get("total_price"),
                    "receipt_date": row.get("receipt_date"),
                })
            else:
                raise ValueError(f"Unknown table: {table}")

            cols = ",".join(record.keys())
            placeholders = ",".join(["?"] * len(record))
            self.cur.execute(
                f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
                list(record.values())
            )

        self.conn.commit()

    def count(self, table):
        self.cur.execute(f"SELECT COUNT(*) FROM {table}")
        return self.cur.fetchone()[0]

    def close(self):
        self.conn.close()
>>>>>>> 06917c4 (Build CM Finance Recovery v1.0 pipeline)
