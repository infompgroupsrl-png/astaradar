import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("""
UPDATE aste
SET
    score = NULL,
    esito = NULL,
    analizzata = 0
""")

conn.commit()

cur.execute("SELECT COUNT(*) FROM aste")
totale = cur.fetchone()[0]

cur.execute("""
SELECT COUNT(*)
FROM aste
WHERE COALESCE(analizzata,0)=0
""")

da_analizzare = cur.fetchone()[0]

print()
print("Totale aste:", totale)
print("Da analizzare:", da_analizzare)

conn.close()