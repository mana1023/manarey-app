"""
scripts/migrate_plaintext_passwords.py

Detecta contraseñas en texto plano en la tabla `usuarios` y las re-hashea con
la rutina `models.auth.hash_password`. Crea una copia de seguridad del archivo
SQLite antes de modificarlo (si aplica).

Uso:
    python scripts/migrate_plaintext_passwords.py

Notas:
- Si la aplicación está configurada para Postgres (DATABASE_URL), el script
  usará la conexión indicada y actualizará las filas allí.
- Un "hash" bcrypt se detecta por empezar con "$2" (p. ej. "$2b$...").
"""
import os
import shutil
import sys

try:
    from models import auth as auth_mod
    from models import db as mdb
except Exception as e:
    print("Error importando módulos del proyecto:", e)
    sys.exit(1)


def is_bcrypt_hash(s: str) -> bool:
    if not s or not isinstance(s, str):
        return False
    return s.startswith("$2")  # covers $2a$, $2b$, $2y$, etc.


def backup_sqlite_if_applicable():
    try:
        if not mdb.is_postgres():
            src = getattr(mdb, "DB_PATH", None)
            if src and os.path.exists(src):
                bak = src + ".pwbak"
                shutil.copy(src, bak)
                print(f"Backup creado: {bak}")
                return bak
    except Exception as e:
        print("No se pudo crear backup del sqlite DB:", e)
    return None


def migrate():
    print("Iniciando migración de contraseñas (rehash de textos planos)...")
    bak = backup_sqlite_if_applicable()

    conn = mdb.get_connection()
    cur = conn.cursor()
    updated = 0
    scanned = 0
    try:
        cur.execute("SELECT username, password FROM usuarios")
        rows = cur.fetchall()
        for r in rows:
            username = r[0]
            stored = r[1] or ""
            scanned += 1
            if not stored:
                continue
            if is_bcrypt_hash(stored):
                continue
            # stored looks like plaintext -> rehash
            try:
                newh = auth_mod.hash_password(stored)
                cur.execute(
                    "UPDATE usuarios SET password=? WHERE username=?", (newh, username)
                )
                updated += 1
            except Exception as e:
                print(f"Error hasheando usuario {username}: {e}")
        conn.commit()
        print(f"Escaneadas {scanned} filas; actualizadas {updated} contraseñas.")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("Error durante la migración:", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    migrate()
