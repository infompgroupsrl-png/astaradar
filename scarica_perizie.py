import sqlite3
from pathlib import Path
from urllib.parse import urljoin

import requests


PERIZIE_DIR = Path("perizie")
TESTI_DIR = Path("testi")
PERIZIE_DIR.mkdir(exist_ok=True)
TESTI_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
}

PVP_CONFIG_URL = (
    "https://pvp.giustizia.it/"
    "bo-5897bc47-986a1b71/bo-ms/fe-config/dettaglio-annunci"
)

ASTALEGALE_API = "https://api.astalegale.net/Aste?id={id_asta}"


def scrivi_perizia_mancante(id_asta, motivo=""):
    with open("perizie_mancanti.txt", "a", encoding="utf-8") as f:
        if motivo:
            f.write(f"{id_asta} - {motivo}\n")
        else:
            f.write(f"{id_asta}\n")


def scarica_pdf(url, pdf_file):
    pdf = requests.get(
        requests.utils.requote_uri(url),
        headers=HEADERS,
        timeout=90,
    )

    if pdf.status_code != 200:
        return False, f"ERRORE DOWNLOAD {pdf.status_code}"

    content = pdf.content or b""
    content_type = (pdf.headers.get("content-type") or "").lower()

    if not content.startswith(b"%PDF") and "pdf" not in content_type:
        return False, f"RISPOSTA NON PDF ({content_type or 'content-type assente'})"

    pdf_file.write_bytes(content)
    return True, ""


def carica_config_pvp():
    try:
        r = requests.get(PVP_CONFIG_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        config = r.json()
    except Exception as e:
        print("Errore config PVP:", e)
        return {
            "host": "https://pvp.giustizia.it",
            "vendite": "ve-3f723b85-986a1b71/ve-ms",
            "buckets_host": "https://resource-pvp.giustizia.it",
        }

    return {
        "host": config.get("host") or "https://pvp.giustizia.it",
        "vendite": (config.get("msUrl") or {}).get("vendite")
        or "ve-3f723b85-986a1b71/ve-ms",
        "buckets_host": config.get("bucketsHost")
        or "https://resource-pvp.giustizia.it",
    }


def testo_da_dettaglio_pvp(body):
    lotto = body.get("lotto") or {}
    indirizzo = lotto.get("indirizzo") or {}
    procedura = body.get("procedura") or {}

    parti = [
        lotto.get("descLotto") or "",
        lotto.get("descTipoCategLotto") or "",
        lotto.get("descTipoLotto") or "",
        body.get("descTipoVendita") or "",
        body.get("descModVendita") or "",
        indirizzo.get("via") or "",
        indirizzo.get("descComune") or indirizzo.get("citta") or "",
        indirizzo.get("descProvincia") or indirizzo.get("provincia") or "",
        body.get("nomeUfficio") or "",
        procedura.get("descTipoProcedura") or "",
    ]

    return "\n".join(parte for parte in parti if parte)


def scegli_allegato_perizia(allegati):
    preferiti = []
    candidati = []

    for allegato in allegati or []:
        nome = (allegato.get("nomeFile") or "").lower()
        descrizione = (allegato.get("descrizione") or "").lower()
        codice = (allegato.get("codiceTipoAllegato") or "").upper()
        link = allegato.get("linkAllegato")

        if not link:
            continue

        testo = f"{nome} {descrizione}"

        if codice == "PERIZ":
            preferiti.append(allegato)
        elif "perizia" in testo or "stima" in testo:
            candidati.append(allegato)

    lista = preferiti or candidati
    if not lista:
        return None

    lista.sort(
        key=lambda a: (
            0 if "privacy" in (a.get("nomeFile") or "").lower() else 1,
            -(a.get("dimensioneAllegato") or 0),
        )
    )
    return lista[0]


def scarica_perizia_pvp(id_asta, pdf_file, pvp_config):
    id_pvp = str(id_asta).replace("PVP-", "", 1)
    detail_url = (
        f"{pvp_config['host'].rstrip('/')}/"
        f"{pvp_config['vendite'].strip('/')}/vendite/{id_pvp}/restricted"
    )

    print()
    print("Cerco perizia PVP:", id_asta)

    try:
        r = requests.get(detail_url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            print("Errore dettaglio PVP:", r.status_code)
            scrivi_perizia_mancante(id_asta, f"ERRORE DETTAGLIO PVP {r.status_code}")
            return

        body = (r.json() or {}).get("body") or {}
    except Exception as e:
        print("Errore dettaglio PVP:", e)
        scrivi_perizia_mancante(id_asta, f"ERRORE DETTAGLIO PVP {e}")
        return

    testo = testo_da_dettaglio_pvp(body)
    if testo:
        txt_file = TESTI_DIR / f"{id_asta}.txt"
        txt_file.write_text(testo, encoding="utf-8")

    allegato = scegli_allegato_perizia(body.get("allegati") or [])

    if not allegato:
        print("Perizia PVP non trovata, uso testo annuncio:", id_asta)
        scrivi_perizia_mancante(id_asta, "PERIZIA PVP NON TROVATA")
        return

    pdf_url = urljoin(
        pvp_config["buckets_host"].rstrip("/") + "/",
        allegato["linkAllegato"].lstrip("/"),
    )

    print("Download PVP:", allegato.get("nomeFile") or pdf_url)

    ok, errore = scarica_pdf(pdf_url, pdf_file)
    if not ok:
        print("Errore download PVP:", errore)
        scrivi_perizia_mancante(id_asta, errore)
        return

    print("Salvato:", pdf_file.name)


def scarica_perizia_astalegale(id_asta, pdf_file):
    print()
    print("Cerco perizia:", id_asta)

    try:
        api_url = ASTALEGALE_API.format(id_asta=id_asta)
        r = requests.get(api_url, headers=HEADERS, timeout=30)

        if r.status_code != 200:
            print("Errore API:", r.status_code)
            scrivi_perizia_mancante(id_asta, f"ERRORE API {r.status_code}")
            return

        data = r.json()
        allegati = (data.get("documentazione") or {}).get("allegati") or []

        pdf_url = None
        for allegato in allegati:
            nome = (allegato.get("name") or "").lower()
            if "perizia" in nome:
                pdf_url = allegato.get("url")
                break

        if not pdf_url:
            print("Perizia non trovata:", id_asta)
            scrivi_perizia_mancante(id_asta)
            return

        print("Download:", pdf_url)

        ok, errore = scarica_pdf(pdf_url, pdf_file)
        if not ok:
            print("Errore download:", errore)
            scrivi_perizia_mancante(id_asta, errore)
            return

        print("Salvato:", pdf_file.name)

    except Exception as e:
        print("Errore:", e)
        scrivi_perizia_mancante(id_asta, str(e))


conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

cur.execute("SELECT id FROM aste")
aste = cur.fetchall()

conn.close()

Path("perizie_mancanti.txt").write_text("", encoding="utf-8")

pvp_config = carica_config_pvp()

for (id_asta,) in aste:
    id_asta = str(id_asta)
    pdf_file = PERIZIE_DIR / f"{id_asta}.pdf"

    if pdf_file.exists():
        print("Gia presente:", pdf_file.name)
        continue

    if id_asta.startswith("PVP-"):
        scarica_perizia_pvp(id_asta, pdf_file, pvp_config)
    else:
        scarica_perizia_astalegale(id_asta, pdf_file)

print()
print("Download completato.")
