import sqlite3
import smtplib
import json
import re

from pathlib import Path

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# -------------------
# CONFIG
# -------------------

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

TESTI_DIR = Path("testi")


def normalizza_testo(testo):
    return (
        testo.lower()
        .replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ì", "i")
        .replace("ò", "o")
        .replace("ù", "u")
        .replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ì", "i")
        .replace("ò", "o")
        .replace("ù", "u")
    )


def contiene(testo, parole):
    return any(parola in testo for parola in parole)


def trova_regex(testo, patterns):
    return any(re.search(pattern, testo) for pattern in patterns)


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

    for pattern in patterns:
        for match in re.finditer(pattern, testo):
            contesto = testo[max(0, match.start() - 120):match.end() + 120]
            if "ciascuno" in contesto or "ciascuna" in contesto:
                continue
            if "attuali proprietari" in contesto or "precedenti proprietari" in contesto:
                continue

            numeratore = int(match.group(1))
            denominatore = int(match.group(2))

            if denominatore > 0 and numeratore < denominatore:
                return numeratore, denominatore

    return None


def ha_quota_intera(testo):
    return (
        re.search(r"\b1\s*/\s*1\b", testo) is not None
        or "intera proprieta" in testo
        or "intera piena proprieta" in testo
        or "piena proprieta per l'intero" in testo
        or "piena proprieta dell'intero" in testo
    )


def aggiungi_punto(lista, punto):
    if punto not in lista:
        lista.append(punto)


def link_annuncio(id_asta, url):
    url = (url or "").strip()

    if url and not url.endswith("idAnnuncio="):
        return url

    return f"https://www.astalegale.net/Aste/Detail/{id_asta}"


def sintesi_perizia(id_asta, score=None):
    txt_file = TESTI_DIR / f"{id_asta}.txt"

    if not txt_file.exists():
        return (
            "Sintesi perizia:\n"
            "- Punti di forza: testo perizia non disponibile.\n"
            "- Punti deboli: impossibile verificare occupazione, diritti e difformita.\n"
        )

    testo = normalizza_testo(
        txt_file.read_text(encoding="utf-8", errors="ignore")
    )

    punti_forza = []
    punti_deboli = []
    quota_frazionaria = trova_quota_frazionaria(testo)

    if quota_frazionaria:
        numeratore, denominatore = quota_frazionaria
        aggiungi_punto(
            punti_deboli,
            f"quota parziale: solo {numeratore}/{denominatore} della piena proprieta"
        )
    elif "piena proprieta" in testo or ha_quota_intera(testo):
        aggiungi_punto(punti_forza, "piena proprieta o quota intera")

    if contiene(testo, [
        "al momento del sopralluogo libero",
        "risulta libero",
        "risultato libero",
        "non occupato",
        "non occupata",
    ]):
        aggiungi_punto(punti_forza, "immobile indicato come libero/non occupato")

    if contiene(testo, ["appartamento", "abitazione", "alloggio", "unita abitativa"]):
        aggiungi_punto(punti_forza, "presenza di abitazione")

    if trova_regex(testo, [
        r"\boccupat[oaie]\b",
        r"\boccupanti\b",
        r"occupato dall",
        r"occupata dall",
    ]) and not contiene(testo, ["non occupato", "non occupata"]):
        aggiungi_punto(punti_deboli, "immobile occupato")

    locazione_negata = trova_regex(testo, [
        r"contratt[io] di locazione.{0,80}non risult",
        r"non risultano.{0,80}contratt[io] di locazione",
        r"non risultano.{0,80}locazioni",
    ])

    if contiene(testo, [
        "contratto di locazione",
        "contratti di locazione",
        "locazione",
        "locato",
        "locata",
        "affitto",
        "affittato",
        "affittata",
    ]) and not locazione_negata:
        aggiungi_punto(punti_deboli, "presenza di locazione/affitto")

    if contiene(testo, ["usufrutto", "nuda proprieta"]):
        aggiungi_punto(punti_deboli, "diritto parziale: usufrutto o nuda proprieta")

    if contiene(testo, ["difformita catastale", "difformita", "non conforme", "non conformi"]):
        aggiungi_punto(punti_deboli, "difformita o non conformita")

    if contiene(testo, ["sanatoria", "sanatorie"]):
        aggiungi_punto(punti_deboli, "necessita o presenza di sanatoria")

    if contiene(testo, ["abuso edilizio", "abusi edilizi", "opere abusive"]):
        aggiungi_punto(punti_deboli, "abusi edilizi/opere abusive")

    if contiene(testo, ["inagibile", "rudere", "fabbricato pericolante", "demolizione"]):
        aggiungi_punto(punti_deboli, "condizioni gravi: inagibile/rudere/demolizione")

    if contiene(testo, ["umidita", "infiltrazioni", "ristrutturare"]):
        aggiungi_punto(punti_deboli, "possibili lavori o problemi manutentivi")

    solo_accessori = (
        contiene(testo, ["posto auto", "box", "box auto", "autorimessa", "garage", "cantina", "deposito"])
        and not contiene(testo, ["appartamento", "abitazione", "alloggio", "unita abitativa"])
    )

    if solo_accessori:
        aggiungi_punto(punti_deboli, "lotto composto da accessori senza abitazione evidente")

    if not punti_forza:
        punti_forza.append("nessun punto di forza rilevante rilevato automaticamente")

    if not punti_deboli:
        if score is not None and score < 75:
            punti_deboli.append("criticita non classificate automaticamente; perizia da verificare manualmente")
        else:
            punti_deboli.append("nessuna criticita automatica evidente; verificare comunque perizia, costi e stato reale")

    criticita_forti = [
        "immobile occupato",
        "presenza di locazione/affitto",
        "quota parziale: solo 1/12 della piena proprieta",
        "diritto parziale: usufrutto o nuda proprieta",
        "abusi edilizi/opere abusive",
        "condizioni gravi: inagibile/rudere/demolizione",
        "lotto composto da accessori senza abitazione evidente",
    ]

    if quota_frazionaria:
        valutazione = "da scartare o approfondire solo per operazioni specialistiche: proprieta non intera"
    elif any(punto in punti_deboli for punto in criticita_forti):
        valutazione = "approfondire prima di procedere: presenti criticita rilevanti"
    elif len(punti_deboli) >= 2:
        valutazione = "interessante ma richiede verifica tecnica/documentale"
    elif score is not None and score < 75:
        valutazione = "da valutare manualmente: mancano elementi automatici sufficienti per classificarla come interessante"
    else:
        valutazione = "profilo tendenzialmente favorevole, salvo verifiche finali"

    return (
        "Sintesi perizia:\n"
        f"- Punti di forza: {'; '.join(punti_forza[:4])}.\n"
        f"- Punti deboli: {'; '.join(punti_deboli[:5])}.\n"
        f"- Valutazione rapida: {valutazione}.\n"
    )

