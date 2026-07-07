from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/moneybird_export")
REPORTS_DIR = Path("reports")
OUTPUT_FILE = REPORTS_DIR / "document_analysis.csv"

REPORTS_DIR.mkdir(exist_ok=True)

def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def main():
    files = list(DATA_DIR.glob("*.xlsx"))

    if not files:
        raise FileNotFoundError("Geen Excel-bestanden gevonden in data/moneybird_export")

    frames = []

    for file in files:
        print(f"Lezen: {file}")
        df = pd.read_excel(file)
        df["bronbestand"] = file.name
        frames.append(df)

    all_docs = pd.concat(frames, ignore_index=True)

    all_docs.to_csv(OUTPUT_FILE, index=False)

    print("\nKLAAR")
    print("Aantal documenten:", len(all_docs))
    print("Rapport:", OUTPUT_FILE)

if __name__ == "__main__":
    main()