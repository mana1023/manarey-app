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
            "SELECT is_nullable FROM information_schema.columns WHERE table_name='ventas' AND column_name='vendedor'"
        )
        row = cur.fetchone()
        if not row:
            print("Columna vendedor no encontrada")
            return
        print(f"vendedor is_nullable = {row[0]}")
        if row[0] == "NO":
            print("Quitando NOT NULL de vendedor")
            cur.execute("ALTER TABLE ventas ALTER COLUMN vendedor DROP NOT NULL")
            conn.commit()
            print("NOT NULL eliminado de vendedor")
        else:
            print("vendedor ya admite NULL")
    except Exception as e:
        print("Error:", e)
        try:
            conn.rollback()
        except:
            pass
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
