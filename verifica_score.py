import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("""
SELECT
    id,
    comune,
    tipologia,
    offerta,
    score,
    esito
FROM aste
ORDER BY score DESC
""")

for riga in cur.fetchall():
    print(riga)

conn.close()