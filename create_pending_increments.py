import sqlite3


def create_table():
    try:
        conn = sqlite3.connect("manarey.sqlite3")
        cursor = conn.cursor()
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS pending_increments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            usuario TEXT NOT NULL,
            local TEXT NOT NULL,
            motivo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        )
        conn.commit()
        conn.close()
        print("Tabla 'pending_increments' creada exitosamente.")
    except Exception as e:
        print(f"Error al crear la tabla: {e}")


if __name__ == "__main__":
    create_table()
