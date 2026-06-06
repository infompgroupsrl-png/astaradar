"""
Analizzatore semantico delle perizie tramite LLM locale (Qwen2.5 via Ollama).
Versione ottimizzata per qwen2.5:3b (prompt semplificato + format json).
"""

import json
import re
import sys
import time
from pathlib import Path

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"   # Modello ottimizzato per CPU: 4x più veloce, 1/3 della RAM


# =========================================================
# PROMPT SEMPLIFICATO PER MODELLI 3B
# =========================================================

PROMPT_TEMPLATE = """Sei un esperto immobiliare italiano. Analizza la perizia di un'asta giudiziaria e rispondi SOLO con un JSON valido. Niente commenti, niente markdown, niente testo fuori dalle graffe.

CAMPI DA COMPILARE (null se l'informazione non c'è, [] per array vuoti):

- tipologia_immobile: scegli UNO tra [appartamento, villa, villetta, cantina, box, altro]
- destinazione: scegli UNO tra [residenziale, commerciale, artigianale, agricolo, altro]
- stato_occupazione: scegli UNO tra [libero, occupato, locato, parzialmente_occupato, incerto]
- diritto_reale: scegli UNO tra [piena proprieta, quota intera, quota parziale, nuda proprieta, usufrutto]
- condizioni_immobile: scegli UNO tra [ottimo, buono, discreto, da ristrutturare, rudere, inagibile]
- abusi_edilizi: true oppure false
- presenza_sanatoria: true oppure false
- vincoli_paesaggistici: true oppure false
- punti_forza: array di stringhe (es. ["buona posizione", "recentemente ristrutturato"])
- punti_deboli: array di stringhe (es. ["presenza di umidita", "impianti da rifare"])
- stima_valore_mercato_eur: numero intero oppure null
- offerta_minima_eur: numero intero oppure null
- note_perizia: breve riassunto in 1-2 frasi
- raccomandazione: scegli UNO tra [INTERESSANTE, DA_VALUTARE, SCARTARE]
- score_qualita: numero intero 0-100

LOGICA SCORE:
- 0-30 = SCARTARE (rudere, inagibile, nuda proprieta, occupato senza titolo, abusi gravi)
- 31-60 = DA_VALUTARE (criticita rilevanti, da approfondire)
- 61-100 = INTERESSANTE (libero, piena proprieta, condizioni discrete o migliori)

ESEMPIO DI OUTPUT:
{
  "tipologia_immobile": "appartamento",
  "destinazione": "residenziale",
  "stato_occupazione": "libero",
  "diritto_reale": "piena proprieta",
  "condizioni_immobile": "buono",
  "abusi_edilizi": false,
  "presenza_sanatoria": false,
  "vincoli_paesaggistici": false,
  "punti_forza": ["luminoso", "centrale"],
  "punti_deboli": ["impianti vecchi"],
  "stima_valore_mercato_eur": 150000,
  "offerta_minima_eur": 90000,
  "note_perizia": "Trilocale in buone condizioni, libero, in zona centrale.",
  "raccomandazione": "INTERESSANTE",
  "score_qualita": 75
}

ORA ANALIZZA QUESTA PERIZIA:
\"\"\"
__TESTO__
\"\"\"
"""


# =========================================================
# VALORI AMMESSI E FALLBACK
# =========================================================

VALORI_AMMESSI = {
    "tipologia_immobile": ["appartamento", "villa", "villetta", "cantina", "box", "altro"],
    "destinazione": ["residenziale", "commerciale", "artigianale", "agricolo", "altro"],
    "stato_occupazione": ["libero", "occupato", "locato", "parzialmente_occupato", "incerto"],
    "diritto_reale": ["piena proprieta", "quota intera", "quota parziale", "nuda proprieta", "usufrutto"],
    "condizioni_immobile": ["ottimo", "buono", "discreto", "da ristrutturare", "rudere", "inagibile"],
    "raccomandazione": ["INTERESSANTE", "DA_VALUTARE", "SCARTARE"],
}

FALLBACK = {
    "tipologia_immobile": "altro",
    "destinazione": "altro",
    "stato_occupazione": "incerto",
    "diritto_reale": "quota parziale",
    "condizioni_immobile": "discreto",
    "raccomandazione": "DA_VALUTARE",
}


# =========================================================
# UTILS
# =========================================================

def chunk_text(testo: str, max_chars: int = 3000) -> list:
    """Divide il testo in chunk (ridotto a 3000 per il modello 3B)."""
    testo = testo.strip()
    if len(testo) <= max_chars:
        return [testo]
    paragrafi = testo.split("\n\n")
    chunks, corrente = [], ""
    for p in paragrafi:
        if len(corrente) + len(p) + 2 > max_chars:
            if corrente:
                chunks.append(corrente)
            corrente = p
        else:
            corrente = corrente + "\n\n" + p if corrente else p
    if corrente:
        chunks.append(corrente)
    return chunks


