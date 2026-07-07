<<<<<<< HEAD
"""Review-queue: verzamel de MANUAL-documenten voor menselijke afhandeling.

Levert een geordende werklijst (hoogste confidence eerst, want die zijn het
snelst af te handelen) en schrijft die naar een CSV. Pure stdlib.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from database.models import Route, Document


class ReviewQueue:
    """In-memory werklijst van documenten die handmatige review nodig hebben."""

    def __init__(self) -> None:
        self._items: list[Document] = []

    @classmethod
    def from_documents(cls, documents: list[Document]) -> "ReviewQueue":
        queue = cls()
        for doc in documents:
            if doc.route == Route.MANUAL:
                queue.add(doc)
        return queue

    def add(self, doc: Document) -> None:
        self._items.append(doc)

    @property
    def items(self) -> list[Document]:
        # Meest afgeronde eerst: hoogste confidence bovenaan.
        return sorted(self._items, key=lambda d: d.confidence, reverse=True)

    def __len__(self) -> int:
        return len(self._items)

    def reasons(self) -> Counter:
        return Counter(d.review_reason or "onbekend" for d in self._items)

    def save(self, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["id", "datum", "referentie", "type", "ledger_code",
                 "ledger_name", "confidence", "review_reason", "flags"]
            )
            for doc in self.items:
                writer.writerow(
                    [doc.id, doc.parsed_date or "", doc.reference, doc.doc_type,
                     doc.ledger_code or "", doc.ledger_name or "",
                     f"{doc.confidence:.3f}", doc.review_reason or "",
                     "|".join(doc.flags)]
                )
        return path
=======
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.models import connect

def add_review_item(item_type, object_id, reason):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO review_queue (item_type, object_id, reason, status)
        VALUES (?, ?, ?, 'OPEN')
    """, (item_type, object_id, reason))
    conn.commit()
    conn.close()

def list_open_reviews():
    conn = connect()
    rows = conn.execute("""
        SELECT id, item_type, object_id, reason, status
        FROM review_queue
        WHERE status = 'OPEN'
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return rows
>>>>>>> 06917c4 (Build CM Finance Recovery v1.0 pipeline)
