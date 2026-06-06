from pathlib import Path
import re

ids_da_verificare = ["B2417083", "B2416752", "B2401310", "B2402150"]

parole_locazione = [
    "contratto di locazione", "contratti di locazione",
    "locato", "locata", "affitto", "affittato", "affittata",
]

for id_asta in ids_da_verificare:
    txt = Path(f"testi/{id_asta}.txt")
    if not txt.exists():
        print(f"[{id_asta}] nessun txt")
        continue

    testo = txt.read_text(encoding="utf-8").lower()

    print(f"\n{'='*55}")
    print(f"ID: {id_asta}")

    for parola in parole_locazione:
        idx = testo.find(parola)
        if idx >= 0:
            contesto = testo[max(0, idx-100):idx+100]
            print(f"  TROVATO '{parola}':")
            print(f"  ...{contesto.strip()}...")
            print()

    # Mostra anche primi 400 caratteri del testo
    print(f"  INIZIO TESTO:")
    print(f"  {testo[:400]}")