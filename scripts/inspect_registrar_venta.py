import os
import sys

sys.path.insert(0, os.getcwd())
from models import stock_model as sm
from models import stock_queue_api as qa
from models import ventas_model as vm
from models.db import get_connection as get_conn

TEST_LOCAL = "TEST_LOCAL_E2E"
TEST_USER = "test_user_e2e"

# Clean up
conn = get_conn()
cur = conn.cursor()
cur.execute("DELETE FROM op_queue")
cur.execute(
    "DELETE FROM detalle_ventas WHERE venta_id IN (SELECT id FROM ventas WHERE local=?)",
    (TEST_LOCAL,),
)
cur.execute("DELETE FROM ventas WHERE local=?", (TEST_LOCAL,))
cur.execute(
    "DELETE FROM historial_stock WHERE producto_id IN (SELECT id FROM productos WHERE local=?)",
    (TEST_LOCAL,),
)
cur.execute("DELETE FROM productos WHERE local=?", (TEST_LOCAL,))
conn.commit()
conn.close()

# Create product
ok, msg = sm.add_or_increment(
    "Producto Venta Inspect",
    "Test",
    "unidad",
    "Nuevo",
    None,
    10,
    100,
    300,
    TEST_LOCAL,
    TEST_USER,
)
print("add_or_increment", ok, msg)

# Get product id
conn = get_conn()
cur = conn.cursor()
cur.execute(
    "SELECT id FROM productos WHERE nombre=? AND local=?",
    ("Producto Venta Inspect", TEST_LOCAL),
)
pid = cur.fetchone()[0]
conn.close()

# Register sale
cliente = {
    "nombre": "Cliente Inspect",
    "telefono": "999",
    "calle": "C",
    "numero": "1",
    "localidad": "L",
}
items = [
    {
        "producto_id": pid,
        "nombre": "Producto Venta Inspect",
        "categoria": "Test",
        "medida": "unidad",
        "estado": "Nuevo",
        "cantidad": 1,
        "precio_unitario": 300,
    }
]
ok, msg, venta_id = vm.registrar_venta(TEST_LOCAL, TEST_USER, cliente, items)
print("registrar_venta", ok, msg, venta_id)

# List op_queue
conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT id, op_type, status, payload, attempts FROM op_queue ORDER BY id")
rows = cur.fetchall()
print("op_queue rows:")
for r in rows:
    print(dict(r))
conn.close()

# Also show historial and detalle_ventas
conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT id FROM detalle_ventas WHERE venta_id=?", (venta_id,))
print("detalle_ventas count", len(cur.fetchall()))
cur.execute("SELECT COUNT(*) FROM historial_stock WHERE producto_id=?", (pid,))
print("hist count", cur.fetchone()[0])
conn.close()
