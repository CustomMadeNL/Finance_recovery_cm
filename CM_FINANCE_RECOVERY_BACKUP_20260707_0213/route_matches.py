python - <<'PY'
from pathlib import Path

p = Path("route_matches.py")

txt = p.read_text()

# Oude varianten vervangen
txt = txt.replace(
    'INPUT = "reports/document_matched.csv"',
    'INPUT = "reports/document_ledgers.csv"'
)

txt = txt.replace(
    'INPUT = "reports/document_matched_ledgers.csv"',
    'INPUT = "reports/document_ledgers.csv"'
)

txt = txt.replace(
    'INPUT = "reports/document_analysis.csv"',
    'INPUT = "reports/document_ledgers.csv"'
)

# Dubbele INPUT verwijderen
regels = txt.splitlines()
nieuw = []
gevonden = False

for regel in regels:
    if regel.strip().startswith("INPUT ="):
        if gevonden:
            continue
        gevonden = True
        nieuw.append('INPUT = "reports/document_ledgers.csv"')
    else:
        nieuw.append(regel)

txt = "\n".join(nieuw)

# OUTPUT goed zetten
if 'OUTPUT =' in txt:
    import re
    txt = re.sub(
        r'OUTPUT\s*=.*',
        'OUTPUT = "reports/document_routed.csv"',
        txt
    )
else:
    txt += '\nOUTPUT = "reports/document_routed.csv"\n'

p.write_text(txt)

print("✅ route_matches.py aangepast")
PY