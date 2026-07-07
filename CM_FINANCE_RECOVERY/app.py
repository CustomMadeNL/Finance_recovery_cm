"""CM Finance Recovery v1.0 — pipeline entrypoint.

Draai de volledige pipeline met één commando:

    python app.py

Stappen: import/sync -> analyse -> ledger-matching -> confidence -> routing ->
review-queue. Alle output komt in `reports/`. De pipeline draait volledig
offline op de meegeleverde Moneybird sync-JSON; er zijn geen secrets of netwerk
nodig. De run eindigt met `KLAAR`.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

# Zorg dat de projectmap altijd importeerbaar is, ongeacht de werkmap.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database.models import Route, Document
from database.repository import DocumentRepository
from importers.loader import sync
from engine.analyzer import analyze_all
from engine.ledger_matcher import match_all
from engine.confidence import score_all
from engine.router import route_all
from engine.review_queue import ReviewQueue


def _write_csv(path: Path, header: list[str], rows: list[list]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def _report_analysis(config: Config, docs: list[Document]) -> Path:
    rows = [
        [d.id, d.parsed_date or "", d.ref_year or "", d.reference, d.doc_type,
         d.supplier or "", d.period or "", "|".join(d.flags)]
        for d in docs
    ]
    return _write_csv(
        config.reports_dir / "document_analysis.csv",
        ["id", "datum", "boekjaar", "referentie", "type", "leverancier", "periode", "flags"],
        rows,
    )


def _report_ledgers(config: Config, docs: list[Document]) -> Path:
    rows = [
        [d.id, d.reference, d.doc_type, d.ledger_code or "",
         d.ledger_name or "", f"{d.ledger_score:.3f}"]
        for d in docs
    ]
    return _write_csv(
        config.reports_dir / "document_ledgers.csv",
        ["id", "referentie", "type", "ledger_code", "ledger_name", "ledger_score"],
        rows,
    )


def _report_routed(config: Config, docs: list[Document]) -> Path:
    rows = [
        [d.id, d.reference, d.doc_type, d.ledger_code or "",
         f"{d.confidence:.3f}", d.route or "", d.review_reason or ""]
        for d in docs
    ]
    return _write_csv(
        config.reports_dir / "document_routed.csv",
        ["id", "referentie", "type", "ledger_code", "confidence", "route", "review_reason"],
        rows,
    )


def run(config: Config | None = None) -> int:
    config = config or Config()
    config.ensure_dirs()

    print("=" * 60)
    print("CM FINANCE RECOVERY v1.0")
    print("=" * 60)

    # 1. Import / sync
    result = sync(config)
    docs = result.documents
    print(f"IMPORT   : sync via {result.source} — {result.deduped_count} documenten "
          f"(van {result.raw_count} ruw)")

    # 2. Persistente opslag (SQLite)
    with DocumentRepository(config.database_file) as repo:
        repo.reset()

        # 3. Analyse
        analyze_all(docs)
        analysis_path = _report_analysis(config, docs)
        print(f"ANALYZE  : {len(docs)} documenten geclassificeerd -> {analysis_path.name}")

        # 4. Ledger-matching
        match_all(docs)
        ledgers_path = _report_ledgers(config, docs)
        matched = sum(1 for d in docs if d.ledger_code)
        print(f"LEDGER   : {matched}/{len(docs)} gekoppeld aan grootboek -> {ledgers_path.name}")

        # 5. Confidence + 6. Routing
        score_all(docs)
        route_all(docs, config.fiscal_year, config.auto_threshold)
        routed_path = _report_routed(config, docs)
        repo.save_many(docs)

        auto = sum(1 for d in docs if d.route == Route.AUTO)
        manual = sum(1 for d in docs if d.route == Route.MANUAL)
        print(f"ROUTING  : AUTO {auto}, MANUAL {manual} "
              f"(drempel {config.auto_threshold:.2f}, boekjaar {config.fiscal_year}) "
              f"-> {routed_path.name}")

        # 7. Review-queue
        queue = ReviewQueue.from_documents(docs)
        queue_path = queue.save(config.reports_dir / "review_queue.csv")
        print(f"REVIEW   : {len(queue)} items in review-queue -> {queue_path.name}")
        top_reasons = ", ".join(f"{r} ({n})" for r, n in queue.reasons().most_common(3))
        if top_reasons:
            print(f"           topredenen: {top_reasons}")

    print("-" * 60)
    print("KLAAR")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
