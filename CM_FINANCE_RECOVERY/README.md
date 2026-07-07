# CM Finance Recovery — v1.0

Pipeline die de achterstand aan financiële documenten van Custommade opschoont:
Moneybird-documenten worden ingelezen, geclassificeerd, aan een
grootboekrekening gekoppeld, van een confidence-score voorzien en vervolgens
gerouteerd naar **AUTO** (straight-through) of **MANUAL** (review-queue).

Draai de volledige pipeline met één commando:

```bash
python app.py
```

De run draait volledig **offline** op de meegeleverde sync-JSON's — geen netwerk,
geen secrets nodig — en eindigt met `KLAAR`.

## Datasets

De pipeline verwerkt twee Moneybird-datasets:

| Dataset | Bestand | Inhoud |
|---|---|---|
| `documents` | `data/moneybird_sync.json` | 42 algemene documenten (aangiftes e.d.), zonder bedragen |
| `inkoop` | `data/moneybird_inkoop.json` | 1.395 inkoopfacturen **met bedragen en leveranciers** |

Kies met `--dataset {documents,inkoop,all}` (standaard `all`):

```bash
python app.py                      # beide datasets (1.437 documenten)
python app.py --dataset documents  # alleen de algemene documenten
python app.py --dataset inkoop     # alleen de inkoopfacturen
```

Indicatieve uitkomst (`all`, boekjaar 2024): **AUTO 6 / MANUAL 1.431** — 4
btw-aangiftes + 2 inkoopfacturen uit het lopende boekjaar met bedrag én een
betrouwbare leverancier gaan straight-through; de rest gaat naar review.

### Leverancier & datakwaliteit

De leverancier van een inkoopfactuur wordt **uit de referentie** afgeleid
("Factuur van X"). Het Moneybird-`contact`-veld is bij deze onverwerkte
"new"-documenten onbetrouwbaar (vaak een default-contact: bv. verzekerings- en
grote facturen die op "TransIP B.V." staan), en wordt daarom **niet** voor
boeking gebruikt.

Gevolg: slechts ~18% van de facturen heeft een leverancier in de data, dus maar
een klein deel kan veilig auto-boeken. Het grootboekschema levert wél voor ~145
facturen een concreet **grootboek-voorstel** in de review-queue.

### Verrijking met Moneybird-herkenning (OCR)

De hefboom voor méér auto-boeking is de door Moneybird **herkende leverancier**
(OCR) — betrouwbaarder dan zowel het contactveld als de referentie. De loader
heeft daarvoor een verrijkingsstap: bestaat `data/moneybird_recognition.json`,
dan zet die per document-id de `recognized_supplier` (en vult een ontbrekend
bedrag aan). De analyzer geeft die herkende leverancier voorrang.

Zo werkt straight-through mee zodra die data binnenkomt — via de Moneybird-API
(zodra `moneybird.com` op de netwerk-allowlist staat) of een export met
herkende velden. Formaat: zie `data/moneybird_recognition.sample.json`. Het echte
bestand is git-ignored (gevoelig). Voorbeeld-effect: 5 herkende leveranciers →
inkoop-AUTO van 2 naar 7.

De herkende data ophalen zodra de API bereikbaar is:

```bash
python fetch_recognition.py          # schrijft data/moneybird_recognition.json
python app.py                        # past de verrijking toe
```

`fetch_recognition.py` haalt per inkoopdocument de herkende leverancier + bedrag
op (vereist `MONEYBIRD_*` in `.env`). Het dekt de **volledige Inkoop-backlog** —
inkoopfacturen, bonnetjes (`receipts`) én algemene documenten, met
`filter=state:all` zodat ook verwerkte/oudere documenten meekomen (zonder die
filter geeft de API enkel de ~42 openstaande todo's). Voorbeeld-run:
~1480 documenten, waarvan ~1270 met een herkende leverancier. In een afgeschermde
omgeving meldt het net dat `moneybird.com` op de allowlist moet.

## Routing-beleid

Een document gaat alleen **AUTO** (straight-through) als het (1) de
confidence-drempel haalt, (2) een grootboekrekening heeft, (3) geen blokkerende
flags draagt én (4) uit het **lopende boekjaar** komt (`CM_FISCAL_YEAR`,
standaard 2024). Dit is bewust voor een recovery-traject: alleen actuele, schone
aangiftes worden automatisch verwerkt; historische backlog (oudere jaren) en
documenten zonder af te leiden boekjaar gaan naar de review-queue met een
leesbare reden. Verruim `CM_FISCAL_YEAR`/`CM_AUTO_THRESHOLD` om het
AUTO/MANUAL-mengsel bij te stellen.

## Architectuur

```
app.py                     # orchestrator: import -> analyse -> ledger -> confidence -> routing -> review
config.py                  # paden + drempels (+ optionele Moneybird-credentials uit .env)
database/
  models.py                # Document-datamodel + SQLite-schema
  repository.py            # persistentie (stdlib sqlite3, data/recovery.db)
importers/
  loader.py                # import/sync-stap (leest sync-JSON; optioneel live)
engine/
  analyzer.py              # classificatie + datum/periode/leverancier + boekjaar
  ledger_schema.py         # grootboekschema + leverancier-mapping (expliciet + keyword-regels)
  ledger_matcher.py        # koppelt document aan grootboekrekening via het schema
  confidence.py            # confidence-score (0..1)
  router.py                # AUTO vs. MANUAL (incl. boekjaar-gate)
  review_queue.py          # werklijst van MANUAL-documenten
data/
  moneybird_sync.json      # INPUT — algemene documenten
  moneybird_inkoop.json    # INPUT — inkoopfacturen met bedragen
reports/                   # OUTPUT — gegenereerde CSV's (git-ignored)
legacy/                    # oude v0-scripts, niet meer gebruikt
```

Alle imports zijn absolute imports vanaf de projectmap; `app.py` voegt zijn
eigen map aan `sys.path` toe, zodat `python app.py` vanuit elke werkmap draait.
De runtime gebruikt uitsluitend de Python-standaardbibliotheek (`sqlite3`,
`csv`, `json`, `re`).

## Output

Elke run schrijft naar `reports/`:

| Bestand | Inhoud |
|---|---|
| `document_analysis.csv` | type, datum, periode, leverancier, flags per document |
| `document_ledgers.csv` | gekoppelde grootboekrekening + score |
| `document_routed.csv` | confidence, route (AUTO/MANUAL) + reden |
| `review_queue.csv` | de MANUAL-werklijst, hoogste confidence eerst |

## Optionele live Moneybird-sync

Standaard leest de loader de sync-JSON. Met geldige credentials in `.env`
(`MONEYBIRD_ADMINISTRATION_ID`, `MONEYBIRD_API_TOKEN`) én netwerktoegang doet de
loader een live-sync; zonder netwerk valt hij stil terug op de sync-JSON. Zie
`.env.example`. Secrets horen nooit in de repo.

## Governance

- Geen secrets of `.env` in Git (zie `.gitignore`).
- Geen geëxporteerde bronbestanden (`.zip`/`.xlsx`) in Git; de pipeline werkt op
  afgeleide JSON-snapshots.
- `data/moneybird_inkoop.json` bevat leveranciersnamen en bedragen. Dit staat
  bewust in de repo als pipeline-input (in overleg); behandel de repo daarom als
  vertrouwelijk.
