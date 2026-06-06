import time

def analizza_perizia_con_llm(testo: str, timeout: int = 600, max_retries: int = 3) -> dict:
    if not testo or len(testo.strip()) < 50:
        return {"errore": "testo troppo corto o vuoto"}

    chunks = chunk_text(testo)
    testo_da_analizzare = (
        "\n\n[...]\n\n".join(chunks[:2]) if len(chunks) > 1 else chunks[0]
    )

    prompt = PROMPT_TEMPLATE.replace("__TESTO__", testo_da_analizzare)

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": "Sei un esperto immobiliare italiano. Rispondi sempre in italiano. Output esclusivamente JSON valido, senza markdown ne commenti. Scegli UN SOLO valore per i campi enumerati.",
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_ctx": 4096,
            "num_predict": 1024,
            "repeat_penalty": 1.1,
        },
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
            response.raise_for_status()
            risposta_testo = response.json().get("response", "")
            break  # successo, esci dal loop
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                return {"errore": f"errore di connessione a Ollama dopo {max_retries} tentativi: {e}"}
            wait = 10 * (attempt + 1)
            print(f"  ⚠️ tentativo {attempt+1}/{max_retries} fallito, riprovo tra {wait}s...")
            time.sleep(wait)

    dati = estrai_json_da_testo(risposta_testo)
    if dati is None:
        return {
            "errore": "risposta del modello non parsabile",
            "risposta_grezza": risposta_testo[:500],
        }

    dati = correggi_risposta(dati)
    return dati
