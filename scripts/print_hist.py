from models.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute(
    "SELECT id,producto_id,detalle,meta,created_at FROM historial_stock ORDER BY id DESC LIMIT 5"
)
for r in cur.fetchall():
    print(tuple(r))
conn.close()
