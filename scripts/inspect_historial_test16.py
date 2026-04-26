import os
import sys

sys.path.insert(0, os.getcwd())
from models import stock_model as sm
from models.db import get_connection as get_conn

TEST_LOCAL = "TEST_LOCAL_E2E"
TEST_USER = "test_user_e2e"

# Limpieza mínima para reproducir exactamente el test
conn = get_conn()
cur = conn.cursor()
cur.execute(
    "DELETE FROM historial_stock WHERE producto_id IN (SELECT id FROM productos WHERE local=?)",
    (TEST_LOCAL,),
)
cur.execute("DELETE FROM productos WHERE local=?", (TEST_LOCAL,))
conn.commit()
conn.close()

# Ejecutar flujo: add_or_increment, luego dos update_stock_quantity
ok, msg = sm.add_or_increment(
    "Prod Hist", "Test", "unidad", "Nuevo", None, 20, 100, 300, TEST_LOCAL, TEST_USER
)
print("add_or_increment ->", ok, msg)

conn = get_conn()
cur = conn.cursor()
cur.execute(
    "SELECT id FROM productos WHERE nombre=? AND local= ?", ("Prod Hist", TEST_LOCAL)
)
row = cur.fetchone()
if not row:
    print("Producto no encontrado, abortando")
    exit(1)
pid = row[0]
print("producto id =", pid)
conn.close()

ok1, msg1 = sm.update_stock_quantity(pid, 20 + 5, TEST_USER, TEST_LOCAL, "test1")
ok2, msg2 = sm.update_stock_quantity(pid, 20 + 5 - 3, TEST_USER, TEST_LOCAL, "test2")
print("update_stock_quantity results:", ok1, ok2)

# List historial rows (print as dict for clarity)
conn = get_conn()
cur = conn.cursor()
cur.execute(
    "SELECT id, producto_id, accion, cantidad, detalle, motivo, usuario, local, created_at, meta, grupo_id FROM historial_stock WHERE producto_id=? ORDER BY id",
    (pid,),
)
rows = cur.fetchall()
print("\nHistorial rows:")
for r in rows:
    try:
        d = dict(r)
    except Exception:
        # sqlite3.Row may not be directly convertible in some envs; fallback
        d = {
            "id": r[0],
            "producto_id": r[1],
            "accion": r[2],
            "cantidad": r[3],
            "detalle": r[4],
            "motivo": r[5],
            "usuario": r[6],
            "local": r[7],
            "created_at": r[8],
            "meta": r[9],
            "grupo_id": r[10],
        }
    print(d)

cur.execute(
    "SELECT COUNT(*), SUM(cantidad) FROM historial_stock WHERE producto_id=?", (pid,)
)
count, total = cur.fetchone()
print("\nSummary: count=", count, " total_delta=", total)
conn.close()
