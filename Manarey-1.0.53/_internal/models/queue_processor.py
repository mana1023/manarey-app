# queue_processor.py
"""
Procesador robusto para la cola de operaciones con prioridades y manejo de errores.
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from models.firestore_db import (
    firestore_execute_add_product,
    firestore_execute_increment,
    firestore_get_queue_items,
    firestore_mark_queue_item_done,
    firestore_mark_queue_item_failed,
    firestore_mark_queue_item_retry,
    firestore_process_queue_once,
)
from models.stock_model import update_stock_field
from utils.queue_utils import format_queue_error, with_retry

logger = logging.getLogger(__name__)


class QueueProcessor:
    """Procesa operaciones encoladas con manejo robusto de errores y prioridades."""

    # Definir prioridades por tipo de operación (menor número = mayor prioridad)
    PRIORITIES = {
        "transfer": 1,  # Transferencias tienen máxima prioridad
        "decrement": 2,  # Decrementos de stock
        "increment": 2,  # Incrementos de stock
        "change_state": 3,  # Cambios de estado
        "update_field": 4,  # Actualizaciones de campos
        "bulk_update_prices": 5,  # Cambios masivos van al final
    }

    def __init__(
        self, max_batch: int = 10, max_retries: int = 3, retry_delay: float = 1.0
    ):
        self.max_batch = max_batch
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._stop = threading.Event()

    def start(self) -> None:
        """Inicia el procesador en un hilo separado."""
        self._stop.clear()
        threading.Thread(
            target=self._process_loop, name="QueueProcessor", daemon=True
        ).start()

    def stop(self) -> None:
        """Detiene el procesador."""
        self._stop.set()

    def _get_priority(self, op_type: str) -> int:
        """Obtiene prioridad para un tipo de operación."""
        return self.PRIORITIES.get(op_type, 10)  # Default baja prioridad

    def _get_batch(self) -> List[Dict[str, Any]]:
        """
        Obtiene un lote de operaciones ordenadas por:
        1. Prioridad del tipo de operación
        2. Tiempo en cola (más antiguas primero)
        3. Número de intentos (menos intentos primero)
        """
        try:
            items = firestore_get_queue_items(limit=self.max_batch * 2)
            if not items:
                return []
            items.sort(
                key=lambda x: (
                    self._get_priority(x.get("op_type")),
                    x.get("created_at") or "",
                    x.get("attempts") or 0,
                )
            )
            return items[: self.max_batch]
        except Exception as e:
            logger.error(f"Error obteniendo batch: {e}")
            return []

    @with_retry(max_retries=3)
    def _process_item(self, item: Dict[str, Any]) -> Tuple[bool, str]:
        qid = item.get("id")
        op_type = item.get("op_type")
        payload = item.get("payload") or {}
        if not all([qid, op_type]):
            return False, "Item inválido"
        try:
            if isinstance(payload, str):
                payload = json.loads(payload)
        except Exception as e:
            return False, f"Payload inválido: {e}"
        try:
            if op_type == "increment":
                return firestore_execute_increment(payload)
            elif op_type == "decrement":
                payload["delta"] = -abs(int(payload.get("delta") or 0))
                return firestore_execute_increment(payload)
            elif op_type == "add_product":
                return firestore_execute_add_product(payload)
            elif op_type == "update_field":
                return self._process_update_field(payload)
            else:
                return False, f"Tipo de operación desconocido: {op_type}"
        except Exception as e:
            return False, str(e)

    def _process_increment(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        return firestore_execute_increment(payload)

    def _process_decrement(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        payload["delta"] = -abs(int(payload.get("delta") or 0))
        return firestore_execute_increment(payload)

    def _process_update_field(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        pid = int(payload.get("producto_id") or 0)
        field = payload.get("field")
        value = payload.get("value")
        usuario = payload.get("usuario", "sistema")
        local = payload.get("local")
        motivo = payload.get("motivo")
        try:
            success = update_stock_field(
                pid, field, value, usuario=usuario, local=local, motivo=motivo
            )
            if success:
                return True, "Campo actualizado"
            else:
                return False, "Fallo al actualizar campo"
        except Exception as e:
            return False, str(e)

    def _process_transfer(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        return False, "transfer_stock no implementado en Firestore aún"


# queue_processor.py
"""
Procesador robusto para la cola de operaciones con prioridades y manejo de errores.
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from models.firestore_db import (
    firestore_execute_add_product,
    firestore_execute_increment,
    firestore_get_queue_items,
    firestore_mark_queue_item_done,
    firestore_mark_queue_item_failed,
    firestore_mark_queue_item_retry,
    firestore_process_queue_once,
)
from models.stock_model import update_stock_field
from utils.queue_utils import format_queue_error, with_retry

logger = logging.getLogger(__name__)


