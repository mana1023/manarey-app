"""Worker especializado para operaciones de stock asíncronas."""

import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import QThread, Signal

from models import stock_model as sm
from models import stock_queue_api as qa
from models.queue_processor import QueueProcessor

logger = logging.getLogger(__name__)


class StockQueueWorker(QThread):
    """Worker que maneja la cola de operaciones de stock."""

    # Señales para actualizar la UI
    operation_enqueued = Signal(str, str)  # tipo, detalles
    operation_started = Signal(str, str)  # tipo, detalles
    operation_completed = Signal(str, str, bool, str)  # tipo, detalles, éxito, mensaje
    queue_count = Signal(int)  # operaciones pendientes

    def __init__(self, username: str, local: str, interval_ms: int = 1000, parent=None):
        super().__init__(parent)
        self.username = username
        self.local = local
        self.interval_ms = interval_ms
        self._running = True
        self._processor = None

    def enqueue_operation(
        self, op_type: str, payload: Dict[str, Any], local: Optional[str] = None
    ) -> bool:
        """
        Encola una nueva operación.

        Args:
            op_type: Tipo de operación ('increment', 'update_field', etc)
            payload: Datos de la operación
            local: Local específico (si es distinto del default)

        Returns:
            bool: True si se encoló correctamente
        """
        try:
            # Asegurar usuario y local
            if "usuario" not in payload:
                payload["usuario"] = self.username
            if "local" not in payload:
                payload["local"] = local or self.local

            # Encolar
            qid = qa.enqueue_op(op_type, payload)
            if qid:
                # Notificar UI
                details = self._get_operation_details(op_type, payload)
                self.operation_enqueued.emit(op_type, details)
                return True

        except Exception as e:
            logger.error(f"Error encolando operación: {e}")

        return False

    def run(self):
        """Loop principal del worker."""
        # Crear procesador
        if not self._processor:
            self._processor = QueueProcessor(
                max_batch=10, max_retries=3, retry_delay=1.0
            )
            self._processor.start()

        # Loop principal
        while self._running:
            try:
                # Contar pendientes
                cnt = qa.get_queue_count()
                self.queue_count.emit(cnt)

                if cnt > 0:
                    # Notificar inicio de procesamiento
                    for item in qa.get_queue_items(limit=5):
                        op_type = item.get("op_type")
                        payload = item.get("payload", {})
                        details = self._get_operation_details(op_type, payload)
                        self.operation_started.emit(op_type, details)

                    # Procesar lote
                    processed = qa.process_queue_once(limit=10)

                    if processed:
                        # Notificar resultados
                        for item in qa.get_queue_items(limit=5):
                            op_type = item.get("op_type")
                            payload = item.get("payload", {})
                            status = item.get("status", 0)
                            error = item.get("last_error")

                            details = self._get_operation_details(op_type, payload)
                            success = status == 2  # 2 = completed
                            msg = error if error else "Operación completada"

                            self.operation_completed.emit(
                                op_type, details, success, msg
                            )

                # Dormir en bloques pequeños
                ms = 0
                while self._running and ms < self.interval_ms:
                    self.msleep(100)
                    ms += 100

            except Exception as e:
                logger.error(f"Error en worker de stock: {e}")
                self.msleep(1000)

    def stop(self):
        """Detiene el worker y su procesador."""
        self._running = False
        if self._processor:
            self._processor.stop()
            self._processor = None

    def _get_operation_details(self, op_type: str, payload: Dict[str, Any]) -> str:
        """Genera descripción amigable de la operación."""
        try:
            if op_type == "increment":
                pid = payload.get("producto_id")
                delta = payload.get("delta", 0)
                return f"Incremento de {delta} unidades del producto {pid}"

            elif op_type == "decrement":
                pid = payload.get("producto_id")
                delta = payload.get("delta", 0)
                return f"Decremento de {delta} unidades del producto {pid}"

            elif op_type == "update_field":
                pid = payload.get("producto_id")
                field = payload.get("field")
                value = payload.get("value")
                return f"Actualización de {field}={value} del producto {pid}"

            elif op_type == "transfer":
                pid = payload.get("row", {}).get("id")
                to_local = payload.get("to_local")
                cant = payload.get("cantidad", 0)
                return (
                    f"Transferencia de {cant} unidades del producto {pid} a {to_local}"
                )

            elif op_type == "change_state":
                pid = payload.get("producto_id")
                nuevo = payload.get("nuevo_estado")
                cant = payload.get("cantidad", 0)
                return (
                    f"Cambio de estado a {nuevo} de {cant} unidades del producto {pid}"
                )

            else:
                return f"Operación {op_type}"

        except Exception:
            return op_type
