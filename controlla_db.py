import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("""
SELECT id, comune
FROM aste
""")

for r in cur.fetchall():
    print(repr(r[0]), "-", r[1])

conn.close()