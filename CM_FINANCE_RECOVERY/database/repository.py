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
    "amount", "doc_type", "supplier", "period", "parsed_date",
    "ledger_code", "ledger_name", "ledger_score", "confidence",
    "route", "review_reason", "flags",
]


class DocumentRepository:
    """CRUD rond de `documents`-tabel."""

    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def reset(self) -> None:
        """Leeg de tabel voor een verse run (idempotent)."""
        self._conn.execute("DELETE FROM documents")
        self._conn.commit()

    @staticmethod
    def _to_row(doc: Document) -> tuple:
        return (
            doc.id, doc.reference, doc.date, doc.due_date, doc.contact,
            doc.contact_number, doc.amount, doc.doc_type, doc.supplier,
            doc.period, doc.parsed_date, doc.ledger_code, doc.ledger_name,
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
