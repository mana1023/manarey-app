"""Vista de gestión de operaciones Boston Creed — solo admin."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
ORANGE = "#fb923c"
BLUE = "#60a5fa"


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


def _btn_style(color: str, tc: str = "#000") -> str:
    return (
        f"QPushButton{{background:{color};color:{tc};border:none;"
        f"border-radius:8px;padding:4px 14px;font-weight:700;}}"
        f"QPushButton:hover{{opacity:0.85;}}"
    )


class BostonCreedWindow(QMainWindow):
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
        self._ops: list = []
        self.setWindowTitle("Financiera Boston Creed — Seguimiento")
        self.setMinimumSize(960, 620)
        self.resize(1150, 780)
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
        self._build_resumen_row()
        self._build_filters()
        self._build_table()
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

        title = QLabel("🏦  Financiera Boston Creed")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color:{GOLD};")
        row.addWidget(title)
        row.addStretch()

        note = QLabel(
            "ⓘ  Los montos internos (+15%) son confidenciales y no aparecen en boletas"
        )
        note.setStyleSheet(f"color:{MUTED};font-size:11px;font-style:italic;")
        row.addWidget(note)
        self._root.addLayout(row)

    # ── Tarjetas de resumen ───────────────────────────────────────────────────

    def _build_resumen_row(self):
        self._res_frame = QFrame()
        self._res_frame.setStyleSheet(
            f"QFrame{{background:{CARD};border:1px solid {BORDER};border-radius:12px;}}"
            f"QLabel{{color:{TEXT};}}"
        )
        rlay = QHBoxLayout(self._res_frame)
        rlay.setContentsMargins(20, 14, 20, 14)
        rlay.setSpacing(32)

        self._lbl_pendiente = self._stat("Pendientes", "0 ops", ORANGE)
        self._lbl_efectivo = self._stat("Efectivo en local", "$0", BLUE)
        self._lbl_liquidado = self._stat("Liquidados", "0 ops", GREEN)
        self._lbl_monto_pend = self._stat("Monto pendiente total", "$0", RED)

        for w in (
            self._lbl_pendiente,
            self._lbl_efectivo,
            self._lbl_liquidado,
            self._lbl_monto_pend,
        ):
            rlay.addWidget(w)
        rlay.addStretch()
        self._root.addWidget(self._res_frame)

    def _stat(self, label: str, value: str, color: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{MUTED};font-size:11px;font-weight:600;")
        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 15, QFont.Bold))
        val.setStyleSheet(f"color:{color};")
        lay.addWidget(lbl)
        lay.addWidget(val)
        w._val_label = val
        w._color = color
        return w

    def _update_stat(self, widget: QWidget, value: str, color: str = None):
        widget._val_label.setText(value)
        if color:
            widget._val_label.setStyleSheet(
                f"color:{color};font-size:15px;font-weight:800;"
            )

    # ── Filtros ───────────────────────────────────────────────────────────────

    def _build_filters(self):
        row = QHBoxLayout()
        row.addWidget(QLabel("Estado:"))
        self._filter_estado = QComboBox()
        self._filter_estado.addItems(
            ["Todos", "pendiente", "efectivo_en_local", "liquidado"]
        )
        self._filter_estado.setFixedHeight(32)
        self._filter_estado.currentIndexChanged.connect(self.load_data)
        row.addWidget(self._filter_estado)
        row.addStretch()
        btn_refresh = QPushButton("↺ Actualizar")
        btn_refresh.setFixedHeight(32)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet(_btn_style(CARD, GOLD))
        btn_refresh.clicked.connect(self.load_data)
        row.addWidget(btn_refresh)
        self._root.addLayout(row)

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _build_table(self):
        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels(
            [
                "N° venta",
                "Cliente",
                "Local",
                "Monto venta",
                "Fecha",
                "Vence",
                "Estado",
                "Acciones",
                "⚠",
            ]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setStyleSheet(_table_style())
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self._table.setMinimumHeight(350)
        self._root.addWidget(self._table)

    # ── Datos ─────────────────────────────────────────────────────────────────

    def load_data(self):
        try:
            from models.boston_creed_model import get_resumen, list_operaciones

            estado = self._filter_estado.currentText()
            estado_filter = "" if estado == "Todos" else estado
            self._ops = list_operaciones(self.local, estado_filter)
            resumen = get_resumen(self.local)
            self._update_stat(
                self._lbl_pendiente, f"{resumen.get('pendiente', 0)} ops", ORANGE
            )
            self._update_stat(
                self._lbl_efectivo, _fmt(resumen.get("monto_efectivo", 0)), BLUE
            )
            self._update_stat(
                self._lbl_liquidado, f"{resumen.get('liquidado', 0)} ops", GREEN
            )
            self._update_stat(
                self._lbl_monto_pend, _fmt(resumen.get("monto_pendiente", 0)), RED
            )
        except Exception:
            logger.exception("Error cargando Boston Creed ops")
            self._ops = []

        self._table.setRowCount(0)
        for op in self._ops:
            r = self._table.rowCount()
            self._table.insertRow(r)

            self._table.setItem(
                r, 0, QTableWidgetItem(str(op.get("numero_venta", "—")))
            )
            self._table.setItem(
                r, 1, QTableWidgetItem(str(op.get("cliente_nombre", "—")))
            )
            self._table.setItem(r, 2, QTableWidgetItem(str(op.get("local", ""))))

            mv = float(op.get("monto_venta", 0))
            mv_item = QTableWidgetItem(_fmt(mv))
            mv_item.setForeground(QColor(GOLD))
            self._table.setItem(r, 3, mv_item)

            self._table.setItem(r, 4, QTableWidgetItem(str(op.get("fecha", ""))[:10]))
            self._table.setItem(
                r, 5, QTableWidgetItem(str(op.get("fecha_esperada", ""))[:10])
            )

            estado_val = str(op.get("estado", ""))
            estado_item = QTableWidgetItem(estado_val)
            estado_colors = {
                "pendiente": ORANGE,
                "efectivo_en_local": BLUE,
                "liquidado": GREEN,
            }
            estado_item.setForeground(QColor(estado_colors.get(estado_val, MUTED)))
            self._table.setItem(r, 6, estado_item)

            # Botones de acción
            op_id = op.get("id")
            estado_actual = op.get("estado", "")
            btn_w = QWidget()
            btn_lay = QHBoxLayout(btn_w)
            btn_lay.setContentsMargins(4, 2, 4, 2)
            btn_lay.setSpacing(4)

            if estado_actual == "pendiente":
                btn_ef = QPushButton("Efectivo cobrado")
                btn_ef.setFixedHeight(26)
                btn_ef.setStyleSheet(_btn_style(BLUE, "#fff"))
                btn_ef.clicked.connect(
                    lambda _, oid=op_id: self._on_marcar_efectivo(oid)
                )
                btn_lay.addWidget(btn_ef)

                btn_liq = QPushButton("Liquidar")
                btn_liq.setFixedHeight(26)
                btn_liq.setStyleSheet(_btn_style(GREEN, "#000"))
                btn_liq.clicked.connect(lambda _, oid=op_id: self._on_liquidar(oid))
                btn_lay.addWidget(btn_liq)

            elif estado_actual == "efectivo_en_local":
                btn_liq = QPushButton("Liquidar")
                btn_liq.setFixedHeight(26)
                btn_liq.setStyleSheet(_btn_style(GREEN, "#000"))
                btn_liq.clicked.connect(lambda _, oid=op_id: self._on_liquidar(oid))
                btn_lay.addWidget(btn_liq)

            self._table.setCellWidget(r, 7, btn_w)

            vencida = op.get("vencida", False)
            alerta = QTableWidgetItem("⚠ VENCIDA" if vencida else "")
            alerta.setForeground(QColor(RED) if vencida else QColor(MUTED))
            self._table.setItem(r, 8, alerta)

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _on_marcar_efectivo(self, op_id: int):
        from models.boston_creed_model import marcar_efectivo_en_local

        if marcar_efectivo_en_local(op_id):
            self.load_data()
        else:
            QMessageBox.critical(self, "Error", "No se pudo actualizar el estado.")

    def _on_liquidar(self, op_id: int):
        from models.boston_creed_model import liquidar_operacion

        confirm = QMessageBox.question(
            self,
            "Liquidar",
            "¿Confirmar liquidación de esta operación?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            if liquidar_operacion(op_id, self.username):
                self.load_data()
            else:
                QMessageBox.critical(self, "Error", "No se pudo liquidar.")
