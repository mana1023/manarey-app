#!/usr/bin/env python3
"""Worker ligero para procesar la cola de operaciones de stock.

Uso: ejecutar este script en cada sucursal (o en un servidor central) para procesar
la tabla `op_queue` mediante la clase `QueueProcessor`.
"""
import logging
import time

from models.queue_processor import QueueProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stock_queue_worker")


def main():
    qp = QueueProcessor(max_batch=20, max_retries=5, retry_delay=1.0)
    logger.info("Iniciando QueueProcessor (CTRL+C para detener)")
    try:
        qp.start()
        # Mantener vivo el hilo principal
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Deteniendo QueueProcessor por señal de teclado")
        qp.stop()


if __name__ == "__main__":
    main()
