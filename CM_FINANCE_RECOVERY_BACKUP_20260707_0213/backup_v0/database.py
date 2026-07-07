import sqlite3
from pathlib import Path

DB_PATH = Path("database/cm_finance_recovery.db")

def connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS supplier_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL,
        suggested_category TEXT,
        suggested_vat TEXT,
        confidence REAL DEFAULT 0.8
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS review_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id TEXT,
        supplier_name TEXT,
        chosen_category TEXT,
        chosen_vat TEXT,
        decision TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database klaar.")