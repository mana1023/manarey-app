import logging
import os
import sys
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import stock_model as sm
from models import stock_queue_api as qa

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyQueueBypass")
logging.getLogger("models.stock_queue_api").setLevel(logging.INFO)
logging.getLogger("models.stock_model").setLevel(logging.INFO)


def verify_queue_bypass():
    logger.info("Starting verification of queue bypass...")

    # 1. Test Add Product
    test_name = f"BypassTest_{int(time.time())}"
    payload = {
        "nombre": test_name,
        "categoria": "Test",
        "medida": "Unidad",
        "estado": "Nuevo",
        "color": "Negro",
        "cantidad": 5,
        "precio_costo": 10.0,
        "precio_venta": 20.0,
        "local": "TestLocal",
        "usuario": "tester",
    }

    logger.info(f"Enqueuing add_product operation for {test_name}...")
    qid = qa.enqueue_op("add_product", payload)

    if qid == "DIRECT_BYPASS":
        logger.info("✅ add_product returned DIRECT_BYPASS")
    else:
        logger.error(f"❌ add_product returned {qid}, expected DIRECT_BYPASS")

    # Verify product exists in SQL
    product = sm._find_product(
        test_name, "Test", "Unidad", "Nuevo", "Negro", "TestLocal"
    )
    if product:
        logger.info("✅ Product found in SQL immediately.")
        pid = product[0]
    else:
        logger.error("❌ Product not found in SQL immediately.")
        return

    # 2. Test Increment
    logger.info("Enqueuing increment operation...")
    inc_payload = {
        "producto_id": pid,
        "delta": 5,
        "usuario": "tester",
        "local": "TestLocal",
    }
    qid_inc = qa.enqueue_op("increment", inc_payload)

    if qid_inc == "DIRECT_BYPASS":
        logger.info("✅ increment returned DIRECT_BYPASS")
    else:
        logger.error(f"❌ increment returned {qid_inc}, expected DIRECT_BYPASS")

    # Verify quantity
    updated_product = sm._find_product(
        test_name, "Test", "Unidad", "Nuevo", "Negro", "TestLocal"
    )
    if updated_product and updated_product[1] == 10:  # 5 + 5
        logger.info("✅ Quantity updated immediately in SQL.")
    else:
        logger.error(
            f"❌ Quantity update failed. Expected 10, got {updated_product[1] if updated_product else 'None'}"
        )


if __name__ == "__main__":
    verify_queue_bypass()
