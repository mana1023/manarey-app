import os
import sqlite3
import sys
import tempfile


def main():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "smoke_manarey.db")
    os.environ["MANAREY_SQLITE_PATH"] = db_path

    # Ejecutar runner
    try:
        import scripts.run_migrations as runner

        runner.run()
    except Exception as e:
        print("Runner failed:", e)
        sys.exit(2)

    # Verificar
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(usuarios)")
        cols = [r[1] for r in cur.fetchall()]
        if "last_seen" not in cols:
            print("FAILED: last_seen missing")
            sys.exit(3)
        cur.execute("SELECT COUNT(*) FROM usuarios")
        n = cur.fetchone()[0]
        print("OK: users=", n)
        conn.close()
    except Exception as e:
        print("DB verification failed:", e)
        sys.exit(4)


if __name__ == "__main__":
    main()
