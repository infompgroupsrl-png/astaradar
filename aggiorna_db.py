import sqlite3

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

# Crea la tabella base se per caso non esiste
cur.execute("""
CREATE TABLE IF NOT EXISTS aste (
    id INTEGER PRIMARY KEY,
    comune TEXT,
    provincia TEXT,
    tipologia TEXT,
    offerta REAL,
    prezzo REAL,
    data_asta TEXT,
    tribunale TEXT,
    url TEXT
)
""")

# Aggiunge le colonne necessarie all'analisi
try:
    cur.execute("ALTER TABLE aste ADD COLUMN score INTEGER")
except sqlite3.OperationalError:
    pass

try:
    cur.execute("ALTER TABLE aste ADD COLUMN esito TEXT")
except sqlite3.OperationalError:
    pass

try:
    cur.execute("ALTER TABLE aste ADD COLUMN analizzata INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass

conn.commit()
conn.close()

print("Database aggiornato con successo.")