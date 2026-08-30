"""Retirar dinero — reemplaza el viejo 'Cierre de caja'.

Muestra, DESDE EL ULTIMO RETIRO, toda la plata que entro al local boleta por
boleta (y en Longchamps los cobros hechos en la casa), deja abrir la boleta o
el remito de cada una, y registra el retiro con contrasena anotando QUIEN
retiro, CUANDO y CUANTO dejo en la caja.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
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
GREEN = "#4ade80"
RED = "#f87171"
ROW_ALT = "#15151c"

LOCALES = ["Longchamps", "Cane", "Estacion", "Glew", "Vidriera"]
_LOCAL_DOMICILIO = "Longchamps"


def _es_todos(local: str) -> bool:
    return (local or "").strip().lower() in ("", "todos", "todos los locales")


def _es_local_domicilio(local: str) -> bool:
    return (local or "").strip().lower() == _LOCAL_DOMICILIO.lower()


def _fmt(v) -> str:
    """Plata siempre con punto cada tres numeros: $1.234.567"""
    try:
        return "${:,.0f}".format(float(v or 0)).replace(",", ".")
    except Exception:
        return "$0"


def _fmt_num(v) -> str:
    """Numero sin el signo $, tambien con puntos: 1.234.567"""
    try:
        return "{:,.0f}".format(float(v or 0)).replace(",", ".")
    except Exception:
        return "0"


def _a_numero(texto) -> float:
    """Lee lo que escribio el usuario aunque tenga puntos o comas."""
    try:
        limpio = str(texto).replace("$", "").replace(" ", "")
        limpio = limpio.replace(".", "").replace(",", ".")
        return float(limpio or 0)
    except Exception:
        return 0.0


def _fmt_fecha(v, con_hora: bool = True) -> str:
    """Fecha en criollo: 26/08 14:35"""
    if not v:
        return "-"
    if isinstance(v, datetime):
        dt = v
    else:
        txt = str(v)
        dt = None
        for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(txt[: len(f) + 2].strip(), f)
                break
            except Exception:
                continue
        if dt is None:
            return txt[:16]
    return dt.strftime("%d/%m %H:%M") if con_hora else dt.strftime("%d/%m/%Y")


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
        self._entradas: list = []
        self._total_disponible = 0.0

        self.setWindowTitle(f"Retirar dinero — {local}")
        self.setMinimumSize(980, 680)
        self.resize(1180, 820)
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
        self._root.setContentsMargins(28, 22, 28, 28)
        self._root.setSpacing(18)

        self._build_header()
        self._build_hero()
        self._build_entradas_section()
        self._build_gastos_section()
        self._build_historial_section()
        self._root.addStretch()

        self._refresh()

    # ── Header ──────────────────────────────────────────────────────────────
    def _build_header(self):
        row = QHBoxLayout()
        row.setSpacing(12)
        if self.back_command:
            back = QPushButton("←  Volver")
            back.setCursor(Qt.PointingHandCursor)
            back.setStyleSheet(self._btn(CARD, TEXT))
            back.clicked.connect(self.back_command)
            row.addWidget(back)

        titulo_box = QVBoxLayout()
        titulo_box.setSpacing(1)
        t = QLabel("Retirar dinero")
        t.setStyleSheet(f"color:{GOLD}; font-size:25px; font-weight:800;")
        sub = QLabel(self.local)
        sub.setStyleSheet(f"color:{MUTED}; font-size:14px;")
        titulo_box.addWidget(t)
        titulo_box.addWidget(sub)
        row.addLayout(titulo_box)
        row.addStretch()

        if _es_todos(self.local):
            self._sel_local = QComboBox()
            self._sel_local.setStyleSheet(self._combo_qss())
            self._sel_local.addItem("Todos los locales")
            for loc in LOCALES:
                self._sel_local.addItem(loc)
            self._sel_local.currentIndexChanged.connect(self._cambiar_local)
            row.addWidget(self._sel_local)

        refresh = QPushButton("↻  Actualizar")
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.setStyleSheet(self._btn(CARD, TEXT))
        refresh.clicked.connect(self._refresh)
        row.addWidget(refresh)
        self._root.addLayout(row)

    def _cambiar_local(self, idx: int):
        self.local = "Todos" if idx == 0 else LOCALES[idx - 1]
        self._refresh()

    # ── Hero: el total grande y el boton de retirar ─────────────────────────
    def _build_hero(self):
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:{CARD}; border:2px solid {GOLD};"
            f" border-radius:18px; }}"
        )
        lay = QHBoxLayout(card)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(24)

        izq = QVBoxLayout()
        izq.setSpacing(4)
        cap = QLabel("TOTAL PARA RETIRAR")
        cap.setStyleSheet(
            f"color:{MUTED}; font-size:13px; font-weight:800;"
            f" letter-spacing:1px; border:none;"
        )
        self._lbl_total = QLabel("$0")
        self._lbl_total.setStyleSheet(
            f"color:{GOLD}; font-size:48px; font-weight:800; border:none;"
        )
        self._lbl_desde = QLabel("")
        self._lbl_desde.setStyleSheet(f"color:{MUTED}; font-size:14px; border:none;")
        izq.addWidget(cap)
        izq.addWidget(self._lbl_total)
        izq.addWidget(self._lbl_desde)

        self._lbl_desglose = QLabel("")
        self._lbl_desglose.setStyleSheet(f"color:{TEXT}; font-size:15px; border:none;")
        self._lbl_desglose.setWordWrap(True)
        izq.addSpacing(6)
        izq.addWidget(self._lbl_desglose)
        lay.addLayout(izq, 1)

        self._btn_retirar = QPushButton("Retirar dinero")
        self._btn_retirar.setCursor(Qt.PointingHandCursor)
        self._btn_retirar.setMinimumHeight(62)
        self._btn_retirar.setMinimumWidth(230)
        self._btn_retirar.setStyleSheet(
            f"QPushButton {{ background:{GOLD}; color:#171717; border:none;"
            f" border-radius:14px; font-size:19px; font-weight:800; padding:0 26px; }}"
            f"QPushButton:hover {{ background:#dcb45a; }}"
            f"QPushButton:disabled {{ background:{BORDER}; color:{MUTED}; }}"
        )
        self._btn_retirar.clicked.connect(self._on_retirar)
        lay.addWidget(self._btn_retirar, 0, Qt.AlignVCenter)
        self._root.addWidget(card)

    # ── Entradas (boleta por boleta) ────────────────────────────────────────
    def _build_entradas_section(self):
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 20)
        lay.setSpacing(10)

        top = QHBoxLayout()
        hdr = QLabel("Plata que entró, una por una")
        hdr.setStyleSheet(
            f"color:{TEXT}; font-size:18px; font-weight:800; border:none;"
        )
        top.addWidget(hdr)
        top.addStretch()
        self._lbl_conteo = QLabel("")
        self._lbl_conteo.setStyleSheet(f"color:{MUTED}; font-size:14px; border:none;")
        top.addWidget(self._lbl_conteo)
        lay.addLayout(top)

        self._lbl_aviso = QLabel("")
        self._lbl_aviso.setStyleSheet(f"color:{RED}; font-size:13px; border:none;")
        self._lbl_aviso.setVisible(False)
        lay.addWidget(self._lbl_aviso)

        self._lbl_vacio = QLabel("No entró plata desde el último retiro.")
        self._lbl_vacio.setAlignment(Qt.AlignCenter)
        self._lbl_vacio.setStyleSheet(
            f"color:{MUTED}; font-size:15px; border:none; padding:34px;"
        )
        self._lbl_vacio.setVisible(False)
        lay.addWidget(self._lbl_vacio)

        self._tabla = QTableWidget(0, 6)
        self._tabla.setHorizontalHeaderLabels(
            ["Cuándo", "Boleta", "Cliente", "Cómo pagó", "Monto", ""]
        )
        self._aplicar_estilo_tabla(self._tabla, alto_fila=46)
        h = self._tabla.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        for i in (0, 1, 3, 4):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        # La columna de botones va con ancho fijo: si se calcula por contenido
        # queda angosta y corta el texto de los botones.
        h.setSectionResizeMode(5, QHeaderView.Fixed)
        # Tiene que entrar "Boleta" + "Remito" sin cortarse. Ojo: el padding
        # de la celda (24px) se descuenta del ancho util.
        self._tabla.setColumnWidth(5, 285)
        self._tabla.setMinimumHeight(300)
        lay.addWidget(self._tabla)
        self._root.addWidget(card)

    # ── Gastos ──────────────────────────────────────────────────────────────
    def _build_gastos_section(self):
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 20)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        hdr = QLabel("Gastos del turno")
        hdr.setStyleSheet(
            f"color:{TEXT}; font-size:18px; font-weight:800; border:none;"
        )
        top.addWidget(hdr)
        ayuda = QLabel("(se descuentan del total)")
        ayuda.setStyleSheet(f"color:{MUTED}; font-size:13px; border:none;")
        top.addWidget(ayuda)
        top.addStretch()
        self._gasto_concepto = QLineEdit()
        self._gasto_concepto.setPlaceholderText("En qué se gastó")
        self._gasto_concepto.setFixedWidth(240)
        self._gasto_concepto.setStyleSheet(self._input_qss())
        self._gasto_monto = QLineEdit()
        self._gasto_monto.setPlaceholderText("Monto")
        self._gasto_monto.setFixedWidth(130)
        self._gasto_monto.setStyleSheet(self._input_qss())
        self._gasto_monto.textEdited.connect(
            lambda _t: self._formatear_campo(self._gasto_monto)
        )
        add = QPushButton("+  Agregar")
        add.setCursor(Qt.PointingHandCursor)
        add.setStyleSheet(self._btn(CARD, GREEN))
        add.clicked.connect(self._on_add_gasto)
        top.addWidget(self._gasto_concepto)
        top.addWidget(self._gasto_monto)
        top.addWidget(add)
        lay.addLayout(top)

        self._gastos_box = QVBoxLayout()
        self._gastos_box.setSpacing(6)
        lay.addLayout(self._gastos_box)
        self._root.addWidget(card)

    # ── Historial ───────────────────────────────────────────────────────────
    def _build_historial_section(self):
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 20)
        lay.setSpacing(10)
        hdr = QLabel("Retiros anteriores")
        hdr.setStyleSheet(
            f"color:{TEXT}; font-size:18px; font-weight:800; border:none;"
        )
        lay.addWidget(hdr)

        self._tabla_hist = QTableWidget(0, 5)
        self._tabla_hist.setHorizontalHeaderLabels(
            ["Cuándo", "Quién retiró", "Local", "Se llevó", "Dejó en caja"]
        )
        self._aplicar_estilo_tabla(self._tabla_hist, alto_fila=42)
        hh = self._tabla_hist.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in (0, 2, 3, 4):
            hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._tabla_hist.setMinimumHeight(200)
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
        # En modo "Todos" hay que sumar CADA local con su propio ultimo retiro:
        # usar un solo corte global daba un total mucho menor que el real.
        locales = LOCALES if _es_todos(self.local) else [self.local]
        last_dt = vm.get_last_withdrawal_datetime(self.local)
        efectivo = 0.0
        entradas = []
        for loc in locales:
            corte = vm.get_last_withdrawal_datetime(loc)
            try:
                efectivo += vm.get_cash_earned_since(loc, corte)
            except Exception:
                pass
            try:
                for e in vm.get_cash_entries_since(loc, corte):
                    if _es_todos(self.local):
                        e = dict(e, cliente=f"{e.get('cliente') or '-'}  ·  {loc}")
                    entradas.append(e)
            except Exception:
                pass

        domicilio_total = 0.0
        viejos_cant, viejos_monto = 0, 0.0
        if _es_local_domicilio(self.local) or _es_todos(self.local):
            last_dt = vm.get_last_withdrawal_datetime(_LOCAL_DOMICILIO)
            try:
                for c in vm.get_domicilio_pagos_pending():
                    monto = float(c.get("monto_productos") or c.get("monto") or 0)
                    creado = c.get("created_at")
                    # El registro se crea al VENDER, pero esa plata se cobra
                    # recien al ENTREGAR: si todavia no se entrego, no esta.
                    if not int(c.get("entregada") or 0):
                        continue
                    # Solo lo cobrado DESPUES del ultimo retiro.
                    if last_dt and str(creado or "") <= str(last_dt):
                        viejos_cant += 1
                        viejos_monto += monto
                        continue
                    domicilio_total += monto
                    entradas.append(
                        {
                            "venta_id": c.get("venta_id"),
                            "_pago_id": c.get("id"),
                            "numero_venta": c.get("numero_venta"),
                            "fecha": creado or c.get("fecha"),
                            "cliente": (c.get("cliente_nombre") or "").strip(),
                            "forma_pago": "Cobro en domicilio",
                            "monto": monto,
                            # Un cobro en domicilio siempre viene de un envio
                            "tiene_remito": True,
                            "origen": "domicilio",
                        }
                    )
            except Exception:
                pass

        gastos = self._gastos_pendientes_total()
        efectivo_neto = max(0.0, efectivo - gastos)
        total = efectivo_neto + domicilio_total
        self._entradas = entradas
        self._total_disponible = total

        # ── Hero ──
        self._lbl_total.setText(_fmt(total))
        if _es_todos(self.local):
            self._lbl_desde.setText(
                "Los 5 locales sumados, cada uno desde su último retiro"
            )
        elif last_dt:
            self._lbl_desde.setText(f"Desde el último retiro ({_fmt_fecha(last_dt)})")
        else:
            self._lbl_desde.setText(
                "Desde el principio (todavía no se hizo ningún retiro)"
            )
        partes = [f"Efectivo en caja: <b>{_fmt(efectivo)}</b>"]
        if _es_local_domicilio(self.local) or _es_todos(self.local):
            partes.append(f"Cobros en domicilio: <b>{_fmt(domicilio_total)}</b>")
        if gastos > 0:
            partes.append(f"<span style='color:{RED}'>Gastos: −{_fmt(gastos)}</span>")
        self._lbl_desglose.setText("　·　".join(partes))
        if _es_todos(self.local):
            # No se puede retirar de los 5 locales a la vez: hay que elegir uno.
            self._btn_retirar.setEnabled(False)
            self._btn_retirar.setText("Elegí un local")
        else:
            self._btn_retirar.setEnabled(total > 0)
            self._btn_retirar.setText("Retirar dinero")

        # ── Aviso de cobros viejos sin retirar (para que no desaparezcan) ──
        if viejos_cant:
            self._lbl_aviso.setText(
                f"⚠  Hay {viejos_cant} cobro(s) en domicilio anteriores al último "
                f"retiro que siguen sin retirar por {_fmt(viejos_monto)}."
            )
            self._lbl_aviso.setVisible(True)
        else:
            self._lbl_aviso.setVisible(False)

        # ── Tabla ──
        self._tabla.setRowCount(0)
        for e in entradas:
            self._add_entrada_row(e)
        hay = len(entradas) > 0
        self._tabla.setVisible(hay)
        self._lbl_vacio.setVisible(not hay)
        self._lbl_conteo.setText(
            f"{len(entradas)} comprobante(s)  ·  {_fmt(total)}" if hay else ""
        )

    def _add_entrada_row(self, e: dict):
        r = self._tabla.rowCount()
        self._tabla.insertRow(r)
        es_dom = e.get("origen") == "domicilio"
        venta_id = e.get("venta_id")
        # El numero de venta es un codigo largo e ilegible: mostramos el numero
        # corto y dejamos el completo en el globito, por si hay que buscarlo.
        corto = f"#{venta_id}" if venta_id else "-"
        vals = [
            _fmt_fecha(e.get("fecha")),
            corto,
            e.get("cliente") or "-",
            e.get("forma_pago") or "",
            _fmt(e.get("monto")),
        ]
        for i, val in enumerate(vals):
            it = QTableWidgetItem(str(val))
            if i == 1:
                completo = str(e.get("numero_venta") or "").strip()
                if completo:
                    it.setToolTip(f"Boleta Nº {completo}")
            if i == 4:
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            self._tabla.setItem(r, i, it)

        cell = QWidget()
        cl = QHBoxLayout(cell)
        cl.setContentsMargins(4, 5, 8, 5)
        cl.setSpacing(8)
        cl.addStretch()
        if venta_id:
            b_bol = QPushButton("Boleta")
            b_bol.setCursor(Qt.PointingHandCursor)
            b_bol.setMinimumHeight(30)
            b_bol.setMinimumWidth(b_bol.sizeHint().width())
            b_bol.setStyleSheet(self._btn_tabla())
            b_bol.clicked.connect(lambda _=False, v=venta_id: self._ver_boleta(v))
            cl.addWidget(b_bol)
            # El remito es del envio: si la venta no lleva envio, no hay remito.
            if e.get("tiene_remito"):
                b_rem = QPushButton("Remito")
                b_rem.setCursor(Qt.PointingHandCursor)
                b_rem.setMinimumHeight(30)
                b_rem.setMinimumWidth(b_rem.sizeHint().width())
                b_rem.setStyleSheet(self._btn_tabla())
                b_rem.clicked.connect(lambda _=False, v=venta_id: self._ver_remito(v))
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
            lbl = QLabel("No se cargó ningún gasto hoy.")
            lbl.setStyleSheet(f"color:{MUTED}; font-size:14px; border:none;")
            self._gastos_box.addWidget(lbl)
            return
        for g in gastos:
            row = QFrame()
            row.setStyleSheet(
                f"QFrame {{ background:{BG}; border:1px solid {BORDER};"
                f" border-radius:10px; }}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 8, 10, 8)
            txt = QLabel(str(g.get("concepto") or ""))
            txt.setStyleSheet(f"color:{TEXT}; font-size:14px; border:none;")
            rl.addWidget(txt)
            rl.addStretch()
            monto = QLabel(f"−{_fmt(g.get('monto'))}")
            monto.setStyleSheet(
                f"color:{RED}; font-size:15px; font-weight:800; border:none;"
            )
            rl.addWidget(monto)
            btn = QPushButton("Borrar")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._btn(CARD, RED, chico=True))
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
                _fmt_fecha(w.get("fecha")),
                w.get("usuario") or "-",
                w.get("local") or "",
                _fmt(w.get("retirado")),
                _fmt(w.get("dejado")),
            ]
            for i, val in enumerate(vals):
                it = QTableWidgetItem(str(val))
                if i in (3, 4):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self._tabla_hist.setItem(r, i, it)

    # ── Acciones ────────────────────────────────────────────────────────────
    def _formatear_campo(self, campo: QLineEdit):
        """Mientras escribe, va poniendo el punto cada tres numeros."""
        valor = _a_numero(campo.text())
        campo.blockSignals(True)
        campo.setText(_fmt_num(valor) if valor else "")
        campo.blockSignals(False)

    def _on_add_gasto(self):
        concepto = self._gasto_concepto.text().strip()
        monto = _a_numero(self._gasto_monto.text())
        if not concepto or monto <= 0:
            QMessageBox.warning(self, "Gasto", "Escribí en qué se gastó y cuánto fue.")
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
        dlg = QDialog(self)
        dlg.setWindowTitle("Contraseña")
        dlg.setStyleSheet(
            f"QDialog {{ background:{CARD}; }} QLabel {{ color:{TEXT}; }}"
        )
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(12)
        t = QLabel("Contraseña para retirar")
        t.setStyleSheet(f"color:{GOLD}; font-size:18px; font-weight:800;")
        lay.addWidget(t)
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.Password)
        edit.setMinimumWidth(280)
        edit.setStyleSheet(self._input_qss())
        lay.addWidget(edit)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Continuar")
        bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.button(QDialogButtonBox.Ok).setStyleSheet(self._btn(GOLD, "#171717"))
        bb.button(QDialogButtonBox.Cancel).setStyleSheet(self._btn(CARD, TEXT))
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.Accepted:
            return False
        if (edit.text() or "").strip() != (pwd_real or "").strip():
            QMessageBox.warning(self, "Retirar dinero", "Contraseña incorrecta.")
            return False
        return True

    def _on_retirar(self):
        if self._total_disponible <= 0:
            QMessageBox.information(
                self, "Retirar dinero", "No hay plata para retirar."
            )
            return
        if not self._pedir_password():
            return
        datos = self._dialogo_retiro()
        if datos is None:
            return
        quien, retiro, dejado = datos

        dom_ids = [
            e.get("_pago_id")
            for e in self._entradas
            if e.get("origen") == "domicilio" and e.get("_pago_id")
        ]
        if dom_ids:
            try:
                vm.retirar_domicilio_pagos(dom_ids, quien)
            except Exception:
                pass

        ok, msg = vm.add_cash_withdrawal(self.local, retiro, quien, dejado=dejado)
        if ok:
            QMessageBox.information(
                self,
                "Listo",
                f"Retiro registrado.\n\nSe lo llevó: {quien}\n"
                f"Se llevó: {_fmt(retiro)}\n"
                f"Quedó en caja: {_fmt(dejado)}",
            )
            self._refresh()
        else:
            QMessageBox.warning(self, "Retirar dinero", f"No se pudo registrar:\n{msg}")

    def _dialogo_retiro(self):
        total = float(self._total_disponible or 0)
        dlg = QDialog(self)
        dlg.setWindowTitle("Retirar dinero")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(
            f"QDialog {{ background:{CARD}; }} QLabel {{ color:{TEXT}; }}"
        )
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(26, 24, 26, 22)
        lay.setSpacing(8)

        cap = QLabel("HAY EN CAJA")
        cap.setStyleSheet(
            f"color:{MUTED}; font-size:12px; font-weight:800; letter-spacing:1px;"
        )
        lay.addWidget(cap)
        disp = QLabel(_fmt(total))
        disp.setStyleSheet(f"color:{GOLD}; font-size:34px; font-weight:800;")
        lay.addWidget(disp)
        lay.addSpacing(12)

        l0 = QLabel("¿Quién se lleva la plata?")
        l0.setStyleSheet(f"color:{TEXT}; font-size:15px; font-weight:700;")
        lay.addWidget(l0)
        cb_quien = QComboBox()
        cb_quien.setEditable(True)
        cb_quien.setStyleSheet(self._combo_qss())
        cb_quien.addItem("")
        for nombre in self._nombres_conocidos():
            cb_quien.addItem(nombre)
        cb_quien.setCurrentText("")
        cb_quien.lineEdit().setPlaceholderText("Nombre de quien retira")
        lay.addWidget(cb_quien)
        lay.addSpacing(6)

        l1 = QLabel("¿Cuánto te llevás?")
        l1.setStyleSheet(f"color:{TEXT}; font-size:15px; font-weight:700;")
        lay.addWidget(l1)
        e_ret = QLineEdit(_fmt_num(total))
        e_ret.setStyleSheet(self._input_qss(grande=True))
        lay.addWidget(e_ret)

        l2 = QLabel("¿Cuánto dejás en la caja?")
        l2.setStyleSheet(f"color:{TEXT}; font-size:15px; font-weight:700;")
        lay.addWidget(l2)
        e_dej = QLineEdit("0")
        e_dej.setStyleSheet(self._input_qss(grande=True))
        lay.addWidget(e_dej)

        e_ret.textEdited.connect(lambda _t: self._formatear_campo(e_ret))
        e_dej.textEdited.connect(lambda _t: self._formatear_campo(e_dej))

        lay.addSpacing(14)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Confirmar retiro")
        bb.button(QDialogButtonBox.Cancel).setText("Cancelar")
        bb.button(QDialogButtonBox.Ok).setStyleSheet(self._btn(GOLD, "#171717"))
        bb.button(QDialogButtonBox.Cancel).setStyleSheet(self._btn(CARD, TEXT))
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)

        if dlg.exec() != QDialog.Accepted:
            return None
        quien = (cb_quien.currentText() or "").strip()
        retiro = _a_numero(e_ret.text())
        dejado = _a_numero(e_dej.text())
        if not quien:
            QMessageBox.warning(
                self, "Retirar dinero", "Poné el nombre de quien se lleva la plata."
            )
            return None
        if retiro <= 0:
            QMessageBox.warning(self, "Retirar dinero", "Poné cuánto te llevás.")
            return None
        if retiro > total + 1:
            QMessageBox.warning(
                self,
                "Retirar dinero",
                f"No podés llevarte más de lo que hay en caja ({_fmt(total)}).",
            )
            return None
        return quien, retiro, dejado

    def _nombres_conocidos(self) -> list:
        """Nombres ya usados antes, para no tener que escribirlos siempre."""
        try:
            vistos = []
            for w in vm.get_cash_withdrawals(self.local, limit=50):
                n = (w.get("usuario") or "").strip()
                if n and n.lower() != (self.local or "").strip().lower():
                    if n not in vistos:
                        vistos.append(n)
            return vistos[:12]
        except Exception:
            return []

    def _ver_boleta(self, venta_id):
        if not venta_id:
            QMessageBox.information(
                self, "Boleta", "Esta fila no tiene boleta asociada."
            )
            return
        try:
            ok, res = vm.generar_pdf_boleta(int(venta_id))
            if ok:
                self._open_pdf(res)
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
                self._open_pdf(res)
            else:
                QMessageBox.warning(self, "Remito", res)
        except Exception as e:
            QMessageBox.warning(self, "Remito", f"No se pudo abrir el remito:\n{e}")

    def _open_pdf(self, filepath: str):
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
    def _card_qss() -> str:
        return (
            f"QFrame {{ background:{CARD}; border:1px solid {BORDER};"
            f" border-radius:16px; }}"
        )

    @staticmethod
    def _combo_qss() -> str:
        return (
            f"QComboBox {{ background:{BG}; color:{TEXT}; border:1px solid {BORDER};"
            f" border-radius:10px; padding:10px 12px; font-size:16px;"
            f" font-weight:700; }}"
            f"QComboBox:focus {{ border:1px solid {GOLD}; }}"
            f"QComboBox QAbstractItemView {{ background:{CARD}; color:{TEXT};"
            f" selection-background-color:{GOLD}; selection-color:#171717; }}"
        )

    @staticmethod
    def _btn_tabla() -> str:
        """Botones de adentro de la tabla: tienen que LEERSE, no camuflarse
        con el fondo de la fila."""
        return (
            f"QPushButton {{ background:{CARD}; color:{GOLD};"
            f" border:1px solid {GOLD}; border-radius:8px;"
            f" padding:4px 16px; font-size:13px; font-weight:800; }}"
            f"QPushButton:hover {{ background:{GOLD}; color:#171717; }}"
        )

    @staticmethod
    def _btn(bg: str, fg: str, chico: bool = False) -> str:
        pad = "6px 14px" if chico else "10px 20px"
        fs = "13px" if chico else "15px"
        return (
            f"QPushButton {{ background:{bg}; color:{fg}; border:1px solid {BORDER};"
            f" border-radius:10px; padding:{pad}; font-size:{fs}; font-weight:700; }}"
            f"QPushButton:hover {{ border:1px solid {GOLD}; color:{GOLD}; }}"
        )

    @staticmethod
    def _input_qss(grande: bool = False) -> str:
        fs = "20px" if grande else "14px"
        pad = "12px 14px" if grande else "8px 12px"
        peso = "800" if grande else "500"
        return (
            f"QLineEdit {{ background:{BG}; color:{TEXT}; border:1px solid {BORDER};"
            f" border-radius:10px; padding:{pad}; font-size:{fs};"
            f" font-weight:{peso}; }}"
            f"QLineEdit:focus {{ border:1px solid {GOLD}; }}"
        )

    def _aplicar_estilo_tabla(self, tabla: QTableWidget, alto_fila: int = 44):
        tabla.setStyleSheet(
            f"QTableWidget {{ background:{BG}; color:{TEXT}; border:1px solid {BORDER};"
            f" border-radius:12px; gridline-color:transparent;"
            f" alternate-background-color:{ROW_ALT}; font-size:14px; }}"
            f"QHeaderView::section {{ background:{CARD}; color:{MUTED};"
            f" border:none; border-bottom:1px solid {BORDER}; padding:10px 12px;"
            f" font-weight:800; font-size:13px; }}"
            f"QTableWidget::item {{ padding:8px 12px; border:none; }}"
        )
        tabla.setAlternatingRowColors(True)
        tabla.verticalHeader().setVisible(False)
        tabla.verticalHeader().setDefaultSectionSize(alto_fila)
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        tabla.setSelectionMode(QTableWidget.NoSelection)
        tabla.setShowGrid(False)
