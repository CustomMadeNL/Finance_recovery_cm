import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("MONEYBIRD_API_TOKEN")
ADMIN = os.getenv("MONEYBIRD_ADMINISTRATION_ID") or os.getenv("MONEYBIRD_ADMIN_ID")

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json"
}

base = f"https://moneybird.com/api/v2/{ADMIN}"

endpoints = [
    "/documents.json",
    "/documents/incoming_documents.json",
    "/incoming_documents.json",
    "/documents/scan_and_recognize.json",
    "/documents/receipts.json?state=new",
    "/documents/purchase_invoices.json?state=new",
]

for endpoint in endpoints:
    url = base + endpoint
    r = requests.get(url, headers=headers)
    print("\n==============================")
    print(endpoint)
    print("STATUS:", r.status_code)
    print(r.text[:1200])