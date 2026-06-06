import os

print()
print("===================================")
print("ASTARADAR AVVIO")
print("===================================")

print()
print("1/5 Ricerca aste")
os.system("python astaradar.py")

print()
print("2/5 Download perizie")
os.system("python scarica_perizie.py")

print()
print("3/5 Analisi perizie")
os.system("python analizza_tutte.py")

print()
print("4/5 Export Excel")
os.system("python export_excel.py")

print()
print("5/5 Invio email")
os.system("python email_report.py")

print()
print("===================================")
print("ASTARADAR COMPLETATO")
print("===================================")