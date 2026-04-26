"""
scripts/export_users.py

Exporta la tabla `usuarios` a JSON (incluye hash de contraseña si existe).
"""
import json

from models import db


def export(path="users_export.json"):
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT username, password, role, local, last_seen FROM usuarios ORDER BY username"
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            try:
                out.append(
                    {
                        "username": r[0],
                        "password": r[1],
                        "role": r[2],
                        "local": r[3],
                        "last_seen": r[4],
                    }
                )
            except Exception:
                out.append(
                    {
                        "username": r["username"],
                        "password": r["password"],
                        "role": r["role"],
                        "local": r["local"],
                        "last_seen": r.get("last_seen"),
                    }
                )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("Exportado", len(out), "usuarios a", path)
    finally:
        conn.close()


if __name__ == "__main__":
    export()
