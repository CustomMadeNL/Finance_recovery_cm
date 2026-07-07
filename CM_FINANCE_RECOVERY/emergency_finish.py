import pandas as pd
from pathlib import Path

REPORTS = Path("reports")
REPORTS.mkdir(exist_ok=True)

INPUT = REPORTS / "document_analysis.csv"

if not INPUT.exists():
    raise FileNotFoundError("reports/document_analysis.csv bestaat niet. Run eerst: python analyzer.py")

df = pd.read_csv(INPUT).fillna("")

RULES = {
    "moneybird": ("Software", "21%"),
    "google": ("Software", "21%"),
    "openai": ("Software / AI", "21%"),
    "adobe": ("Software", "21%"),
    "canva": ("Software", "21%"),
    "transip": ("Hosting", "21%"),
    "one.com": ("Hosting", "21%"),
    "mijndomein": ("Hosting", "21%"),
    "yellowbrick": ("Parkeren / Autokosten", "21%"),
    "shell": ("Brandstof / Autokosten", "21%"),
    "bp": ("Brandstof / Autokosten", "21%"),
    "esso": ("Brandstof / Autokosten", "21%"),
    "eg services": ("Brandstof / Autokosten", "21%"),
    "athlon": ("Autokosten", "21%"),
    "autoradam": ("Autokosten", "21%"),
    "ikea": ("Inventaris / Kantoorinrichting", "21%"),
    "gamma": ("Inventaris / Onderhoud", "21%"),
    "praxis": ("Inventaris / Onderhoud", "21%"),
    "action": ("Kantoorbenodigdheden", "21%"),
    "bol.com": ("Kantoorbenodigdheden", "21%"),
    "jumbo": ("Representatie / Kantoor", "9/21%"),
    "albert heijn": ("Representatie / Kantoor", "9/21%"),
    "dekamarkt": ("Representatie / Kantoor", "9/21%"),
    "kpn": ("Telefoon / Internet", "21%"),
    "ziggo": ("Telefoon / Internet", "21%"),
    "odido": ("Telefoon / Internet", "21%"),
    "vodafone": ("Telefoon / Internet", "21%"),
    "bennett": ("Accountantskosten", "21%"),
    "belastingdienst": ("Belastingen / BTW", "0%"),
    "kvk": ("Overige bedrijfskosten", "21%"),
    "sor": ("Artiestkosten / Voorschotten", "0/21%"),
    "kalibwoy": ("Artiestkosten", "0/21%"),
    "regalo music": ("Muziekproductie", "21%"),
}

def text(row):
    return " ".join(str(v) for v in row.values).lower()

def suggest(row):
    t = text(row)
    for key, value in RULES.items():
        if key in t:
            return value[0], value[1], key
    return "REVIEW", "REVIEW", ""

def has_value(row, names):
    for n in names:
        if n in row.index and str(row[n]).strip():
            return True
    return False

ledgers, vats, matched_rules, actions, reasons = [], [], [], [], []

for _, row in df.iterrows():
    ledger, vat, rule = suggest(row)

    has_date = has_value(row, ["date", "datum", "invoice_date"])
    has_amount = has_value(row, ["total_price", "totaalbedrag", "bedrag", "total_price_incl_tax"])
    has_contact = has_value(row, ["contact_name", "contact", "leverancier"])

    reason = []

    if ledger == "REVIEW":
        reason.append("Geen zekere grootboekregel")
    if not has_date:
        reason.append("Datum ontbreekt")
    if not has_amount:
        reason.append("Bedrag ontbreekt")
    if not has_contact:
        reason.append("Contact ontbreekt")

    if ledger != "REVIEW" and has_date and has_amount:
        action = "AUTO_READY"
    else:
        action = "REVIEW"

    ledgers.append(ledger)
    vats.append(vat)
    matched_rules.append(rule)
    actions.append(action)
    reasons.append("; ".join(reason))

df["suggested_ledger"] = ledgers
df["suggested_vat"] = vats
df["matched_rule"] = matched_rules
df["processing_status"] = actions
df["review_reason"] = reasons

processed = REPORTS / "FINAL_1400_PROCESSED.csv"
auto = REPORTS / "FINAL_AUTO_READY.csv"
review = REPORTS / "FINAL_REVIEW_REQUIRED.csv"
summary = REPORTS / "FINAL_SUMMARY.txt"

df.to_csv(processed, index=False)
df[df["processing_status"] == "AUTO_READY"].to_csv(auto, index=False)
df[df["processing_status"] == "REVIEW"].to_csv(review, index=False)

with open(summary, "w") as f:
    f.write("CM MONEYBIRD SPOEDVERWERKING\n")
    f.write("============================\n\n")
    f.write(f"Totaal documenten: {len(df)}\n")
    f.write(str(df["processing_status"].value_counts()))
    f.write("\n\nTop grootboeken:\n")
    f.write(str(df["suggested_ledger"].value_counts().head(30)))

print("KLAAR")
print("Totaal:", len(df))
print(df["processing_status"].value_counts())
print("Processed:", processed)
print("Auto-ready:", auto)
print("Review:", review)
print("Summary:", summary)
