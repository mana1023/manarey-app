"""stock_widget_pyqt.py

Widget PyQt que muestra productos en una tabla y ejecuta operaciones de
stock (increment/decrement/add) en threads usando el worker `workers/stock_worker.py`.

Está pensado como ejemplo listo para copiar/pegar en tu proyecto y adaptar
a las funciones reales de carga de productos.

Uso:
    from stock_widget_pyqt import StockWidget
    widget = StockWidget(username='juan', local='Cane')
    widget.load_products_async()  # opcional: carga demo o real

"""

import logging
import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models import stock_model as sm
from workers.operation_queue import OperationQueue
from workers.stock_worker import StockWorker

logger = logging.getLogger(__name__)


class LoaderThread(QThread):
    data_loaded = pyqtSignal(list)

    def __init__(self, local, search="", categoria="", medida=""):
        super().__init__()
        self.local = local
        self.search = search
        self.categoria = categoria
        self.medida = medida

    def run(self):
        try:
            rows = sm.get_stock_filtered(
                self.local, self.search, self.categoria, self.medida
            )
            self.data_loaded.emit(rows)
        except Exception as e:
            logger.error(f"Error cargando productos demo: {e}")
            self.data_loaded.emit([])


class StockWidget(QWidget):
    """Widget de ejemplo para mostrar y operar sobre stock sin bloquear UI."""

    def __init__(self, username: str = "demo", local: str = "Cane", parent=None):
        super().__init__(parent)
        self.username = username
        self.local = local
        self._products_by_id = {}
        self.operation_threads = []  # referencias a QThread (legacy)

        # Cola centralizada de operaciones y throttling
        self.operation_queue = OperationQueue(retry=1, delay_between=0.12)
        self.operation_queue.operation_finished.connect(self._on_queue_finished)
        self.operation_queue.operation_error.connect(self._on_queue_error)
        self.operation_queue.start()

        self._last_op_time_by_pid = {}

        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(f"Stock Widget - {self.local}")
        self.resize(900, 500)

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        lbl = QLabel(f"Usuario: {self.username} — Local: {self.local}")
        header.addWidget(lbl)
        btn_reload = QPushButton("Cargar productos")
        btn_reload.clicked.connect(self.load_products_async)
        header.addWidget(btn_reload)
        header.addStretch()
        layout.addLayout(header)

        # Tabla
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Nombre", "Cant", "Categoria", "Medida", "Estado", "+", "-"]
        )
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(1, QHeaderView.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.Fixed)
        header_view.resizeSection(2, 80)
        layout.addWidget(self.table)

    def load_products_async(self):
        """Carga productos usando `sm.get_stock_filtered` en un thread (no bloqueante)."""
        self.loader = LoaderThread(self.local)
        self.loader.data_loaded.connect(self.populate_table)
        self.loader.start()

    def populate_table(self, products):
        """Puebla la tabla con `products` (lista de dicts)."""
        self.table.setRowCount(len(products))
        self._products_by_id = {}
        for i, p in enumerate(products):
            pid = p.get("id")
            self._products_by_id[pid] = p

            id_item = QTableWidgetItem(str(pid))
            id_item.setData(Qt.UserRole, pid)
            self.table.setItem(i, 0, id_item)

            name_item = QTableWidgetItem(str(p.get("nombre", "-")))
            self.table.setItem(i, 1, name_item)

            qty_item = QTableWidgetItem(str(p.get("cantidad", 0)))
            qty_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 2, qty_item)

            cat_item = QTableWidgetItem(str(p.get("categoria", "-")))
            self.table.setItem(i, 3, cat_item)

            med_item = QTableWidgetItem(str(p.get("medida", "-")))
            self.table.setItem(i, 4, med_item)

            est_item = QTableWidgetItem(str(p.get("estado", "Nuevo")))
            self.table.setItem(i, 5, est_item)

            # Botones sencillos
            btn_plus = QPushButton("+")
            btn_plus.clicked.connect(lambda _, row=i: self._on_plus_clicked(row))
            self.table.setCellWidget(i, 6, btn_plus)

            btn_minus = QPushButton("-")
            btn_minus.clicked.connect(lambda _, row=i: self._on_minus_clicked(row))
            self.table.setCellWidget(i, 7, btn_minus)

    def _on_plus_clicked(self, row):
        try:
            pid = self.table.item(row, 0).data(Qt.UserRole)
        except Exception:
            return
        product = self._products_by_id.get(pid)
        if not product:
            return
        payload = {
            "producto_id": pid,
            "delta": 1,
            "usuario": self.username,
            "local": self.local,
            "detalle": "Botón +",
        }
        self._start_stock_worker(payload, row)

    def _on_minus_clicked(self, row):
        try:
            pid = self.table.item(row, 0).data(Qt.UserRole)
        except Exception:
            return
        product = self._products_by_id.get(pid)
        if not product:
            return
        current = int(product.get("cantidad", 0))
        if current <= 0:
            QMessageBox.information(
                self, "Sin stock", "No hay unidades para decrementar"
            )
            return
        payload = {
            "producto_id": pid,
            "delta": -1,
            "usuario": self.username,
            "local": self.local,
            "detalle": "Botón -",
        }
        self._start_stock_worker(payload, row)

    def _start_stock_worker(self, payload, row):
        """Encola la operación en `OperationQueue` (no bloquea UI).

        Cuando termine, `_on_worker_finished` actualizará la fila correspondiente.
        """
        pid = payload.get("producto_id")
        # Throttle rápido por producto
        now = time.time()
        last = self._last_op_time_by_pid.get(pid, 0)
        if now - last < 0.15:
            return
        self._last_op_time_by_pid[pid] = now

        # Encolar
        try:
            self.operation_queue.enqueue(payload)
        except Exception as e:
            logger.error(f"Error encolando operación desde widget: {e}")

        # Guardar mapeo row->pid si es necesario (la cola devolverá payload con producto_id)

    def _on_worker_finished(self, ok, payload, response, row):
        try:
            pid = payload.get("producto_id")
            delta = payload.get("delta", 0)
            if ok:
                # actualizar cantidad localmente y en tabla
                prod = self._products_by_id.get(pid)
                if prod is None:
                    return
                current = int(prod.get("cantidad", 0))
                new_qty = current + delta
                prod["cantidad"] = new_qty
                qty_item = self.table.item(row, 2)
                if qty_item:
                    qty_item.setText(str(new_qty))
                # Toast simple (console)
                logger.info(f"Stock actualizado {pid}: {delta:+d}")
            else:
                msg = response.get("msg", "Error desconocido")
                QMessageBox.warning(self, "Error", str(msg))
        except Exception as e:
            logger.error(f"Error en _on_worker_finished: {e}")

    def _on_queue_finished(self, payload, response):
        """Wrapper para llamadas desde `OperationQueue`.

        Busca el `row` correspondiente al `producto_id` y delega a `_on_worker_finished`.
        """
        try:
            pid = payload.get("producto_id")
            # Buscar fila con ese pid
            row = None
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if item and item.data(Qt.UserRole) == pid:
                    row = r
                    break
            ok = bool(response.get("ok"))
            self._on_worker_finished(ok, payload, response, row)
        except Exception as e:
            logger.error(f"Error en _on_queue_finished (widget): {e}")

    def _on_queue_error(self, payload, error_msg):
        try:
            info = {"error": error_msg, "payload": payload}
            self._on_worker_error(info)
        except Exception as e:
            logger.error(f"Error en _on_queue_error (widget): {e}")

    def _on_worker_error(self, info):
        try:
            if isinstance(info, dict):
                err = info.get("error")
            else:
                err = str(info)
            QMessageBox.critical(self, "Error", f"Error en operación de stock: {err}")
        except Exception as e:
            logger.error(f"Error mostrando worker error: {e}")


if __name__ == "__main__":
    # Demo standalone
    app = QApplication(sys.argv)
    w = StockWidget(username="demo", local="Cane")

    # Si sm.get_stock_filtered no funciona en tu entorno, puedes poblar manualmente:
    try:
        w.load_products_async()
    except Exception:
        demo = [
            {
                "id": "p1",
                "nombre": "Producto A",
                "cantidad": 10,
                "categoria": "Cat1",
                "medida": "unidad",
                "estado": "Nuevo",
            },
            {
                "id": "p2",
                "nombre": "Producto B",
                "cantidad": 3,
                "categoria": "Cat2",
                "medida": "cm",
                "estado": "Nuevo",
            },
        ]
        w.populate_table(demo)

    w.show()
    sys.exit(app.exec_())
