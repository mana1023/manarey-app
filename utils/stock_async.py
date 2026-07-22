"""Worker especializado para operaciones asíncronas de stock con rate-limiting."""

import logging
import threading
import time
from queue import Queue
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QThread, Signal

from models import stock_model as sm
from models import stock_queue_api as qa
from models.db import get_connection
from utils.rate_limiter import TokenBucket

logger = logging.getLogger(__name__)


class StockAsyncWorker(QThread):
    """Worker que maneja operaciones asíncronas de stock."""

    # Señales para notificar a la UI
    operation_started = Signal(str, dict)  # tipo, detalles
    operation_completed = Signal(str, dict, bool, str)  # tipo, detalles, éxito, mensaje
    queue_updated = Signal(int)  # número de operaciones pendientes
    field_updated = Signal(int, str, object)  # producto_id, field, value
    execute_callback = Signal(object, bool, str)  # callback, success, message

    def __init__(self, username: str, local: str, interval_ms: int = 1000, parent=None):
        super().__init__(parent)
        self.username = username
        self.local = local
        self.interval_ms = interval_ms
        self._running = True
        self._queue = Queue()
        self._results = {}  # mapeo op_id -> resultado
        self._lock = threading.Lock()
        # Token-bucket para rate-limiting hacia op_queue API (máx 10 ops/sec, burst 20)
        self._token_bucket = TokenBucket(rate=10.0, capacity=20)

    def enqueue_operation(
        self, op_type: str, payload: Dict[str, Any], callback=None
    ) -> str:
        """
        Encola una nueva operación.

        Args:
            op_type: Tipo de operación ('increment', 'update_field', etc)
            payload: Datos de la operación
            callback: Función opcional a llamar cuando termine la operación

        Returns:
            str: ID de la operación encolada
        """
        # Asegurar usuario/local
        if "usuario" not in payload:
            payload["usuario"] = self.username
        if "local" not in payload:
            payload["local"] = self.local

        # Generar ID único para la operación
        import uuid

        op_id = str(uuid.uuid4())

        # Encolar con metadata
        self._queue.put(
            {
                "id": op_id,
                "type": op_type,
                "payload": payload,
                "callback": callback,
                "enqueued_at": time.time(),
            }
        )

        # Notificar cambio en cola
        self.queue_updated.emit(self._queue.qsize())

        return op_id

    def get_operation_result(self, op_id: str) -> Optional[Tuple[bool, str]]:
        """Obtiene el resultado de una operación por su ID."""
        with self._lock:
            return self._results.get(op_id)

    def clear_result(self, op_id: str):
        """Limpia el resultado de una operación."""
        with self._lock:
            self._results.pop(op_id, None)

    def get_pending_count(self) -> int:
        """Obtiene número de operaciones pendientes."""
        return self._queue.qsize()

    def run(self):
        """Loop principal del worker con rate-limiting."""
        while self._running:
            try:
                # Procesar lote de operaciones con token-bucket rate-limiting
                while not self._queue.empty() and self._running:
                    # Aplicar token-bucket: si no hay tokens, parar y dormir
                    if not self._token_bucket.consume(1):
                        logger.debug(
                            f"Rate limit: no tokens available ({self._token_bucket.available()} available)"
                        )
                        break

                    # Obtener siguiente operación
                    op = self._queue.get_nowait()
                    if not op:
                        continue

                    op_id = op["id"]
                    op_type = op["type"]
                    payload = op["payload"]
                    callback = op["callback"]

                    # Notificar inicio
                    self.operation_started.emit(op_type, payload)

                    try:
                        # Encolar en la API dedicada de la cola
                        # MODIFICACIÓN: Si retorna "DIRECT_BYPASS", es que ya se ejecutó.
                        qid = qa.enqueue_op(op_type, payload)

                        if qid == "DIRECT_BYPASS":
                            success = True
                            message = "Operación ejecutada directamente (Bypass)"
                            # No necesitamos polling, ya está hecho.

                            # Guardar resultado
                            with self._lock:
                                self._results[op_id] = (success, message, qid)

                            # Notificar completado inmediato
                            self.operation_completed.emit(
                                op_type, payload, success, message
                            )

                            # Ejecutar callback inicial
                            if callback:
                                self.execute_callback.emit(callback, success, message)

                            # Si fue update_field, emitir señal de campo actualizado
                            if op_type == "update_field":
                                try:
                                    pid = int(payload.get("producto_id") or 0)
                                    field = payload.get("field")
                                    value = payload.get("value")
                                    if pid and field:
                                        self.field_updated.emit(pid, field, value)
                                except Exception:
                                    pass

                            # Marcar como procesada y continuar
                            self._queue.task_done()
                            continue

                        success = True if qid else False
                        message = (
                            "Operación encolada"
                            if success
                            else "Error encolando operación"
                        )
                    except Exception as e:
                        success = False
                        message = str(e)
                        qid = None
                        logger.error(f"Error encolando operación: {e}")

                    # Guardar resultado (estado de encolado)
                    with self._lock:
                        self._results[op_id] = (success, message, qid)

                    # Notificar que la operación fue enviada a la cola
                    self.operation_completed.emit(op_type, payload, success, message)

                    # Ejecutar callback inicial si existe (vía señal para thread-safety)
                    if callback:
                        self.execute_callback.emit(callback, success, message)

                    # Lanzar un poller en background que espere al resultado final
                    if success and qid:

                        def _poll_final(
                            qid_local, op_id_local, cb, op_type_local, payload_local
                        ):
                            try:
                                # Esperar hasta que el elemento salga de status 0
                                final_ok = False
                                final_msg = "Timeout esperando resultado"
                                waited = 0.0
                                timeout = 10.0  # segundos
                                interval = 0.3
                                while waited < timeout:
                                    try:
                                        items = qa.get_queue_all_items(limit=200)
                                        target = None
                                        for it in items:
                                            if str(it.get("id") or "") == str(
                                                qid_local
                                            ):
                                                target = it
                                                break
                                        if not target:
                                            # ya no está en la cola → asumimos procesado
                                            final_ok = True
                                            final_msg = (
                                                "Procesado (no encontrado en cola)"
                                            )
                                            break
                                        status = int(target.get("status") or 0)
                                        if status == 2:
                                            final_ok = True
                                            final_msg = "Procesado correctamente"
                                            break
                                        if status == 3:
                                            final_ok = False
                                            final_msg = f"Falló procesamiento: {target.get('last_error') or ''}"
                                            break
                                    except Exception:
                                        pass
                                    time.sleep(interval)
                                    waited += interval

                                # Guardar resultado final
                                with self._lock:
                                    self._results[op_id_local] = (
                                        final_ok,
                                        final_msg,
                                        qid_local,
                                    )

                                # Si fue update_field y resultó OK, emitir señal
                                if final_ok and op_type_local == "update_field":
                                    try:
                                        pid = int(payload_local.get("producto_id") or 0)
                                        field = payload_local.get("field")
                                        value = payload_local.get("value")
                                        if pid and field:
                                            self.field_updated.emit(pid, field, value)
                                    except Exception as e:
                                        logger.error(
                                            f"Error emitiendo field_updated: {e}"
                                        )

                                # Llamar callback final si existe (vía señal para thread-safety)
                                if cb:
                                    self.execute_callback.emit(cb, final_ok, final_msg)

                            except Exception as e:
                                logger.error(f"Poller error: {e}")

                        # Ejecutar poller en hilo separado (daemon)
                        t = threading.Thread(
                            target=_poll_final,
                            args=(qid, op_id, callback, op_type, payload),
                            daemon=True,
                        )
                        t.start()

                    # Marcar como procesada
                    self._queue.task_done()

                # Notificar estado de cola
                self.queue_updated.emit(self._queue.qsize())

                # Dormir entre ciclos
                self.msleep(self.interval_ms)

            except Exception as e:
                logger.error(f"Error en worker de stock: {e}")
                self.msleep(1000)

    def stop(self):
        """Detiene el worker."""
        self._running = False
