import pandas as pd
from pathlib import Path

INPUT = Path("reports/document_analysis.csv")
OUTPUT = Path("reports/1400_processed.csv")
REVIEW = Path("reports/1400_review_queue.csv")

RULES = {
    "moneybird": "Software",
    "google": "Software",
    "transip": "Hosting",
    "one.com": "Hosting",
    "shell": "Autokosten",
    "bp": "Autokosten",
    "athlon": "Autokosten",
    "yellowbrick": "Autokosten",
    "jumbo": "Kantoorbenodigdheden",
    "albert heijn": "Kantoorbenodigdheden",
    "dekamarkt": "Kantoorbenodigdheden",
    "ikea": "Inventaris",
    "bennett": "Accountantskosten",
}

df = pd.read_csv(INPUT).fillna("")

def get_text(row):
    return " ".join(str(v) for v in row.values).lower()

def match_ledger(row):
    text = get_text(row)
    for key, ledger in RULES.items():
        if key in text:
            return ledger
    return "REVIEW"

def route(row):
    ledger = row["ledger"]
    text = get_text(row)
    has_vendor = any(x in text for x in RULES.keys())
    if ledger != "REVIEW" and has_vendor:
        return "AUTO"
    return "REVIEW"

df["ledger"] = df.apply(match_ledger, axis=1)
df["route_action"] = df.apply(route, axis=1)
df["review_reason"] = df["ledger"].apply(lambda x: "" if x != "REVIEW" else "Geen zekere ledger-match")

df.to_csv(OUTPUT, index=False)
df[df["route_action"] != "AUTO"].to_csv(REVIEW, index=False)

print("KLAAR")
print("Totaal verwerkt:", len(df))
print(df["route_action"].value_counts())
print("Output:", OUTPUT)
print("Review:", REVIEW)
