import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("""
SELECT
    id,
    url
FROM aste
LIMIT 10
""")

for riga in cur.fetchall():
    print(riga)

conn.close()