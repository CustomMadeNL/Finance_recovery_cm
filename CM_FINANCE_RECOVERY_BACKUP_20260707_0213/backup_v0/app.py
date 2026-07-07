import os
import csv
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("MONEYBIRD_API_TOKEN")
ADMIN_ID = os.getenv("MONEYBIRD_ADMINISTRATION_ID") or os.getenv("MONEYBIRD_ADMIN_ID")

BASE_URL = f"https://moneybird.com/api/v2/{ADMIN_ID}"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json"
}


def get(endpoint, params=None):
    response = requests.get(
        f"{BASE_URL}{endpoint}",
        headers=HEADERS,
        params=params or {}
    )
    if response.status_code >= 400:
        print("ERROR", response.status_code, response.text)
        response.raise_for_status()
    return response.json()


def get_all(endpoint):
    all_items = []
    page = 1

    while True:
        items = get(endpoint, {"page": page, "per_page": 100})
        if not items:
            break
        all_items.extend(items)
        page += 1

    return all_items


def safe_contact(doc):
    contact = doc.get("contact") or {}
    return (
        contact.get("company_name")
        or contact.get("firstname")
        or contact.get("lastname")
        or ""
    )


def extract_tax_info(doc):
    details = doc.get("details") or []
    if not details:
        return "", "", ""

    first = details[0]

    tax_rate = (
        first.get("tax_rate_id")
        or first.get("tax_rate")
        or first.get("tax_rate_name")
        or ""
    )

    ledger = ""
    ledger_account = first.get("ledger_account") or {}
    if isinstance(ledger_account, dict):
        ledger = ledger_account.get("name") or ledger_account.get("id") or ""

    description = first.get("description") or ""

    return tax_rate, ledger, description


def classify_advice(doc, soort):
    contact = safe_contact(doc)
    date = doc.get("date") or doc.get("invoice_date") or ""
    total = doc.get("total_price_incl_tax") or doc.get("total_price_excl_tax") or "0"
    tax_number = doc.get("tax_number") or ""
    state = doc.get("state") or ""

    missing = []

    if not contact:
        missing.append("contact")
    if not date:
        missing.append("datum")
    if float(str(total).replace(",", ".") or 0) == 0:
        missing.append("bedrag")
    if not tax_number and soort in ["purchase_invoice", "receipt"]:
        missing.append("btw/factuurnummer mogelijk ontbrekend")

    if state == "new":
        status = "NIEUW"
    else:
        status = state

    if missing:
        return f"REVIEW - ontbreekt: {', '.join(missing)}"

    return "OK - kan waarschijnlijk verwerkt worden"


def export_documents():
    print("CM DOCUMENT PROCESSOR — READ ONLY")
    print("Administratie:", ADMIN_ID)

    print("\n1. Inkoopfacturen ophalen...")
    purchase_invoices = get_all("/documents/purchase_invoices.json")
    print("Inkoopfacturen:", len(purchase_invoices))

    print("\n2. Bonnetjes ophalen...")
    receipts = get_all("/documents/receipts.json")
    print("Bonnetjes:", len(receipts))

    documents = []

    for doc in purchase_invoices:
        documents.append(("purchase_invoice", doc))

    for doc in receipts:
        documents.append(("receipt", doc))

    rows = []

    for soort, doc in documents:
        tax_rate, category, line_description = extract_tax_info(doc)

        rows.append({
            "document_id": doc.get("id", ""),
            "soort": soort,
            "status": doc.get("state", ""),
            "contact": safe_contact(doc),
            "datum": doc.get("date") or doc.get("invoice_date") or "",
            "omschrijving": line_description or doc.get("reference", ""),
            "referentie": doc.get("reference", ""),
            "factuurnummer": doc.get("tax_number", ""),
            "bedrag_excl": doc.get("total_price_excl_tax", ""),
            "btw_bedrag": doc.get("total_tax", ""),
            "btw_tarief": tax_rate,
            "bedrag_incl": doc.get("total_price_incl_tax", ""),
            "categorie": category,
            "betaald_op": doc.get("paid_at", ""),
            "valuta": doc.get("currency", ""),
            "advies": classify_advice(doc, soort)
        })

    filename = "cm_document_processor_report.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "document_id",
            "soort",
            "status",
            "contact",
            "datum",
            "omschrijving",
            "referentie",
            "factuurnummer",
            "bedrag_excl",
            "btw_bedrag",
            "btw_tarief",
            "bedrag_incl",
            "categorie",
            "betaald_op",
            "valuta",
            "advies"
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("\nKLAAR.")
    print("Rapport gemaakt:", filename)
    print("Aantal documenten:", len(rows))
    print("Dit script heeft NIETS gewijzigd in Moneybird.")


if __name__ == "__main__":
    export_documents()