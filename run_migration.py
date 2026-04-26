import os
import sys

from models.db import get_connection


def run_migration():
    print("Running migration...")
    try:
        conn = get_connection()
        cur = conn.cursor()

        with open("migration.sql", "r") as f:
            sql = f.read()

        cur.execute(sql)
        conn.commit()
        print("Migration successful!")
        conn.close()
    except Exception as e:
        print(f"Migration failed: {e}")


if __name__ == "__main__":
    # Add project root to path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    run_migration()
