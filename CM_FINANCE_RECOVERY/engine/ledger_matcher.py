"""Ledger-matching: koppel elk document aan een grootboekrekening.

Statutaire documenten (btw, loonheffing, inkomstenbelasting) mappen
deterministisch op een controlerekening. Inkoopfacturen worden op de
leveranciersnaam (het Moneybird-contact) gekoppeld aan een kostenrekening.

De leverancier->grootboek-mapping hieronder is een **startset** voor
terugkerende leveranciers; uitbreiden tot het volledige Custommade-rekeningschema
is een aparte tuning-stap. Onbekende leveranciers krijgen een defaultrekening met
lage zekerheid, zodat ze naar review gaan i.p.v. verkeerd auto-geboekt te worden.
"""

from __future__ import annotations

from database.models import DocType, Flag, Document

# Vast grootboekschema per documenttype: (code, naam, basiszekerheid 0..1).
LEDGER_BY_TYPE: dict[str, tuple[str, str, float]] = {
    DocType.VAT_RETURN: ("1520", "Af te dragen omzetbelasting", 1.0),
    DocType.VAT_SUPPLETION: ("1520", "Af te dragen omzetbelasting (suppletie)", 0.7),
    DocType.PAYROLL_TAX: ("1530", "Af te dragen loonheffing", 1.0),
    DocType.INCOME_TAX: ("0510", "Te betalen inkomsten-/vennootschapsbelasting", 0.9),
    DocType.LEGAL: ("4400", "Juridische kosten", 0.6),
    DocType.REPORT: ("4510", "Advies- en administratiekosten", 0.6),
}

# Leverancier (substring in het contact) -> (code, naam) kostenrekening.
# Startset voor terugkerende leveranciers; uitbreiden = aparte tuning-stap.
SUPPLIER_LEDGERS: list[tuple[str, str, str]] = [
    ("transip", "4300", "Hosting & domeinen"),
    ("google cloud", "4300", "Hosting & domeinen"),
    ("moneybird", "4305", "Software & abonnementen"),
    ("bennett's finance", "4510", "Advies- en administratiekosten"),
    ("yellowbrick", "4310", "Betaaldienst- en transactiekosten"),
    ("buckaroo", "4310", "Betaaldienst- en transactiekosten"),
    ("advocaten", "4400", "Juridische kosten"),
    ("juristen", "4400", "Juridische kosten"),
    ("artiestenverloningen", "4020", "Inhuur & verloning artiesten"),
    ("ikea", "4600", "Kantoorinrichting"),
    ("nordic nest", "4600", "Kantoorbenodigdheden"),
    ("het catshuis", "4610", "Inkoop artikelgroep"),
    ("bol.com", "4600", "Kantoorbenodigdheden"),
    ("blokker", "4600", "Kantoorbenodigdheden"),
]

_PURCHASE_DEFAULT = ("4000", "Inkoop / directe kosten")


def _match_supplier_ledger(supplier: str) -> tuple[str, str, float] | None:
    target = supplier.lower()
    for key, code, name in SUPPLIER_LEDGERS:
        if key in target:
            return code, name, 0.9
    return None


def match(doc: Document) -> Document:
    """Koppel een grootboekrekening en zet `ledger_score`."""
    if doc.doc_type in LEDGER_BY_TYPE:
        code, name, score = LEDGER_BY_TYPE[doc.doc_type]
        doc.ledger_code, doc.ledger_name, doc.ledger_score = code, name, score
        return doc

    if doc.doc_type == DocType.PURCHASE_INVOICE:
        if doc.supplier:
            matched = _match_supplier_ledger(doc.supplier)
            if matched:
                doc.ledger_code, doc.ledger_name, doc.ledger_score = matched
            else:
                # Bekende leverancier zonder mapping: defaultrekening, matig zeker.
                doc.ledger_code, doc.ledger_name, doc.ledger_score = (*_PURCHASE_DEFAULT, 0.5)
        else:
            # Geen leverancier bekend: defaultrekening, lage zekerheid.
            doc.ledger_code, doc.ledger_name, doc.ledger_score = (*_PURCHASE_DEFAULT, 0.3)
        return doc

    # Onbekend type: geen betrouwbare rekening.
    doc.ledger_code, doc.ledger_name, doc.ledger_score = None, None, 0.0
    doc.add_flag(Flag.NO_LEDGER)
    return doc


def match_all(documents: list[Document]) -> list[Document]:
    return [match(doc) for doc in documents]
