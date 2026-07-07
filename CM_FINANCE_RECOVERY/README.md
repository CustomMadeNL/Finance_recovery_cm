# CM Finance Recovery — v1.0

Pipeline die de achterstand aan financiële documenten van Custommade opschoont:
Moneybird-documenten worden ingelezen, geclassificeerd, aan een
grootboekrekening gekoppeld, van een confidence-score voorzien en vervolgens
gerouteerd naar **AUTO** (straight-through) of **MANUAL** (review-queue).

Draai de volledige pipeline met één commando:

```bash
python app.py
```

De run draait volledig **offline** op de meegeleverde sync-JSON
(`data/moneybird_sync.json`) — geen netwerk, geen secrets nodig — en eindigt met
`KLAAR`.

Op de 42 meegeleverde documenten levert de pipeline **AUTO 4 / MANUAL 38**.

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
  analyzer.py              # classificatie + datum/periode/leverancier
  ledger_matcher.py        # koppeling aan grootboekrekening
  confidence.py            # confidence-score (0..1)
  router.py                # AUTO vs. MANUAL
  review_queue.py          # werklijst van MANUAL-documenten
data/
  moneybird_sync.json      # INPUT — Moneybird-documentensync (wordt behouden)
reports/                   # OUTPUT — gegenereerde CSV's (git-ignored)
legacy/                    # oude v0-scripts, niet meer gebruikt
```

Alle imports zijn absolute imports vanaf de projectmap; `app.py` voegt zijn
eigen map aan `sys.path` toe, zodat `python app.py` vanuit elke werkmap draait.
De runtime gebruikt uitsluitend de Python-standaardbibliotheek (`sqlite3`,
`csv`, `json`, `re`, `difflib`).

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
- Geen geëxporteerde bronbestanden (`.zip`/`.xlsx`) in Git; de pipeline werkt
  op de afgeleide `data/moneybird_sync.json` (alleen documentmetadata).
