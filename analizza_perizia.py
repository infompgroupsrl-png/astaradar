from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

# -------------------
# CONFIG
# -------------------
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
POPPLER = r"C:\poppler\Library\bin"

file_pdf = Path(r"perizie\test.pdf")

if not file_pdf.exists():
    print(f"Errore: Il file {file_pdf} non esiste. Controlla il percorso.")
    exit()

print(f"Avvio OCR di test su: {file_pdf.name}")

try:
    pagine = convert_from_path(
        str(file_pdf),
        poppler_path=POPPLER
    )

    for i, pagina in enumerate(pagine):
        testo = pytesseract.image_to_string(pagina, lang="ita")
        
        print()
        print("PAGINA", i + 1)
        print("-" * 50)
        
        if testo.strip():
            # Mostra i primi 1000 caratteri trovati nella pagina corrente
            print(testo[:1000])
        else:
            print("NESSUN TESTO RILEVATO IN QUESTA PAGINA (Immagine vuota o sfocata)")

except Exception as e:
    print(f"Si è verificato un errore durante l'elaborazione del PDF: {e}")