def estrai_json_da_testo(testo: str):
    """Estrae il primo JSON valido dal testo della risposta."""
    if not testo:
        return None

    # Prova prima a parsare il testo intero
    try:
        return json.loads(testo.strip())
    except json.JSONDecodeError:
        pass

    # Cerca il blocco {...} più esterno
    match = re.search(r"\{.*\}", testo, re.DOTALL)
    if not match:
        return None

    candidato = match.group(0)
    try:
        return json.loads(candidato)
    except json.JSONDecodeError:
        pass

    # Tenta fix comuni: rimuovi newline dentro stringhe, trailing commas, ecc.
    candidato_pulito = candidato
    # Rimuovi trailing commas
    candidato_pulito = re.sub(r",\s*([}\]])", r"\1", candidato_pulito)
    # Sostituisci newline dentro a stringhe
    candidato_pulito = re.sub(r'"\s*\n\s*"', '" "', candidato_pulito)

    try:
        return json.loads(candidato_pulito)
    except json.JSONDecodeError:
        pass

    # Ultimo tentativo: rimuovi blocchi di testo non-JSON attorno
    inizio = candidato.find("{")
    fine = candidato.rfind("}")
    if inizio != -1 and fine != -1 and fine > inizio:
        try:
            return json.loads(candidato[inizio:fine+1])
        except json.JSONDecodeError:
            return None

    return None


def correggi_risposta(dati: dict) -> dict:
    """Pulisce e corregge i valori del JSON in base a quelli ammessi."""
    if not isinstance(dati, dict):
        return dati

    for campo, ammessi in VALORI_AMMESSI.items():
        valore = dati.get(campo)
        if not isinstance(valore, str):
            continue
        valore_pulito = valore.strip().strip('"').strip("'")
        if "|" in valore_pulito:
            valore_pulito = valore_pulito.split("|")[0].strip()
        if valore_pulito in ammessi:
            dati[campo] = valore_pulito
            continue
        trovato = None
        for ammesso in ammessi:
            if ammesso in valore_pulito.lower():
                trovato = ammesso
                break
        dati[campo] = trovato if trovato else FALLBACK.get(campo, valore_pulito)
    return dati


# =========================================================
# FUNZIONE PRINCIPALE CON RETRY
# =========================================================

def analizza_perizia_con_llm(testo: str, timeout: int = 600, max_retries: int = 3) -> dict:
    """Analizza una perizia usando Ollama. Include retry con backoff."""
    if not testo or len(testo.strip()) < 50:
        return {"errore": "testo troppo corto o vuoto"}

    # Tronca testo (modello 3B ha limiti di prompt)
    testo_da_analizzare = testo[:3000]

    prompt = PROMPT_TEMPLATE.replace("__TESTO__", testo_da_analizzare)

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_ctx": 4096,
            "num_predict": 1024,
            "repeat_penalty": 1.1,
            "format": "json",     # ← Forza output JSON valido
        },
    }

    risposta_testo = ""
    for tentativo in range(max_retries):
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
            response.raise_for_status()
            risposta_testo = response.json().get("response", "")
            if risposta_testo.strip():
                break  # Risposta ok
        except requests.RequestException as e:
            if tentativo == max_retries - 1:
                return {"errore": f"errore Ollama dopo {max_retries} tentativi: {e}"}
            wait = 10 * (tentativo + 1)
            time.sleep(wait)

    if not risposta_testo.strip():
        return {"errore": "risposta vuota da Ollama"}

    dati = estrai_json_da_testo(risposta_testo)
    if dati is None:
        return {
            "errore": "risposta del modello non parsabile",
            "risposta_grezza": risposta_testo[:500],
        }

    dati = correggi_risposta(dati)
    return dati


def unisci_score(score_regex: int, analisi_llm: dict) -> int:
    """Combina score regex con score LLM (60% LLM + 40% regex)."""
    if "errore" in analisi_llm:
        return score_regex
    score_llm = analisi_llm.get("score_qualita")
    if score_llm is None:
        return score_regex
    try:
        return int(score_regex * 0.4 + int(score_llm) * 0.6)
    except (ValueError, TypeError):
        return score_regex


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analisi_llm.py <file.txt>")
        sys.exit(1)

    txt_file = Path(sys.argv[1])

    if not txt_file.exists():
        print(f"ERRORE: file non trovato: {txt_file}")
        sys.exit(1)

    print(f"Analisi di: {txt_file.name}")
    print(f"Modello: {MODEL}")
    print("=" * 60)

    testo = txt_file.read_text(encoding="utf-8", errors="ignore")
    t0 = time.time()
    risultato = analizza_perizia_con_llm(testo)
    durata = time.time() - t0

    print(f"\n[Completato in {durata:.1f}s]")
    print(json.dumps(risultato, indent=2, ensure_ascii=False))
