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
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='ventas' ORDER BY ordinal_position"
        )
        for col, dtype in cur.fetchall():
            print(col, dtype)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
