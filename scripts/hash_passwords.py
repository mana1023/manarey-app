"""
scripts/hash_passwords.py

Migra contraseñas en texto plano a hashes bcrypt. Detecta si la contraseña
ya está hasheada (intentando reconocer prefijos bcrypt) y la salta.

Ejecutar con cuidado: crea hashes para las filas que no parecen estar en bcrypt.
"""
from models import auth as auth_mod
from models import db


def looks_hashed(s: str) -> bool:
    if not s:
        return False
    return s.startswith("$2b$") or s.startswith("$2a$") or s.startswith("$2y$")


def migrate():
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT username, password FROM usuarios")
        rows = cur.fetchall()
        updated = 0
        for r in rows:
            try:
                username = r[0]
                pw = r[1]
            except Exception:
                username = r["username"]
                pw = r["password"]
            if not looks_hashed(pw):
                newh = auth_mod.hash_password(pw)
                cur.execute(
                    "UPDATE usuarios SET password = ? WHERE username = ?",
                    (newh, username),
                )
                updated += 1
        conn.commit()
        print(f"Passwords migrados: {updated}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
