"""
Direct migration script for pending_increments table.
Works with both PostgreSQL and SQLite.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.db import get_connection, is_postgres


def create_pending_increments_table():
    """Creates the pending_increments table directly in the database."""
    print("Creating pending_increments table...")
    using_postgres = is_postgres()
    print(f"Using PostgreSQL: {using_postgres}")

    try:
        conn = get_connection()
        cur = conn.cursor()

        # Drop existing table to ensure clean creation
        print("Dropping existing table if it exists...")
        cur.execute("DROP TABLE IF EXISTS pending_increments")

        # Create table with correct schema for both databases
        print("Creating new table...")
        if using_postgres:
            create_sql = """
                CREATE TABLE pending_increments (
                    producto_id INTEGER PRIMARY KEY,
                    delta INTEGER NOT NULL DEFAULT 0,
                    usuario TEXT,
                    local TEXT,
                    motivo TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """
        else:  # SQLite
            create_sql = """
                CREATE TABLE pending_increments (
                    producto_id INTEGER PRIMARY KEY,
                    delta INTEGER NOT NULL DEFAULT 0,
                    usuario TEXT,
                    local TEXT,
                    motivo TEXT,
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """

        cur.execute(create_sql)

        # Create index
        print("Creating index...")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_pending_increments_updated_at ON pending_increments(updated_at)"
        )

        # Commit changes
        conn.commit()
        print("✓ Table created successfully!")

        # Verify
        print("\nVerifying table structure...")
        if using_postgres:
            cur.execute(
                """
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'pending_increments'
                ORDER BY ordinal_position
            """
            )
        else:  # SQLite
            cur.execute("PRAGMA table_info(pending_increments)")

        columns = cur.fetchall()
        print("Columns:")
        for col in columns:
            if using_postgres:
                print(f"  - {col[0]}: {col[1]}")
            else:  # SQLite returns different structure
                print(f"  - {col[1]}: {col[2]}")

        conn.close()
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return False


if __name__ == "__main__":
    success = create_pending_increments_table()
    sys.exit(0 if success else 1)
