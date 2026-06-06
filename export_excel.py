import sqlite3
import pandas as pd

# ---------------------
# DATABASE
# ---------------------

conn = sqlite3.connect("database/aste.db")

query = """
SELECT
    id,
    comune,
    provincia,
    tipologia,
    offerta,
    prezzo,
    score,
    esito,
    data_asta,
    tribunale,
    url
FROM aste
ORDER BY
    CASE
        WHEN esito = 'INTERESSANTE' THEN 1
        WHEN esito = 'DA VALUTARE' THEN 2
        WHEN esito = 'SCARTARE' THEN 3
        ELSE 4
    END,
    score DESC,
    offerta ASC
"""

df = pd.read_sql_query(
    query,
    conn
)

conn.close()

# ---------------------
# EXPORT EXCEL
# ---------------------

output_file = "export/aste.xlsx"

df.to_excel(
    output_file,
    index=False
)

print()
print("Excel aggiornato:", output_file)
print("Righe esportate:", len(df))