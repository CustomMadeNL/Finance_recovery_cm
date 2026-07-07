import sqlite3
from pathlib import Path

DB = Path("data/cm_finance.db")


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB)


def init_db():
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id TEXT PRIMARY KEY,
        name TEXT,
        company_name TEXT,
        email TEXT,
        data TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ledger_accounts (
        id TEXT PRIMARY KEY,
        name TEXT,
        account_type TEXT,
        data TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tax_rates (
        id TEXT PRIMARY KEY,
        name TEXT,
        percentage REAL,
        data TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchase_invoices (
        id TEXT PRIMARY KEY,
        contact_id TEXT,
        state TEXT,
        total_price REAL,
        invoice_date TEXT,
        data TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS receipts (
        id TEXT PRIMARY KEY,
        contact_id TEXT,
        total_price REAL,
        receipt_date TEXT,
        data TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS review_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        object_id TEXT,
        reason TEXT,
        status TEXT DEFAULT 'OPEN'
    )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database aangemaakt.")