"""Script de diagnóstico rápido: lista usuarios en la DB (usando models.db) y verifica formatos de hash.
Imprime usuario, prefijo del hash y, para las cuentas seed conocidas, intenta verificar con la contraseña seed.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.db import get_connection as get_conn

try:
    from models import auth as auth_mod
except Exception:
    auth_mod = None

# Map de usuarios seed conocidos (usuario -> contraseña en texto plano) usados por la app
KNOWN_SEEDS = {
    "Administrador": "lautaro10",
    "Cane": "Manarey10",
    "Vidriera": "Manarey10",
    "Longchamps": "Manarey10",
    "Glew": "Manarey10",
}


def main():
    try:
        conn = get_conn()
    except Exception as e:
        print("ERROR: no se pudo obtener conexión a la DB:", e)
        return

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT username, password, role, local FROM usuarios ORDER BY username"
        )
    except Exception as e:
        print("ERROR: consulta falló:", e)
        try:
            conn.close()
        except Exception:
            pass
        return

    rows = cur.fetchall()
    print(f"Usuarios en DB: {len(rows)}\n")
    for r in rows:
        # r puede ser tuple o dict-like (psycopg2.extras.DictRow)
        try:
            username = r[0]
            stored = r[1]
            role = r[2]
        except Exception:
            # intentar por clave
            username = r.get("username")
            stored = r.get("password")
            role = r.get("role")

        stored_s = str(stored) if stored is not None else ""
        prefix = stored_s[:8]
        print(f"- {username} (role={role}) hash_prefix={prefix} len={len(stored_s)}")

        # Si es usuario seed conocido, intentar verificar con la contraseña seed
        seed_pw = KNOWN_SEEDS.get(username)
        if seed_pw is not None:
            if auth_mod:
                try:
                    ok = auth_mod.verify_password(seed_pw, stored_s)
                except Exception as e:
                    ok = False
                    print("   verify raised exception:", e)
            else:
                ok = stored_s == seed_pw
            print(f"   -> verify seed_password '{seed_pw[:4]}...' -> {ok}")

    try:
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
