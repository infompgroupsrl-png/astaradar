from pathlib import Path
import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()
cur.execute("SELECT id, comune, score FROM aste WHERE esito='SCARTARE' LIMIT 10")

for id_asta, comune, score in cur.fetchall():
    txt = Path(f"testi/{id_asta}.txt")
    print("=" * 50)
    print(f"ID: {id_asta} | Comune: {comune} | Score: {score}")
    if txt.exists():
        print(txt.read_text(encoding="utf-8")[:300])
    else:
        print("(nessun file txt)")
    print()

conn.close()