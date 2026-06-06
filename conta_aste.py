import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("""
SELECT comune, tipologia, offerta
FROM aste
ORDER BY offerta
LIMIT 10
""")

for riga in cur.fetchall():
    print(riga)

conn.close()