class QueueProcessor:
    """Procesa operaciones encoladas con manejo robusto de errores y prioridades."""

    # Definir prioridades por tipo de operación (menor número = mayor prioridad)
    PRIORITIES = {
        "transfer": 1,  # Transferencias tienen máxima prioridad
        "decrement": 2,  # Decrementos de stock
        "increment": 2,  # Incrementos de stock
        "change_state": 3,  # Cambios de estado
        "update_field": 4,  # Actualizaciones de campos
        "bulk_update_prices": 5,  # Cambios masivos van al final
    }

    def __init__(
        self, max_batch: int = 10, max_retries: int = 3, retry_delay: float = 1.0
    ):
        self.max_batch = max_batch
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._stop = threading.Event()

    def start(self) -> None:
        """Inicia el procesador en un hilo separado."""
        self._stop.clear()
        threading.Thread(
            target=self._process_loop, name="QueueProcessor", daemon=True
        ).start()

    def stop(self) -> None:
        """Detiene el procesador."""
        self._stop.set()

    def _get_priority(self, op_type: str) -> int:
        """Obtiene prioridad para un tipo de operación."""
        return self.PRIORITIES.get(op_type, 10)  # Default baja prioridad

    def _get_batch(self) -> List[Dict[str, Any]]:
        """
        Obtiene un lote de operaciones ordenadas por:
        1. Prioridad del tipo de operación
        2. Tiempo en cola (más antiguas primero)
        3. Número de intentos (menos intentos primero)
        """
        try:
            items = firestore_get_queue_items(limit=self.max_batch * 2)
            if not items:
                return []
            items.sort(
                key=lambda x: (
                    self._get_priority(x.get("op_type")),
                    x.get("created_at") or "",
                    x.get("attempts") or 0,
                )
            )
            return items[: self.max_batch]
        except Exception as e:
            logger.error(f"Error obteniendo batch: {e}")
            return []

    @with_retry(max_retries=3)
    def _process_item(self, item: Dict[str, Any]) -> Tuple[bool, str]:
        qid = item.get("id")
        op_type = item.get("op_type")
        payload = item.get("payload") or {}
        if not all([qid, op_type]):
            return False, "Item inválido"
        try:
            if isinstance(payload, str):
                payload = json.loads(payload)
        except Exception as e:
            return False, f"Payload inválido: {e}"
        try:
            if op_type == "increment":
                return firestore_execute_increment(payload)
            elif op_type == "decrement":
                payload["delta"] = -abs(int(payload.get("delta") or 0))
                return firestore_execute_increment(payload)
            elif op_type == "add_product":
                return firestore_execute_add_product(payload)
            elif op_type == "update_field":
                return self._process_update_field(payload)
            else:
                return False, f"Tipo de operación desconocido: {op_type}"
        except Exception as e:
            return False, str(e)

    def _process_increment(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        return firestore_execute_increment(payload)

    def _process_decrement(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        payload["delta"] = -abs(int(payload.get("delta") or 0))
        return firestore_execute_increment(payload)

    def _process_update_field(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        pid = int(payload.get("producto_id") or 0)
        field = payload.get("field")
        value = payload.get("value")
        usuario = payload.get("usuario", "sistema")
        local = payload.get("local")
        motivo = payload.get("motivo")
        try:
            success = update_stock_field(
                pid, field, value, usuario=usuario, local=local, motivo=motivo
            )
            if success:
                return True, "Campo actualizado"
            else:
                return False, "Fallo al actualizar campo"
        except Exception as e:
            return False, str(e)

    def _process_transfer(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        return False, "transfer_stock no implementado en Firestore aún"

    def _process_add_product(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        return firestore_execute_add_product(payload)

    def _process_change_state(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        return False, "change_state_quantity no implementado en Firestore aún"

    def _process_loop(self):
        """Ciclo principal de procesamiento."""
        while not self._stop.is_set():
            try:
                items = self._get_batch()
                if not items:
                    time.sleep(self.retry_delay)
                    continue

                for item in items:
                    if self._stop.is_set():
                        break

                    qid = item.get("id", 0)
                    # Asegurar que qid sea string para Firestore si es necesario, o int para SQL
                    # En este contexto, firestore_mark_* espera el ID tal cual viene de firestore (string)
                    qid_for_methods = qid

                    attempts = int(item.get("attempts") or 0)

                    try:
                        ok, msg = self._process_item(item)
                        if ok:
                            firestore_mark_queue_item_done(qid_for_methods)
                        else:
                            attempts += 1
                            if attempts >= self.max_retries:
                                firestore_mark_queue_item_failed(qid_for_methods, msg)
                            else:
                                firestore_mark_queue_item_retry(
                                    qid_for_methods, msg, attempts
                                )
                    except Exception as e:
                        logger.error(f"Error procesando item {qid_for_methods}: {e}")
                        attempts += 1
                        if attempts >= self.max_retries:
                            firestore_mark_queue_item_failed(qid_for_methods, str(e))
                        else:
                            firestore_mark_queue_item_retry(
                                qid_for_methods, str(e), attempts
                            )

            except Exception as e:
                logger.error(f"Error en process_loop: {e}")
                time.sleep(1)
