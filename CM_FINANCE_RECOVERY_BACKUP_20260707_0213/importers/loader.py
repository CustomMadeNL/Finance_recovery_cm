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

if __name__ == "__main__":
    run()
