import subprocess

steps = [
    ("Sync Moneybird", "python sync.py"),
    ("Analyse documenten", "python analyzer.py"),
    ("Contact matching", "python matcher.py"),
    ("Ledger matching", "python ledger_matcher.py"),
]

for title, cmd in steps:
    print(f"\n=== {title} ===")
    result = subprocess.run(cmd, shell=True)

    if result.returncode != 0:
        print(f"STOP: {title} mislukt.")
        exit(1)

print("\nCM FINANCE RECOVERY PIPELINE KLAAR")