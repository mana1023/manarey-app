# views/envios_view.py
import os
import platform
import subprocess
from datetime import datetime, timedelta

from PyQt5.QtCore import QAbstractTableModel, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont

try:
    import app_theme as _theme

    def _T(k, fallback):
        return _theme.get_palette_value(k) or fallback

except ImportError:

    def _T(k, fallback):
        return fallback


# ── Constantes de color dinámicas (se recalculan al arrancar) ────────────────
def _colors():
    return {
        "DORADO": _T("GOLD", "#C9A040"),
        "DARK": _T("BG", "#1f1f22"),
        "CARD": _T("CARD", "#232327"),
        "BORDER": _T("BORDER", "#34343a"),
        "TEXT": _T("TEXT", "#ECECF1"),
        "MUTED": _T("TEXT_MUTED", "#c9c9cf"),
        "BG": _T("BG", "#0f0f14"),
        "BG_ALT": _T("BG_ALT", "#1a1a22"),
        "CARD_BG": _T("CARD", "#1a1a22"),
        "CARD_BORDER": _T("BORDER", "rgba(201,160,64,0.18)"),
        "ACCENT": _T("GOLD", "#C9A040"),
        "TEXT_MUTED": _T("TEXT_MUTED", "#a0a0a8"),
        "PRIMARY": _T("GOLD", "#C9A040"),
        "GREEN": "#5E8B6F",
    }


_c = _colors()
DORADO = _c["DORADO"]
DARK = _c["DARK"]
CARD = _c["CARD"]
BORDER = _c["BORDER"]
TEXT = _c["TEXT"]
MUTED = _c["MUTED"]
BG = _c["BG"]
BG_ALT = _c["BG_ALT"]
CARD_BG = _c["CARD_BG"]
CARD_BORDER = _c["CARD_BORDER"]
ACCENT = _c["ACCENT"]
TEXT_MUTED = _c["TEXT_MUTED"]
PRIMARY = _c["PRIMARY"]
# ─────────────────────────────────────────────────────────────────────────────


from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models import ventas_historial_model as vhm
from models import ventas_model as vm
from models.firestore_db import get_all_locals

PRIMARY = "#C9A040"
GREEN = "#5E8B6F"


def _parse_envio_datetime(value):
    s = str(value or "").strip()
    if not s:
        return None
    if "." in s:
        s = s.split(".")[0]
    s = s.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def _format_programada_label(value):
    dt = _parse_envio_datetime(value)
    if not dt:
        return "Hoy"
    today = datetime.now().date()
    if dt.date() == today:
        return "Hoy"
    return ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"][
        dt.weekday()
    ]


class EnviosTableModel(QAbstractTableModel):
    HEADERS = [
        "Remito",
        "Fecha",
        "A partir de",
        "Local",
        "Entrega",
        "Cliente",
        "Direccion",
        "Pago envio local",
        "Accion",
    ]

    def __init__(self, rows=None, parent=None):
        super().__init__(parent)
        self._rows = list(rows or [])
        self._bulk_mode = False
        self._bulk_selected = set()

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = list(rows or [])
        self.endResetModel()

    def set_bulk_state(self, bulk_mode: bool, selected_ids: set):
        self._bulk_mode = bool(bulk_mode)
        self._bulk_selected = set(selected_ids or [])
        if self._rows:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._rows) - 1, 0)
            self.dataChanged.emit(
                top_left, bottom_right, [Qt.DisplayRole, Qt.ForegroundRole]
            )

    def rowCount(self, parent=None):
        return len(self._rows)

    def columnCount(self, parent=None):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            try:
                return self.HEADERS[section]
            except Exception:
                return None
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._rows):
            return None
        v = self._rows[row]
        remito_ok = int(v.get("remito_impreso") or 0) == 1
        venta_id = int(v.get("id") or 0)

        if role == Qt.DisplayRole:
            if col == 0:
                if self._bulk_mode:
                    return "?" if venta_id in self._bulk_selected else ""
                return "?" if remito_ok else ""
            if col == 1:
                return str(v.get("fecha") or "")
            if col == 2:
                return str(v.get("_programada_fmt") or "")
            if col == 3:
                return str(v.get("local") or "")
            if col == 4:
                return str(v.get("entrega_local") or "")
            if col == 5:
                return str(v.get("cliente_nombre") or "")
            if col == 6:
                return str(v.get("_direccion_fmt") or "")
            if col == 7:
                return str(v.get("_pago_envio_fmt") or "")
            if col == 8:
                return ""

        if role == Qt.TextAlignmentRole:
            if col in (0, 2, 3, 4, 7):
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.ForegroundRole:
            if col == 0:
                if self._bulk_mode:
                    return QColor(PRIMARY)
                return QColor(GREEN) if remito_ok else QColor(TEXT)
            return QColor(TEXT)

        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def venta_id_at(self, row):
        if 0 <= row < len(self._rows):
            try:
                return int(self._rows[row].get("id") or 0)
            except Exception:
                return 0
        return 0


