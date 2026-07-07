"""Classificatieregels voor de CM Finance Recovery module.

Elke inkoopfactuur wordt tegen een set regels gehouden. Het resultaat is een
lijst van `Issue`-labels die aangeeft welke opschoonactie nodig is. De labels
corresponderen direct met de stapels uit de export-analyse:

* geen bedrag        -> MISSING_AMOUNT
* geen leverancier   -> MISSING_CONTACT
* btw-aangifte       -> TAX_RETURN
* mogelijk dubbel    -> POSSIBLE_DUPLICATE
* nooit verwerkt     -> UNPROCESSED (status == "new")
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from moneybird import PurchaseInvoice


class Issue(str, Enum):
    MISSING_AMOUNT = "missing_amount"
    MISSING_CONTACT = "missing_contact"
    TAX_RETURN = "tax_return"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    UNPROCESSED = "unprocessed"
    OK = "ok"


# Referenties die op een btw-aangifte of algemeen belastingdocument wijzen.
_TAX_RETURN_PATTERN = re.compile(
    r"\b(aangifte\s+omzetbelasting|omzetbelasting|btw[- ]?aangifte|aangifte)\b",
    re.IGNORECASE,
)


@dataclass
class Classification:
    invoice: PurchaseInvoice
    issues: list[Issue]

    @property
    def needs_action(self) -> bool:
        return any(issue is not Issue.OK for issue in self.issues)

    @property
    def primary_issue(self) -> Issue:
        # Volgorde van urgentie voor rapportage/sortering.
        for issue in (
            Issue.MISSING_CONTACT,
            Issue.MISSING_AMOUNT,
            Issue.POSSIBLE_DUPLICATE,
            Issue.TAX_RETURN,
            Issue.UNPROCESSED,
        ):
            if issue in self.issues:
                return issue
        return Issue.OK


def _duplicate_references(invoices: Iterable[PurchaseInvoice]) -> set[str]:
    counts: Counter[str] = Counter()
    for inv in invoices:
        ref = (inv.reference or "").strip().lower()
        if ref:
            counts[ref] += 1
    return {ref for ref, n in counts.items() if n > 1}


def classify(
    invoice: PurchaseInvoice,
    duplicate_refs: set[str] | None = None,
) -> Classification:
    """Classificeer één inkoopfactuur."""
    issues: list[Issue] = []

    if not invoice.has_contact:
        issues.append(Issue.MISSING_CONTACT)

    if not invoice.has_amount:
        issues.append(Issue.MISSING_AMOUNT)

    reference = invoice.reference or ""
    if _TAX_RETURN_PATTERN.search(reference):
        issues.append(Issue.TAX_RETURN)

    if duplicate_refs is not None:
        ref = reference.strip().lower()
        if ref and ref in duplicate_refs:
            issues.append(Issue.POSSIBLE_DUPLICATE)

    if (invoice.status or "").lower() == "new":
        issues.append(Issue.UNPROCESSED)

    if not issues:
        issues.append(Issue.OK)

    return Classification(invoice=invoice, issues=issues)


def classify_all(invoices: list[PurchaseInvoice]) -> list[Classification]:
    """Classificeer een volledige batch; berekent duplicaten over de hele set."""
    duplicate_refs = _duplicate_references(invoices)
    return [classify(inv, duplicate_refs) for inv in invoices]
