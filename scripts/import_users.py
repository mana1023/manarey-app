"""
scripts/import_users.py

Importa usuarios desde un JSON exportado por `export_users.py`.
Si la contraseña no parece ser un hash bcrypt se la hashea antes de insertar.
"""
import json

from models import auth as auth_mod
from models import db


def looks_hashed(s: str) -> bool:
    if not s:
        return False
    return s.startswith("$2b$") or s.startswith("$2a$") or s.startswith("$2y$")


def import_file(path="users_export.json"):
    with open(path, "r", encoding="utf-8") as f:
        users = json.load(f)

    conn = db.get_connection()
    cur = conn.cursor()
    try:
        for u in users:
            username = u.get("username")
            pw = u.get("password")
            role = u.get("role")
            local = u.get("local")
            if not looks_hashed(pw):
                pw = auth_mod.hash_password(pw)
            # upsert
            try:
                cur.execute(
                    "INSERT OR REPLACE INTO usuarios (username, password, role, local) VALUES (?,?,?,?)",
                    (username, pw, role, local),
                )
            except Exception:
                # try generic
                cur.execute(
                    "INSERT OR REPLACE INTO usuarios (username, password, role, local) VALUES (?, ?, ?, ?)",
                    (username, pw, role, local),
                )
        conn.commit()
        print("Import completed")
    finally:
        conn.close()


if __name__ == "__main__":
    import_file()
