import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

print("=== Locales en la BD ===")
try:
    import sqlite3

    from models.stock_model import _get_conn_cm

    with _get_conn_cm() as conn:
        cur = conn.cursor()
        ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
        cur.execute(
            f"SELECT local, COUNT(*) FROM productos GROUP BY local ORDER BY COUNT(*) DESC"
        )
        rows = cur.fetchall()
        for r in rows:
            print(f"  local={r[0]} count={r[1]}")

        # Verificar si hay 'Glew' o variaciones
        cur.execute(
            f"SELECT local, COUNT(*) FROM productos WHERE LOWER(TRIM(local)) = LOWER(TRIM({ph})) GROUP BY local",
            ("Glew",),
        )
        glew_rows = cur.fetchall()
        print(f"\nProductos para 'Glew': {sum(r[1] for r in glew_rows)}")
        for r in glew_rows:
            print(f"  local={r[0]} count={r[1]}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback

    traceback.print_exc()
print("=== Fin ===")
