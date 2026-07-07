import json
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import * 

def run():
    conn = connect()

    rows = conn.execute("""
        SELECT id, contact_id, state, total_price, invoice_date, data
        FROM purchase_invoices
    """).fetchall()

    output = []

    for id_, contact_id, state, total_price, invoice_date, raw in rows:
        data = json.loads(raw or "{}")

        output.append({
            "id": id_,
            "type": "purchase_invoice",
            "contact_id": contact_id or "",
            "state": state or "",
            "total_price": total_price or 0,
            "date": invoice_date or "",
            "reference": data.get("reference", ""),
            "contact_name": (data.get("contact") or {}).get("company_name", ""),
            "status": "ANALYZED",
        })

    df = pd.DataFrame(output)
    df.to_csv(DOCUMENT_ANALYSIS, index=False)

    conn.close()

    print(f"ANALYZE OK: {len(df)} documenten")
    print(f"Output: {DOCUMENT_ANALYSIS}")

if __name__ == "__main__":
    run()
