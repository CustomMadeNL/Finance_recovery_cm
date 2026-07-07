#!/usr/bin/env bash
set -e

mkdir -p database importers engine data/sync reports backup_v1 docs tests
touch database/__init__.py importers/__init__.py engine/__init__.py

cat > config.py <<'PY'
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SYNC_DIR = DATA_DIR / "sync"
REPORTS_DIR = ROOT / "reports"
DB_PATH = DATA_DIR / "cm_finance.db"

DOCUMENT_ANALYSIS = REPORTS_DIR / "document_analysis.csv"
DOCUMENT_MATCHED = REPORTS_DIR / "document_matched.csv"
DOCUMENT_LEDGERS = REPORTS_DIR / "document_ledgers.csv"
DOCUMENT_ROUTED = REPORTS_DIR / "document_routed.csv"

AUTO_THRESHOLD = 95
REVIEW_THRESHOLD = 80

for p in [DATA_DIR, SYNC_DIR, REPORTS_DIR]:
    p.mkdir(parents=True, exist_ok=True)
PY

cat > database/models.py <<'PY'
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
PY

cat > database/repository.py <<'PY'
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
PY

cat > importers/loader.py <<'PY'
import json
from config import SYNC_DIR
from database.repository import Repository

FILES = {
    "contacts.json": "contacts",
    "ledger_accounts.json": "ledger_accounts",
    "tax_rates.json": "tax_rates",
    "purchase_invoices.json": "purchase_invoices",
    "receipts.json": "receipts",
}

def run():
    repo = Repository()

    for filename, table in FILES.items():
        path = SYNC_DIR / filename
        if not path.exists():
            print(f"SKIP {filename}")
            continue

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        repo.save_many(table, data)
        print(f"{table}: {len(data)} geïmporteerd")

    repo.close()
    print("IMPORT OK")
PY

cat > engine/analyzer.py <<'PY'
import json
import pandas as pd
from config import DOCUMENT_ANALYSIS
from database.models import connect

def run():
    conn = connect()
    rows = conn.execute("""
        SELECT id, contact_id, state, total_price, invoice_date, data
        FROM purchase_invoices
    """).fetchall()

    output = []

    for id_, contact_id, state, total_price, invoice_date, raw in rows:
        data = json.loads(raw or "{}")
        contact = data.get("contact") or {}

        output.append({
            "id": id_,
            "type": "purchase_invoice",
            "contact_id": contact_id or "",
            "state": state or "",
            "total_price": total_price or 0,
            "date": invoice_date or "",
            "reference": data.get("reference", ""),
            "contact_name": contact.get("company_name", "") or contact.get("name", ""),
            "ledger": "",
            "status": "ANALYZED",
        })

    df = pd.DataFrame(output)
    df.to_csv(DOCUMENT_ANALYSIS, index=False)
    conn.close()

    print(f"ANALYZE OK: {len(df)} documenten")
    print(f"Output: {DOCUMENT_ANALYSIS}")
PY

cat > engine/confidence.py <<'PY'
from config import AUTO_THRESHOLD, REVIEW_THRESHOLD

def score_match(row):
    score = 0
    reasons = []

    contact = str(row.get("contact_name", "") or row.get("matched_contact_name", "")).strip()
    ledger = str(row.get("ledger", "")).strip()
    reference = str(row.get("reference", "")).strip()

    if contact:
        score += 45
    else:
        reasons.append("Geen contact")

    if ledger and ledger.upper() != "REVIEW":
        score += 40
    else:
        reasons.append("Geen ledger")

    if reference:
        score += 15
    else:
        reasons.append("Geen referentie")

    if score >= AUTO_THRESHOLD:
        action = "AUTO"
    elif score >= REVIEW_THRESHOLD:
        action = "REVIEW"
    else:
        action = "MANUAL"

    return {"score": score, "action": action, "reasons": reasons}
PY

cat > engine/review_queue.py <<'PY'
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
PY

cat > engine/router.py <<'PY'
import pandas as pd
from config import DOCUMENT_ANALYSIS, DOCUMENT_ROUTED
from engine.confidence import score_match
from engine.review_queue import add_review_item

def run():
    df = pd.read_csv(DOCUMENT_ANALYSIS).fillna("")

    scores = []
    actions = []
    reasons_col = []

    for _, row in df.iterrows():
        result = score_match(row)
        scores.append(result["score"])
        actions.append(result["action"])
        reasons = "; ".join(result["reasons"])
        reasons_col.append(reasons)

        if result["action"] in ["REVIEW", "MANUAL"]:
            add_review_item(
                result["action"],
                str(row.get("id", "UNKNOWN")),
                reasons or "Confidence onder AUTO-drempel"
            )

    df["confidence_score"] = scores
    df["route_action"] = actions
    df["route_reasons"] = reasons_col
    df.to_csv(DOCUMENT_ROUTED, index=False)

    print("ROUTING OK")
    print(df["route_action"].value_counts())
    print(f"Output: {DOCUMENT_ROUTED}")
PY

cat > app.py <<'PY'
from database.models import init_db
from importers.loader import run as import_sync
from engine.analyzer import run as analyze
from engine.router import run as route

def main():
    print("CM FINANCE RECOVERY v1.0")
    print("=========================")

    print("1. Database init")
    init_db()

    print("2. Import sync data")
    import_sync()

    print("3. Analyze")
    analyze()

    print("4. Route")
    route()

    print("KLAAR")

if __name__ == "__main__":
    main()
PY

python -m py_compile config.py database/models.py database/repository.py importers/loader.py engine/analyzer.py engine/confidence.py engine/review_queue.py engine/router.py app.py
python app.py
