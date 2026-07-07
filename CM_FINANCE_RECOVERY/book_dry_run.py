"""DRY-RUN van de boekstap — laat zien wàt er naar Moneybird geboekt zou worden.

    python book_dry_run.py                 # alle datasets, alle AUTO-documenten
    python book_dry_run.py --limit 20      # toon max 20 regels in de preview
    CM_FISCAL_YEAR=2023 python book_dry_run.py   # ander boekjaar

Draait de volledige classificatie/routing (import -> analyse -> ledger ->
confidence -> routing) en toont per **AUTO**-document het beoogde boekvoorstel:
grootboekrekening + bedrag + leverancier. Schrijft daarnaast
`reports/dry_run_bookings.csv`.

VEILIG: dit script leest alleen. Er wordt NIETS naar Moneybird geschreven — geen
POST/PATCH, geen state-transitie. Het is puur een preview van wat een echte
write-back-stap zou doen.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database.models import Route, Document
from importers.loader import sync
from engine.analyzer import analyze_all
from engine.ledger_matcher import match_all
from engine.confidence import score_all
from engine.router import route_all


def _supplier(doc: Document) -> str:
    return doc.recognized_supplier or doc.supplier or doc.contact or ""


def plan_bookings(config: Config, dataset: str = "all") -> tuple[list[Document], object]:
    """Draai de pipeline t/m routing en geef de AUTO-documenten terug."""
    config.ensure_dirs()
    result = sync(config, dataset)
    docs = result.documents
    analyze_all(docs)
    match_all(docs)
    score_all(docs)
    route_all(docs, config.fiscal_year, config.auto_threshold)
    auto_docs = [d for d in docs if d.route == Route.AUTO]
    return auto_docs, result


def _write_plan_csv(path: Path, docs: list[Document]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "dataset", "type", "leverancier", "bedrag",
                    "ledger_code", "ledger_name", "boekjaar", "confidence", "referentie"])
        for d in docs:
            w.writerow([d.id, d.dataset, d.doc_type, _supplier(d),
                        f"{d.amount:.2f}" if d.amount is not None else "",
                        d.ledger_code or "", d.ledger_name or "", d.ref_year or "",
                        f"{d.confidence:.3f}", d.reference])
    return path


def dry_run(config: Config | None = None, dataset: str = "all", limit: int | None = None) -> int:
    config = config or Config()

    print("=" * 68)
    print("CM FINANCE RECOVERY — DRY-RUN BOEKSTAP  (geen schrijfacties)")
    print("=" * 68)

    auto_docs, result = plan_bookings(config, dataset)

    print(f"Bron        : {result.source}  ({result.deduped_count} documenten)")
    print(f"Boekjaar    : {config.fiscal_year}   |   confidence-drempel: {config.auto_threshold:.2f}")
    print(f"AUTO-plan   : {len(auto_docs)} documenten zouden geboekt worden\n")

    if not auto_docs:
        print("Geen AUTO-documenten voor dit boekjaar — niets te boeken.")
        return 0

    # Elk AUTO-document heeft gegarandeerd een grootboekrekening; controleer
    # defensief of er toch iets ontbreekt dat een echte boeking zou blokkeren.
    unbookable = [d for d in auto_docs if not d.ledger_code or d.amount is None]

    # Overzicht per grootboekrekening.
    by_ledger: dict[str, dict] = {}
    for d in auto_docs:
        key = f"{d.ledger_code} {d.ledger_name}".strip()
        agg = by_ledger.setdefault(key, {"n": 0, "sum": 0.0})
        agg["n"] += 1
        agg["sum"] += d.amount or 0.0

    total = sum(d.amount or 0.0 for d in auto_docs)

    print("Voorgenomen boekingen per grootboekrekening:")
    print("-" * 68)
    for key, agg in sorted(by_ledger.items(), key=lambda kv: kv[1]["sum"], reverse=True):
        print(f"  {key:<44} {agg['n']:>4}x  EUR {agg['sum']:>12,.2f}")
    print("-" * 68)
    print(f"  {'TOTAAL':<44} {len(auto_docs):>4}x  EUR {total:>12,.2f}\n")

    shown = auto_docs if limit is None else auto_docs[:limit]
    print(f"Regel-voorbeeld ({len(shown)} van {len(auto_docs)}):")
    print("-" * 68)
    for d in shown:
        supplier = (_supplier(d) or "—")[:28]
        bedrag = f"{d.amount:,.2f}" if d.amount is not None else "—"
        print(f"  [{d.dataset:<9}] {d.id}  {supplier:<28} "
              f"EUR {bedrag:>11}  -> {d.ledger_code or '—'} ({d.confidence:.2f})")
    if limit is not None and len(auto_docs) > limit:
        print(f"  … en nog {len(auto_docs) - limit} regels (zie CSV).")

    csv_path = _write_plan_csv(config.reports_dir / "dry_run_bookings.csv", auto_docs)
    print("-" * 68)
    print(f"Volledig boekplan weggeschreven -> {csv_path}")

    if unbookable:
        print(f"\nLET OP: {len(unbookable)} AUTO-document(en) missen grootboek of bedrag "
              f"en zouden bij een echte run overgeslagen worden.")

    print("\nDRY-RUN — er is NIETS naar Moneybird geschreven.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run van de Moneybird-boekstap")
    parser.add_argument("--dataset", choices=["documents", "inkoop", "all"], default="all",
                        help="Welke dataset(s) meenemen (standaard: all).")
    parser.add_argument("--limit", type=int, default=25,
                        help="Aantal regels in de stdout-preview (standaard 25; CSV bevat alles).")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    raise SystemExit(dry_run(dataset=args.dataset, limit=args.limit))
