import os

import psycopg2


def fix_sequences():
    try:
        DATABASE_URL = None
        dburl_path = ".dburl"
        if os.path.exists(dburl_path):
            with open(dburl_path, "r", encoding="utf-8") as f:
                DATABASE_URL = (f.readline() or "").strip()

        if not DATABASE_URL:
            print("No se encontró .dburl")
            return

        print("Conectando a la base de datos...")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Lista de tablas a corregir
        tables = ["ventas", "detalle_ventas", "productos", "historial_stock"]

        for table in tables:
            try:
                # Obtener el valor máximo actual del ID
                cur.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
                max_id = cur.fetchone()[0]

                # Obtener el nombre de la secuencia
                cur.execute(f"SELECT pg_get_serial_sequence('{table}', 'id')")
                sequence = cur.fetchone()[0]

                if sequence:
                    # Actualizar la secuencia al máximo ID + 1
                    cur.execute(f"SELECT setval('{sequence}', {max_id}, true)")
                    print(f"Tabla {table}: secuencia actualizada a {max_id}")

            except Exception as e:
                print(f"Error en tabla {table}: {e}")
                continue

        conn.commit()
        cur.close()
        conn.close()
        print("Secuencias corregidas")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    fix_sequences()
