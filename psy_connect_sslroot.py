import os
import traceback
from urllib.parse import urlparse

import certifi


def main():
    try:
        dsn = os.environ.get("DATABASE_URL")
        print("DSN:", dsn)
        u = urlparse(dsn)
        user = u.username
        pw = u.password
        host = u.hostname
        port = u.port
        dbname = u.path.lstrip("/")
        print(user, host, port, dbname)
        import psycopg2

        print("psycopg2 version", psycopg2.__version__)
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=pw,
            sslmode="require",
            sslrootcert=certifi.where(),
            connect_timeout=10,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        print("OK", cur.fetchone())
        conn.close()
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
