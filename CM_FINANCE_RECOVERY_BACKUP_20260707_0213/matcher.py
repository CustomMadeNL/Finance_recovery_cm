import json
import re
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

DOCS_FILE = Path("reports/document_analysis.csv")
CONTACTS_FILE = Path("data/sync/contacts.json")
OUTPUT_FILE = Path("reports/document_matched.csv")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def norm(value):
    value = str(value or "").lower()
    value = re.sub(r"\b(b\.v\.|bv|b\.v|n\.v\.|nv|vof|v\.o\.f\.|the|de)\b", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return value.strip()


def contact_name(contact):
    return (
        contact.get("company_name")
        or f"{contact.get('firstname','')} {contact.get('lastname','')}".strip()
        or ""
    )


def build_contact_index(contacts):
    index = []
    for c in contacts:
        name = contact_name(c)
        if not name:
            continue

        index.append({
            "id": c.get("id"),
            "name": name,
            "norm": norm(name),
            "tax_number": norm(c.get("tax_number")),
            "chamber": norm(c.get("chamber_of_commerce")),
            "iban": norm(c.get("bank_account")),
            "email": norm(c.get("email")),
        })

    return index


def extract_vendor(row):
    """
    Strenge vendor-extractie:
    1. Gebruik Moneybird contactveld als dat gevuld is.
    2. Gebruik alleen expliciete patronen zoals 'Factuur van ...' of 'Bon van ...'.
    3. Geen losse B.V.-namen uit omschrijving pakken, want dat gaf valse TransIP/IKEA matches.
    """

    contact = str(row.get("contact", "")).strip()
    if contact and contact.lower() not in ["geen contact", "nan", "none", ""]:
        return contact

    text = " ".join([
        str(row.get("referentie", "")),
        str(row.get("omschrijving", "")),
    ])

    patterns = [
        r"factuur van ([A-Za-z0-9 .&'’\-]+?)(?:_|,| -|$)",
        r"bon van ([A-Za-z0-9 .&'’\-]+?)(?:_|,| -|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            vendor = match.group(1).strip()
            vendor = re.sub(r"\s+", " ", vendor)
            return vendor

    return ""


def exact_match(vendor_norm, text_norm, contacts):
    # Eerst harde identifiers: btw, KvK, IBAN, email
    for c in contacts:
        for key in ["tax_number", "chamber", "iban", "email"]:
            value = c.get(key)
            if value and value in text_norm:
                return c, 100, f"EXACT_{key.upper()}"

    # Daarna exacte vendornaam
    if vendor_norm:
        for c in contacts:
            if c["norm"] == vendor_norm:
                return c, 100, "EXACT_VENDOR_NAME"

        for c in contacts:
            if c["norm"] and c["norm"] in vendor_norm:
                return c, 98, "PARTIAL_VENDOR_NAME"

    return None, 0, ""


def fuzzy_match(vendor_norm, contacts):
    names = [c["norm"] for c in contacts]

    if not vendor_norm or not names:
        return None, 0, ""

    result = process.extractOne(vendor_norm, names, scorer=fuzz.token_set_ratio)

    if not result:
        return None, 0, ""

    matched_norm, score, idx = result
    return contacts[idx], score, "FUZZY_VENDOR_NAME"


def main():
    docs = pd.read_csv(DOCS_FILE).fillna("")
    contacts = build_contact_index(load_json(CONTACTS_FILE))

    rows = []

    for _, row in docs.iterrows():
        vendor = extract_vendor(row)
        vendor_norm = norm(vendor)

        full_text = " ".join([
            str(row.get("contact", "")),
            str(row.get("referentie", "")),
            str(row.get("omschrijving", "")),
        ])
        text_norm = norm(full_text)

        matched, score, method = exact_match(vendor_norm, text_norm, contacts)

        if not matched:
            matched, score, method = fuzzy_match(vendor_norm, contacts)

        new_row = row.to_dict()
        new_row["extracted_vendor"] = vendor

        if matched and score >= 95:
            new_row["matched_contact_id"] = matched["id"]
            new_row["matched_contact_name"] = matched["name"]
            new_row["contact_match_score"] = round(score, 2)
            new_row["contact_match_method"] = method
            new_row["match_status"] = "AUTO_CONTACT"

        elif matched and score >= 85:
            new_row["matched_contact_id"] = matched["id"]
            new_row["matched_contact_name"] = matched["name"]
            new_row["contact_match_score"] = round(score, 2)
            new_row["contact_match_method"] = method
            new_row["match_status"] = "REVIEW_CONTACT"

        else:
            new_row["matched_contact_id"] = ""
            new_row["matched_contact_name"] = ""
            new_row["contact_match_score"] = round(score, 2) if score else 0
            new_row["contact_match_method"] = method
            new_row["match_status"] = "NO_CONTACT_MATCH"

        rows.append(new_row)

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_FILE, index=False)

    print("VENDOR MATCHER V2 STRICT KLAAR")
    print("Documenten:", len(out))
    print(out["match_status"].value_counts())
    print("Output:", OUTPUT_FILE)

    print("\nTop extracted vendors:")
    print(out["extracted_vendor"].value_counts().head(30))


if __name__ == "__main__":
    main()