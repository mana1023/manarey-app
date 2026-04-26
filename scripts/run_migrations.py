"""
Simple migrations runner.

Each migration is a Python file inside `migrations/` that defines an `upgrade(conn)` function.
This runner executes migrations in lexicographic order and records applied migrations
in the `app_migrations` table.
"""
import importlib
import importlib.util
import os
import sys

# Asegurar que el path del proyecto esté en sys.path para permitir importar `models`
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Nota: no importamos `models.db` a nivel de módulo porque durante tests se sobrescribe
# la variable de entorno `MANAREY_SQLITE_PATH` y queremos asegurar que el módulo lea
# la variable cuando ejecutemos `run()`.


MIGRATIONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "migrations")
)


def ensure_migrations_table(conn):
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS app_migrations (name TEXT PRIMARY KEY, applied_at TEXT)"
    )
    conn.commit()


def get_applied(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM app_migrations")
    return {r[0] for r in cur.fetchall()}


def apply_migration(conn, path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load migration spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    # mypy/typing: spec.loader is not None here
    spec.loader.exec_module(mod)
    if hasattr(mod, "upgrade"):
        print("Applying", name)
        mod.upgrade(conn)
        cur = conn.cursor()
        from datetime import datetime

        cur.execute(
            "INSERT OR REPLACE INTO app_migrations (name, applied_at) VALUES (?, ?)",
            (name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()


def run():
    # Importar/reload del módulo models.db en tiempo de ejecución para respetar
    # cambios en variables de entorno realizados justo antes de llamar al runner.
    if "models.db" in sys.modules:
        db = importlib.reload(sys.modules["models.db"])
    else:
        db = importlib.import_module("models.db")

    conn = db.get_connection()
    ensure_migrations_table(conn)
    applied = get_applied(conn)
    if not os.path.isdir(MIGRATIONS_DIR):
        print("No migrations directory:", MIGRATIONS_DIR)
        return
    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".py"))
    for f in files:
        if f in applied:
            continue
        path = os.path.join(MIGRATIONS_DIR, f)
        apply_migration(conn, path, f)
    conn.close()


if __name__ == "__main__":
    run()
