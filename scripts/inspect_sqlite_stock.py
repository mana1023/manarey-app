import argparse
import os
import sqlite3
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(ROOT, ".."))
DB_PATH = os.path.join(ROOT, "manarey.db")


def fetch_products(limit=50):
    if not os.path.exists(DB_PATH):
        print(f"No existe la base SQLite en: {DB_PATH}")
        return []
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute(
            """
            SELECT id, nombre, categoria, IFNULL(medida,''), estado, IFNULL(color,''),
                   COALESCE(cantidad,0), COALESCE(precio_venta,0), local
            FROM productos
            ORDER BY local ASC, nombre ASC
            LIMIT ?
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
        con.close()
        return rows
    except Exception as e:
        print(f"Error leyendo SQLite: {e}")
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    rows = fetch_products(args.limit)
    if not rows:
        print("No hay productos para mostrar.")
        return

    # Agrupar por local
    by_local = defaultdict(list)
    for r in rows:
        _id, nombre, categoria, medida, estado, color, cantidad, precio, local = r
        by_local[local or "(sin local)"].append(r)

    total = sum(len(v) for v in by_local.values())
    print(f"Mostrando hasta {args.limit} productos (primeros por orden alfabético).\n")
    for local in sorted(by_local.keys()):
        print(f"== {local} ({len(by_local[local])}) ==")
        print(
            f"{'ID':>6}  {'Nombre':<28} {'Cat':<16} {'Medida':<10} {'Estado':<14} {'Color':<10} {'Cant':>5} {'Precio':>8}"
        )
        for (
            _id,
            nombre,
            categoria,
            medida,
            estado,
            color,
            cantidad,
            precio,
            _local,
        ) in by_local[local]:
            print(
                f"{_id:>6}  {str(nombre)[:28]:<28} {str(categoria)[:16]:<16} {str(medida)[:10]:<10} {str(estado)[:14]:<14} {str(color)[:10]:<10} {int(cantidad):>5} {int(precio):>8}"
            )
        print()


if __name__ == "__main__":
    main()
