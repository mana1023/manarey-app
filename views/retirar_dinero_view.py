"""Retirar dinero — reemplaza el viejo 'Cierre de caja'.

Muestra el efectivo que entró al local BOLETA POR BOLETA (y, en Longchamps,
los cobros en domicilio hechos en la casa), permite abrir la boleta o el
remito de cada una, y registra el retiro con contraseña anotando QUIEN retiró,
CUANDO y CUANTO dejó en la caja. Abajo, el historial de retiros.
"""
from __future__ import annotations

import logging
import os
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models import cierre_caja_model as ccm
from models import ventas_model as vm

logger = logging.getLogger(__name__)

try:
    import app_theme as _at

    def _T(k, fb):
        return getattr(_at, k, fb)

except Exception:

    def _T(k, fb):
        return fb


BG = _T("BG", "#0f0f14")
CARD = _T("CARD", "#1a1a22")
BORDER = _T("BORDER", "#2a2a35")
TEXT = _T("TEXT", "#e5e7eb")
MUTED = _T("TEXT_MUTED", "#a0a0a8")
GOLD = _T("GOLD", "#C9A040")
GREEN = _T("GREEN", "#3fae6b")
RED = _T("RED", "#e05656")

_LOCAL_DOMICILIO = "Longchamps"


def _es_local_domicilio(local: str) -> bool:
    return (local or "").strip().lower() == _LOCAL_DOMICILIO.lower()


def _fmt(v: float) -> str:
    try:
        return "${:,.0f}".format(float(v or 0)).replace(",", ".")
    except Exception:
        return "$0"


def _card_style(border: str = BORDER) -> str:
    return (
        f"QFrame {{ background:{CARD}; border:1px solid {border};"
        f" border-radius:14px; }}"
    )


class StatCard(QFrame):
    def __init__(self, label: str, value: str, color: str = GOLD):
        super().__init__()
        self.setStyleSheet(_card_style())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{MUTED}; font-size:13px; border:none;")
        self._val = QLabel(value)
        self._val.setStyleSheet(
            f"color:{color}; font-size:26px; font-weight:800; border:none;"
        )
        lay.addWidget(lbl)
        lay.addWidget(self._val)

    def set_value(self, v: str, color: str = GOLD):
        self._val.setText(v)
        self._val.setStyleSheet(
            f"color:{color}; font-size:26px; font-weight:800; border:none;"
        )


