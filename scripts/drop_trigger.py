import os
import sys

# Asegurar que el root del repo esté en sys.path cuando se ejecute el script directamente
sys.path.insert(0, os.getcwd())
import sqlite3

from models.db import DB_PATH

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
try:
    cur.execute("DROP TRIGGER IF EXISTS trg_producto_insert_historial")
    conn.commit()
    print("Trigger dropped (if existed)")
    cur.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    print("Remaining triggers:", cur.fetchall())
finally:
    conn.close()
