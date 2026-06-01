"""Vista CRM de clientes — solo admin."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

try:
    import app_theme as _at

    def _T(k, fb):
        return _at.get_palette_value(k) or fb

except ImportError:

    def _T(k, fb):
        return fb


BG = _T("BG", "#0f0f14")
CARD = _T("CARD", "#1a1a22")
BORDER = _T("BORDER", "#2a2a35")
TEXT = _T("TEXT", "#e5e7eb")
MUTED = _T("TEXT_MUTED", "#a0a0a8")
GOLD = _T("GOLD", "#C9A040")
GREEN = "#4ade80"


def _fmt(v: float) -> str:
    return f"${v:,.0f}"


def _table_style() -> str:
    return f"""
        QTableWidget {{
            background:{CARD}; color:{TEXT};
            border:1px solid {BORDER}; border-radius:8px;
            gridline-color:{BORDER};
        }}
        QHeaderView::section {{
            background:{BG}; color:{MUTED}; font-weight:700;
            padding:6px; border:none;
            border-bottom:1px solid {BORDER};
        }}
        QTableWidget::item:selected {{ background:#2a2a40; }}
    """


def _btn(text: str, color: str = GOLD, tc: str = "#000") -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(36)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:{color};color:{tc};border:none;"
        f"border-radius:10px;padding:4px 16px;font-weight:700;}}"
        f"QPushButton:hover{{opacity:0.85;}}"
    )
    return b


class ClientesWindow(QMainWindow):
    def __init__(
        self,
        username: str,
        role: str,
        back_command: Optional[Callable] = None,
    ):
        super().__init__()
        self.username = username
        self.role = role
        self.back_command = back_command
        self._clientes: list = []
        self.setWindowTitle("Clientes")
        self.setMinimumSize(900, 600)
        self.resize(1100, 720)
        self.setStyleSheet(f"QMainWindow{{background:{BG};}} QLabel{{color:{TEXT};}}")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.setCentralWidget(scroll)

        root_w = QWidget()
        scroll.setWidget(root_w)
        self._root = QVBoxLayout(root_w)
        self._root.setContentsMargins(24, 20, 24, 24)
        self._root.setSpacing(14)

        self._build_header()
        self._build_search_bar()
        self._build_table()
        self._build_detail_panel()

        QTimer.singleShot(100, self.load_data)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        row = QHBoxLayout()
        if self.back_command:
            btn_back = QPushButton("← Volver")
            btn_back.setFixedHeight(34)
            btn_back.setCursor(Qt.PointingHandCursor)
            btn_back.setStyleSheet(
                f"QPushButton{{background:{CARD};color:{GOLD};"
                f"border:1px solid {BORDER};border-radius:8px;"
                f"padding:4px 14px;font-weight:700;}}"
                f"QPushButton:hover{{background:{GOLD};color:#000;}}"
            )
            btn_back.clicked.connect(self.back_command)
            row.addWidget(btn_back)
        title = QLabel("👥  Clientes")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color:{GOLD};")
        row.addWidget(title)
        row.addStretch()
        btn_new = _btn("+ Nuevo cliente", GREEN, "#000")
        btn_new.clicked.connect(self._on_new_cliente)
        row.addWidget(btn_new)
        self._root.addLayout(row)

    # ── Búsqueda ──────────────────────────────────────────────────────────────

    def _build_search_bar(self):
        row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar por nombre o teléfono…")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(
            f"QLineEdit{{background:{CARD};color:{TEXT};border:1px solid {BORDER};"
            f"border-radius:10px;padding:4px 12px;}}"
        )
        self._search.textChanged.connect(self._on_search)
        row.addWidget(self._search)
        self._root.addLayout(row)

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _build_table(self):
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Nombre", "Teléfono", "Email", "Compras", "Total gastado"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setStyleSheet(_table_style())
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.setMinimumHeight(300)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._root.addWidget(self._table)

    # ── Detalle / historial ───────────────────────────────────────────────────

    def _build_detail_panel(self):
        self._detail_frame = QFrame()
        self._detail_frame.setStyleSheet(
            f"QFrame{{background:{CARD};border:1px solid {BORDER};border-radius:12px;}}"
            f"QLabel{{color:{TEXT};}}"
        )
        self._detail_frame.hide()
        lay = QVBoxLayout(self._detail_frame)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        hdr_row = QHBoxLayout()
        self._detail_name = QLabel("Cliente")
        self._detail_name.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._detail_name.setStyleSheet(f"color:{GOLD};")
        hdr_row.addWidget(self._detail_name)
        hdr_row.addStretch()
        btn_edit = _btn("✏ Editar", CARD, GOLD)
        btn_edit.clicked.connect(self._on_edit_cliente)
        hdr_row.addWidget(btn_edit)
        lay.addLayout(hdr_row)

        self._detail_stats = QLabel("")
        self._detail_stats.setStyleSheet(f"color:{MUTED};font-size:12px;")
        lay.addWidget(self._detail_stats)

        hist_lbl = QLabel("Historial de compras:")
        hist_lbl.setStyleSheet(f"color:{MUTED};font-size:11px;font-weight:700;")
        lay.addWidget(hist_lbl)

        self._hist_table = QTableWidget(0, 5)
        self._hist_table.setHorizontalHeaderLabels(
            ["N° venta", "Fecha", "Total", "Forma pago", "Local"]
        )
        self._hist_table.verticalHeader().setVisible(False)
        self._hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._hist_table.setStyleSheet(_table_style())
        h = self._hist_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._hist_table.setMaximumHeight(220)
        lay.addWidget(self._hist_table)
        self._root.addWidget(self._detail_frame)

    # ── Carga de datos ────────────────────────────────────────────────────────

    def load_data(self, search: str = ""):
        try:
            from models.clientes_model import list_clientes

            self._clientes = list_clientes(search)
        except Exception:
            self._clientes = []
        self._populate_table(self._clientes)

    def _populate_table(self, clientes: list):
        self._table.setRowCount(0)
        for c in clientes:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(str(c.get("nombre", ""))))
            self._table.setItem(r, 1, QTableWidgetItem(str(c.get("telefono", ""))))
            self._table.setItem(r, 2, QTableWidgetItem(str(c.get("email", "") or "")))
            # Stats (lazy)
            self._table.setItem(r, 3, QTableWidgetItem("—"))
            self._table.setItem(r, 4, QTableWidgetItem("—"))

        # Cargar stats en background
        QTimer.singleShot(200, self._load_stats_lazy)

    def _load_stats_lazy(self):
        try:
            from models.clientes_model import get_cliente_stats
        except Exception:
            return
        for r, c in enumerate(self._clientes):
            try:
                stats = get_cliente_stats(c["id"])
                self._table.setItem(
                    r, 3, QTableWidgetItem(str(stats.get("cantidad", 0)))
                )
                item_total = QTableWidgetItem(_fmt(float(stats.get("total", 0))))
                item_total.setForeground(QColor(GOLD))
                self._table.setItem(r, 4, item_total)
            except Exception:
                pass

    # ── Eventos ───────────────────────────────────────────────────────────────

    def _on_search(self, text: str):
        self.load_data(text)

    def _on_selection_changed(self):
        rows = self._table.selectedItems()
        if not rows:
            self._detail_frame.hide()
            return
        r = self._table.currentRow()
        if r < 0 or r >= len(self._clientes):
            return
        cliente = self._clientes[r]
        self._show_detail(cliente)

    def _show_detail(self, cliente: dict):
        self._current_cliente = cliente
        self._detail_name.setText(
            f"{cliente.get('nombre', '')} — {cliente.get('telefono', '')}"
        )
        try:
            from models.clientes_model import get_cliente_historial, get_cliente_stats

            stats = get_cliente_stats(cliente["id"])
            self._detail_stats.setText(
                f"Compras: {stats.get('cantidad', 0)}  ·  "
                f"Total gastado: {_fmt(float(stats.get('total', 0)))}  ·  "
                f"Última visita: {str(stats.get('ultima', '—'))[:10]}"
            )
            historial = get_cliente_historial(cliente["id"])
        except Exception:
            historial = []

        self._hist_table.setRowCount(0)
        for h in historial:
            r = self._hist_table.rowCount()
            self._hist_table.insertRow(r)
            self._hist_table.setItem(
                r, 0, QTableWidgetItem(str(h.get("numero_venta", "")))
            )
            self._hist_table.setItem(
                r, 1, QTableWidgetItem(str(h.get("fecha", ""))[:10])
            )
            t_item = QTableWidgetItem(_fmt(float(h.get("total", 0))))
            t_item.setForeground(QColor(GOLD))
            self._hist_table.setItem(r, 2, t_item)
            self._hist_table.setItem(
                r, 3, QTableWidgetItem(str(h.get("forma_pago", "")))
            )
            self._hist_table.setItem(r, 4, QTableWidgetItem(str(h.get("local", ""))))

        self._detail_frame.show()

    def _on_new_cliente(self):
        self._open_form_dialog()

    def _on_edit_cliente(self):
        if hasattr(self, "_current_cliente"):
            self._open_form_dialog(self._current_cliente)

    def _open_form_dialog(self, cliente: dict = None):
        dlg = QDialog(self)
        dlg.setWindowTitle("Cliente")
        dlg.setMinimumWidth(380)
        dlg.setStyleSheet(
            f"QDialog{{background:{BG};}}"
            f"QLabel{{color:{TEXT};}}"
            f"QLineEdit{{background:{CARD};color:{TEXT};border:1px solid {BORDER};"
            f"border-radius:8px;padding:4px 10px;}}"
            f"QTextEdit{{background:{CARD};color:{TEXT};border:1px solid {BORDER};"
            f"border-radius:8px;padding:4px 10px;}}"
        )
        lay = QVBoxLayout(dlg)
        lay.setSpacing(10)

        def field(label, placeholder="", value=""):
            lay.addWidget(QLabel(label))
            inp = QLineEdit(value)
            inp.setPlaceholderText(placeholder)
            inp.setFixedHeight(34)
            lay.addWidget(inp)
            return inp

        f_nombre = field(
            "Nombre *", "Nombre completo", cliente.get("nombre", "") if cliente else ""
        )
        f_tel = field(
            "Teléfono *",
            "Ej: 11-1234-5678",
            cliente.get("telefono", "") if cliente else "",
        )
        f_email = field(
            "Email", "Opcional", cliente.get("email", "") or "" if cliente else ""
        )
        lay.addWidget(QLabel("Notas"))
        f_notas = QTextEdit(cliente.get("notas", "") or "" if cliente else "")
        f_notas.setMaximumHeight(70)
        lay.addWidget(f_notas)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dlg.reject)
        btn_save = QPushButton("Guardar")
        btn_save.setStyleSheet(
            f"QPushButton{{background:{GOLD};color:#000;border:none;"
            f"border-radius:8px;padding:6px 20px;font-weight:700;}}"
        )
        btn_save.clicked.connect(dlg.accept)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        lay.addLayout(btns)

        if dlg.exec_() == QDialog.Accepted:
            nombre = f_nombre.text().strip()
            tel = f_tel.text().strip()
            if not nombre or not tel:
                QMessageBox.warning(
                    self, "Cliente", "Nombre y teléfono son obligatorios."
                )
                return
            from models.clientes_model import save_cliente

            save_cliente(
                nombre, tel, f_email.text().strip(), f_notas.toPlainText().strip()
            )
            self.load_data()
