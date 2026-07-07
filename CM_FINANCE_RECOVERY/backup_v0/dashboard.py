from flask import Flask, render_template_string
import pandas as pd
from pathlib import Path

app = Flask(__name__)

DATA_FILE = Path("reports/document_classification.csv")

HTML = """
<!doctype html>
<html>
<head>
    <title>CM Finance Recovery</title>
    <style>
        body { font-family: Arial; margin: 40px; background: #f7f7f7; }
        h1 { margin-bottom: 10px; }
        .cards { display: flex; gap: 20px; margin-bottom: 30px; }
        .card { background: white; padding: 20px; border-radius: 12px; min-width: 180px; box-shadow: 0 2px 8px #ddd; }
        table { width: 100%; border-collapse: collapse; background: white; }
        th, td { padding: 10px; border-bottom: 1px solid #eee; font-size: 13px; }
        th { text-align: left; background: #111; color: white; }
        .AUTO { color: green; font-weight: bold; }
        .REVIEW { color: orange; font-weight: bold; }
        .HANDMATIG { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <h1>CM Finance Recovery Dashboard</h1>
    <p>Moneybird document recovery — read only</p>

    <div class="cards">
        <div class="card"><h2>{{ total }}</h2><p>Totaal documenten</p></div>
        <div class="card"><h2>{{ auto }}</h2><p>AUTO</p></div>
        <div class="card"><h2>{{ review }}</h2><p>REVIEW</p></div>
        <div class="card"><h2>{{ handmatig }}</h2><p>HANDMATIG</p></div>
    </div>

    <table>
        <tr>
            {% for col in columns %}
            <th>{{ col }}</th>
            {% endfor %}
        </tr>
        {% for row in rows %}
        <tr>
            {% for col in columns %}
            <td class="{{ row.get('status', '') }}">{{ row.get(col, '') }}</td>
            {% endfor %}
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route("/")
def dashboard():
    df = pd.read_csv(DATA_FILE).fillna("")

    total = len(df)
    auto = (df["status"] == "AUTO").sum() if "status" in df else 0
    review = (df["status"] == "REVIEW").sum() if "status" in df else 0
    handmatig = (df["status"] == "HANDMATIG").sum() if "status" in df else 0

    columns = list(df.columns)[:12]
    rows = df.head(100).to_dict(orient="records")

    return render_template_string(
        HTML,
        total=total,
        auto=auto,
        review=review,
        handmatig=handmatig,
        columns=columns,
        rows=rows
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)