class EnviosWindow(QMainWindow):
    def __init__(self, username: str, role: str, local: str, back_command=None):
        super().__init__()
        self.username = username
        self.role = role
        self.local = local or "Todos"
        self.back_command = back_command
        self._bulk_select_mode = False
        self._bulk_selected_ids = set()
        self._load_counter = 0
        self._current_load_id = 0
        self._load_thread = None
        self._setup_ui()
        self.load_data()

    def _setup_ui(self):
        try:
            import app_theme as _at_init

            _dark_init = _at_init.is_dark_mode()
            _px_init = _at_init.get_font_size_px()
            self.setStyleSheet(_at_init.build_stylesheet(_dark_init, _px_init))
        except Exception:
            pass
        self.setWindowTitle("Envios")
        self.resize(1100, 780)
        self.setWindowState(self.windowState() | Qt.WindowMaximized)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(14)
        if self.back_command:
            back_btn = QPushButton("← Volver")
            back_btn.setCursor(Qt.PointingHandCursor)
            try:
                import app_theme as _at_bk

                _dark_bk = _at_bk.is_dark_mode()
                _c_bk = _at_bk._palette(_dark_bk)
                back_btn.setStyleSheet(
                    f"QPushButton{{background:{_c_bk['BG_ALT']};color:{_c_bk['GOLD']};"
                    f"border:1px solid {_c_bk['BORDER']};border-radius:10px;padding:8px 14px;font-weight:700;}}"
                    f"QPushButton:hover{{background:{_c_bk['SURFACE']};border-color:{_c_bk['GOLD']};}}"
                )
            except Exception:
                back_btn.setStyleSheet(
                    "QPushButton{background:#34343a;color:#C9A040;border:1px solid #3e3e44;"
                    "border-radius:10px;padding:8px 14px;font-weight:700;}"
                    "QPushButton:hover{background:#3e3e44;}"
                )
            back_btn.clicked.connect(self.back_command)
            header.addWidget(back_btn)
        title = QLabel("Envios")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet(f"color:{_T('GOLD', PRIMARY)};")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        filters = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por cliente o numero de venta")
        self.search_input.textChanged.connect(self.load_data)
        filters.addWidget(self.search_input)

        refresh_btn = QPushButton("Refrescar")
        refresh_btn.clicked.connect(self.load_data)
        filters.addWidget(refresh_btn)

        filters.addStretch()
        layout.addLayout(filters)

        pendientes_header = QHBoxLayout()
        pendientes_label = QLabel("Restantes")
        pendientes_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        pendientes_label.setStyleSheet(
            f"color:{_T('TEXT', '#ECECF1')}; background:transparent;"
        )
        pendientes_header.addWidget(pendientes_label)
        pendientes_header.addStretch()
        self.print_all_btn = QPushButton("Imprimir todo")
        self.print_all_btn.clicked.connect(self._on_bulk_print_clicked)
        pendientes_header.addWidget(self.print_all_btn)
        self.toggle_programados_btn = QPushButton("Ver programados")
        self.toggle_programados_btn.clicked.connect(self._toggle_programados)
        pendientes_header.addWidget(self.toggle_programados_btn)
        layout.addLayout(pendientes_header)

        self.table_pendientes = QTableView()
        self.pendientes_model = EnviosTableModel([], self)
        self.table_pendientes.setModel(self.pendientes_model)
        self._setup_table(self.table_pendientes)
        self.table_pendientes.clicked.connect(self._on_pendientes_cell_clicked)
        layout.addWidget(self.table_pendientes)

        self.programados_label = QLabel("Programados")
        self.programados_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.programados_label.setStyleSheet(f"color:{_T('TEXT', '#ECECF1')};")
        self.programados_label.setVisible(False)
        layout.addWidget(self.programados_label)

        self.table_programados = QTableView()
        self.programados_model = EnviosTableModel([], self)
        self.table_programados.setModel(self.programados_model)
        self._setup_table(self.table_programados)
        self.table_programados.setVisible(False)
        layout.addWidget(self.table_programados)

        entregados_label = QLabel("Entregados")
        entregados_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        entregados_label.setStyleSheet(f"color:{_T('TEXT', '#ECECF1')};")
        layout.addWidget(entregados_label)

        self.table_entregados = QTableView()
        self.entregados_model = EnviosTableModel([], self)
        self.table_entregados.setModel(self.entregados_model)
        self._setup_table(self.table_entregados)
        layout.addWidget(self.table_entregados)

    def _setup_table(self, table: QTableView):
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(46)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        try:
            import app_theme as _at_st

            _dark_st = _at_st.is_dark_mode()
            _c_st = _at_st._palette(_dark_st)
            _hover_st = "rgba(255,255,255,0.04)" if _dark_st else "rgba(0,0,0,0.06)"
            table.setStyleSheet(
                f"QTableView {{ background:{_c_st['SURFACE']};"
                f"alternate-background-color:{_c_st['ROW_EVEN']};"
                f"color:{_c_st['TEXT']}; gridline-color:{_c_st['BORDER']};"
                f"border:1px solid {_c_st['BORDER']}; border-radius:12px;"
                f"selection-background-color:{_c_st['SEL_BG']}; }}"
                f"QTableView::item {{ color:{_c_st['TEXT']}; padding:8px 10px;"
                f"border-bottom:1px solid {_c_st['BORDER']}; }}"
                f"QTableView::item:selected {{ background:{_c_st['SEL_BG']}; color:{_c_st['TEXT']}; }}"
                f"QTableView::item:hover {{ background:{_hover_st}; }}"
                f"QHeaderView::section {{ background:{_c_st['TH_BG']}; color:{_c_st['GOLD']};"
                f"font-weight:700; padding:10px 8px; border:none;"
                f"border-bottom:2px solid {_c_st['GOLD']}; }}"
            )
        except Exception:
            table.setStyleSheet(
                f"QTableView {{ background:{_T('BG', '#0f0f14')};"
                f"alternate-background-color:{BG_ALT}; color:{_T('TEXT', '#ECECF1')};"
                f"gridline-color:#3e3e44; border:1px solid #3e3e44; border-radius:12px; }}"
                f"QHeaderView::section {{ background:#141420; color:{PRIMARY};"
                f"font-weight:700; padding:10px 8px; border:none; border-bottom:2px solid {PRIMARY}; }}"
            )
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Interactive)
        header.resizeSection(7, 160)
        header.setSectionResizeMode(8, QHeaderView.Interactive)
        header.resizeSection(8, 220)

    def load_data(self):
        search = self.search_input.text().strip() if self.search_input else ""
        if self._bulk_select_mode:
            self._disable_bulk_mode()
        self._load_counter += 1
        self._current_load_id = self._load_counter
        if self._load_thread and self._load_thread.isRunning():
            try:
                self._load_thread.requestInterruption()
            except Exception:
                pass
        self._load_thread = EnviosLoadWorker(search, self._current_load_id, self)
        self._load_thread.data_loaded.connect(self._on_envios_loaded)
        self._load_thread.start()

    def _on_envios_loaded(self, load_id, pendientes, programados, entregados):
        if load_id != self._current_load_id:
            return
        self._fill_table(self.table_pendientes, pendientes, entregado=False)
        self._fill_table(self.table_programados, programados, entregado=False)
        self._fill_table(self.table_entregados, entregados, entregado=True)

    def _toggle_programados(self):
        visible = not self.table_programados.isVisible()
        self.table_programados.setVisible(visible)
        self.programados_label.setVisible(visible)
        self.toggle_programados_btn.setText(
            "Ocultar programados" if visible else "Ver programados"
        )

    def closeEvent(self, event):
        try:
            if self._load_thread and self._load_thread.isRunning():
                self._load_thread.requestInterruption()
                self._load_thread.wait(200)
        except Exception:
            pass
        super().closeEvent(event)

    def _fill_table(self, table: QTableView, ventas: list, entregado: bool):
        # Preparar filas con campos calculados
        rows = []
        for v in ventas or []:
            v = dict(v)
            v["_direccion_fmt"] = self._format_direccion(v)
            fp_envio = (v.get("forma_pago_envio") or "").strip()
            try:
                precio_envio = int(float(v.get("precio_envio") or 0))
            except Exception:
                precio_envio = 0
            if precio_envio > 0:
                monto_fmt = f"${precio_envio:,}".replace(",", ".")
                v["_pago_envio_fmt"] = (
                    f"{monto_fmt} ({fp_envio})" if fp_envio else monto_fmt
                )
            elif fp_envio:
                v["_pago_envio_fmt"] = f"Si ({fp_envio})"
            else:
                v["_pago_envio_fmt"] = "No"
            v["_programada_fmt"] = _format_programada_label(v.get("entrega_programada"))
            rows.append(v)

        if table is self.table_pendientes:
            model = self.pendientes_model
        elif table is self.table_programados:
            model = self.programados_model
        else:
            model = self.entregados_model
        model.set_rows(rows)

        # Botones de accion en columna 8
        for row_idx, venta in enumerate(rows):
            actions = QWidget()
            actions.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(actions)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            btn_print = QPushButton("Imprimir")
            btn_print.setStyleSheet(
                f"QPushButton{{background:{_T('SURFACE','#252530')};color:{_T('TEXT','#F8F1E7')};font-weight:700;"
                f"border-radius:8px;padding:6px 14px;border:1px solid {_T('BORDER','#3e3e44')};}}"
                f"QPushButton:hover{{background:{_T('BG_ALT','#34343a')};}}"
            )
            btn_print.setMinimumWidth(95)
            btn_print.clicked.connect(
                lambda _=None, vid=venta.get("id"): self.imprimir_remito(vid)
            )
            row_layout.addWidget(btn_print)

            if entregado:
                btn_cancel = QPushButton("Anular entrega")
                btn_cancel.setStyleSheet(
                    "QPushButton{background:#C56A6A;color:white;font-weight:700;"
                    "border-radius:8px;padding:6px 12px;}"
                    "QPushButton:hover{background:#b55555;}"
                )
                btn_cancel.setMinimumWidth(110)
                btn_cancel.clicked.connect(
                    lambda _=None, vid=venta.get("id"): self.anular_entrega(vid)
                )
                row_layout.addWidget(btn_cancel)
            else:
                btn_deliver = QPushButton("Entregar")
                btn_deliver.setStyleSheet(
                    "QPushButton{background:#5E8B6F;color:white;font-weight:700;"
                    "border-radius:8px;padding:6px 14px;}"
                    "QPushButton:hover{background:#4e7a5f;}"
                )
                btn_deliver.setMinimumWidth(95)
                btn_deliver.clicked.connect(
                    lambda _=None, vid=venta.get("id"): self.marcar_entregado(vid)
                )
                row_layout.addWidget(btn_deliver)

            row_layout.addStretch()
            table.setIndexWidget(model.index(row_idx, 8), actions)

        if table is self.table_pendientes and self._bulk_select_mode:
            self._refresh_remito_selection_markers()

    def _on_bulk_print_clicked(self):
        if not self._bulk_select_mode:
            if self.pendientes_model.rowCount() == 0:
                QMessageBox.information(
                    self, "Envios", "No hay envios pendientes para imprimir."
                )
                return
            self._enable_bulk_mode()
            return
        self._print_bulk_selected()

    def _enable_bulk_mode(self):
        self._bulk_select_mode = True
        self._bulk_selected_ids = set()
        for row in range(self.pendientes_model.rowCount()):
            venta_id = self.pendientes_model.venta_id_at(row)
            if venta_id:
                self._bulk_selected_ids.add(int(venta_id))
        self._update_bulk_button()
        self._refresh_remito_selection_markers()

    def _disable_bulk_mode(self):
        self._bulk_select_mode = False
        self._bulk_selected_ids = set()
        self._update_bulk_button()
        self._refresh_remito_selection_markers()

    def _update_bulk_button(self):
        if hasattr(self, "print_all_btn"):
            self.print_all_btn.setText(
                "Imprimir" if self._bulk_select_mode else "Imprimir todo"
            )

    def _on_pendientes_cell_clicked(self, index):
        if not self._bulk_select_mode:
            return
        row = index.row()
        col = index.column()
        if col != 0:
            return
        venta_id = self.pendientes_model.venta_id_at(row)
        if not venta_id:
            return
        if int(venta_id) in self._bulk_selected_ids:
            self._bulk_selected_ids.discard(int(venta_id))
        else:
            self._bulk_selected_ids.add(int(venta_id))
        self._refresh_remito_selection_markers()

    def _refresh_remito_selection_markers(self):
        self.pendientes_model.set_bulk_state(
            self._bulk_select_mode, self._bulk_selected_ids
        )

    def _print_bulk_selected(self):
        selected_ids = list(self._bulk_selected_ids)
        if not selected_ids:
            QMessageBox.warning(
                self, "Envios", "No hay remitos seleccionados para imprimir."
            )
            return
        ok, path_or_msg, errors, included_ids = vm.generar_pdf_remitos(selected_ids)
        if not ok:
            msg = path_or_msg
            if errors:
                msg = f"{msg}\n\n" + "\n".join(errors[:5])
            QMessageBox.warning(self, "Envios", msg)
            return

        self._open_pdf(path_or_msg)
        for venta_id in included_ids:
            vm.marcar_remito_impreso(int(venta_id), True)

        self._disable_bulk_mode()
        self.load_data()

    def _format_direccion(self, venta: dict) -> str:
        calle = str(venta.get("cliente_calle") or "").strip()
        numero = str(venta.get("cliente_numero") or "").strip()
        localidad = str(venta.get("cliente_localidad") or "").strip()
        entre = str(venta.get("entre_calles") or "").strip()
        base = " ".join(p for p in [calle, numero] if p)
        if localidad:
            base = f"{base} - {localidad}" if base else localidad
        if entre:
            base = f"{base} (entre {entre})"
        return base

    def imprimir_remito(self, venta_id):
        if not venta_id:
            return
        ok, path_or_msg = vm.generar_pdf_remito(int(venta_id))
        if not ok:
            QMessageBox.warning(
                self, "Remito", f"No se pudo generar el remito: {path_or_msg}"
            )
            return
        self._open_pdf(path_or_msg)
        vm.marcar_remito_impreso(int(venta_id), True)
        self.load_data()

    def marcar_entregado(self, venta_id):
        if not venta_id:
            return
        venta = vm.get_venta_detalle(int(venta_id))
        if not venta:
            QMessageBox.warning(self, "Entregas", "Venta no encontrada.")
            return
        items = venta.get("items") or []
        if not items:
            QMessageBox.warning(self, "Entregas", "La venta no tiene productos.")
            return

        locals_list = []
        try:
            locals_list = [l for l in (get_all_locals() or []) if l]
        except Exception:
            locals_list = []
        if self.local and self.local not in locals_list:
            locals_list.insert(0, self.local)

        selections = self._seleccionar_locales_entrega(items, locals_list, venta)
        if selections is None:
            return

        ok, msg = vm.marcar_entrega(
            int(venta_id),
            True,
            usuario=self.username,
            local_entrega=self.local,
            local_por_item=selections,
        )
        if not ok:
            QMessageBox.warning(self, "Entregas", msg)
            return
        try:
            vm.auto_retirar_domicilio_por_venta(int(venta_id), self.username)
        except Exception:
            pass
        self.load_data()

    def _seleccionar_locales_entrega(self, items: list, locals_list: list, venta: dict):
        dlg = QDialog(self)
        dlg.setWindowTitle("Entregar - Seleccionar local")
        dlg.resize(1200, 680)
        dlg.setMinimumSize(1100, 620)
        lay = QVBoxLayout(dlg)

        info = QLabel("Selecciona el local desde donde sale cada producto:")
        info.setStyleSheet(f"color:{_T('TEXT', '#ECECF1')}; font-weight:700;")
        lay.addWidget(info)

        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            [
                "Producto",
                "Categoria",
                "Color",
                "Fabricante",
                "Medida",
                "Estado",
                "Cantidad",
                "Local de entrega",
            ]
        )
        table.setRowCount(0)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        try:
            import app_theme as _at_tbl

            _dark_tbl = _at_tbl.is_dark_mode()
            _c_tbl = _at_tbl._palette(_dark_tbl)
            table.setStyleSheet(
                f"QTableWidget{{background:{_c_tbl['SURFACE']};color:{_c_tbl['TEXT']};"
                f"border:1px solid {_c_tbl['BORDER']};border-radius:8px;"
                f"alternate-background-color:{_c_tbl['ROW_EVEN']};}}"
                f"QTableWidget::item{{padding:6px 8px;color:{_c_tbl['TEXT']};}}"
                f"QHeaderView::section{{background:{_c_tbl['TH_BG']};color:{_c_tbl['GOLD']};"
                f"font-weight:700;padding:6px;border:none;border-bottom:2px solid {_c_tbl['GOLD']};}}"
            )
            table.setAlternatingRowColors(True)
        except Exception:
            table.setStyleSheet(
                "QTableWidget{background:#1a1a22;color:#F8F1E7;border:1px solid #3e3e44;border-radius:8px;}"
                "QHeaderView::section{background:#141420;color:#C9A040;font-weight:700;padding:6px;border:none;border-bottom:1px solid #3e3e44;}"
            )

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.resizeSection(0, 260)
        header.resizeSection(1, 150)
        header.resizeSection(2, 110)
        header.resizeSection(3, 160)
        header.resizeSection(4, 120)
        header.resizeSection(5, 100)
        header.resizeSection(6, 90)
        header.resizeSection(7, 140)

        row_meta = []
        blocked_rows = 0

        def _item_key(it):
            try:
                did = int(it.get("id") or 0)
            except Exception:
                did = 0
            if did > 0:
                return ("detail", did)
            try:
                pid = int(it.get("producto_id") or 0)
            except Exception:
                pid = 0
            return ("pid", pid)

        def _get_allowed_locals(it):
            allowed = []
            for l in locals_list or []:
                if vm.get_available_qty_for_item_local(it, l) > 0:
                    allowed.append(l)
            return allowed

        def _get_allocated_qty(key, local, skip_row=None):
            total = 0
            for idx, meta in enumerate(row_meta):
                if skip_row is not None and idx == skip_row:
                    continue
                if meta.get("key") == key and (meta.get("local") or "") == (
                    local or ""
                ):
                    total += int(meta.get("qty") or 0)
            return total

        def _add_row(it, qty, default_local):
            nonlocal blocked_rows
            row = table.rowCount()
            table.insertRow(row)

            nombre = it.get("producto_nombre") or it.get("nombre") or "Producto"
            categoria = it.get("producto_categoria") or it.get("categoria") or ""
            color = it.get("producto_color") or it.get("color") or ""
            fabricante = it.get("producto_fabricante") or it.get("fabricante") or ""
            medida = it.get("producto_medida") or it.get("medida") or ""
            estado = it.get("producto_estado") or it.get("estado") or ""

            table.setItem(row, 0, QTableWidgetItem(str(nombre)))
            table.setItem(row, 1, QTableWidgetItem(str(categoria)))
            table.setItem(row, 2, QTableWidgetItem(str(color)))
            table.setItem(row, 3, QTableWidgetItem(str(fabricante)))
            table.setItem(row, 4, QTableWidgetItem(str(medida)))
            table.setItem(row, 5, QTableWidgetItem(str(estado)))
            qty_item = QTableWidgetItem(str(qty))
            qty_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 6, qty_item)

            allowed = _get_allowed_locals(it)
            if not allowed:
                empty_lbl = QLabel("SIN STOCK")
                empty_lbl.setStyleSheet("color:#ef4444;font-weight:700;")
                empty_lbl.setAlignment(Qt.AlignCenter)
                table.setCellWidget(row, 7, empty_lbl)
                blocked_rows += 1
                meta = {"item": it, "qty": int(qty), "local": "", "key": _item_key(it)}
                row_meta.append(meta)
                return

            combo = QComboBox()
            combo.addItems(allowed)
            if default_local in allowed:
                combo.setCurrentText(default_local)
            combo.setFixedWidth(120)
            table.setCellWidget(row, 7, combo)
            meta = {
                "item": it,
                "qty": int(qty),
                "local": combo.currentText(),
                "key": _item_key(it),
            }
            row_meta.append(meta)

            def _handle_change():
                nonlocal blocked_rows
                current_row = row
                if current_row >= len(row_meta):
                    return
                meta = row_meta[current_row]
                it_local = meta.get("item")
                local_sel = combo.currentText()
                meta["local"] = local_sel

                stock = vm.get_available_qty_for_item_local(it_local, local_sel)
                allocated_other = _get_allocated_qty(
                    meta["key"], local_sel, skip_row=current_row
                )
                available = max(0, int(stock) - int(allocated_other))

                if available <= 0:
                    QMessageBox.warning(
                        self, "Entregas", "Ese local no tiene stock disponible."
                    )
                    # buscar otro local con disponible
                    found = None
                    for l in _get_allowed_locals(it_local):
                        st = vm.get_available_qty_for_item_local(it_local, l)
                        if (
                            st
                            - _get_allocated_qty(meta["key"], l, skip_row=current_row)
                            > 0
                        ):
                            found = l
                            break
                    if found:
                        combo.setCurrentText(found)
                    return

                qty_now = int(meta.get("qty") or 0)
                if qty_now > available:
                    meta["qty"] = available
                    table.item(current_row, 6).setText(str(available))
                    remaining = qty_now - available
                    QMessageBox.information(
                        self,
                        "Entregas",
                        f"En {local_sel} hay {available}. Se duplico la fila para completar {remaining}.",
                    )
                    _add_row(it_local, remaining, default_local="")

            combo.currentTextChanged.connect(_handle_change)

        # Crear filas iniciales
        for it in items:
            try:
                qty = int(it.get("cantidad") or 0)
            except Exception:
                qty = 0
            stock_local = it.get("stock_local") or venta.get("local") or ""
            default_local = (
                self.local or stock_local or (locals_list[0] if locals_list else "")
            )
            if default_local not in locals_list and default_local:
                locals_list.insert(0, default_local)
            _add_row(it, qty, default_local)

        lay.addWidget(table)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Confirmar")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        lay.addWidget(btns)

        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec_() != QDialog.Accepted:
            return None
        if blocked_rows > 0:
            QMessageBox.warning(
                self,
                "Entregas",
                "Hay productos sin stock en ningun local. No se puede confirmar la entrega.",
            )
            return None

        selections = []
        for meta in row_meta:
            it = meta.get("item") or {}
            qty = int(meta.get("qty") or 0)
            local_sel = (meta.get("local") or "").strip()
            if qty <= 0 or not local_sel:
                QMessageBox.warning(
                    self, "Entregas", "Faltan locales para completar la entrega."
                )
                return None
            entrega_pid = vm.get_delivery_pid_for_local(it, local_sel)
            selections.append(
                {
                    "detalle_id": it.get("id"),
                    "producto_id": it.get("producto_id"),
                    "cantidad": qty,
                    "local": local_sel,
                    "entrega_producto_id": entrega_pid,
                }
            )
        return selections

    def anular_entrega(self, venta_id):
        if not venta_id:
            return
        motivo, ok = QInputDialog.getText(self, "Anular entrega", "Motivo:")
        if not ok:
            return
        motivo = (motivo or "").strip()
        if not motivo:
            QMessageBox.warning(self, "Anular entrega", "Debe ingresar un motivo")
            return
        ok, msg = vm.anular_entrega_con_devolucion(int(venta_id), motivo, self.username)
        if not ok:
            QMessageBox.warning(self, "Anular entrega", msg)
            return
        try:
            vm.revertir_domicilio_por_venta(int(venta_id))
        except Exception:
            pass
        self.load_data()

    def _open_pdf(self, filepath):
        try:
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.call(["open", filepath])
            else:
                subprocess.call(["xdg-open", filepath])
        except Exception as e:
            QMessageBox.warning(self, "Remito", f"No se pudo abrir el PDF: {e}")

    def _abrir_boleta(self, venta_id: int):
        if not venta_id:
            return
        ok, path_or_msg = vm.generar_pdf_boleta(int(venta_id))
        if not ok:
            QMessageBox.warning(
                self, "Boleta", f"No se pudo generar la boleta: {path_or_msg}"
            )
            return
        self._open_pdf(path_or_msg)

    def _fmt_money(self, value) -> str:
        try:
            return f"{int(float(value or 0)):,}".replace(",", ".")
        except Exception:
            return str(value or 0)

    def refresh_theme(self):
        """Aplica tema global cuando cambia dark/light mode."""
        try:
            import app_theme as _at

            dark = _at.is_dark_mode()
            px = _at.get_font_size_px()
            _c = _at._palette(dark)
            self.setStyleSheet(_at.build_stylesheet(dark, px))
        except Exception:
            pass


