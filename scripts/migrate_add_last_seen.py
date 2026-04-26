"""
scripts/migrate_add_last_seen.py
Añade la columna last_seen a la tabla usuarios si no existe.
"""
from models import db

conn = db.get_connection()
cur = conn.cursor()
try:
    cur.execute("PRAGMA table_info(usuarios)")
    cols = [r[1] for r in cur.fetchall()]
    if "last_seen" not in cols:
        try:
            cur.execute("ALTER TABLE usuarios ADD COLUMN last_seen TEXT")
            conn.commit()
            print("Columna last_seen agregada a usuarios")
        except Exception as e:
            print("No se pudo agregar columna last_seen:", e)
    else:
        print("Columna last_seen ya existe")
finally:
    conn.close()
