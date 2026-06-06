import sqlite3
from pathlib import Path

FILE_TXT = r"perizie\test.txt"
ID_ASTA = 4568509   # test

with open(FILE_TXT, "r", encoding="utf-8") as f:
    testo = f.read().lower()

if (
    "cantina" in testo
    and "camera" not in testo
    and "cucina" not in testo
    and "bagno" not in testo
):
    print()
    print("SCORE: 0")
    print("ESITO: SCARTARE (SOLO CANTINA)")
    
    # Aggiorna il db anche in caso di scarto immediato
    conn = sqlite3.connect("database/aste.db")
    cur = conn.cursor()
    cur.execute("UPDATE aste SET score=0, esito='SCARTARE', analizzata=1 WHERE id=?", (ID_ASTA,))
    conn.commit()
    conn.close()
    exit()

score = 50

positivi = []
warning = []
negativi = []

# -------------------
# POSITIVI
# -------------------

positive = {
    "piena proprietà": 20,
    "libero": 15,
    "non occupato": 15,
    "camera": 5,
    "bagno": 5,
    "cucina": 5,
    "soggiorno": 5,
    "appartamento": 10,
}

for parola, punti in positive.items():
    if parola in testo:
        score += punti
        positivi.append(parola)

# Controllo speciale 1/1
if "1/1" in testo and "piena proprietà" in testo:
    score += 20
    positivi.append("Piena proprietà 1/1")

# -------------------
# WARNING
# -------------------

warning_words = {
    "abbandono": 10,
    "deposito": 10,
    "umidità": 10,
    "difformità": 10,
    "sanatoria": 10,
    "ristrutturare": 15,
}

for parola, penalita in warning_words.items():
    if parola in testo:
        score -= penalita
        warning.append(parola)

# -------------------
# NEGATIVI
# -------------------
negative_words = {
    "rudere": 60,
    "inagibile": 50,
    "demolizione": 60,
    "fabbricato pericolante": 60,
    "usufrutto": 50,
    "nuda proprietà": 50
}

for parola, penalita in negative_words.items():
    if parola in testo:
        score -= penalita
        negativi.append(parola)

# -------------------
# LIMITE SCORE
# -------------------

score = max(0, min(score, 100))

# -------------------
# ESITO
# -------------------

if score >= 75:
    esito = "INTERESSANTE"
elif score >= 40:
    esito = "DA VALUTARE"
else:
    esito = "SCARTARE"

print()
print("SCORE:", score)
print()

print("POSITIVI")
for x in positivi:
    print("✓", x)

print()

print("WARNING")
for x in warning:
    print("⚠", x)

print()

print("NEGATIVI")
for x in negativi:
    print("✗", x)

print()
print("ESITO:", esito)

# -------------------
# SALVATAGGIO DB
# -------------------

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("""
UPDATE aste
SET
    score=?,
    esito=?,
    analizzata=1
WHERE id=?
""", (score, esito, ID_ASTA))

conn.commit()
conn.close()

print("Database aggiornato.")