class RetirarDineroWindow(QMainWindow):
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
        self._entradas: list = []  # cache de la ultima carga

        self.setWindowTitle(f"Retirar dinero — {local}")
        self.setMinimumSize(940, 660)
        self.resize(1100, 780)
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
        self._build_entradas_section()
        self._build_gastos_section()
        self._build_historial_section()

        self._refresh()

    # ── Header ──────────────────────────────────────────────────────────────
    def _build_header(self):
        row = QHBoxLayout()
        if self.back_command:
            back = QPushButton("← Volver")
            back.setCursor(Qt.PointingHandCursor)
            back.setStyleSheet(self._btn_style(CARD, TEXT))
            back.clicked.connect(self.back_command)
            row.addWidget(back)
        title = QLabel("Retirar dinero")
        title.setStyleSheet(f"color:{GOLD}; font-size:24px; font-weight:800;")
        row.addWidget(title)
        row.addStretch()
        refresh = QPushButton("↻ Actualizar")
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.setStyleSheet(self._btn_style(CARD, TEXT))
        refresh.clicked.connect(self._refresh)
        row.addWidget(refresh)
        self._root.addLayout(row)

    def _build_stats_row(self):
        row = QHBoxLayout()
        row.setSpacing(14)
        self._card_efectivo = StatCard("Efectivo en caja", "$0", GREEN)
        self._card_domicilio = StatCard("Cobros en domicilio", "$0", GOLD)
        self._card_total = StatCard("Total para retirar", "$0", GOLD)
        row.addWidget(self._card_efectivo)
        if _es_local_domicilio(self.local):
            row.addWidget(self._card_domicilio)
        row.addWidget(self._card_total)
        self._root.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_retirar = QPushButton("💵  Retirar dinero")
        self._btn_retirar.setCursor(Qt.PointingHandCursor)
        self._btn_retirar.setMinimumHeight(48)
        self._btn_retirar.setStyleSheet(self._btn_style(GOLD, "#171717", big=True))
        self._btn_retirar.clicked.connect(self._on_retirar)
        btn_row.addWidget(self._btn_retirar)
        self._root.addLayout(btn_row)

    # ── Entradas (boleta por boleta) ────────────────────────────────────────
    def _build_entradas_section(self):
        card = QFrame()
        card.setStyleSheet(_card_style())
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 16)
        hdr = QLabel("Efectivo que entró (boleta por boleta)")
        hdr.setStyleSheet(
            f"color:{TEXT}; font-size:17px; font-weight:700; border:none;"
        )
        lay.addWidget(hdr)
        sub = QLabel(
            "Desde el último retiro. En Longchamps incluye los cobros en domicilio."
            if _es_local_domicilio(self.local)
            else "Desde el último retiro."
        )
        sub.setStyleSheet(f"color:{MUTED}; font-size:12px; border:none;")
        lay.addWidget(sub)

        self._tabla = QTableWidget(0, 6)
        self._tabla.setHorizontalHeaderLabels(
            ["Fecha", "N° / Tipo", "Cliente", "Forma", "Monto", "Comprobante"]
        )
        self._tabla.setStyleSheet(self._table_style())
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionMode(QTableWidget.NoSelection)
        h = self._tabla.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        for i in (0, 1, 3, 4, 5):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._tabla.setMinimumHeight(280)
        lay.addWidget(self._tabla)
        self._root.addWidget(card)

    # ── Gastos ──────────────────────────────────────────────────────────────
    def _build_gastos_section(self):
        card = QFrame()
        card.setStyleSheet(_card_style())
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 16)
        top = QHBoxLayout()
        hdr = QLabel("Gastos del turno")
        hdr.setStyleSheet(
            f"color:{TEXT}; font-size:16px; font-weight:700; border:none;"
        )
        top.addWidget(hdr)
        top.addStretch()
        self._gasto_concepto = QLineEdit()
        self._gasto_concepto.setPlaceholderText("Concepto")
        self._gasto_concepto.setFixedWidth(220)
        self._gasto_concepto.setStyleSheet(self._input_style())
        self._gasto_monto = QLineEdit()
        self._gasto_monto.setPlaceholderText("Monto")
        self._gasto_monto.setFixedWidth(110)
        self._gasto_monto.setStyleSheet(self._input_style())
        add = QPushButton("+ Agregar")
        add.setCursor(Qt.PointingHandCursor)
        add.setStyleSheet(self._btn_style(CARD, TEXT))
        add.clicked.connect(self._on_add_gasto)
        top.addWidget(self._gasto_concepto)
        top.addWidget(self._gasto_monto)
        top.addWidget(add)
        lay.addLayout(top)
        self._gastos_box = QVBoxLayout()
        lay.addLayout(self._gastos_box)
        self._root.addWidget(card)

    # ── Historial ───────────────────────────────────────────────────────────
    def _build_historial_section(self):
        card = QFrame()
        card.setStyleSheet(_card_style())
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 16)
        hdr = QLabel("Historial de retiros")
        hdr.setStyleSheet(
            f"color:{TEXT}; font-size:16px; font-weight:700; border:none;"
        )
        lay.addWidget(hdr)
        self._tabla_hist = QTableWidget(0, 5)
        self._tabla_hist.setHorizontalHeaderLabels(
            ["Fecha", "Quién retiró", "Local", "Retiró", "Dejó"]
        )
        self._tabla_hist.setStyleSheet(self._table_style())
        self._tabla_hist.verticalHeader().setVisible(False)
        self._tabla_hist.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla_hist.setSelectionMode(QTableWidget.NoSelection)
        hh = self._tabla_hist.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in (0, 2, 3, 4):
            hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._tabla_hist.setMinimumHeight(180)
        lay.addWidget(self._tabla_hist)
        self._root.addWidget(card)

    # ── Carga de datos ──────────────────────────────────────────────────────
    def _refresh(self):
        self._load_entradas()
        self._load_gastos()
        self._load_historial()

    def _gastos_pendientes_total(self) -> float:
        try:
            return sum(float(g["monto"]) for g in ccm.get_gastos_del_dia(self.local))
        except Exception:
            return 0.0

    def _load_entradas(self):
        last_dt = vm.get_last_withdrawal_datetime(self.local)
        try:
            efectivo = vm.get_cash_earned_since(self.local, last_dt)
        except Exception:
            efectivo = 0.0
        entradas = []
        try:
            entradas = list(vm.get_cash_entries_since(self.local, last_dt))
        except Exception:
            logger.exception("Error cargando entradas de efectivo")

        domicilio_total = 0.0
        if _es_local_domicilio(self.local):
            try:
                for c in vm.get_domicilio_pagos_pending():
                    monto = float(c.get("monto_productos") or c.get("monto") or 0)
                    domicilio_total += monto
                    entradas.append(
                        {
                            "venta_id": c.get("venta_id"),
                            "_pago_id": c.get("id"),
                            "numero_venta": c.get("numero_venta"),
                            "fecha": c.get("fecha") or c.get("created_at"),
                            "cliente": (c.get("cliente_nombre") or "").strip(),
                            "forma_pago": "Cobro domicilio",
                            "monto": monto,
                            "origen": "domicilio",
                        }
                    )
            except Exception:
                logger.exception("Error cargando cobros en domicilio")

        gastos = self._gastos_pendientes_total()
        efectivo_neto = max(0.0, efectivo - gastos)
        total = efectivo_neto + domicilio_total
        self._entradas = entradas

        self._card_efectivo.set_value(_fmt(efectivo_neto), GREEN)
        if _es_local_domicilio(self.local):
            self._card_domicilio.set_value(_fmt(domicilio_total), GOLD)
        self._card_total.set_value(_fmt(total), GOLD)

        self._tabla.setRowCount(0)
        for e in entradas:
            self._add_entrada_row(e)

    def _add_entrada_row(self, e: dict):
        r = self._tabla.rowCount()
        self._tabla.insertRow(r)
        fecha = str(e.get("fecha") or "")[:16]
        es_dom = e.get("origen") == "domicilio"
        tipo = "Domicilio" if es_dom else str(e.get("numero_venta") or "")
        cols = [
            fecha,
            tipo,
            e.get("cliente") or "-",
            e.get("forma_pago") or "",
            _fmt(e.get("monto")),
        ]
        for i, val in enumerate(cols):
            it = QTableWidgetItem(str(val))
            if i == 4:
                it.setForeground(Qt.green if not es_dom else Qt.yellow)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tabla.setItem(r, i, it)

        venta_id = e.get("venta_id")
        cell = QWidget()
        cl = QHBoxLayout(cell)
        cl.setContentsMargins(4, 2, 4, 2)
        cl.setSpacing(6)
        b_bol = QPushButton("Boleta")
        b_bol.setCursor(Qt.PointingHandCursor)
        b_bol.setStyleSheet(self._btn_style(CARD, TEXT, small=True))
        b_bol.clicked.connect(lambda _=False, v=venta_id: self._ver_boleta(v))
        b_rem = QPushButton("Remito")
        b_rem.setCursor(Qt.PointingHandCursor)
        b_rem.setStyleSheet(self._btn_style(CARD, TEXT, small=True))
        b_rem.clicked.connect(lambda _=False, v=venta_id: self._ver_remito(v))
        cl.addWidget(b_bol)
        cl.addWidget(b_rem)
        self._tabla.setCellWidget(r, 5, cell)

    def _load_gastos(self):
        while self._gastos_box.count():
            item = self._gastos_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        try:
            gastos = ccm.get_gastos_del_dia(self.local)
        except Exception:
            gastos = []
        if not gastos:
            lbl = QLabel("Sin gastos cargados hoy.")
            lbl.setStyleSheet(f"color:{MUTED}; font-size:13px; border:none;")
            self._gastos_box.addWidget(lbl)
            return
        for g in gastos:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)
            txt = QLabel(f"{g.get('concepto', '')}  —  {_fmt(g.get('monto'))}")
            txt.setStyleSheet(f"color:{TEXT}; font-size:13px; border:none;")
            rl.addWidget(txt)
            rl.addStretch()
            btn = QPushButton("✕")
            btn.setFixedWidth(34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._btn_style(CARD, RED, small=True))
            btn.clicked.connect(
                lambda _=False, gid=g.get("id"): self._on_delete_gasto(gid)
            )
            rl.addWidget(btn)
            self._gastos_box.addWidget(row)

    def _load_historial(self):
        try:
            hist = vm.get_cash_withdrawals(self.local, limit=50)
        except Exception:
            hist = []
        self._tabla_hist.setRowCount(0)
        for w in hist:
            r = self._tabla_hist.rowCount()
            self._tabla_hist.insertRow(r)
            vals = [
                str(w.get("fecha") or "")[:16],
                w.get("usuario") or "-",
                w.get("local") or "",
                _fmt(w.get("retirado")),
                _fmt(w.get("dejado")),
            ]
            for i, val in enumerate(vals):
                it = QTableWidgetItem(str(val))
                if i in (3, 4):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._tabla_hist.setItem(r, i, it)

    # ── Acciones ────────────────────────────────────────────────────────────
    def _on_add_gasto(self):
        concepto = self._gasto_concepto.text().strip()
        try:
            monto = float(
                str(self._gasto_monto.text()).replace(".", "").replace(",", ".")
            )
        except Exception:
            monto = 0.0
        if not concepto or monto <= 0:
            QMessageBox.warning(self, "Gasto", "Poné un concepto y un monto válido.")
            return
        if ccm.add_gasto(self.local, self.username, concepto, monto):
            self._gasto_concepto.clear()
            self._gasto_monto.clear()
            self._refresh()
        else:
            QMessageBox.warning(self, "Gasto", "No se pudo agregar el gasto.")

    def _on_delete_gasto(self, gasto_id):
        if gasto_id and ccm.delete_gasto(gasto_id):
            self._refresh()

    def _pedir_password(self) -> bool:
        pwd_real = vm.get_cash_withdraw_password()
        pwd, ok = self._input_password()
        if not ok:
            return False
        if (pwd or "").strip() != (pwd_real or "").strip():
            QMessageBox.warning(self, "Retirar dinero", "Contraseña incorrecta.")
            return False
        return True

    def _input_password(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Contraseña")
        dlg.setStyleSheet(
            f"QDialog {{ background:{CARD}; }} QLabel {{ color:{TEXT}; }}"
        )
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Ingresá la contraseña para retirar:"))
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.Password)
        edit.setStyleSheet(self._input_style())
        lay.addWidget(edit)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        ok = dlg.exec() == QDialog.Accepted
        return edit.text(), ok

    def _on_retirar(self):
        if not self._pedir_password():
            return
        datos = self._dialogo_retiro()
        if datos is None:
            return
        retiro, dejado = datos

        # Marcar cobros en domicilio como retirados (Longchamps)
        dom_ids = [
            e.get("_pago_id")
            for e in self._entradas
            if e.get("origen") == "domicilio" and e.get("_pago_id")
        ]
        if dom_ids:
            try:
                vm.retirar_domicilio_pagos(dom_ids, self.username)
            except Exception:
                logger.exception("Error retirando cobros domicilio")

        ok, msg = vm.add_cash_withdrawal(
            self.local, retiro, self.username, dejado=dejado
        )
        if ok:
            QMessageBox.information(
                self,
                "Retirar dinero",
                f"Retiro registrado.\nRetirado: {_fmt(retiro)}\nDejado en caja: {_fmt(dejado)}",
            )
            self._refresh()
        else:
            QMessageBox.warning(self, "Retirar dinero", f"No se pudo registrar:\n{msg}")

    def _dialogo_retiro(self):
        try:
            total = float(
                self._card_total._val.text().replace("$", "").replace(".", "") or 0
            )
        except Exception:
            total = 0.0
        dlg = QDialog(self)
        dlg.setWindowTitle("Retirar dinero")
        dlg.setStyleSheet(
            f"QDialog {{ background:{CARD}; }} QLabel {{ color:{TEXT}; }}"
        )
        form = QFormLayout(dlg)
        info = QLabel(f"Disponible: {_fmt(total)}")
        info.setStyleSheet(f"color:{GOLD}; font-size:16px; font-weight:700;")
        form.addRow(info)
        e_ret = QLineEdit(str(int(total)))
        e_ret.setStyleSheet(self._input_style())
        e_dej = QLineEdit("0")
        e_dej.setStyleSheet(self._input_style())
        form.addRow("Cuánto retirás ($)", e_ret)
        form.addRow("Cuánto dejás ($)", e_dej)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec() != QDialog.Accepted:
            return None

        def _num(s):
            try:
                return float(str(s).replace(".", "").replace(",", "."))
            except Exception:
                return 0.0

        retiro = _num(e_ret.text())
        dejado = _num(e_dej.text())
        if retiro <= 0:
            QMessageBox.warning(
                self, "Retirar dinero", "El monto a retirar debe ser mayor a 0."
            )
            return None
        if retiro > total + 1:
            QMessageBox.warning(
                self, "Retirar dinero", "No podés retirar más de lo disponible."
            )
            return None
        return retiro, dejado

    def _ver_boleta(self, venta_id):
        if not venta_id:
            QMessageBox.information(
                self, "Boleta", "Esta fila no tiene boleta asociada."
            )
            return
        try:
            ok, res = vm.generar_pdf_boleta(int(venta_id))
            if ok:
                self._open_pdf_path(res)
            else:
                QMessageBox.warning(self, "Boleta", res)
        except Exception as e:
            QMessageBox.warning(self, "Boleta", f"No se pudo abrir la boleta:\n{e}")

    def _ver_remito(self, venta_id):
        if not venta_id:
            QMessageBox.information(
                self, "Remito", "Esta fila no tiene remito asociado."
            )
            return
        try:
            ok, res = vm.generar_pdf_remito(int(venta_id))
            if ok:
                self._open_pdf_path(res)
            else:
                QMessageBox.warning(self, "Remito", res)
        except Exception as e:
            QMessageBox.warning(self, "Remito", f"No se pudo abrir el remito:\n{e}")

    def _open_pdf_path(self, filepath: str):
        try:
            if filepath and os.path.exists(filepath):
                os.startfile(filepath)  # Windows
            else:
                QMessageBox.information(
                    self, "PDF", "No se encontró el archivo generado."
                )
        except Exception as e:
            QMessageBox.warning(self, "PDF", f"No se pudo abrir el PDF:\n{e}")

    # ── Estilos ─────────────────────────────────────────────────────────────
    @staticmethod
    def _btn_style(bg: str, fg: str, big: bool = False, small: bool = False) -> str:
        pad = "12px 22px" if big else ("4px 10px" if small else "8px 14px")
        fs = "17px" if big else ("12px" if small else "14px")
        return (
            f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {BORDER};"
            f" border-radius:10px; padding:{pad}; font-size:{fs}; font-weight:700; }}"
            f"QPushButton:hover {{ border:1px solid {GOLD}; }}"
        )

    @staticmethod
    def _input_style() -> str:
        return (
            f"QLineEdit {{ background:{BG}; color:{TEXT}; border:1px solid {BORDER};"
            f" border-radius:8px; padding:7px 10px; font-size:14px; }}"
        )

    @staticmethod
    def _table_style() -> str:
        return (
            f"QTableWidget {{ background:{BG}; color:{TEXT}; border:none;"
            f" gridline-color:{BORDER}; }}"
            f"QHeaderView::section {{ background:{CARD}; color:{MUTED};"
            f" border:none; padding:8px; font-weight:700; }}"
            f"QTableWidget::item {{ padding:6px; }}"
        )
