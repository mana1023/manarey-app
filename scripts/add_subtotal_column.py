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
        # Añadir columna subtotal si no existe
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='ventas' AND column_name='subtotal'"
        )
        if not cur.fetchone():
            print("Agregando columna subtotal DOUBLE PRECISION a ventas")
            cur.execute(
                "ALTER TABLE ventas ADD COLUMN subtotal DOUBLE PRECISION DEFAULT 0"
            )
        else:
            print("Columna subtotal ya existe")

        # Usar subtotal_productos si existe para poblar subtotal
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='ventas' AND column_name='subtotal_productos'"
        )
        if cur.fetchone():
            cur.execute(
                "UPDATE ventas SET subtotal = COALESCE(subtotal, subtotal_productos)"
            )
            print(f"Filas actualizadas con subtotal_productos: {cur.rowcount}")
        else:
            print("subtotal_productos no existe; no se copian valores")

        conn.commit()
    except Exception as e:
        print("Error agregando subtotal:", e)
        try:
            conn.rollback()
        except:
            pass
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
