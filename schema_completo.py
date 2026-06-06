import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("""
SELECT sql
FROM sqlite_master
WHERE type='table'
AND name='aste'
""")

print(cur.fetchone()[0])

conn.close()