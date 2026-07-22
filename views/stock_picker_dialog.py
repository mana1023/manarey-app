# views/stock_picker_dialog.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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


def _theme_colors():
    """Devuelve colores del tema actual."""
    try:
        import app_theme as _at

        dark = _at.is_dark_mode()
        c = _at._palette(dark)
        return {
            "bg": c["SURFACE"],
            "text": c["TEXT"],
            "border": c["BORDER"],
            "th_bg": c["TH_BG"],
            "gold": c["GOLD"],
            "row_odd": c["ROW_ODD"],
            "row_even": c["ROW_EVEN"],
            "btn_bg": c["BG_ALT"],
            "lbl_bg": c["INPUT_BG"],
        }
    except Exception:
        return {
            "bg": "#1c1c28",
            "text": "#F8F1E7",
            "border": "#3e3e44",
            "th_bg": "#141420",
            "gold": "#C9A040",
            "row_odd": "#1c1c28",
            "row_even": "#222229",
            "btn_bg": "#34343a",
            "lbl_bg": "#252530",
        }


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

        # Aplicar tema global al dialog
        try:
            import app_theme as _at

            dark = _at.is_dark_mode()
            px = _at.get_font_size_px()
            self.setStyleSheet(_at.build_stylesheet(dark, px))
        except Exception:
            pass

        self._build_ui()
        self._load()

    def _build_ui(self):
        c = _theme_colors()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        title = QLabel("Seleccioná productos del stock")
        title.setStyleSheet(
            f"font-weight:700; font-size:15px; color:{c['gold']}; background:transparent;"
        )
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
            f"QTableWidget {{ background:{c['bg']}; color:{c['text']};"
            f"alternate-background-color:{c['row_even']}; gridline-color:{c['border']};"
            f"border:1px solid {c['border']}; border-radius:8px; }}"
            f"QTableWidget::item {{ padding:6px; color:{c['text']}; }}"
            f"QHeaderView::section {{ background:{c['th_bg']}; color:{c['gold']};"
            f"border:none; border-bottom:2px solid {c['gold']}; padding:6px 8px;"
            f"font-weight:700; }}"
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
        c = _theme_colors()
        cont = QWidget()
        cont.setStyleSheet("background: transparent;")

        lay = QHBoxLayout(cont)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(6)

        btn_menos = QPushButton("–")
        btn_menos.setFixedWidth(30)
        btn_menos.setCursor(Qt.PointingHandCursor)
        btn_menos.setStyleSheet(
            f"QPushButton{{background:{c['btn_bg']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:6px;font-weight:700;}}"
            f"QPushButton:hover{{background:{c['gold']};color:#1a1208;border-color:{c['gold']};}}"
        )

        btn_mas = QPushButton("+")
        btn_mas.setFixedWidth(30)
        btn_mas.setCursor(Qt.PointingHandCursor)
        btn_mas.setStyleSheet(
            f"QPushButton{{background:{c['btn_bg']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:6px;font-weight:700;}}"
            f"QPushButton:hover{{background:{c['gold']};color:#1a1208;border-color:{c['gold']};}}"
        )

        lbl = QLabel("0")
        lbl.setFixedWidth(34)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"QLabel{{background:{c['lbl_bg']};color:{c['text']};"
            f"border:1px solid {c['border']};border-radius:6px;font-weight:700;}}"
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
