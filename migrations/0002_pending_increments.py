"""
Migración: Crear tabla pending_increments para batching de increments.

Reduces carga en DB al agregar múltiples increments (botón +) en una sola
operación batch cada N segundos, en vez de encolar cada click individualmente.
"""


def migrate_up():
    from models.db import get_connection

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Crear tabla pending_increments (SQLite)
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
