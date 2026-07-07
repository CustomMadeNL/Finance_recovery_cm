import json
from pathlib import Path
from database.repository import Repository

SYNC = Path("data/sync")

FILES = {
    "contacts.json": "contacts",
    "ledger_accounts.json": "ledger_accounts",
    "tax_rates.json": "tax_rates",
    "purchase_invoices.json": "purchase_invoices",
    "receipts.json": "receipts",
}

def main():
    repo = Repository()

    for filename, table in FILES.items():
        path = SYNC / filename

        if not path.exists():
            print(f"Overslaan: {filename}")
            continue

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        repo.save_many(table, data)
        print(f"{table}: {len(data)} geïmporteerd")

    repo.close()
    print("IMPORT KLAAR")

if __name__ == "__main__":
    main()
