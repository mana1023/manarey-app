"""Vista de proveedores y compras — solo admin."""
from __future__ import annotations

import logging
from typing import Callable, List, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
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
RED = "#f87171"


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


def _btn(text: str, color: str, tc: str = "#000") -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(34)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:{color};color:{tc};border:none;"
        f"border-radius:9px;padding:4px 14px;font-weight:700;}}"
        f"QPushButton:hover{{opacity:0.85;}}"
    )
    return b


INPUT_STYLE = (
    f"QLineEdit{{background:{CARD};color:{TEXT};border:1px solid {BORDER};"
    f"border-radius:8px;padding:4px 10px;}}"
    f"QTextEdit{{background:{CARD};color:{TEXT};border:1px solid {BORDER};"
    f"border-radius:8px;padding:4px 10px;}}"
    f"QSpinBox{{background:{CARD};color:{TEXT};border:1px solid {BORDER};"
    f"border-radius:8px;padding:2px 8px;}}"
    f"QComboBox{{background:{CARD};color:{TEXT};border:1px solid {BORDER};"
    f"border-radius:8px;padding:2px 8px;}}"
)


class ProveedoresWindow(QMainWindow):
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
        self._proveedores: list = []
        self.setWindowTitle("Proveedores y Compras")
        self.setMinimumSize(960, 640)
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

        tabs = QTabWidget()
        tabs.setStyleSheet(
            f"QTabWidget::pane{{background:{CARD};border:1px solid {BORDER};border-radius:10px;}}"
            f"QTabBar::tab{{background:{BG};color:{MUTED};padding:8px 20px;"
            f"border-top-left-radius:8px;border-top-right-radius:8px;}}"
            f"QTabBar::tab:selected{{background:{CARD};color:{GOLD};font-weight:700;}}"
        )

        # Tab 1: Proveedores
        tab_prov = QWidget()
        self._build_proveedores_tab(tab_prov)
        tabs.addTab(tab_prov, "🏭  Proveedores")

        # Tab 2: Nueva compra
        tab_compra = QWidget()
        self._build_nueva_compra_tab(tab_compra)
        tabs.addTab(tab_compra, "🛒  Nueva compra")

        # Tab 3: Historial de compras
        tab_hist = QWidget()
        self._build_historial_tab(tab_hist)
        tabs.addTab(tab_hist, "📋  Historial")

        self._root.addWidget(tabs)
        QTimer.singleShot(100, self._load_proveedores)

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
        title = QLabel("🏭  Proveedores y Compras")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet(f"color:{GOLD};")
        row.addWidget(title)
        row.addStretch()
        self._root.addLayout(row)

    # ── Tab Proveedores ───────────────────────────────────────────────────────

    def _build_proveedores_tab(self, parent: QWidget):
        lay = QVBoxLayout(parent)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_new = _btn("+ Nuevo proveedor", GREEN, "#000")
        btn_new.clicked.connect(self._on_new_proveedor)
        btn_row.addWidget(btn_new)
        lay.addLayout(btn_row)

        self._prov_table = QTableWidget(0, 6)
        self._prov_table.setHorizontalHeaderLabels(
            ["Nombre", "Teléfono", "Email", "Dirección", "Activo", "Acciones"]
        )
        self._prov_table.verticalHeader().setVisible(False)
        self._prov_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._prov_table.setStyleSheet(_table_style())
        hdr = self._prov_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 5):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        lay.addWidget(self._prov_table)

    def _load_proveedores(self):
        try:
            from models.proveedores_model import list_proveedores

            self._proveedores = list_proveedores(solo_activos=False)
        except Exception:
            self._proveedores = []

        self._prov_table.setRowCount(0)
        for p in self._proveedores:
            r = self._prov_table.rowCount()
            self._prov_table.insertRow(r)
            self._prov_table.setItem(r, 0, QTableWidgetItem(str(p.get("nombre", ""))))
            self._prov_table.setItem(
                r, 1, QTableWidgetItem(str(p.get("telefono", "") or ""))
            )
            self._prov_table.setItem(
                r, 2, QTableWidgetItem(str(p.get("email", "") or ""))
            )
            self._prov_table.setItem(
                r, 3, QTableWidgetItem(str(p.get("direccion", "") or ""))
            )
            activo = bool(p.get("activo", True))
            act_item = QTableWidgetItem("✔ Activo" if activo else "✗ Inactivo")
            act_item.setForeground(QColor(GREEN if activo else RED))
            self._prov_table.setItem(r, 4, act_item)

            pid = p.get("id")
            btn_w = QWidget()
            blay = QHBoxLayout(btn_w)
            blay.setContentsMargins(2, 1, 2, 1)
            blay.setSpacing(4)
            btn_edit = QPushButton("✏")
            btn_edit.setFixedSize(28, 26)
            btn_edit.setStyleSheet(
                f"QPushButton{{background:{CARD};color:{GOLD};border:1px solid {BORDER};border-radius:6px;}}"
            )
            btn_edit.clicked.connect(lambda _, p=p: self._on_edit_proveedor(p))
            btn_toggle = QPushButton("🚫" if activo else "✔")
            btn_toggle.setFixedSize(28, 26)
            btn_toggle.setStyleSheet(
                f"QPushButton{{background:{CARD};color:{MUTED};border:1px solid {BORDER};border-radius:6px;}}"
            )
            btn_toggle.clicked.connect(
                lambda _, pid=pid: self._on_toggle_proveedor(pid)
            )
            blay.addWidget(btn_edit)
            blay.addWidget(btn_toggle)
            self._prov_table.setCellWidget(r, 5, btn_w)

        # Actualizar combo de nueva compra
        try:
            self._prov_combo.clear()
            for p in [p for p in self._proveedores if p.get("activo", True)]:
                self._prov_combo.addItem(p["nombre"], p["id"])
        except Exception:
            pass

    def _on_new_proveedor(self):
        self._open_proveedor_form()

    def _on_edit_proveedor(self, p: dict):
        self._open_proveedor_form(p)

    def _on_toggle_proveedor(self, pid: int):
        from models.proveedores_model import toggle_proveedor_activo

        toggle_proveedor_activo(pid)
        self._load_proveedores()

    def _open_proveedor_form(self, p: dict = None):
        dlg = QDialog(self)
        dlg.setWindowTitle("Proveedor")
        dlg.setMinimumWidth(380)
        dlg.setStyleSheet(
            f"QDialog{{background:{BG};}}" + INPUT_STYLE + f"QLabel{{color:{TEXT};}}"
        )
        lay = QVBoxLayout(dlg)
        lay.setSpacing(8)

        def field(label, val=""):
            lay.addWidget(QLabel(label))
            inp = QLineEdit(val)
            inp.setFixedHeight(34)
            lay.addWidget(inp)
            return inp

        f_nombre = field("Nombre *", p.get("nombre", "") if p else "")
        f_tel = field("Teléfono", p.get("telefono", "") or "" if p else "")
        f_email = field("Email", p.get("email", "") or "" if p else "")
        f_dir = field("Dirección", p.get("direccion", "") or "" if p else "")
        lay.addWidget(QLabel("Notas"))
        f_notas = QTextEdit(p.get("notas", "") or "" if p else "")
        f_notas.setMaximumHeight(60)
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
            if not nombre:
                QMessageBox.warning(self, "Proveedor", "El nombre es obligatorio.")
                return
            from models.proveedores_model import save_proveedor

            save_proveedor(
                nombre,
                f_tel.text().strip(),
                f_email.text().strip(),
                f_dir.text().strip(),
                f_notas.toPlainText().strip(),
                proveedor_id=p.get("id") if p else None,
            )
            self._load_proveedores()

    # ── Tab Nueva Compra ──────────────────────────────────────────────────────

    def _build_nueva_compra_tab(self, parent: QWidget):
        lay = QVBoxLayout(parent)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        lay.setStyleSheet = lambda _: None

        parent.setStyleSheet(INPUT_STYLE + f"QLabel{{color:{TEXT};}}")

        prov_row = QHBoxLayout()
        prov_row.addWidget(QLabel("Proveedor:"))
        self._prov_combo = QComboBox()
        self._prov_combo.setFixedHeight(34)
        prov_row.addWidget(self._prov_combo)
        prov_row.addStretch()
        lay.addLayout(prov_row)

        # Items de la compra
        items_lbl = QLabel("Productos a comprar:")
        items_lbl.setStyleSheet(f"color:{MUTED};font-weight:700;")
        lay.addWidget(items_lbl)

        add_row = QHBoxLayout()
        self._compra_nombre = QLineEdit()
        self._compra_nombre.setPlaceholderText("Nombre del producto")
        self._compra_cantidad = QSpinBox()
        self._compra_cantidad.setMinimum(1)
        self._compra_cantidad.setMaximum(9999)
        self._compra_cantidad.setFixedWidth(80)
        self._compra_precio = QLineEdit()
        self._compra_precio.setPlaceholderText("Precio unit.")
        self._compra_precio.setFixedWidth(110)
        btn_add_item = _btn("+ Agregar", GOLD)
        btn_add_item.clicked.connect(self._on_add_compra_item)
        for w in (
            self._compra_nombre,
            self._compra_cantidad,
            self._compra_precio,
            btn_add_item,
        ):
            add_row.addWidget(w)
        lay.addLayout(add_row)

        self._compra_items_table = QTableWidget(0, 4)
        self._compra_items_table.setHorizontalHeaderLabels(
            ["Producto", "Cantidad", "Precio unit.", ""]
        )
        self._compra_items_table.verticalHeader().setVisible(False)
        self._compra_items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._compra_items_table.setStyleSheet(_table_style())
        hdr = self._compra_items_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in (1, 2, 3):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._compra_items_table.setMaximumHeight(200)
        lay.addWidget(self._compra_items_table)

        self._compra_notas = QLineEdit()
        self._compra_notas.setPlaceholderText("Notas de la compra (opcional)")
        self._compra_notas.setFixedHeight(34)
        lay.addWidget(self._compra_notas)

        self._total_compra_lbl = QLabel("Total: $0")
        self._total_compra_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._total_compra_lbl.setStyleSheet(f"color:{GOLD};")
        lay.addWidget(self._total_compra_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_guardar = _btn("💾  Registrar compra", GREEN, "#000")
        btn_guardar.clicked.connect(self._on_guardar_compra)
        btn_row.addWidget(btn_guardar)
        lay.addLayout(btn_row)

        lay.addStretch()
        self._compra_items: list = []

    def _on_add_compra_item(self):
        nombre = self._compra_nombre.text().strip()
        if not nombre:
            return
        try:
            precio = float(
                self._compra_precio.text().replace("$", "").replace(",", "") or 0
            )
        except ValueError:
            precio = 0.0
        cantidad = self._compra_cantidad.value()
        item = {
            "producto_nombre": nombre,
            "cantidad": cantidad,
            "precio_unitario": precio,
        }
        self._compra_items.append(item)
        self._refresh_compra_table()
        self._compra_nombre.clear()
        self._compra_precio.clear()
        self._compra_cantidad.setValue(1)

    def _refresh_compra_table(self):
        self._compra_items_table.setRowCount(0)
        total = 0.0
        for item in self._compra_items:
            r = self._compra_items_table.rowCount()
            self._compra_items_table.insertRow(r)
            self._compra_items_table.setItem(
                r, 0, QTableWidgetItem(item["producto_nombre"])
            )
            self._compra_items_table.setItem(
                r, 1, QTableWidgetItem(str(item["cantidad"]))
            )
            self._compra_items_table.setItem(
                r, 2, QTableWidgetItem(_fmt(item["precio_unitario"]))
            )
            idx = r
            btn_del = QPushButton("✕")
            btn_del.setFixedSize(26, 22)
            btn_del.setStyleSheet(
                f"QPushButton{{background:#3a1a1a;color:{RED};border:none;border-radius:5px;}}"
            )
            btn_del.clicked.connect(lambda _, i=idx: self._on_del_compra_item(i))
            self._compra_items_table.setCellWidget(r, 3, btn_del)
            total += item["cantidad"] * item["precio_unitario"]
        self._total_compra_lbl.setText(f"Total: {_fmt(total)}")

    def _on_del_compra_item(self, idx: int):
        if 0 <= idx < len(self._compra_items):
            self._compra_items.pop(idx)
            self._refresh_compra_table()

    def _on_guardar_compra(self):
        prov_id = self._prov_combo.currentData()
        if not prov_id:
            QMessageBox.warning(self, "Compra", "Seleccioná un proveedor.")
            return
        if not self._compra_items:
            QMessageBox.warning(self, "Compra", "Agregá al menos un producto.")
            return
        from models.proveedores_model import crear_compra

        compra_id = crear_compra(
            prov_id,
            self.local,
            self.username,
            self._compra_items,
            self._compra_notas.text().strip(),
        )
        if compra_id:
            confirm = QMessageBox.question(
                self,
                "Compra registrada",
                f"Compra #{compra_id} registrada.\n¿Confirmar recepción ahora (incrementa stock)?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm == QMessageBox.Yes:
                from models.proveedores_model import confirmar_recepcion

                confirmar_recepcion(compra_id, self.username)
            self._compra_items = []
            self._refresh_compra_table()
            self._compra_notas.clear()
            self._load_historial()
        else:
            QMessageBox.critical(self, "Error", "No se pudo registrar la compra.")

    # ── Tab Historial ─────────────────────────────────────────────────────────

    def _build_historial_tab(self, parent: QWidget):
        lay = QVBoxLayout(parent)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        btn_refresh = QPushButton("↺ Actualizar")
        btn_refresh.setFixedHeight(30)
        btn_refresh.setFixedWidth(120)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet(
            f"QPushButton{{background:{CARD};color:{GOLD};border:1px solid {BORDER};"
            f"border-radius:8px;padding:3px 10px;font-weight:700;}}"
        )
        btn_refresh.clicked.connect(self._load_historial)
        lay.addWidget(btn_refresh)

        self._hist_compras_table = QTableWidget(0, 7)
        self._hist_compras_table.setHorizontalHeaderLabels(
            ["#", "Proveedor", "Local", "Usuario", "Fecha", "Total", "Estado"]
        )
        self._hist_compras_table.verticalHeader().setVisible(False)
        self._hist_compras_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._hist_compras_table.setStyleSheet(_table_style())
        hdr = self._hist_compras_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in (2, 3, 4, 5, 6):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        lay.addWidget(self._hist_compras_table)

        # Botón confirmar recepción
        btn_confirmar = _btn("✔ Confirmar recepción seleccionada", GOLD)
        btn_confirmar.clicked.connect(self._on_confirmar_selected)
        lay.addWidget(btn_confirmar)

        QTimer.singleShot(300, self._load_historial)

    def _load_historial(self):
        try:
            from models.proveedores_model import list_compras

            compras = list_compras(self.local)
        except Exception:
            compras = []

        self._hist_compras_table.setRowCount(0)
        for c in compras:
            r = self._hist_compras_table.rowCount()
            self._hist_compras_table.insertRow(r)
            self._hist_compras_table.setItem(
                r, 0, QTableWidgetItem(str(c.get("id", "")))
            )
            self._hist_compras_table.setItem(
                r, 1, QTableWidgetItem(str(c.get("proveedor", "—")))
            )
            self._hist_compras_table.setItem(
                r, 2, QTableWidgetItem(str(c.get("local", "")))
            )
            self._hist_compras_table.setItem(
                r, 3, QTableWidgetItem(str(c.get("usuario", "")))
            )
            self._hist_compras_table.setItem(
                r, 4, QTableWidgetItem(str(c.get("fecha", ""))[:10])
            )
            t_item = QTableWidgetItem(_fmt(float(c.get("total", 0))))
            t_item.setForeground(QColor(GOLD))
            self._hist_compras_table.setItem(r, 5, t_item)
            estado = str(c.get("estado", ""))
            e_item = QTableWidgetItem(estado)
            e_item.setForeground(QColor(GREEN if estado == "recibida" else MUTED))
            self._hist_compras_table.setItem(r, 6, e_item)

    def _on_confirmar_selected(self):
        r = self._hist_compras_table.currentRow()
        if r < 0:
            QMessageBox.information(self, "Confirmar", "Seleccioná una compra.")
            return
        id_item = self._hist_compras_table.item(r, 0)
        if not id_item:
            return
        estado_item = self._hist_compras_table.item(r, 6)
        if estado_item and estado_item.text() == "recibida":
            QMessageBox.information(self, "Confirmar", "Esta compra ya fue recibida.")
            return
        from models.proveedores_model import confirmar_recepcion

        if confirmar_recepcion(int(id_item.text()), self.username):
            QMessageBox.information(
                self, "OK", "Recepción confirmada. Stock actualizado."
            )
            self._load_historial()
        else:
            QMessageBox.critical(self, "Error", "No se pudo confirmar la recepción.")
