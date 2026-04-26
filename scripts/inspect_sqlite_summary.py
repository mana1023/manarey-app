import os
import sqlite3
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(ROOT, ".."))
DB_PATH = os.path.join(ROOT, "manarey.db")

if not os.path.exists(DB_PATH):
    print(f"No existe la base en {DB_PATH}")
    raise SystemExit(0)

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# Resumen por local
cur.execute(
    "SELECT COALESCE(local,''), COUNT(*), SUM(COALESCE(cantidad,0)) FROM productos GROUP BY COALESCE(local,'') ORDER BY 1"
)
sum_rows = cur.fetchall()
print("Resumen por local (local, filas, suma_cantidades):")
for r in sum_rows:
    print(r)

print("\nEjemplos (primeros 5 por local):")
cur.execute(
    """
    SELECT id, nombre, categoria, IFNULL(medida,''), estado, IFNULL(color,''),
           COALESCE(cantidad,0), COALESCE(precio_venta,0), COALESCE(local,'')
    FROM productos
    ORDER BY local ASC, nombre ASC
"""
)
rows = cur.fetchall()
by_local = defaultdict(list)
for r in rows:
    by_local[r[-1]].append(r)

for loc in sorted(by_local.keys()):
    print(f"\n== {loc or '(sin local)'} ==")
    for r in by_local[loc][:5]:
        _id, nombre, categoria, medida, estado, color, cant, precio, _loc = r
        print(
            f"{_id:>6}  {nombre[:28]:<28} {categoria[:16]:<16} {medida[:10]:<10} {estado[:14]:<14} {color[:10]:<10} {int(cant):>5} {int(precio):>8}"
        )

con.close()
