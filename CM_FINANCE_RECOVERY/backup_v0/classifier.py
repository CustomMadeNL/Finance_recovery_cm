import pandas as pd
from pathlib import Path

INPUT = Path("reports/document_analysis.csv")
OUTPUT = Path("reports/document_classification.csv")


def classify(row):
    supplier = str(row.get("supplier", "")).lower()
    filename = str(row.get("filename", "")).lower()
    text = (supplier + " " + filename)

    category = "Overig"
    confidence = 0.50

    if any(x in text for x in [
        "albert", "jumbo", "lidl", "ah", "plus", "dirk"
    ]):
        category = "Kantoor / Boodschappen"
        confidence = 0.95

    elif any(x in text for x in [
        "shell", "bp", "esso", "texaco", "tinq"
    ]):
        category = "Reiskosten"
        confidence = 0.95

    elif any(x in text for x in [
        "moneybird"
    ]):
        category = "Software"
        confidence = 0.99

    elif any(x in text for x in [
        "kpn", "vodafone", "ziggo", "odido"
    ]):
        category = "Telecom"
        confidence = 0.95

    elif any(x in text for x in [
        "google", "meta", "facebook", "openai", "anthropic"
    ]):
        category = "Marketing / AI"
        confidence = 0.95

    review = "AUTO" if confidence >= 0.90 else "REVIEW"

    return pd.Series([category, confidence, review])


print("CM CLASSIFIER")

df = pd.read_csv(INPUT)

df[["category", "confidence", "status"]] = df.apply(classify, axis=1)

df.to_csv(OUTPUT, index=False)

print(f"Gereed: {OUTPUT}")
print(df["status"].value_counts())