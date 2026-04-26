import logging

logging.basicConfig(level=logging.DEBUG)
from models.db import get_connection
from models.stock_model import _find_product, add_or_increment, update_stock_field

# prepare
local = "TestLocal"
conn = get_connection()
cur = conn.cursor()
cur.execute("DELETE FROM productos WHERE nombre=?", ("TMP_CALL",))
cur.execute(
    "DELETE FROM historial_stock WHERE producto_id IN (SELECT id FROM productos WHERE nombre=?)",
    ("TMP_CALL",),
)
conn.commit()
conn.close()
ok, msg = add_or_increment(
    "TMP_CALL", "CatA", "1m", "Nuevo", None, 5, 0, 100, "TestLocal", "tester"
)
print("add", ok, msg)
rows = _find_product("TMP_CALL", "CatA", "1m", "Nuevo", None, "TestLocal")
print("rows", rows)
pid = rows[0]
res = update_stock_field(pid, "nombre", "TMP_CALL_X", "tester", "TestLocal", "test")
print("update_stock_field returned", res)
conn = get_connection()
cur = conn.cursor()
cur.execute(
    "SELECT COUNT(*) FROM historial_stock WHERE producto_id=? AND detalle LIKE 'cambio de nombre%'",
    (pid,),
)
print("count", cur.fetchone()[0])
cur.execute(
    "SELECT id,producto_id,detalle,meta FROM historial_stock WHERE producto_id=?",
    (pid,),
)
print(cur.fetchall())
conn.close()