class EnviosLoadWorker(QThread):
    data_loaded = pyqtSignal(int, list, list, list)

    def __init__(self, search: str, load_id: int, parent=None):
        super().__init__(parent)
        self.search = search
        self.load_id = load_id

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            ventas = vhm.get_ventas_por_local_fast(
                "Todos", filtro_fecha="todo", search=self.search
            )
        except Exception:
            ventas = []
        ventas = [v for v in (ventas or []) if int(v.get("incluye_envio") or 0) == 1]
        pendientes = []
        programados = []
        entregados = []
        cutoff_dt = datetime.now() - timedelta(days=7)
        today = datetime.now().date()
        for v in ventas:
            if int(v.get("entrega_entregado") or 0) == 1:
                entrega_dt = _parse_envio_datetime(
                    v.get("entrega_fecha") or v.get("fecha")
                )
                if entrega_dt and entrega_dt < cutoff_dt:
                    continue
                entregados.append(v)
            else:
                programada_dt = _parse_envio_datetime(v.get("entrega_programada"))
                if programada_dt and programada_dt.date() > today:
                    programados.append(v)
                else:
                    pendientes.append(v)

        pendientes.sort(key=lambda v: str(v.get("fecha") or ""), reverse=True)
        entregados.sort(
            key=lambda v: str(v.get("entrega_fecha") or v.get("fecha") or ""),
            reverse=True,
        )
        programados.sort(
            key=lambda v: str(v.get("entrega_programada") or v.get("fecha") or ""),
            reverse=False,
        )
        try:
            if self.isInterruptionRequested():
                return
            self.data_loaded.emit(self.load_id, pendientes, programados, entregados)
        except Exception:
            pass
