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
        cur.execute(
            "SELECT is_nullable FROM information_schema.columns WHERE table_name='ventas' AND column_name='numero_venta'"
        )
        row = cur.fetchone()
        if not row:
            print("Columna numero_venta no encontrada")
            return
        is_nullable = row[0]
        print(f"numero_venta is_nullable = {is_nullable}")
        if is_nullable == "NO":
            print("Quitando NOT NULL de numero_venta")
            cur.execute("ALTER TABLE ventas ALTER COLUMN numero_venta DROP NOT NULL")
            conn.commit()
            print("NOT NULL eliminado")
        else:
            print("numero_venta ya admite NULL")
    except Exception as e:
        print("Error comprobando/quitando NOT NULL:", e)
        try:
            conn.rollback()
        except:
            pass
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
