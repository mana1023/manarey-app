"""Vista de historial de cambios de precio — solo admin."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
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
RED = "#f87171"


def _fmt(v) -> str:
    try:
        return f"${float(v):,.0f}"
    except Exception:
        return str(v or "—")


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


class PrecioHistorialWindow(QMainWindow):
    def __init__(
        self,
        username: str,
        role: str,
        local: str = "",
        back_command: Optional[Callable] = None,
    ):
        super().__init__()
        self.username = username
        self.role = role
        self.local = local
        self.back_command = back_command
        self.setWindowTitle("Historial de precios")
        self.setMinimumSize(960, 600)
        self.resize(1150, 760)
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
        self._build_filters()
        self._build_table()
        QTimer.singleShot(100, self.load_data)

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
        title = QLabel("📈  Historial de cambios de precio")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color:{GOLD};")
        row.addWidget(title)
        row.addStretch()
        note = QLabel("Registro de cada modificación de precio o costo por usuario.")
        note.setStyleSheet(f"color:{MUTED};font-size:11px;")
        row.addWidget(note)
        self._root.addLayout(row)

    def _build_filters(self):
        row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar producto…")
        self._search.setFixedHeight(34)
        self._search.setStyleSheet(
            f"QLineEdit{{background:{CARD};color:{TEXT};border:1px solid {BORDER};"
            f"border-radius:10px;padding:4px 12px;}}"
        )
        self._search.textChanged.connect(self.load_data)
        row.addWidget(self._search)

        btn_ref = QPushButton("↺")
        btn_ref.setFixedSize(34, 34)
        btn_ref.setCursor(Qt.PointingHandCursor)
        btn_ref.setStyleSheet(
            f"QPushButton{{background:{CARD};color:{GOLD};border:1px solid {BORDER};"
            f"border-radius:10px;font-weight:700;}}"
        )
        btn_ref.clicked.connect(self.load_data)
        row.addWidget(btn_ref)
        self._root.addLayout(row)

    def _build_table(self):
        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels(
            [
                "Producto",
                "Local",
                "Usuario",
                "Fecha",
                "Costo ant.",
                "Costo nuevo",
                "Venta ant.",
                "Venta nueva",
                "Motivo",
            ]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setStyleSheet(_table_style())
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        for i in (4, 5, 6, 7):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(8, QHeaderView.Stretch)
        self._table.setMinimumHeight(400)
        self._root.addWidget(self._table)

    def load_data(self):
        try:
            from models.precio_historial_model import get_historial_global

            rows = get_historial_global(self.local)
        except Exception:
            rows = []

        search = self._search.text().strip().lower()
        if search:
            rows = [r for r in rows if search in str(r.get("producto", "")).lower()]

        self._table.setRowCount(0)
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(
                r, 0, QTableWidgetItem(str(row.get("producto", "") or ""))
            )
            self._table.setItem(r, 1, QTableWidgetItem(str(row.get("local", "") or "")))
            self._table.setItem(
                r, 2, QTableWidgetItem(str(row.get("usuario", "") or ""))
            )
            self._table.setItem(r, 3, QTableWidgetItem(str(row.get("fecha", ""))[:16]))

            c_ant = float(row.get("costo_ant", 0) or 0)
            c_new = float(row.get("costo_nuevo", 0) or 0)
            v_ant = float(row.get("venta_ant", 0) or 0)
            v_new = float(row.get("venta_nuevo", 0) or 0)

            self._table.setItem(r, 4, QTableWidgetItem(_fmt(c_ant)))
            c_item = QTableWidgetItem(_fmt(c_new))
            c_item.setForeground(QColor(GREEN if c_new >= c_ant else RED))
            self._table.setItem(r, 5, c_item)

            self._table.setItem(r, 6, QTableWidgetItem(_fmt(v_ant)))
            v_item = QTableWidgetItem(_fmt(v_new))
            v_item.setForeground(QColor(GREEN if v_new >= v_ant else RED))
            self._table.setItem(r, 7, v_item)

            self._table.setItem(
                r, 8, QTableWidgetItem(str(row.get("motivo", "") or ""))
            )
