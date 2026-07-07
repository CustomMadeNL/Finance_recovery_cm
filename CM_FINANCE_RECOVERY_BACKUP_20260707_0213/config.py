from pathlib import Path

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"
SYNC_DIR = DATA_DIR / "sync"
REPORTS_DIR = ROOT / "reports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
SYNC_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "cm_finance.db"

DOCUMENT_ANALYSIS = REPORTS_DIR / "document_analysis.csv"
DOCUMENT_MATCHED = REPORTS_DIR / "document_matched.csv"
DOCUMENT_LEDGERS = REPORTS_DIR / "document_ledgers.csv"
DOCUMENT_ROUTED = REPORTS_DIR / "document_routed.csv"

AUTO_THRESHOLD = 95
REVIEW_THRESHOLD = 80
