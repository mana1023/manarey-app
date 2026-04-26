import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

print("=== Diagnostico de productos ===")
try:
    from models.stock_model import get_stock_filtered, list_by_local

    print("stock_model import OK")
    rows = list_by_local("", "", "", "", "", "", "", "")
    print(f"list_by_local(''): {len(rows)} filas")
    if rows:
        print("Primer row:", rows[0])
    rows2 = get_stock_filtered("", apply_reservas=False)
    print(f"get_stock_filtered(''): {len(rows2)} dicts")
    if rows2:
        print("Primer dict keys:", list(rows2[0].keys()))
        print("Primer dict:", rows2[0])
except Exception as e:
    print(f"ERROR stock_model: {e}")
    import traceback

    traceback.print_exc()

try:
    from models.firestore_db import list_products_by_local

    print("\nfirestore_db import OK")
    prods = list_products_by_local(None)
    print(f"list_products_by_local(None): {len(prods)} productos")
    if prods:
        print("Primer producto keys:", list(prods[0].keys()))
        print("Primer producto:", prods[0])
except Exception as e:
    print(f"ERROR firestore_db: {e}")
    import traceback

    traceback.print_exc()

try:
    import sqlite3

    db_path = os.path.join(os.path.dirname(__file__), "manarey.db")
    print(f"\nSQLite local existe: {os.path.exists(db_path)}")
    if os.path.exists(db_path):
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM productos")
        count = cur.fetchone()[0]
        print(f"manarey.db productos count: {count}")
        cur.execute("SELECT local, COUNT(*) FROM productos GROUP BY local LIMIT 10")
        for r in cur.fetchall():
            print(f"  local={r[0]} count={r[1]}")
        con.close()
except Exception as e:
    print(f"ERROR sqlite: {e}")
    import traceback

    traceback.print_exc()

print("\n=== Fin diagnostico ===")
