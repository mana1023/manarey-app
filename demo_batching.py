#!/usr/bin/env python3
"""
Demo: Sistema de Batching de Increments para Supabase Free Tier

Demuestra cómo 100 increments se acumulan en pending_increments
y se procesan en 1 batch UPDATE atómico cada 2 segundos.
"""

import logging
import sys
import time

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from models import stock_model as sm
from models.db import get_connection, init_db
from utils.pending_increments_processor import (
    get_pending_increments_stats,
    process_pending_increments,
)


def demo():
    """Demostración completa del sistema de batching."""

    # Inicializar BD
    logger.info("Inicializando BD...")
    init_db()

    # Crear producto de prueba
    logger.info("Creando producto de prueba...")
    ok, msg = sm.add_or_increment(
        nombre="DEMO_BATCHING",
        categoria="Demo",
        medida="u",
        estado="Nuevo",
        color=None,
        cantidad=1000,
        precio_costo=100,
        precio_venta=500,
        local="Demo",
        usuario="demo_user",
    )
    if not ok:
        logger.error(f"Error creando producto: {msg}")
        return

    # Obtener ID del producto
    rows = sm._find_product("DEMO_BATCHING", "Demo", "u", "Nuevo", None, "Demo")
    if not rows:
        logger.error("Producto no encontrado después de crear")
        return

    producto_id = int(rows[0])
    logger.info(f"Producto creado con ID: {producto_id}")

    # Limpiar pending_increments
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM pending_increments")
    conn.commit()
    conn.close()

    # Simular 100 increments en batch (como si fueran 100 clicks de botón)
    logger.info("\n=== FASE 1: Acumulando 100 increments ===")
    print()

    for i in range(100):
        conn = get_connection()
        cur = conn.cursor()

        # Upsert en pending_increments (como hace enqueue_operation para increments)
        cur.execute(
            """
            INSERT INTO pending_increments (producto_id, delta, usuario, local, motivo, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
            ON CONFLICT(producto_id) DO UPDATE SET
                delta = pending_increments.delta + EXCLUDED.delta,
                updated_at = datetime('now','localtime')
        """,
            (producto_id, 1, "demo_user", "Demo", "venta"),
        )
        conn.commit()
        conn.close()

        if (i + 1) % 10 == 0:
            logger.info(f"  Acumulados {i + 1} increments...")

    # Mostrar stats
    stats = get_pending_increments_stats()
    logger.info(f"\nStats después de acumular:")
    logger.info(f"  - Total items en tabla: {stats['total_items']}")
    logger.info(f"  - Productos únicos: {stats['num_productos']}")
    logger.info(f"  - Delta total: {stats['total_delta']}")

    # Verificar que la tabla tiene 1 entrada (no 100)
    assert stats["total_items"] == 1, f"Esperaba 1 item, obtuve {stats['total_items']}"
    assert (
        stats["total_delta"] == 100
    ), f"Esperaba delta=100, obtuve {stats['total_delta']}"
    logger.info("✓ Acumulación correcta: 1 entrada con delta=100")

    # Procesar batch
    logger.info("\n=== FASE 2: Procesando batch ===")
    print()

    # Guardar cantidad antes del batch
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT cantidad FROM productos WHERE id = ?", (producto_id,))
    cantidad_antes = cur.fetchone()[0]
    conn.close()
    logger.info(f"Cantidad antes del batch: {cantidad_antes}")

    # Procesar pending_increments
    start = time.time()
    num_productos, num_items = process_pending_increments()
    elapsed = time.time() - start

    logger.info(f"Batch procesado en {elapsed:.3f}s:")
    logger.info(f"  - Productos procesados: {num_productos}")
    logger.info(f"  - Items agregados: {num_items}")

    # Verificar cantidad después
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT cantidad FROM productos WHERE id = ?", (producto_id,))
    cantidad_despues = cur.fetchone()[0]
    conn.close()

    logger.info(f"Cantidad después del batch: {cantidad_despues}")
    assert (
        cantidad_despues == cantidad_antes + 100
    ), f"Esperaba {cantidad_antes + 100}, obtuve {cantidad_despues}"
    logger.info("✓ UPDATE atómico correcto: cantidad += 100")

    # Verificar historial
    logger.info("\n=== FASE 3: Verificando historial ===")
    print()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT accion, detalle, cantidad, meta
        FROM historial_stock
        WHERE producto_id = ? AND accion = 'suma'
        ORDER BY id DESC LIMIT 1
    """,
        (producto_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row:
        accion, detalle, cantidad, meta = row
        logger.info(f"Última entrada de historial batch:")
        logger.info(f"  - Acción: {accion}")
        logger.info(f"  - Detalle: {detalle}")
        logger.info(f"  - Cantidad: {cantidad}")
        logger.info(f"  - Meta: {meta}")
        assert cantidad == 100, f"Esperaba cantidad=100 en historial, obtuve {cantidad}"
        logger.info(
            "✓ Historial batch registrado correctamente (1 entrada para 100 increments)"
        )
    else:
        logger.warning("No se encontró entrada de historial batch")

    # Stats finales
    stats = get_pending_increments_stats()
    logger.info(f"\nStats después de procesar:")
    logger.info(f"  - Total items: {stats['total_items']}")
    logger.info(f"  - Productos: {stats['num_productos']}")
    logger.info(f"  - Delta total: {stats['total_delta']}")
    assert (
        stats["total_items"] == 0
    ), "Tabla debería estar vacía después del procesamiento"
    logger.info("✓ Tabla limpiada correctamente")

    # Limpiar
    logger.info("\n=== FASE 4: Limpieza ===")
    print()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM historial_stock WHERE producto_id = ?", (producto_id,))
    cur.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
    conn.commit()
    conn.close()
    logger.info("Producto de prueba eliminado")

    logger.info("\n" + "=" * 60)
    logger.info("✅ DEMOSTRACIÓN COMPLETADA EXITOSAMENTE")
    logger.info("=" * 60)
    logger.info("\nResultado: 100 increments acumulados en 1 entrada")
    logger.info("          1 UPDATE atómico procesado")
    logger.info("          1 entrada de historial registrada")
    logger.info("\nImpacto esperado:")
    logger.info("  - Sin batching: 100 ops encoladas → N conexiones")
    logger.info("  - Con batching: 1 UPDATE batch → 1 conexión")
    logger.info("  - Reducción: 100x menos carga en DB/Supabase")


if __name__ == "__main__":
    try:
        demo()
    except Exception as e:
        logger.error(f"Error en demo: {e}", exc_info=True)
        sys.exit(1)
