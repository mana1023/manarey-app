"""
scripts/ensure_local_users.py

Asegura que las cuentas locales basicas existan en la base de datos.
No cambia passwords de usuarios ya existentes.

Uso:
    python scripts/ensure_local_users.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_locales
from models import auth as auth_mod
from models import db

USERS = [(local, "Manarey10", "local", local) for local in get_locales()]


def ensure_users():
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        hashed = []
        for username, pw, role, local in USERS:
            hashed.append((username, auth_mod.hash_password(pw), role, local))

        if db.is_postgres():
            cur.executemany(
                """
                INSERT INTO usuarios (username, password, role, local)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
                """,
                hashed,
            )
        else:
            cur.executemany(
                "INSERT OR IGNORE INTO usuarios (username, password, role, local) VALUES (?,?,?,?)",
                hashed,
            )
        conn.commit()
    except Exception as e:
        print("Error al asegurar usuarios:", e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            db.put_connection(conn)
        except Exception:
            conn.close()


if __name__ == "__main__":
    ensure_users()
    print("Operacion completada.")
