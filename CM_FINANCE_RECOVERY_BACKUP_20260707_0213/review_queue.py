import sqlite3
from pathlib import Path

DB = Path("data/cm_finance.db")

def add_review_item(item_type, object_id, reason):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO review_queue (type, object_id, reason, status)
        VALUES (?, ?, ?, 'OPEN')
    """, (item_type, object_id, reason))

    conn.commit()
    conn.close()

def list_open_reviews():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, type, object_id, reason, status
        FROM review_queue
        WHERE status = 'OPEN'
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()
    return rows