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

            cols = ",".join(record.keys())
            placeholders = ",".join(["?"] * len(record))
            values = list(record.values())

            self.cur.execute(
                f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
                values
            )

        self.conn.commit()

    def count(self, table):
        self.cur.execute(f"SELECT COUNT(*) FROM {table}")
        return self.cur.fetchone()[0]

    def close(self):
        self.conn.close()
