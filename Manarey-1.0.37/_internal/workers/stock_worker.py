import logging

from PyQt5.QtCore import QObject, pyqtSignal

from models import stock_queue_api as qa

logger = logging.getLogger(__name__)


class StockWorker(QObject):
    """Worker para ejecutar una operación de stock en un hilo separado.

    Emite:
        finished(bool, dict, dict): ok, payload, response
        error(dict): {'error': str, 'payload': payload}
    """

    finished = pyqtSignal(bool, dict, dict)
    error = pyqtSignal(dict)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            ok, msg = qa.execute_increment(self.payload)
            resp = {"msg": msg, "ok": ok}
            self.finished.emit(ok, self.payload, resp)
        except Exception as e:
            logger.error(f"Error en StockWorker.run: {e}")
            self.error.emit({"error": str(e), "payload": self.payload})
