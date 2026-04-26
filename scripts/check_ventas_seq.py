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
        cur.execute("SELECT COALESCE(MAX(id),0) FROM ventas")
        max_id = cur.fetchone()[0]
        print(f"MAX(id) en ventas = {max_id}")

        cur.execute("SELECT pg_get_serial_sequence('ventas','id')")
        seq = cur.fetchone()[0]
        print(f"pg_get_serial_sequence('ventas','id') = {seq}")

        if seq:
            cur.execute(f"SELECT last_value, is_called FROM {seq}")
            last_value, is_called = cur.fetchone()
            print(f"Sequence {seq} last_value={last_value}, is_called={is_called}")
            # compute what nextval would return
            if is_called:
                print(f"nextval would be {last_value+1}")
            else:
                print(f"nextval would be {last_value}")
        else:
            print("No sequence associated to ventas.id (seq is NULL)")

        # show a few rows of ventas to check ids
        cur.execute("SELECT id, fecha, total FROM ventas ORDER BY id LIMIT 10")
        rows = cur.fetchall()
        print("Primeras filas en ventas:")
        for r in rows:
            print(r)

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
