import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("""
SELECT
    id,
    score,
    esito,
    analizzata
FROM aste
WHERE id='B2416752'
""")

print(cur.fetchone())

conn.close()