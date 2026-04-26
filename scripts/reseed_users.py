"""
scripts/reseed_users.py
Forzar restauración (re-seed) de usuarios semilla con confirmación interactiva.
"""
import sys

from models import db

confirm = input(
    "¿Estás seguro que quieres restaurar los usuarios locales a sus valores por defecto? (s/N): "
)
if confirm.lower() not in ("s", "y", "si", "yes"):
    print("Cancelado")
    sys.exit(0)

conn = db.get_connection()
cur = conn.cursor()
try:
    db.seed_users(cur, force=True)
    conn.commit()
    print("Usuarios reseed realizados (forzado).")
finally:
    conn.close()
