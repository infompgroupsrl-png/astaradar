import os
import sqlite3
import json
import base64
import httpx

from pathlib import Path
from pdf2image import convert_from_path

# ---------------------
# CONFIG
# ---------------------

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or config.get("anthropic_api_key")
PERIZIE_DIR = Path("perizie")
TESTI_DIR = Path("testi")
TESTI_DIR.mkdir(exist_ok=True)

# ---------------------
# DATABASE
# ---------------------

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("""
SELECT id FROM aste
WHERE analizzata = 0
""")

da_analizzare = cur.fetchall()

print(f"Da analizzare: {len(da_analizzare)}")

# ---------------------
# ANALISI
# ---------------------

def analizza_perizia(id_asta):

    pdf_file = PERIZIE_DIR / f"{id_asta}.pdf"
    txt_file = TESTI_DIR / f"{id_asta}.txt"

    immagini = []

    if pdf_file.exists():

        try:
            pagine = convert_from_path(pdf_file, dpi=100, first_page=1, last_page=8)
        except Exception as e:
            print(f"Errore conversione PDF {id_asta}: {e}")
            pagine = []

        for pagina in pagine:
            import io
            buf = io.BytesIO()
            pagina.save(buf, format="JPEG", quality=70)
            b64 = base64.b64encode(buf.getvalue()).decode()
            immagini.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": b64
                }
            })

    testo_annuncio = ""

    if txt_file.exists():
        testo_annuncio = txt_file.read_text(encoding="utf-8", errors="ignore").strip()

    if not immagini and not testo_annuncio:
        return None, None, None

    contenuto = []

    if testo_annuncio:
        contenuto.append({
            "type": "text",
            "text": f"Testo annuncio:\n{testo_annuncio}\n\n"
        })

    contenuto.extend(immagini)

    contenuto.append({
        "type": "text",
        "text": """
Sei un esperto immobiliare italiano specializzato in aste giudiziarie.
Analizza questa perizia e rispondi SOLO con un JSON con questi campi:

{
  "esito": "INTERESSANTE" | "DA VALUTARE" | "SCARTARE",
  "score": numero da 0 a 100,
  "note": "stringa breve con motivazione"
}

Criteri:
- SCARTARE: quota frazionaria, occupato, solo accessori (box/cantina/garage), abusi non sanabili, inagibile
- DA VALUTARE: mancano info chiave o ci sono criticità parziali
- INTERESSANTE: piena proprietà, libero o con locazione regolare, abitabile, prezzo conveniente

Rispondi SOLO con il JSON, senza testo aggiuntivo.
"""
    })

    try:

        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-opus-4-5",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": contenuto}]
            },
            timeout=120
        )

        risposta = r.json()
        testo = risposta["content"][0]["text"].strip()

        if testo.startswith("```"):
            testo = testo.split("```")[1]
            if testo.startswith("json"):
                testo = testo[4:]

        dati = json.loads(testo)
        return dati.get("esito"), dati.get("score"), dati.get("note")

    except Exception as e:
        print(f"Errore API Claude {id_asta}: {e}")
        return None, None, None


for (id_asta,) in da_analizzare:

    print(f"Analizzo: {id_asta}")

    esito, score, note = analizza_perizia(id_asta)

    if esito:
        cur.execute("""
            UPDATE aste
            SET esito = ?, score = ?, analizzata = 1
            WHERE id = ?
        """, (esito, score, id_asta))
        conn.commit()
        print(f"  → {esito} (score {score})")
    else:
        cur.execute("""
            UPDATE aste SET analizzata = 1 WHERE id = ?
        """, (id_asta,))
        conn.commit()
        print(f"  → non classificata")

conn.close()
