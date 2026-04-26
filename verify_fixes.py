import logging
import os
import sys

from models.db import get_connection
from models.stock_model import _find_product, increment_stock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify_pending_increments():
    print("Verifying pending_increments table...")
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Check if table exists
        cur.execute("SELECT * FROM pending_increments LIMIT 1")
        print("✅ pending_increments table exists.")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ pending_increments table check failed: {e}")
        return False


def verify_increment_stock():
    print("Verifying increment_stock...")
    try:
        # Need a valid product ID. Let's find one or create one.
        # For safety, we'll try to find a product first.
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, local FROM productos LIMIT 1")
        row = cur.fetchone()
        conn.close()

        if not row:
            print("⚠️ No products found to test increment_stock.")
            return True  # Skip but don't fail if DB is empty

        pid, nombre, local = row[0], row[1], row[2]
        print(f"Testing increment on product {pid} ({nombre})...")

        success, msg = increment_stock(pid, 1, "test_user", local, "test increment")
        if success:
            print(f"✅ increment_stock succeeded: {msg}")
            return True
        else:
            print(f"❌ increment_stock failed: {msg}")
            return False
    except Exception as e:
        print(f"❌ increment_stock exception: {e}")
        return False


def verify_coalesce():
    print("Verifying COALESCE queries...")
    try:
        # Call _find_product which uses the fixed query
        # We pass dummy values that would trigger the query
        _find_product("dummy", "dummy", "dummy", "dummy", "dummy", "dummy")
        print("✅ _find_product query executed (no syntax error).")
        return True
    except Exception as e:
        print(f"❌ _find_product query failed: {e}")
        return False


if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

    ok1 = verify_pending_increments()
    ok2 = verify_increment_stock()
    ok3 = verify_coalesce()

    if ok1 and ok2 and ok3:
        print("\n🎉 ALL CHECKS PASSED!")
        sys.exit(0)
    else:
        print("\n💥 SOME CHECKS FAILED.")
        sys.exit(1)
