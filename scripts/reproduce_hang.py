"""
Script para reproducir condiciones de bloqueo/hang sobre _sync_field_all_locales.
Ejecutar desde el entorno del proyecto: python scripts/reproduce_hang.py

El script intenta simular carga concurrente en la función de sincronización entre locales
lanzando múltiples threads que encolan operaciones y llaman a _sync_field_all_locales.
Registra excepciones y tiempos para ayudar a reproducir bloqueos o errores "database is locked".
"""
import logging
import random
import threading
import time

from models import stock_model as sm
from models import stock_queue_api as qa

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("repro_hang")

RUN_SECONDS = 30
N_THREADS = 8


def pick_product():
    """Obtiene un producto cualquiera de la DB. Si no existe, intenta crear uno simple."""
    try:
        with sm._get_conn_cm() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id,nombre,categoria,medida,estado,color,local FROM productos LIMIT 1"
            )
            r = cur.fetchone()
            if r:
                return r
            # Si no hay producto, insertar uno
            cur.execute(
                "INSERT INTO productos (nombre,categoria,medida,estado,color,cantidad,precio_costo,precio_venta,local,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "REPRO_PRODUCT",
                    "REPRO_CAT",
                    "u",
                    "Nuevo",
                    None,
                    1,
                    0,
                    100,
                    "ReproLocal",
                    sm._now_local(),
                    sm._now_local(),
                ),
            )
            conn.commit()
            cur.execute(
                "SELECT id,nombre,categoria,medida,estado,color,local FROM productos WHERE nombre=? LIMIT 1",
                ("REPRO_PRODUCT",),
            )
            return cur.fetchone()
    except Exception as e:
        logger.exception(f"Error picking product: {e}")
        raise


def worker_sync(old_key, field, prod_local, user, iterations=50):
    for i in range(iterations):
        try:
            # Alternar valores para forzar actualizaciones
            new_val = random.randint(1, 100000)
            sm._sync_field_all_locales(old_key, field, new_val, prod_local, user)
            # A veces también encolar directamente
            payload = {
                "producto_id": int(old_key[0] if isinstance(old_key[0], int) else 0),
                "field": field,
                "value": new_val,
                "usuario": user,
                "local": prod_local,
                "motivo": "repro_hang",
            }
            try:
                qa.enqueue_op("update_field", payload)
            except Exception as e:
                logger.debug(f"enqueue_op failed: {e}")
        except Exception as e:
            logger.exception(f"worker_sync error: {e}")
        time.sleep(random.random() * 0.2)


def main():
    row = pick_product()
    if not row:
        logger.error("No se pudo obtener/crear producto de prueba")
        return

    pid, nombre, categoria, medida, estado, color, prod_local = row
    old_key = sm._match_tuple(nombre, categoria, medida, estado, color)
    logger.info(f"Selected product id={pid} local={prod_local} key={old_key}")

    threads = []
    for i in range(N_THREADS):
        t = threading.Thread(
            target=worker_sync,
            args=(
                old_key,
                "precio_venta",
                prod_local,
                f"repro_user_{i}",
                int(RUN_SECONDS / 1),
            ),
        )
        t.daemon = True
        threads.append(t)
        t.start()

    t0 = time.time()
    try:
        while time.time() - t0 < RUN_SECONDS:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrumpido por usuario")

    logger.info("Esperando threads...")
    for t in threads:
        t.join(timeout=1)

    logger.info("Script terminado")


if __name__ == "__main__":
    main()
