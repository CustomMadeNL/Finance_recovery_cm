from pathlib import Path

DB_PATH = Path("data/cm_finance.db")

SYNC_DIR = Path("data/sync")
REPORTS_DIR = Path("reports")

DOCUMENT_ANALYSIS = REPORTS_DIR / "document_analysis.csv"
DOCUMENT_MATCHED = REPORTS_DIR / "document_matched.csv"
DOCUMENT_LEDGERS = REPORTS_DIR / "document_ledgers.csv"
DOCUMENT_ROUTED = REPORTS_DIR / "document_routed.csv"

AUTO_THRESHOLD = 95
REVIEW_THRESHOLD = 80