import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("""
DELETE FROM aste
WHERE offerta <= 0
""")

conn.commit()

print("Record eliminati:", cur.rowcount)

conn.close()