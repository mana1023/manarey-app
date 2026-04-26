import logging
import queue
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtCore import QThread, pyqtSignal

from models import stock_queue_api as qa

logger = logging.getLogger(__name__)


class OperationQueue(QThread):
    """Procesador de operaciones de stock con concurrencia controlada.

    Esta cola mantiene un buffer de payloads y los ejecuta usando un
    ThreadPoolExecutor con `max_workers`. Emite señales por cada
    operación completada o fallida, y emite `queue_count` cuando cambia
    el tamaño de la cola.
    """

    operation_finished = pyqtSignal(dict, dict)  # payload, response
    operation_error = pyqtSignal(dict, str)  # payload, error_msg
    queue_count = pyqtSignal(int)

    def __init__(
        self,
        parent=None,
        retry: int = 1,
        delay_between: float = 0.05,
        max_workers: int = 20,
    ):
        super().__init__(parent)
        self._queue = queue.Queue()
        self._running = True
        self._retry = int(retry)
        self._delay_between = float(delay_between)
        self._max_workers = int(max_workers)

    def enqueue(self, payload: dict):
        try:
            self._queue.put(payload)
            # Emitir el tamaño actualizado
            try:
                self.queue_count.emit(self._queue.qsize())
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Error enqueuing payload: {e}")
            return False

    def _process_payload(self, payload: dict):
        """Función ejecutada en el thread pool para procesar una operación."""
        last_resp = None
        success = False
        for attempt in range(self._retry + 1):
            try:
                ok, msg = qa.execute_increment(payload)
                last_resp = {"ok": ok, "msg": msg}
                if ok:
                    success = True
                    break
            except Exception as e:
                last_resp = {"ok": False, "msg": str(e)}
            time.sleep(self._delay_between)
        return success, last_resp

    def run(self):
        # Usar ThreadPoolExecutor para procesar multiples operaciones en paralelo
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures_map = {}
            while self._running or futures_map:
                if len(futures_map) < self._max_workers and self._running:
                    try:
                        payload = self._queue.get(timeout=0.2)
                        if payload is None:
                            continue
                        fut = executor.submit(self._process_payload, payload)
                        futures_map[fut] = payload
                        try:
                            self.queue_count.emit(self._queue.qsize())
                        except Exception:
                            pass
                    except queue.Empty:
                        pass

                done = [f for f in list(futures_map.keys()) if f.done()]
                for f in done:
                    payload = futures_map.pop(f)
                    try:
                        success, resp = f.result()
                        if success:
                            self.operation_finished.emit(payload, resp)
                        else:
                            self.operation_error.emit(
                                payload, resp.get("msg", "Unknown error")
                            )
                    except Exception as e:
                        logger.error(f"Exception processing future: {e}")
                        self.operation_error.emit(payload, str(e))

                if not done:
                    time.sleep(0.02)

    def stop(self):
        self._running = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
