import json
from pathlib import Path

from moneybird.client import MoneybirdClient

DATA_DIR = Path("data/sync")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_json(name, data):
    path = DATA_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"{name}: {len(data)} opgeslagen → {path}")


def main():
    c = MoneybirdClient()

    save_json("contacts", c.get_all("/contacts.json"))
    save_json("ledger_accounts", c.get("/ledger_accounts.json"))
    save_json("tax_rates", c.get("/tax_rates.json"))
    save_json("purchase_invoices", c.get("/documents/purchase_invoices.json"))
    save_json("receipts", c.get("/documents/receipts.json"))

    print("SYNC KLAAR")


if __name__ == "__main__":
    main()