# -------------------
# DATABASE
# -------------------

conn = sqlite3.connect("database/aste.db")
cur = conn.cursor()

# INTERESSANTI

cur.execute("""
SELECT
    id,
    comune,
    provincia,
    offerta,
    score,
    data_asta,
    tribunale,
    url
FROM aste
WHERE esito='INTERESSANTE'
ORDER BY score DESC, offerta ASC
""")

interessanti = cur.fetchall()

# DA VALUTARE

cur.execute("""
SELECT
    id,
    comune,
    provincia,
    offerta,
    score,
    data_asta,
    tribunale,
    url
FROM aste
WHERE esito='DA VALUTARE'
ORDER BY score DESC, offerta ASC
""")

da_valutare = cur.fetchall()

# STATISTICHE

cur.execute("SELECT COUNT(*) FROM aste")
totale = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM aste WHERE esito='INTERESSANTE'")
num_interessanti = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM aste WHERE esito='DA VALUTARE'")
num_da_valutare = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM aste WHERE esito='SCARTARE'")
num_scartate = cur.fetchone()[0]

conn.close()

# -------------------
# TESTO EMAIL
# -------------------

testo = ""

testo += "ASTARADAR REPORT\n"
testo += "========================================\n\n"

testo += f"Aste archiviate : {totale}\n"
testo += f"Interessanti    : {num_interessanti}\n"
testo += f"Da valutare     : {num_da_valutare}\n"
testo += f"Scartate        : {num_scartate}\n\n"

# -------------------
# INTERESSANTI
# -------------------

if interessanti:

    testo += "🏆 ASTE INTERESSANTI\n"
    testo += "========================================\n\n"

    for (
        id_asta,
        comune,
        provincia,
        offerta,
        score,
        data_asta,
        tribunale,
        url
    ) in interessanti:

        link = link_annuncio(id_asta, url)
        sintesi = sintesi_perizia(id_asta, score)

        testo += (
            f"📍 {comune} ({provincia})\n"
            f"💰 Offerta: {offerta:,.0f} €\n"
            f"📊 Score: {score}/100\n"
            f"📅 Data asta: {data_asta}\n"
            f"⚖ Tribunale: {tribunale}\n"
            f"🔗 {link}\n"
            f"{sintesi}\n"
        )

# -------------------
# DA VALUTARE
# -------------------

if da_valutare:

    testo += "\n"
    testo += "⚠️ ASTE DA VALUTARE\n"
    testo += "========================================\n\n"

    for (
        id_asta,
        comune,
        provincia,
        offerta,
        score,
        data_asta,
        tribunale,
        url
    ) in da_valutare:

        link = link_annuncio(id_asta, url)
        sintesi = sintesi_perizia(id_asta, score)

        testo += (
            f"📍 {comune} ({provincia})\n"
            f"💰 Offerta: {offerta:,.0f} €\n"
            f"📊 Score: {score}/100\n"
            f"📅 Data asta: {data_asta}\n"
            f"⚖ Tribunale: {tribunale}\n"
            f"🔗 {link}\n"
            f"{sintesi}\n"
        )

# -------------------
# EMAIL
# -------------------

msg = MIMEMultipart()

msg["From"] = config["email_mittente"]

destinatari = config["email_destinatario"]
msg["To"] = ", ".join(destinatari)

msg["Subject"] = (
    f"AstaRadar | "
    f"{num_interessanti} interessanti | "
    f"{num_da_valutare} da valutare"
)

msg.attach(
    MIMEText(testo, "plain", "utf-8")
)

server = smtplib.SMTP(
    config["smtp_server"],
    config["smtp_port"]
)

server.starttls()

server.login(
    config["email_mittente"],
    config["password_app"]
)

server.sendmail(
    config["email_mittente"],
    destinatari,
    msg.as_string()
)

server.quit()

print("Email inviata.")


