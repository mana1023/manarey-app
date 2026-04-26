"""
Migración: Crear tabla pending_increments para batching de increments.

Reduces carga en DB al agregar múltiples increments (botón +) en una sola
operación batch cada N segundos, en vez de encolar cada click individualmente.

Soporta SQLite y Postgres.
"""


def migrate_up():
    from models.db import get_connection, is_postgres

    conn = get_connection()
    cur = conn.cursor()

    try:
        if is_postgres():
            # Postgres version
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_increments (
                    producto_id INTEGER PRIMARY KEY,
                    delta INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usuario TEXT,
                    local TEXT,
                    motivo TEXT DEFAULT 'pending_increment'
                )
            """
            )
            # Index para queries rápidas
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pending_increments_updated_at 
                ON pending_increments(updated_at)
            """
            )
        else:
            # SQLite version
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_increments (
                    producto_id INTEGER PRIMARY KEY,
                    delta INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT DEFAULT (datetime('now','localtime')),
                    usuario TEXT,
                    local TEXT,
                    motivo TEXT DEFAULT 'pending_increment'
                )
            """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pending_increments_updated_at 
                ON pending_increments(updated_at)
            """
            )

        conn.commit()
        print("[Migration] pending_increments created successfully")
    except Exception as e:
        print(f"[Migration] Error creating pending_increments: {e}")
        conn.rollback()
    finally:
        conn.close()


def migrate_down():
    from models.db import get_connection

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("DROP TABLE IF EXISTS pending_increments")
        conn.commit()
        print("[Migration] pending_increments dropped successfully")
    except Exception as e:
        print(f"[Migration] Error dropping pending_increments: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_up()
