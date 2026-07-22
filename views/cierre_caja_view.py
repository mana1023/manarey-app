"""Vista de cierre de turno / caja diaria."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
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

logger = logging.getLogger(__name__)


def _fmt(v: float) -> str:
    return f"${v:,.0f}"


def _card_style(border_color: str = BORDER) -> str:
    return f"""
        QFrame {{
            background: {CARD};
            border: 1px solid {border_color};
            border-radius: 14px;
        }}
        QLabel {{ color: {TEXT}; }}
    """


class StatCard(QFrame):
    def __init__(self, label: str, value: str, color: str = GOLD):
        super().__init__()
        self.setStyleSheet(_card_style())
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:600;")
        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 20, QFont.Bold))
        val.setStyleSheet(f"color:{color};")
        lay.addWidget(lbl)
        lay.addWidget(val)
        self.val_label = val

    def set_value(self, v: str, color: str = GOLD):
        self.val_label.setText(v)
        self.val_label.setStyleSheet(f"color:{color};")


class CierreCajaWindow(QMainWindow):
    def __init__(
        self,
        username: str,
        role: str,
        local: str,
        back_command: Optional[Callable] = None,
    ):
        super().__init__()
        self.username = username
        self.role = role
        self.local = local
        self.back_command = back_command
        self.setWindowTitle(f"Cierre de caja — {local}")
        self.setMinimumSize(900, 640)
        self.resize(1050, 750)
        self.setStyleSheet(
            f"QMainWindow {{ background:{BG}; }} QLabel {{ color:{TEXT}; }}"
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.setCentralWidget(scroll)

        root_w = QWidget()
        scroll.setWidget(root_w)
        self._root = QVBoxLayout(root_w)
        self._root.setContentsMargins(24, 20, 24, 24)
        self._root.setSpacing(16)

        self._build_header()
        self._build_stats_row()
        self._build_gastos_section()
        self._build_cierre_section()
        self._build_historial_section()

        self._refresh()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        row = QHBoxLayout()
        if self.back_command:
            btn_back = QPushButton("← Volver")
            btn_back.setFixedHeight(34)
            btn_back.setCursor(Qt.PointingHandCursor)
            btn_back.setStyleSheet(
                f"QPushButton{{background:{CARD};color:{GOLD};border:1px solid {BORDER};"
                f"border-radius:8px;padding:4px 14px;font-weight:700;}}"
                f"QPushButton:hover{{background:{GOLD};color:#000;}}"
            )
            btn_back.clicked.connect(self.back_command)
            row.addWidget(btn_back)
        title = QLabel(f"💰  Cierre de caja — {self.local}")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color:{GOLD};")
        row.addWidget(title)
        row.addStretch()
        self._root.addLayout(row)

    # ── Tarjetas de resumen ───────────────────────────────────────────────────

    def _build_stats_row(self):
        row = QHBoxLayout()
        row.setSpacing(12)
        self._card_efectivo = StatCard("Efectivo ventas hoy", "$0", GREEN)
        self._card_gastos = StatCard("Gastos registrados", "$0", ORANGE)
        self._card_esperado = StatCard("Esperado en caja", "$0", GOLD)
        for c in (self._card_efectivo, self._card_gastos, self._card_esperado):
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(c)
        self._root.addLayout(row)

    # ── Gastos del turno ──────────────────────────────────────────────────────

    def _build_gastos_section(self):
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        hdr = QLabel("Gastos del turno")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Bold))
        hdr.setStyleSheet(f"color:{GOLD};")
        lay.addWidget(hdr)

        add_row = QHBoxLayout()
        self._gasto_concepto = QLineEdit()
        self._gasto_concepto.setPlaceholderText("Concepto (ej: Limpieza, Flete extra…)")
        self._gasto_monto = QLineEdit()
        self._gasto_monto.setPlaceholderText("Monto")
        self._gasto_monto.setFixedWidth(120)
        btn_add = QPushButton("+ Agregar")
        btn_add.setFixedHeight(34)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(self._btn_style(GREEN))
        btn_add.clicked.connect(self._on_add_gasto)
        for w in (self._gasto_concepto, self._gasto_monto, btn_add):
            add_row.addWidget(w)
        lay.addLayout(add_row)

        self._gastos_table = QTableWidget(0, 4)
        self._gastos_table.setHorizontalHeaderLabels(
            ["Concepto", "Monto", "Usuario", ""]
        )
        self._gastos_table.verticalHeader().setVisible(False)
        self._gastos_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._gastos_table.setStyleSheet(self._table_style())
        hdr_h = self._gastos_table.horizontalHeader()
        hdr_h.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr_h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr_h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr_h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._gastos_table.setMaximumHeight(200)
        lay.addWidget(self._gastos_table)
        self._root.addWidget(frame)

    # ── Cierre formal ─────────────────────────────────────────────────────────

    def _build_cierre_section(self):
        frame = QFrame()
        frame.setStyleSheet(_card_style(GOLD))
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        hdr = QLabel("Cierre de turno")
        hdr.setFont(QFont("Segoe UI", 14, QFont.Bold))
        hdr.setStyleSheet(f"color:{GOLD};")
        lay.addWidget(hdr)

        form = QHBoxLayout()
        form.setSpacing(16)

        ini_col = QVBoxLayout()
        ini_col.addWidget(QLabel("Efectivo inicial ($)"))
        self._inicial_input = QLineEdit()
        self._inicial_input.setPlaceholderText("0")
        self._inicial_input.setFixedWidth(140)
        self._inicial_input.textChanged.connect(self._recalcular_diferencia)
        ini_col.addWidget(self._inicial_input)
        form.addLayout(ini_col)

        real_col = QVBoxLayout()
        real_col.addWidget(QLabel("Efectivo real contado ($)"))
        self._real_input = QLineEdit()
        self._real_input.setPlaceholderText("0")
        self._real_input.setFixedWidth(140)
        self._real_input.textChanged.connect(self._recalcular_diferencia)
        real_col.addWidget(self._real_input)
        form.addLayout(real_col)

        dif_col = QVBoxLayout()
        dif_col.addWidget(QLabel("Diferencia"))
        self._dif_label = QLabel("$0")
        self._dif_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self._dif_label.setStyleSheet(f"color:{MUTED};")
        dif_col.addWidget(self._dif_label)
        form.addLayout(dif_col)

        form.addStretch()
        lay.addLayout(form)

        notas_lbl = QLabel("Notas (opcional)")
        lay.addWidget(notas_lbl)
        self._notas_input = QTextEdit()
        self._notas_input.setMaximumHeight(70)
        self._notas_input.setPlaceholderText("Observaciones del turno…")
        lay.addWidget(self._notas_input)

        btn_cerrar = QPushButton("✔  Cerrar turno")
        btn_cerrar.setFixedHeight(42)
        btn_cerrar.setCursor(Qt.PointingHandCursor)
        btn_cerrar.setFont(QFont("Segoe UI", 12, QFont.Bold))
        btn_cerrar.setStyleSheet(self._btn_style(GOLD, text_color="#000"))
        btn_cerrar.clicked.connect(self._on_cerrar_turno)
        lay.addWidget(btn_cerrar)
        self._root.addWidget(frame)

    # ── Historial de cierres ──────────────────────────────────────────────────

    def _build_historial_section(self):
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        hdr_row = QHBoxLayout()
        hdr = QLabel("Historial de cierres")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Bold))
        hdr.setStyleSheet(f"color:{MUTED};")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        lay.addLayout(hdr_row)

        self._hist_table = QTableWidget(0, 8)
        self._hist_table.setHorizontalHeaderLabels(
            [
                "Fecha",
                "Usuario",
                "Inicial",
                "Ventas ef.",
                "Gastos",
                "Esperado",
                "Real",
                "Diferencia",
            ]
        )
        self._hist_table.verticalHeader().setVisible(False)
        self._hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._hist_table.setStyleSheet(self._table_style())
        hdr_h = self._hist_table.horizontalHeader()
        for i in range(8):
            hdr_h.setSectionResizeMode(
                i, QHeaderView.Stretch if i in (0, 1) else QHeaderView.ResizeToContents
            )
        self._hist_table.setMinimumHeight(200)
        lay.addWidget(self._hist_table)
        self._root.addWidget(frame)

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _refresh(self):
        self._load_gastos()
        self._load_efectivo_hoy()
        self._load_historial()
        self._recalcular_diferencia()

    def _load_efectivo_hoy(self):
        try:
            from datetime import date

            from models import ventas_model as vm

            last_wd = vm.get_last_withdrawal_datetime(self.local)
            efectivo = vm.get_cash_earned_since(self.local, last_wd)
            self._efectivo_hoy = efectivo
            self._card_efectivo.set_value(_fmt(efectivo), GREEN)
        except Exception:
            self._efectivo_hoy = 0.0

    def _load_gastos(self):
        try:
            from models.cierre_caja_model import get_gastos_del_dia

            self._gastos = get_gastos_del_dia(self.local)
        except Exception:
            self._gastos = []
        total_g = sum(float(g["monto"]) for g in self._gastos)
        self._card_gastos.set_value(_fmt(total_g), ORANGE)
        self._gastos_table.setRowCount(0)
        for g in self._gastos:
            r = self._gastos_table.rowCount()
            self._gastos_table.insertRow(r)
            self._gastos_table.setItem(
                r, 0, QTableWidgetItem(str(g.get("concepto", "")))
            )
            self._gastos_table.setItem(
                r, 1, QTableWidgetItem(_fmt(float(g.get("monto", 0))))
            )
            self._gastos_table.setItem(
                r, 2, QTableWidgetItem(str(g.get("usuario", "")))
            )
            gid = g.get("id")
            btn = QPushButton("✕")
            btn.setFixedSize(28, 24)
            btn.setStyleSheet(
                f"QPushButton{{background:#3a1a1a;color:{RED};border:none;border-radius:6px;}}"
                f"QPushButton:hover{{background:{RED};color:#fff;}}"
            )
            btn.clicked.connect(lambda _, gid=gid: self._on_delete_gasto(gid))
            self._gastos_table.setCellWidget(r, 3, btn)
        self._recalcular_diferencia()

    def _load_historial(self):
        try:
            from models.cierre_caja_model import get_cierres

            cierres = get_cierres(self.local, limit=30)
        except Exception:
            cierres = []
        self._hist_table.setRowCount(0)
        for c in cierres:
            r = self._hist_table.rowCount()
            self._hist_table.insertRow(r)
            fecha = str(c.get("fecha_cierre", ""))[:16]
            dif = float(c.get("diferencia", 0))
            color = GREEN if dif >= 0 else RED
            self._hist_table.setItem(r, 0, QTableWidgetItem(fecha))
            self._hist_table.setItem(r, 1, QTableWidgetItem(str(c.get("usuario", ""))))
            self._hist_table.setItem(
                r, 2, QTableWidgetItem(_fmt(float(c.get("monto_inicial", 0))))
            )
            self._hist_table.setItem(
                r, 3, QTableWidgetItem(_fmt(float(c.get("ventas_efectivo", 0))))
            )
            self._hist_table.setItem(
                r, 4, QTableWidgetItem(_fmt(float(c.get("gastos_total", 0))))
            )
            self._hist_table.setItem(
                r, 5, QTableWidgetItem(_fmt(float(c.get("monto_esperado", 0))))
            )
            self._hist_table.setItem(
                r, 6, QTableWidgetItem(_fmt(float(c.get("monto_real", 0))))
            )
            dif_item = QTableWidgetItem(_fmt(dif))
            dif_item.setForeground(QColor(color))
            self._hist_table.setItem(r, 7, dif_item)

    def _recalcular_diferencia(self):
        try:
            ini = float(
                self._inicial_input.text().replace("$", "").replace(",", "") or 0
            )
        except ValueError:
            ini = 0.0
        try:
            real = float(self._real_input.text().replace("$", "").replace(",", "") or 0)
        except ValueError:
            real = 0.0
        total_g = sum(float(g["monto"]) for g in getattr(self, "_gastos", []))
        efect = getattr(self, "_efectivo_hoy", 0.0)
        esperado = ini + efect - total_g
        self._card_esperado.set_value(_fmt(esperado), GOLD)
        dif = real - esperado
        color = GREEN if dif >= 0 else RED
        sign = "+" if dif >= 0 else ""
        self._dif_label.setText(f"{sign}{_fmt(dif)}")
        self._dif_label.setStyleSheet(
            f"color:{color}; font-size:16px; font-weight:800;"
        )

    def _on_add_gasto(self):
        concepto = self._gasto_concepto.text().strip()
        if not concepto:
            QMessageBox.warning(self, "Gasto", "Ingresá el concepto.")
            return
        try:
            monto = float(
                self._gasto_monto.text().replace("$", "").replace(",", "") or 0
            )
        except ValueError:
            monto = 0.0
        if monto <= 0:
            QMessageBox.warning(self, "Gasto", "El monto debe ser mayor a 0.")
            return
        from models.cierre_caja_model import add_gasto

        add_gasto(self.local, self.username, concepto, monto)
        self._gasto_concepto.clear()
        self._gasto_monto.clear()
        self._load_gastos()

    def _on_delete_gasto(self, gasto_id: int):
        from models.cierre_caja_model import delete_gasto

        delete_gasto(gasto_id)
        self._load_gastos()

    def _on_cerrar_turno(self):
        try:
            ini = float(
                self._inicial_input.text().replace("$", "").replace(",", "") or 0
            )
        except ValueError:
            ini = 0.0
        try:
            real = float(self._real_input.text().replace("$", "").replace(",", "") or 0)
        except ValueError:
            QMessageBox.warning(self, "Cierre", "Ingresá el efectivo real contado.")
            return
        notas = self._notas_input.toPlainText().strip()

        total_g = sum(float(g["monto"]) for g in self._gastos)
        efect = getattr(self, "_efectivo_hoy", 0.0)
        esperado = ini + efect - total_g
        dif = real - esperado
        sign = "+" if dif >= 0 else ""
        estado_txt = "SOBRANTE ✔" if dif >= 0 else "FALTANTE ✘"

        confirm = QMessageBox.question(
            self,
            "Confirmar cierre",
            f"Ventas efectivo: {_fmt(efect)}\n"
            f"Gastos: {_fmt(total_g)}\n"
            f"Esperado: {_fmt(esperado)}\n"
            f"Real contado: {_fmt(real)}\n"
            f"Diferencia: {sign}{_fmt(dif)} ({estado_txt})\n\n"
            f"¿Confirmar cierre de turno?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        from models.cierre_caja_model import hacer_cierre

        cierre_id = hacer_cierre(self.local, self.username, ini, efect, real, notas)
        if cierre_id:
            QMessageBox.information(self, "Cierre", f"Turno cerrado. ID: {cierre_id}")
            self._inicial_input.clear()
            self._real_input.clear()
            self._notas_input.clear()
            self._refresh()
        else:
            QMessageBox.critical(self, "Error", "No se pudo guardar el cierre.")

    # ── Helpers de estilo ─────────────────────────────────────────────────────

    @staticmethod
    def _btn_style(color: str, text_color: str = "#fff") -> str:
        return (
            f"QPushButton{{background:{color};color:{text_color};border:none;"
            f"border-radius:10px;padding:6px 18px;font-weight:700;}}"
            f"QPushButton:hover{{opacity:0.85;}}"
        )

    @staticmethod
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
