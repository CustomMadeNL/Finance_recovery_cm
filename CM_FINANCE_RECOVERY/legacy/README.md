# Legacy scripts (v0 — niet gebruiken)

Deze flat scripts waren de eerste opzet van de recovery-module. Ze zijn in v1.0
**vervangen** door de package-structuur (`database/`, `importers/`, `engine/`)
en worden door de pipeline niet meer geïmporteerd of uitgevoerd.

| Legacy | Opgevolgd door |
|---|---|
| `moneybird.py` | `importers/loader.py` + `database/models.py` |
| `matcher.py` | `engine/ledger_matcher.py` |
| `rules.py` | `engine/analyzer.py` |

Ze staan hier alleen ter referentie. Draai altijd `python app.py` in de map
erboven; verwijs niet naar deze bestanden vanuit nieuwe code.
