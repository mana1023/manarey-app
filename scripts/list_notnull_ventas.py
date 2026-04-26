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
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='ventas' AND is_nullable='NO' ORDER BY ordinal_position"
    )
    rows = cur.fetchall()
    print("NOT NULL columns in ventas:")
    for r in rows:
        print("-", r[0])
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
