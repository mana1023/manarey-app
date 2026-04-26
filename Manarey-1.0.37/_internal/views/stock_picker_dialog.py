# views/stock_picker_dialog.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
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


class StockPickerDialog(QDialog):
    """
    Muestra el stock con – [0] + por fila y devuelve un dict product_id -> cantidad (>0)
    """

    def __init__(self, parent=None, productos=None, titulo="Seleccionar productos"):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setModal(True)
        self.resize(920, 560)

        self.productos = productos or []
        self.seleccion = {}  # product_id -> cant

        self._build_ui()
        self._load()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Seleccioná productos del stock")
        title.setStyleSheet("font-weight:600; font-size:15px;")
        root.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Código", "Producto", "Categoría", "Precio", "Cantidad"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeToContents
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            """
            QTableWidget { gridline-color:#333; }
            QTableWidget::item { padding:6px; }
            QHeaderView::section { background:#222; color:#ddd; border:none; padding:6px 8px; }
        """
        )
        root.addWidget(self.table)

        btns = QHBoxLayout()
        btns.addStretch()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_ok = QPushButton("Agregar selección")
        self.btn_ok.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._on_ok)

        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_ok)
        root.addLayout(btns)

    def _load(self):
        self.table.setRowCount(len(self.productos))
        for r, p in enumerate(self.productos):
            pid = int(p["id"])
            self.seleccion[pid] = 0

            self.table.setItem(r, 0, QTableWidgetItem(str(pid)))
            self.table.setItem(r, 1, QTableWidgetItem(p.get("nombre", "")))
            self.table.setItem(r, 2, QTableWidgetItem(p.get("categoria", "-")))
            self.table.setItem(
                r, 3, QTableWidgetItem(self._fmt_money(p.get("precio", 0.0)))
            )

            w = self._cantidad_widget(pid, p.get("disponible", None))
            self.table.setCellWidget(r, 4, w)

    def _cantidad_widget(self, pid, max_disp=None) -> QWidget:
        cont = QWidget()
        from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton

        lay = QHBoxLayout(cont)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        btn_menos = QPushButton("–")
        btn_menos.setFixedWidth(28)
        btn_menos.setCursor(Qt.PointingHandCursor)
        btn_menos.setStyleSheet("QPushButton{background:#333; border-radius:6px;}")

        btn_mas = QPushButton("+")
        btn_mas.setFixedWidth(28)
        btn_mas.setCursor(Qt.PointingHandCursor)
        btn_mas.setStyleSheet("QPushButton{background:#333; border-radius:6px;}")

        lbl = QLabel("0")
        lbl.setFixedWidth(32)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            "QLabel{background:#111; border:1px solid #333; border-radius:6px;}"
        )

        def inc():
            cur = self.seleccion[pid]
            if (max_disp is None) or (cur < max_disp):
                cur += 1
                self.seleccion[pid] = cur
                lbl.setText(str(cur))

        def dec():
            cur = self.seleccion[pid]
            if cur > 0:
                cur -= 1
                self.seleccion[pid] = cur
                lbl.setText(str(cur))

        btn_mas.clicked.connect(inc)
        btn_menos.clicked.connect(dec)

        lay.addWidget(btn_menos)
        lay.addWidget(lbl)
        lay.addWidget(btn_mas)
        return cont

    def _on_ok(self):
        elegidos = {pid: c for pid, c in self.seleccion.items() if c > 0}
        if not elegidos:
            QMessageBox.information(
                self, "Sin selección", "Usá + / – para elegir cantidades."
            )
            return
        self.accept()

    def get_selection(self):
        return {pid: c for pid, c in self.seleccion.items() if c > 0}

    def _fmt_money(self, v: float) -> str:
        s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"${s}"
