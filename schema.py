import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("PRAGMA table_info(aste)")

for riga in cur.fetchall():
    print(riga)

conn.close()