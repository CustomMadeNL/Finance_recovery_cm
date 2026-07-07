"""Grootboekschema + leverancier-resolutie voor CM Finance Recovery.

Dit is de centrale bron voor het koppelen van documenten aan grootboekrekeningen:

* `LEDGER_ACCOUNTS`   — het rekeningschema (code -> naam + categorie).
* `LEDGER_BY_TYPE`    — statutaire documenttypes -> vaste controlerekening.
* `SUPPLIER_LEDGERS`  — expliciete mapping voor herkende (terugkerende) leveranciers.
* `KEYWORD_RULES`     — schaalbare patroonregels voor leveranciers per categorie.
* `resolve_supplier()`— bepaalt de rekening + zekerheid voor een leveranciersnaam.

LET OP: de rekeningcodes volgen een gangbaar Nederlands mkb-schema en zijn een
redelijke benadering. Verifieer ze tegen het werkelijke Custommade-grootboek in
Moneybird voordat er live op geboekt wordt.
"""

from __future__ import annotations

import re
from typing import Optional

from database.models import DocType

# --- Rekeningschema: code -> (naam, categorie) ---------------------------------
LEDGER_ACCOUNTS: dict[str, tuple[str, str]] = {
    "0510": ("Te betalen inkomsten-/vennootschapsbelasting", "belastingen"),
    "1520": ("Af te dragen omzetbelasting", "belastingen"),
    "1530": ("Af te dragen loonheffing", "belastingen"),
    "4000": ("Inkoop / nog te classificeren", "inkoop"),
    "4020": ("Inhuur & productie artiesten", "directe kosten"),
    "4100": ("Personeel / inhuur talent", "personeel"),
    "4200": ("Autokosten - brandstof", "auto"),
    "4210": ("Autokosten - lease & onderhoud", "auto"),
    "4220": ("Reis- & parkeerkosten", "reizen"),
    "4300": ("Hosting & domeinen", "it"),
    "4305": ("Software & abonnementen", "it"),
    "4310": ("Betaaldienst- & transactiekosten", "financieel"),
    "4400": ("Juridische kosten", "advies"),
    "4410": ("Notariskosten", "advies"),
    "4510": ("Advies- & administratiekosten", "advies"),
    "4520": ("Accountantskosten", "advies"),
    "4600": ("Kantoorbenodigdheden", "kantoor"),
    "4610": ("Inkoop artikelgroep / handelsgoederen", "inkoop"),
    "4620": ("Kantoorinrichting", "kantoor"),
    "4700": ("Representatie & catering", "representatie"),
    "4800": ("Marketing & advertenties", "marketing"),
    "4810": ("Telefoon & internet", "communicatie"),
    "4900": ("Verzekeringen", "verzekeringen"),
    "4910": ("Huisvestingskosten", "huisvesting"),
}

# --- Statutaire documenttypes -> vaste controlerekening (code, basiszekerheid) --
LEDGER_BY_TYPE: dict[str, tuple[str, float]] = {
    DocType.VAT_RETURN: ("1520", 1.0),
    DocType.VAT_SUPPLETION: ("1520", 0.7),
    DocType.PAYROLL_TAX: ("1530", 1.0),
    DocType.INCOME_TAX: ("0510", 0.9),
    DocType.LEGAL: ("4400", 0.6),
    DocType.REPORT: ("4510", 0.6),
}

# --- Expliciete leveranciers (substring in contact -> rekening) -----------------
SUPPLIER_LEDGERS: list[tuple[str, str]] = [
    ("transip", "4300"),
    ("google cloud", "4300"),
    ("moneybird", "4305"),
    ("artwin software", "4305"),
    ("bennett's finance", "4510"),
    ("yellowbrick", "4220"),
    ("athlon car lease", "4210"),
    ("autoradam", "4210"),
    ("servauto", "4210"),
    ("schaap juristen", "4400"),
    ("de vos & partners", "4400"),
    ("talentzone", "4100"),
    ("artiestenverloningen", "4020"),
    ("ikea", "4620"),
    ("bol.com", "4600"),
    ("action", "4600"),
    ("nordic nest", "4600"),
    ("het catshuis", "4610"),
]

# --- Schaalbare keyword-regels (regex op de leveranciersnaam) -------------------
KEYWORD_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(advocaten|advocaat|juristen|jurist)\b"), "4400"),
    (re.compile(r"\bnotaris"), "4410"),
    (re.compile(r"\b(accountant|boekhoud)"), "4520"),
    (re.compile(r"car\s*lease|autolease|leaseplan|athlon"), "4210"),
    (re.compile(r"\b(shell|bp|esso|tango|tinq|totalenergies|total|tamoil)\b"), "4200"),
    (re.compile(r"albert heijn|jumbo|dekamarkt|deka|\blidl\b|\baldi\b|\bspar\b|\bplus\b|\bdirk\b|supermarkt|kiosk"), "4700"),
    (re.compile(r"hosting|cloud|transip|hostnet|vimexx|strato|\bbyte\b|datacenter|domain"), "4300"),
    (re.compile(r"software|microsoft|adobe|atlassian|\bslack\b|\bzoom\b|abonnement|saas"), "4305"),
    (re.compile(r"verzeker|insurance|zekur|nationale.?nederlanden|allianz|\basr\b|aegon"), "4900"),
    (re.compile(r"parkeren|parking|q-?park|\bns\b|uber|\btaxi\b|greenwheels|domizil|booking\.com|\bhotel\b|airbnb"), "4220"),
    (re.compile(r"telefoon|\bkpn\b|vodafone|t-mobile|odido|ziggo|internet"), "4810"),
    (re.compile(r"google ads|adwords|\bmeta\b|facebook|instagram|linkedin|adverten|marketing"), "4800"),
    (re.compile(r"entertainment|\bmusic\b|records|sounds|productions?|studio"), "4020"),
    (re.compile(r"buckaroo|mollie|adyen|stripe|paypal"), "4310"),
    (re.compile(r"verhuur|\bhuur\b|leegstand|vastgoed"), "4910"),
]

# Zekerheid per matchtype (voor ledger_score).
SCORE_EXPLICIT = 0.95
SCORE_KEYWORD = 0.85
SCORE_DEFAULT = 0.30

DEFAULT_LEDGER = "4000"


def account_name(code: Optional[str]) -> Optional[str]:
    if code is None:
        return None
    entry = LEDGER_ACCOUNTS.get(code)
    return entry[0] if entry else code


def resolve_supplier(supplier: Optional[str]) -> tuple[str, str, float]:
    """Bepaal (code, naam, score) voor een leveranciersnaam.

    Prioriteit: expliciete leverancier -> keyword-regel -> default (review).
    """
    if not supplier:
        return DEFAULT_LEDGER, account_name(DEFAULT_LEDGER), SCORE_DEFAULT

    target = supplier.lower()

    for key, code in SUPPLIER_LEDGERS:
        if key in target:
            return code, account_name(code), SCORE_EXPLICIT

    for pattern, code in KEYWORD_RULES:
        if pattern.search(target):
            return code, account_name(code), SCORE_KEYWORD

    return DEFAULT_LEDGER, account_name(DEFAULT_LEDGER), SCORE_DEFAULT
