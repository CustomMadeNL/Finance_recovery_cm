import pandas as pd

df = pd.read_csv("reports/document_matched.csv")

RULES = {
    "Klarna": "Betalingskosten",
    "Moneybird": "Software",
    "Yellowbrick": "Autokosten",
    "Regalo Music": "Muziekproductie",
    "Bennett": "Accountantskosten",
    "MijnDomein": "Hosting",
    "Bol.com": "Kantoorbenodigdheden",
}

def ledger(contact):
    if pd.isna(contact):
        return "REVIEW"

    for key, value in RULES.items():
        if key.lower() in str(contact).lower():
            return value

    return "REVIEW"

df["ledger"] = df["matched_contact_name"].apply(ledger)

df.to_csv("reports/document_ledgers.csv", index=False)

print(df["ledger"].value_counts())
print("KLAAR")