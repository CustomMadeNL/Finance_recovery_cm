"""CM Finance Recovery — command line entrypoint.

Leest inkoopfacturen in (uit een Moneybird Excel-export of live via de API),
classificeert ze, matcht ontbrekende leveranciers, en produceert een rapport met
werklijsten. Standaard draait alles als **dry-run**: er wordt niets in Moneybird
gewijzigd. Pas met `--apply` worden auto-matches teruggeschreven.

Voorbeelden:

    # Analyse van een export (geen API nodig):
    python app.py --source excel --invoices ../inkoop.xlsx

    # Live tegen Moneybird (leest credentials uit .env), nog steeds dry-run:
    python app.py --source api

    # Live én auto-matches wegschrijven:
    python app.py --source api --apply
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Optional, Sequence

from config import Config
from matcher import MatchResult, SupplierMatcher
from moneybird import (
    MoneybirdClient,
    PurchaseInvoice,
    load_invoices_from_excel,
)
from rules import Classification, Issue, classify_all


def _load_invoices(args: argparse.Namespace, config: Config) -> tuple[list[PurchaseInvoice], list[str]]:
    """Geef (facturen, contactnamen) terug op basis van de gekozen bron."""
    if args.source == "excel":
        if not args.invoices:
            raise SystemExit("--invoices <pad naar inkoop.xlsx> is verplicht bij --source excel")
        invoices = load_invoices_from_excel(args.invoices)
        contact_names: list[str] = []
        if args.contacts:
            # Optioneel: contacten uit de export halen die wél een contact hebben.
            contact_names = sorted({inv.contact for inv in invoices if inv.contact})
        else:
            contact_names = sorted({inv.contact for inv in invoices if inv.contact})
        return invoices, contact_names

    # source == "api"
    client = MoneybirdClient(config)
    invoices = list(client.iter_purchase_invoices())
    raw_contacts = client.list_contacts()
    contact_names = sorted(
        {
            (c.get("company_name") or c.get("full_name") or "").strip()
            for c in raw_contacts
            if (c.get("company_name") or c.get("full_name"))
        }
    )
    return invoices, contact_names


def _print_summary(classifications: Sequence[Classification], matches: dict[str, MatchResult]) -> None:
    total = len(classifications)
    issue_counter: Counter[Issue] = Counter()
    for c in classifications:
        for issue in c.issues:
            issue_counter[issue] += 1

    decision_counter: Counter[str] = Counter(m.decision for m in matches.values())

    print("=" * 60)
    print("CM FINANCE RECOVERY — samenvatting")
    print("=" * 60)
    print(f"Inkoopfacturen totaal      : {total}")
    print(f"  zonder leverancier       : {issue_counter[Issue.MISSING_CONTACT]}")
    print(f"  zonder bedrag            : {issue_counter[Issue.MISSING_AMOUNT]}")
    print(f"  mogelijk dubbel          : {issue_counter[Issue.POSSIBLE_DUPLICATE]}")
    print(f"  btw-aangifte/document    : {issue_counter[Issue.TAX_RETURN]}")
    print(f"  onverwerkt (status=new)  : {issue_counter[Issue.UNPROCESSED]}")
    print(f"  geen issues (ok)         : {issue_counter[Issue.OK]}")
    print("-" * 60)
    print("Leverancier-matching (voor facturen zonder contact):")
    print(f"  auto-koppelbaar          : {decision_counter.get('auto', 0)}")
    print(f"  handmatige review        : {decision_counter.get('review', 0)}")
    print(f"  geen match               : {decision_counter.get('none', 0)}")
    print("=" * 60)


def _write_report(
    output_dir: Path,
    classifications: Sequence[Classification],
    matches: dict[str, MatchResult],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "recovery_report.csv"
    with report_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "id",
                "datum",
                "referentie",
                "contact",
                "bedrag_incl_btw_eur",
                "issues",
                "primair_issue",
                "match_kandidaat",
                "match_contact",
                "match_score",
                "match_beslissing",
            ]
        )
        for c in classifications:
            inv = c.invoice
            m = matches.get(inv.id)
            writer.writerow(
                [
                    inv.id,
                    inv.date or "",
                    inv.reference or "",
                    inv.contact or "",
                    inv.amount_inc_vat_eur if inv.amount_inc_vat_eur is not None else "",
                    "|".join(i.value for i in c.issues),
                    c.primary_issue.value,
                    (m.candidate_name if m else "") or "",
                    (m.matched_contact if m else "") or "",
                    (m.score if m else "") if m else "",
                    (m.decision if m else "") or "",
                ]
            )
    return report_path


def _apply_matches(
    client: MoneybirdClient,
    matches: dict[str, MatchResult],
    raw_contacts: Optional[list[dict]] = None,
) -> int:
    """Schrijf auto-matches terug naar Moneybird. Geeft aantal bijgewerkte facturen terug.

    NB: het koppelen van een contact vereist het Moneybird `contact_id`. Dit
    wordt afgeleid uit de contactnaam. Alleen 'auto'-beslissingen worden
    weggeschreven; review/none blijven handmatig.
    """
    name_to_id: dict[str, str] = {}
    for c in raw_contacts or client.list_contacts():
        name = (c.get("company_name") or c.get("full_name") or "").strip()
        if name:
            name_to_id.setdefault(name, str(c.get("id")))

    updated = 0
    for match in matches.values():
        if match.decision != "auto" or not match.matched_contact:
            continue
        contact_id = name_to_id.get(match.matched_contact)
        if not contact_id:
            continue
        client.update_purchase_invoice(match.invoice_id, {"contact_id": contact_id})
        updated += 1
    return updated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CM Finance Recovery")
    parser.add_argument(
        "--source",
        choices=["excel", "api"],
        default="excel",
        help="Databron: Moneybird Excel-export of live API (standaard: excel).",
    )
    parser.add_argument("--invoices", help="Pad naar inkoop.xlsx (bij --source excel).")
    parser.add_argument(
        "--contacts",
        help="Optioneel pad naar een contactenexport (anders afgeleid uit de facturen).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Schrijf auto-matches terug naar Moneybird (alleen bij --source api). "
        "Zonder deze vlag draait alles als dry-run.",
    )
    parser.add_argument("--output-dir", help="Map voor rapporten (standaard uit config).")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    config = Config()
    if args.output_dir:
        object.__setattr__(config, "output_dir", Path(args.output_dir))

    invoices, contact_names = _load_invoices(args, config)
    if not invoices:
        print("Geen inkoopfacturen gevonden.")
        return 0

    classifications = classify_all(invoices)

    matcher = SupplierMatcher(contact_names, config)
    # Alleen matchen voor facturen zonder contact — daar zit de winst.
    matches: dict[str, MatchResult] = {}
    for c in classifications:
        if Issue.MISSING_CONTACT in c.issues:
            matches[c.invoice.id] = matcher.match(c.invoice)

    _print_summary(classifications, matches)
    report_path = _write_report(config.output_dir, classifications, matches)
    print(f"\nRapport geschreven naar: {report_path}")

    if args.apply:
        if args.source != "api":
            print("\n--apply wordt genegeerd: alleen beschikbaar bij --source api.", file=sys.stderr)
        else:
            client = MoneybirdClient(config)
            updated = _apply_matches(client, matches)
            print(f"\n{updated} inkoopfacturen bijgewerkt in Moneybird.")
    else:
        print("\nDry-run: er is niets in Moneybird gewijzigd. Gebruik --source api --apply om te schrijven.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
