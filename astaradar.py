import requests
import sqlite3
import json
import pandas as pd
from pathlib import Path

# ---------------------
# CONFIG
# ---------------------

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# ---------------------
# DATABASE
# ---------------------

DB_DIR = Path("database")
DB_DIR.mkdir(exist_ok=True)

TESTI_DIR = Path("testi")
TESTI_DIR.mkdir(exist_ok=True)

conn = sqlite3.connect(DB_DIR / "aste.db")
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

# ---------------------
# FUNZIONI
# ---------------------

def euro_to_float(valore):

    if not valore:
        return 0

    valore = str(valore)
    valore = valore.replace("€", "")
    valore = valore.replace(".", "")
    valore = valore.replace(",", ".")

    try:
        return float(valore.strip())
    except:
        return 0

# ---------------------
# API ASTALEGALE
# ---------------------

URL = "https://api.astalegale.net/Search"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json"
}

totale_nuove = 0

for provincia in config["province"]:

    pagina = 1

    while True:

        payload = {
            "categories": [],
            "luoghi": [provincia],
            "includiFasce": True,
            "tipoDiRicerca": "Immobili",
            "page": pagina
        }

        try:

            r = requests.post(
                URL,
                json=payload,
                headers=headers,
                timeout=30
            )

        except requests.RequestException as e:

            print(
                f"Errore di connessione sulla provincia {provincia}: {e}"
            )

            break

        if r.status_code != 200:

            print("Errore API:", r.status_code)
            break

        data = r.json()

        if (
            "results" not in data
            or
            "currentPage" not in data["results"]
        ):
            break

        risultati = data["results"]["currentPage"]

        if len(risultati) == 0:
            break

        for immobile in risultati:

            tipologia = immobile.get("tipologia", "")

            offerta = euro_to_float(
                immobile.get("offertaMinima", "")
            )

            if offerta <= 0:
                continue

            if "abitazione" not in tipologia.lower():
                continue

            if offerta > config["offerta_massima"]:
                continue

            id_asta = str(immobile["id"])

            cur.execute(
                "SELECT id FROM aste WHERE id=?",
                (id_asta,)
            )

            esiste = cur.fetchone()

            if esiste:
                continue

            cur.execute("""
                INSERT INTO aste (
                    id,
                    comune,
                    provincia,
                    tipologia,
                    offerta,
                    prezzo,
                    data_asta,
                    tribunale,
                    url
                )
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                id_asta,
                immobile.get("comune"),
                immobile.get("provincia"),
                tipologia,
                offerta,
                immobile.get("prezzoNum", 0),
                immobile.get("dataAsta"),
                immobile.get("tribunale"),
                immobile.get("externalDetailUrl")
            ))

            totale_nuove += 1

            print(
                immobile.get("comune"),
                offerta
            )

        pagina += 1



# ---------------------
# API PVP GIUSTIZIA
# ---------------------

PVP_SEARCH_URL = (
    "https://pvp.giustizia.it/"
    "ric-496b258c-986a1b71/ric-ms/ricerca/vendite"
)

PVP_FILTERS_URL = (
    "https://pvp.giustizia.it/"
    "bo-5897bc47-986a1b71/bo-ms/filtriRicercaVendite"
)


def testo_pvp(immobile):
    indirizzo = immobile.get("indirizzo") or {}
    parti = [
        immobile.get("descLotto") or "",
        " ".join(immobile.get("categoriaBene") or []),
        " ".join(immobile.get("disponibilita") or []),
        indirizzo.get("via") or "",
        indirizzo.get("citta") or "",
        indirizzo.get("provincia") or "",
        immobile.get("tribunale") or "",
    ]
    return "\n".join(parte for parte in parti if parte)


def salva_testo_pvp(id_asta, immobile):
    txt_file = TESTI_DIR / f"{id_asta}.txt"
    if txt_file.exists():
        return
    txt_file.write_text(testo_pvp(immobile), encoding="utf-8")


def province_pvp_da_config():
    province_config = {
        provincia.upper()
        for provincia in config["province"]
    }
    regioni = {}

    try:
        r = requests.get(
            PVP_FILTERS_URL,
            headers=headers,
            timeout=30
        )
        r.raise_for_status()
        body = r.json().get("body") or {}
    except requests.RequestException as e:
        print("Errore filtri PVP:", e)
        return regioni

    for nazione in body.get("nazioni", []):
        for regione in nazione.get("regioni", []):
            nome_regione = regione.get("descRegione")

            for provincia in regione.get("province", []):
                sigla = (provincia.get("codiceProvincia") or "").upper()

                if sigla not in province_config:
                    continue

                regioni.setdefault(nome_regione, set()).add(
                    provincia.get("descProvincia")
                )

    return regioni


regioni_pvp = province_pvp_da_config()

for regione, province_ammesse in regioni_pvp.items():

    pagina = 0

    while True:

        payload = {
            "filtroAnnunci": 0,
            "tipoLotto": "IMMOBILI",
            "categoriaLotto": "IMMOBILE_RESIDENZIALE",
            "prezzoBaseAstaMax": config["offerta_massima"],
            "flagRicerca": "RICERCA_GEO",
            "nazione": "Italia",
            "regione": regione,
        }

        params = {
            "language": "it",
            "page": pagina,
            "size": 100,
            "sort": [
                "dataOraVendita,asc",
                "citta,asc",
            ],
        }

        try:

            r = requests.post(
                PVP_SEARCH_URL,
                json=payload,
                params=params,
                headers=headers,
                timeout=30
            )

        except requests.RequestException as e:

            print(
                f"Errore PVP sulla regione {regione}: {e}"
            )

            break

        if r.status_code != 200:

            print("Errore API PVP:", r.status_code)
            break

        data = r.json().get("body") or {}
        risultati = data.get("content") or []

        if len(risultati) == 0:
            break

        for immobile in risultati:

            indirizzo = immobile.get("indirizzo") or {}
            provincia_pvp = indirizzo.get("provincia")

            if provincia_pvp not in province_ammesse:
                continue

            prezzo_base = immobile.get("prezzoBaseAsta") or 0
            offerta = immobile.get("offertaMinima") or prezzo_base

            if offerta <= 0:
                continue

            if offerta > config["offerta_massima"]:
                continue

            id_pvp = str(immobile.get("id"))
            id_asta = f"PVP-{id_pvp}"

            cur.execute(
                "SELECT id FROM aste WHERE id=?",
                (id_asta,)
            )

            esiste = cur.fetchone()

            if esiste:
                salva_testo_pvp(id_asta, immobile)
                continue

            categoria_bene = ", ".join(immobile.get("categoriaBene") or [])
            data_asta = immobile.get("dataVendita") or ""
            orario = immobile.get("orarioVendita") or ""

            if orario:
                data_asta = f"{data_asta} - {orario}"

            cur.execute("""
                INSERT INTO aste (
                    id,
                    comune,
                    provincia,
                    tipologia,
                    offerta,
                    prezzo,
                    data_asta,
                    tribunale,
                    url
                )
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                id_asta,
                indirizzo.get("citta"),
                provincia_pvp,
                categoria_bene or immobile.get("categoriaLotto"),
                offerta,
                prezzo_base,
                data_asta,
                immobile.get("tribunale"),
                f"https://pvp.giustizia.it/pvp/it/detail_annuncio.page?idAnnuncio={id_pvp}"
            ))

            salva_testo_pvp(id_asta, immobile)
            totale_nuove += 1

            print(
                "PVP",
                indirizzo.get("citta"),
                offerta
            )

        if data.get("last", True):
            break

        pagina += 1

conn.commit()
conn.close()

print()
print("Nuove aste trovate:", totale_nuove)

# ---------------------
# EXPORT EXCEL
# ---------------------

EXPORT_DIR = Path("export")
EXPORT_DIR.mkdir(exist_ok=True)

conn = sqlite3.connect(DB_DIR / "aste.db")

query = """
SELECT
    id,
    comune,
    provincia,
    tipologia,
    offerta,
    prezzo,
    data_asta,
    tribunale,
    url
FROM aste
ORDER BY offerta ASC
"""

df = pd.read_sql_query(query, conn)

conn.close()

output_file = EXPORT_DIR / "aste.xlsx"

df.to_excel(
    output_file,
    index=False
)

print()
print("Excel aggiornato:", str(output_file))
print("Righe esportate:", len(df))