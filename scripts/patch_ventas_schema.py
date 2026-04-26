import os

import psycopg2


def main():
    dburl_path = ".dburl"
    if os.path.exists(dburl_path):
        with open(dburl_path, "r", encoding="utf-8") as f:
            DATABASE_URL = (f.readline() or "").strip()
    else:
        print("No .dburl encontrado")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        # Añadir columna usuario si no existe
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='ventas' AND column_name='usuario'"
        )
        if not cur.fetchone():
            print("Agregando columna usuario TEXT a ventas")
            cur.execute("ALTER TABLE ventas ADD COLUMN usuario TEXT")
        else:
            print("Columna usuario ya existe")

        # Añadir columna created_at si no existe
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='ventas' AND column_name='created_at'"
        )
        if not cur.fetchone():
            print("Agregando columna created_at TEXT a ventas")
            cur.execute("ALTER TABLE ventas ADD COLUMN created_at TEXT")
        else:
            print("Columna created_at ya existe")

        # Copiar valores actuales desde vendedor/fecha si las nuevas columnas son NULL
        print("Actualizando filas: usuario<-vendedor, created_at<-fecha donde es NULL")
        cur.execute(
            "UPDATE ventas SET usuario = coalesce(usuario, vendedor), created_at = coalesce(created_at, fecha) WHERE usuario IS NULL OR created_at IS NULL"
        )
        updated = cur.rowcount
        print(f"Filas actualizadas: {updated}")

        conn.commit()
    except Exception as e:
        print("Error al parchear esquema:", e)
        try:
            conn.rollback()
        except:
            pass
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
