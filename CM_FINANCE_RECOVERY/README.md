# CM Finance Recovery

Module om de achterstand aan **onverwerkte inkoopfacturen** in Moneybird op te
schonen. De bijgeleverde export (`inkoop.xlsx`) bevat ~1.400 facturen die
allemaal op status `new` staan: zonder gekoppelde leverancier, zonder
betaalstatus en deels zonder bedrag, opgebouwd over ~10 jaar.

De module leest die facturen in, **classificeert** ze in werkstapels, **matcht**
ontbrekende leveranciers op naam, en levert een rapport. Standaard verandert hij
niets in Moneybird (dry-run).

## Structuur

| Bestand | Rol |
|---|---|
| `config.py` | Instellingen + secrets uit `.env` (Moneybird-token, drempels). |
| `moneybird.py` | Datamodel `PurchaseInvoice`, Excel-loader en REST-client. |
| `rules.py` | Classificatie: geen contact / geen bedrag / btw-aangifte / dubbel / onverwerkt. |
| `matcher.py` | Leveranciersnaam uit referentie halen en fuzzy matchen (`rapidfuzz`). |
| `app.py` | CLI die alles aanstuurt en een CSV-rapport schrijft. |

## Installatie

```bash
pip install -r requirements.txt
cp .env.example .env   # vul MONEYBIRD_* in voor live gebruik
```

## Gebruik

Analyse van de Excel-export (geen API-token nodig):

```bash
python app.py --source excel --invoices ../inkoop.xlsx
```

Live tegen Moneybird, nog steeds dry-run (leest `.env`):

```bash
python app.py --source api
```

Live én auto-matches wegschrijven:

```bash
python app.py --source api --apply
```

De run print een samenvatting en schrijft `output/recovery_report.csv` met per
factuur de gevonden issues en het match-resultaat.

## Veiligheid & governance

- **Dry-run is standaard**; alleen `--source api --apply` muteert Moneybird, en
  dan uitsluitend `auto`-matches (score ≥ `CM_MATCH_AUTO_THRESHOLD`).
- Secrets staan in `.env` (in `.gitignore`), nooit in de repo.
- Conform het CM Operating System horen geëxporteerde financiële documenten
  (`.zip`, `.xlsx`) niet in GitHub — bewaar die in Google Drive en geef het pad
  mee via `--invoices`.
