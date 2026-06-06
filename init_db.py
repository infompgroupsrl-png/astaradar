import sqlite3
from pathlib import Path

Path("database").mkdir(exist_ok=True)

conn = sqlite3.connect("database/aste.db")

cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS aste (

    id TEXT PRIMARY KEY,

    comune TEXT,
    provincia TEXT,
    tipologia TEXT,

    offerta REAL,
    prezzo REAL,

    data_asta TEXT,
    tribunale TEXT,
    url TEXT,

    score INTEGER,
    esito TEXT,

    analizzata INTEGER DEFAULT 0
)
""")

conn.commit()
conn.close()

print("Database creato.")