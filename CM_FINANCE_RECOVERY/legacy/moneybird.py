"""Moneybird-datalaag voor de CM Finance Recovery module.

Deze module levert:

* `PurchaseInvoice` — een taal-neutrale weergave van een inkoopfactuur.
* `load_invoices_from_excel` — inlezen van een Moneybird Excel-export (offline).
* `MoneybirdClient` — een dunne wrapper rond de Moneybird REST API voor het
  live ophalen en bijwerken van inkoopfacturen en contacten.

De offline-loader maakt het mogelijk de hele pipeline te draaien en te testen
zonder API-token, tegen de bijgeleverde export.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from config import EXCEL_COLUMN_MAP, Config


def _clean(value: Any) -> Optional[Any]:
    """Normaliseer lege/NaN-waarden naar None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _to_float(value: Any) -> Optional[float]:
    value = _clean(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class PurchaseInvoice:
    """Een inkoopfactuur, onafhankelijk van de bron (Excel of API)."""

    id: str
    reference: Optional[str] = None
    status: Optional[str] = None
    date: Optional[str] = None
    due_date: Optional[str] = None
    contact: Optional[str] = None
    contact_number: Optional[str] = None
    currency: Optional[str] = None
    paid_at: Optional[str] = None
    amount_ex_vat_eur: Optional[float] = None
    amount_inc_vat_eur: Optional[float] = None
    vat: Optional[float] = None
    # Vrije ruimte voor afgeleide informatie (issues, match-resultaat, ...).
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def has_contact(self) -> bool:
        return _clean(self.contact) is not None

    @property
    def has_amount(self) -> bool:
        amount = self.amount_inc_vat_eur
        return amount is not None and amount != 0

    @property
    def is_paid(self) -> bool:
        return _clean(self.paid_at) is not None

    @classmethod
    def from_excel_row(cls, row: dict[str, Any]) -> "PurchaseInvoice":
        mapped: dict[str, Any] = {}
        for excel_col, field_name in EXCEL_COLUMN_MAP.items():
            if excel_col in row:
                mapped[field_name] = row[excel_col]
        return cls(
            id=str(_clean(mapped.get("id")) or ""),
            reference=_clean(mapped.get("reference")),
            status=_clean(mapped.get("status")),
            date=_stringify_date(mapped.get("date")),
            due_date=_stringify_date(mapped.get("due_date")),
            contact=_clean(mapped.get("contact")),
            contact_number=_clean(mapped.get("contact_number")),
            currency=_clean(mapped.get("currency")),
            paid_at=_stringify_date(mapped.get("paid_at")),
            amount_ex_vat_eur=_to_float(mapped.get("amount_ex_vat_eur")),
            amount_inc_vat_eur=_to_float(mapped.get("amount_inc_vat_eur")),
            vat=_to_float(mapped.get("vat")),
        )

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "PurchaseInvoice":
        contact = payload.get("contact") or {}
        return cls(
            id=str(payload.get("id") or ""),
            reference=_clean(payload.get("reference")),
            status=_clean(payload.get("state")),
            date=_clean(payload.get("date")),
            due_date=_clean(payload.get("due_date")),
            contact=_clean(contact.get("company_name") or contact.get("full_name")),
            contact_number=_clean(str(contact.get("customer_id")) if contact.get("customer_id") else None),
            currency=_clean(payload.get("currency")),
            paid_at=_clean(payload.get("paid_at")),
            amount_ex_vat_eur=_to_float(payload.get("total_price_excl_tax_base")),
            amount_inc_vat_eur=_to_float(payload.get("total_price_incl_tax_base")),
            vat=_to_float(payload.get("total_tax")),
        )


def _stringify_date(value: Any) -> Optional[str]:
    value = _clean(value)
    if value is None:
        return None
    # pandas Timestamp / datetime -> ISO-datum
    try:
        return value.date().isoformat()  # type: ignore[attr-defined]
    except AttributeError:
        return str(value)


def load_invoices_from_excel(path: Path | str) -> list[PurchaseInvoice]:
    """Lees inkoopfacturen uit een Moneybird Excel-export (`inkoop.xlsx`)."""
    import pandas as pd  # lokaal geïmporteerd zodat import van deze module goedkoop blijft

    df = pd.read_excel(path)
    invoices: list[PurchaseInvoice] = []
    for record in df.to_dict(orient="records"):
        invoices.append(PurchaseInvoice.from_excel_row(record))
    return invoices


class MoneybirdClient:
    """Dunne client rond de Moneybird REST API (v2).

    Alleen de endpoints die de recovery nodig heeft zijn geïmplementeerd. De
    schrijf-methoden worden uitsluitend aangeroepen wanneer de app niet in
    dry-run draait.
    """

    def __init__(self, config: Config) -> None:
        config.require_api_credentials()
        self._config = config
        self._session = self._build_session(config.api_token)
        self._base = f"{config.api_base_url}/{config.administration_id}"

    @staticmethod
    def _build_session(token: str):
        import requests

        session = requests.Session()
        session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )
        return session

    def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        response = self._session.get(f"{self._base}/{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def iter_purchase_invoices(self, page_size: int = 100) -> Iterable[PurchaseInvoice]:
        """Paginerend alle inkoopfacturen ophalen."""
        page = 1
        while True:
            batch = self._get(
                "documents/purchase_invoices.json",
                params={"page": page, "per_page": page_size},
            )
            if not batch:
                break
            for payload in batch:
                yield PurchaseInvoice.from_api(payload)
            if len(batch) < page_size:
                break
            page += 1

    def list_contacts(self, page_size: int = 100) -> list[dict[str, Any]]:
        """Alle contacten ophalen (voor de matcher)."""
        contacts: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._get("contacts.json", params={"page": page, "per_page": page_size})
            if not batch:
                break
            contacts.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return contacts

    def update_purchase_invoice(self, invoice_id: str, attributes: dict[str, Any]) -> dict[str, Any]:
        """Werk een inkoopfactuur bij (bv. contact koppelen)."""
        response = self._session.patch(
            f"{self._base}/documents/purchase_invoices/{invoice_id}.json",
            json={"purchase_invoice": attributes},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
