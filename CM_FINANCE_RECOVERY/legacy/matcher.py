"""Leveranciers-matching voor de CM Finance Recovery module.

Veel inkoopfacturen missen een gekoppeld contact, maar dragen de leveranciersnaam
wel in hun `referentie`, bv. "2021-05-30 Factuur van e-domizil_ Reis- en
verblijfskosten". Deze module haalt die kandidaat-naam eruit en matcht die met
`rapidfuzz` tegen een lijst bekende Moneybird-contacten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence

from config import Config
from moneybird import PurchaseInvoice

# "Factuur van <Leverancier>_ ..." of "Factuur van <Leverancier> ..."
_SUPPLIER_FROM_REF = re.compile(r"factuur\s+van\s+(.+?)(?:[_:]|$)", re.IGNORECASE)


@dataclass
class MatchResult:
    invoice_id: str
    candidate_name: Optional[str]
    matched_contact: Optional[str]
    score: float
    # "auto" (>= auto_threshold), "review" (>= review_threshold) of "none".
    decision: str


def extract_supplier_name(reference: Optional[str]) -> Optional[str]:
    """Haal een kandidaat-leveranciersnaam uit de factuurreferentie."""
    if not reference:
        return None
    match = _SUPPLIER_FROM_REF.search(reference)
    if not match:
        return None
    name = match.group(1).strip(" -_")
    return name or None


def _best_match(
    name: str,
    contact_names: Sequence[str],
) -> tuple[Optional[str], float]:
    """Geef het best passende contact + score (0-100) terug."""
    from rapidfuzz import fuzz, process

    if not contact_names:
        return None, 0.0
    result = process.extractOne(name, contact_names, scorer=fuzz.token_sort_ratio)
    if result is None:
        return None, 0.0
    matched_name, score, _ = result
    return matched_name, float(score)


class SupplierMatcher:
    def __init__(self, contact_names: Sequence[str], config: Config) -> None:
        # Ontdubbel en verwijder lege namen.
        self._contact_names = sorted({c.strip() for c in contact_names if c and c.strip()})
        self._config = config

    def match(self, invoice: PurchaseInvoice) -> MatchResult:
        candidate = extract_supplier_name(invoice.reference)
        if not candidate:
            return MatchResult(invoice.id, None, None, 0.0, "none")

        matched, score = _best_match(candidate, self._contact_names)

        if score >= self._config.match_auto_threshold:
            decision = "auto"
        elif score >= self._config.match_review_threshold:
            decision = "review"
        else:
            decision = "none"

        return MatchResult(
            invoice_id=invoice.id,
            candidate_name=candidate,
            matched_contact=matched if decision != "none" else None,
            score=round(score, 1),
            decision=decision,
        )

    def match_all(self, invoices: Sequence[PurchaseInvoice]) -> list[MatchResult]:
        return [self.match(inv) for inv in invoices]
