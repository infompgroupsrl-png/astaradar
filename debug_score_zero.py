from pathlib import Path
import re

def normalizza(testo):
    return (
        testo.lower()
        .replace("à","a").replace("è","e").replace("é","e")
        .replace("ì","i").replace("ò","o").replace("ù","u")
    )

def trova_quota_frazionaria(testo):
    patterns = [
        r"quota\s+(?:di|pari\s+a|del|della)?\s*(\d+)\s*/\s*(\d+)",
        r"per\s+la\s+quota\s+(?:di|pari\s+a|del|della)?\s*(\d+)\s*/\s*(\d+)",
        r"quota\s+indivisa\s+(?:di|pari\s+a|del|della)?\s*(\d+)\s*/\s*(\d+)",
        r"quote?\s+indivise?\s+pari\s+a\s*(\d+)\s*/\s*(\d+)",
        r"proprieta'?[\s:]+(\d+)\s*/\s*(\d+)",
        r"(\d+)\s*/\s*(\d+)\s+del\s+presente\s+lotto",
        r"(\d+)\s*/\s*(\d+)\s+(?:di|della|dell')?\s*piena\s+proprieta",
        r"piena\s+proprieta\s+(?:per|di|della|del)?\s*(\d+)\s*/\s*(\d+)",
    ]
    trovate = []
    for pattern in patterns:
        for m in re.finditer(pattern, testo):
            contesto = testo[max(0, m.start()-120):m.end()+120]
            if "ciascuno" in contesto or "ciascuna" in contesto:
                continue
            if "attuali proprietari" in contesto or "precedenti proprietari" in contesto:
                continue
            n, d = int(m.group(1)), int(m.group(2))
            if d > 0 and n < d:
                trovate.append({
                    "pattern": pattern,
                    "match": m.group(0),
                    "contesto": contesto.strip()
                })
    return trovate

# Analizza i file delle aste scartate con score 0
import sqlite3
conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()
cur.execute("SELECT id, comune FROM aste WHERE score=0 AND esito='SCARTARE' LIMIT 8")
aste = cur.fetchall()
conn.close()

for id_asta, comune in aste:
    txt = Path(f"testi/{id_asta}.txt")
    if not txt.exists():
        print(f"[{id_asta}] {comune}: nessun txt")
        continue

    testo = normalizza(txt.read_text(encoding="utf-8"))

    quote = trova_quota_frazionaria(testo)
    locato = any(p in testo for p in ["contratto di locazione","locato","locata","affitto","affittato"])
    collabente = any(p in testo for p in ["rudere","inagibile","collabente","f/2","demolizione"])
    solo_cantina = "cantina" in testo and "appartamento" not in testo and "camera" not in testo

    print(f"\n{'='*55}")
    print(f"ID: {id_asta} | {comune}")
    print(f"  Quota frazionaria trovata: {len(quote) > 0}")
    print(f"  Locato/affittato: {locato}")
    print(f"  Collabente/rudere: {collabente}")
    print(f"  Solo cantina: {solo_cantina}")
    if quote:
        for q in quote[:2]:
            print(f"  → match: '{q['match']}'")
            print(f"    contesto: ...{q['contesto'][:150]}...")