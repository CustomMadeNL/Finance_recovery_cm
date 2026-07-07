import pandas as pd
from pathlib import Path

DATA = Path("data/moneybird_export")
REPORTS = Path("reports")
REPORTS.mkdir(exist_ok=True)

files = list(DATA.glob("*.xlsx"))

if not files:
    raise FileNotFoundError("Geen Excel-bestanden gevonden in data/moneybird_export")

frames = []

for f in files:
    df = pd.read_excel(f)
    df["source_file"] = f.name
    frames.append(df)

df = pd.concat(frames, ignore_index=True).fillna("")

RULES = {
    "moneybird": "Software",
    "google": "Software",
    "openai": "Software / AI",
    "adobe": "Software",
    "canva": "Software",
    "transip": "Hosting",
    "one.com": "Hosting",
    "yellowbrick": "Parkeren / Autokosten",
    "shell": "Brandstof / Autokosten",
    "bp": "Brandstof / Autokosten",
    "athlon": "Autokosten",
    "ikea": "Inventaris / Kantoorinrichting",
    "gamma": "Inventaris / Onderhoud",
    "praxis": "Inventaris / Onderhoud",
    "action": "Kantoorbenodigdheden",
    "bol.com": "Kantoorbenodigdheden",
    "jumbo": "Representatie / Kantoor",
    "albert heijn": "Representatie / Kantoor",
    "dekamarkt": "Representatie / Kantoor",
    "kpn": "Telefoon / Internet",
    "ziggo": "Telefoon / Internet",
    "odido": "Telefoon / Internet",
    "bennett": "Accountantskosten",
    "belastingdienst": "Belastingen / BTW",
    "kvk": "Overige bedrijfskosten",
    "sor": "Artiestkosten / Voorschotten",
    "kalibwoy": "Artiestkosten",
    "regalo music": "Muziekproductie",
}

def all_text(row):
    return " ".join(str(v) for v in row.values).lower()

def ledger(row):
    t = all_text(row)
    for key, value in RULES.items():
        if key in t:
            return value
    return "REVIEW"

df["suggested_ledger"] = df.apply(ledger, axis=1)
df["processing_status"] = df["suggested_ledger"].apply(lambda x: "AUTO_READY" if x != "REVIEW" else "REVIEW")

df.to_csv(REPORTS / "REAL_1400_PROCESSED.csv", index=False)
df[df["processing_status"] == "AUTO_READY"].to_csv(REPORTS / "REAL_AUTO_READY.csv", index=False)
df[df["processing_status"] == "REVIEW"].to_csv(REPORTS / "REAL_REVIEW_REQUIRED.csv", index=False)

print("KLAAR")
print("Totaal echte documenten:", len(df))
print(df["processing_status"].value_counts())
print("Output: reports/REAL_1400_PROCESSED.csv")
print("Auto: reports/REAL_AUTO_READY.csv")
print("Review: reports/REAL_REVIEW_REQUIRED.csv")
