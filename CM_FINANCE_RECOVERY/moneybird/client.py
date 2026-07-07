import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

class MoneybirdClient:
    def __init__(self):
        self.token = os.getenv("MONEYBIRD_API_TOKEN")
        self.admin_id = os.getenv("MONEYBIRD_ADMINISTRATION_ID") or os.getenv("MONEYBIRD_ADMIN_ID")
        self.base_url = f"https://moneybird.com/api/v2/{self.admin_id}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get(self, endpoint, query=None):
        response = requests.get(self.base_url + endpoint, headers=self.headers, params=query or {})
        if response.status_code == 429:
            time.sleep(10)
            response = requests.get(self.base_url + endpoint, headers=self.headers, params=query or {})
        if response.status_code >= 400:
            raise RuntimeError(f"Moneybird API error {response.status_code}: {response.text}")
        return response.json()

    def get_all(self, endpoint, params=None):
        results = []
        page = 1
        while True:
            query = params.copy() if params else {}
            query["page"] = page
            query["per_page"] = 100
            batch = self.get(endpoint, query)
            if not batch:
                break
            results.extend(batch)
            page += 1
            time.sleep(1)
        return results

    def contacts(self):
        return self.get_all("/contacts.json")