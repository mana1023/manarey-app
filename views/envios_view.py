# views/envios_view.py
import os
import platform
import subprocess
from datetime import datetime, timedelta

from PySide6.QtCore import QAbstractTableModel, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtGui import QPixmap as _QPixmap

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


from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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
    QScrollArea,
    QSizePolicy,
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


def _styled_combo(items: list, default: str = "") -> "QComboBox":
    """Crea un QComboBox con estilo explícito para que el texto sea siempre legible,
    independientemente del tema del sistema operativo o el tamaño de pantalla."""
    gold = _T("GOLD", "#C9A040")
    bg = _T("CARD", "#232327")
    fg = _T("TEXT", "#ECECF1")
    sel_bg = gold
    combo = QComboBox()
    combo.addItems(items)
    if default and default in items:
        combo.setCurrentText(default)
    combo.setStyleSheet(
        f"QComboBox {{"
        f"  color: {fg};"
        f"  background: {bg};"
        f"  padding: 3px 8px;"
        f"  border: 1px solid {gold};"
        f"  border-radius: 4px;"
        f"  font-size: 12px;"
        f"  min-width: 110px;"
        f"}}"
        f"QComboBox:disabled {{"
        f"  color: #555555;"
        f"  background: #1a1a1a;"
        f"  border-color: #444;"
        f"}}"
        f"QComboBox::drop-down {{"
        f"  border: none; width: 22px;"
        f"}}"
        f"QComboBox QAbstractItemView {{"
        f"  color: {fg};"
        f"  background: {bg};"
        f"  selection-background-color: {sel_bg};"
        f"  selection-color: #111111;"
        f"  border: 1px solid {gold};"
        f"  outline: none;"
        f"  padding: 2px;"
        f"}}"
    )
    return combo


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
            self._back_btn_ref = back_btn
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

        ruta_btn = QPushButton("Crear Ruta")
        ruta_btn.setStyleSheet(
            f"background:{_T('GOLD', PRIMARY)}; color:#111; font-weight:bold;"
        )
        ruta_btn.clicked.connect(self._crear_ruta)
        filters.addWidget(ruta_btn)

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

    def set_back_command(self, cmd):
        self.back_command = cmd
        btn = getattr(self, "_back_btn_ref", None)
        if btn is not None:
            try:
                btn.clicked.disconnect()
            except Exception:
                pass
            if cmd:
                btn.clicked.connect(cmd)
            btn.setVisible(bool(cmd))

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

        # Preguntar origen por producto para cada remito seleccionado
        items_origen_per_venta = self._seleccionar_origen_bulk(selected_ids)
        if items_origen_per_venta is None:
            return  # cancelado

        ok, path_or_msg, errors, included_ids = vm.generar_pdf_remitos(
            selected_ids,
            items_origen_per_venta=items_origen_per_venta,
        )
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

    def _seleccionar_origen_bulk(self, venta_ids: list) -> dict | None:
        """Muestra diálogo con todos los remitos seleccionados y un local de origen
        por producto. Retorna {venta_id: {item_index: local_name}} o None si se cancela.
        """
        locales = self._get_locales_list()

        # Cargar detalles completos de cada venta
        orders_full = []
        for vid in venta_ids:
            try:
                full = vm.get_venta_detalle(int(vid))
                if full:
                    orders_full.append(full)
            except Exception:
                pass

        if not orders_full:
            return {}

        _HDR_BG = _T("CARD", "#232327")
        _HDR_FG = _T("GOLD", PRIMARY)
        _PROD_BG = _T("BG_ALT", "#1a1a22")
        _PROD_FG = _T("TEXT", "#ECECF1")
        _MUTED_FG = _T("TEXT_MUTED", "#a0a0a8")

        dlg = QDialog(self)
        dlg.setWindowTitle("Imprimir remitos — ¿De qué local sale cada producto?")
        dlg.resize(980, 580)
        dlg.setMinimumSize(860, 480)
        layout = QVBoxLayout(dlg)

        lbl = QLabel("Indicá de qué local sale cada producto en cada remito:")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color:{_HDR_FG}; font-weight:bold; font-size:12px; padding:4px 0;"
        )
        layout.addWidget(lbl)

        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(
            [
                "Producto  /  Cliente — Dirección",
                "Color",
                "Medida",
                "Cant.",
                "Sale de (local)",
            ]
        )
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.NoSelection)
        tbl.setWordWrap(False)
        try:
            import app_theme as _at_b

            _dk = _at_b.is_dark_mode()
            _cp = _at_b._palette(_dk)
            tbl.setStyleSheet(
                f"QTableWidget{{background:{_cp.get('SURFACE',_PROD_BG)};color:{_cp.get('TEXT',_PROD_FG)};"
                f"border:1px solid {_cp.get('BORDER','#3e3e44')};border-radius:8px;"
                f"gridline-color:{_cp.get('BORDER','#3e3e44')};}}"
                f"QTableWidget::item{{padding:4px 8px;}}"
                f"QHeaderView::section{{background:{_cp.get('TH_BG','#141420')};color:{_cp.get('GOLD',PRIMARY)};"
                f"font-weight:700;padding:5px;border:none;border-bottom:2px solid {_cp.get('GOLD',PRIMARY)};}}"
            )
        except Exception:
            tbl.setStyleSheet(
                f"QTableWidget{{background:{_PROD_BG};color:{_PROD_FG};"
                "border:1px solid #3e3e44;border-radius:8px;gridline-color:#3e3e44;}}"
                "QTableWidget::item{padding:4px 8px;}"
                f"QHeaderView::section{{background:#141420;color:{PRIMARY};"
                "font-weight:700;padding:5px;border:none;border-bottom:2px solid #C9A040;}}"
            )

        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.resizeSection(0, 370)
        hdr.resizeSection(1, 100)
        hdr.resizeSection(2, 90)
        hdr.resizeSection(3, 55)
        hdr.resizeSection(4, 150)
        tbl.verticalHeader().setDefaultSectionSize(28)

        def _make_empty(bg: str) -> QTableWidgetItem:
            it = QTableWidgetItem("")
            it.setBackground(QBrush(QColor(bg)))
            it.setFlags(it.flags() & ~Qt.ItemIsSelectable)
            return it

        def _prod_item(txt: str, muted: bool = False) -> QTableWidgetItem:
            i = QTableWidgetItem(txt)
            i.setForeground(QBrush(QColor(_MUTED_FG if muted else _PROD_FG)))
            i.setBackground(QBrush(QColor(_PROD_BG)))
            i.setFlags(i.flags() & ~Qt.ItemIsSelectable)
            return i

        # order_combos: {venta_id: [combo_per_product]}
        order_combos = {}

        for venta in orders_full:
            vid = int(venta.get("id") or 0)
            nombre = venta.get("cliente_nombre") or ""
            direccion = self._format_direccion(venta)
            local_v = (venta.get("local") or "").strip()
            items = venta.get("items") or []

            # ── Fila de cabecera del envío ──────────────────────────────────
            hr = tbl.rowCount()
            tbl.insertRow(hr)
            tbl.setRowHeight(hr, 32)

            hdr_txt = f"  {nombre}  —  {direccion}"
            hi = QTableWidgetItem(hdr_txt)
            hi.setFont(QFont("Segoe UI", 10, QFont.Bold))
            hi.setForeground(QBrush(QColor(_HDR_FG)))
            hi.setBackground(QBrush(QColor(_HDR_BG)))
            hi.setFlags(hi.flags() & ~Qt.ItemIsSelectable)
            tbl.setItem(hr, 0, hi)
            for c in range(1, 5):
                tbl.setItem(hr, c, _make_empty(_HDR_BG))

            # ── Filas de productos ──────────────────────────────────────────
            combos_for_venta = []
            if not items:
                pr = tbl.rowCount()
                tbl.insertRow(pr)
                pi = QTableWidgetItem("   (sin detalle de productos)")
                pi.setForeground(QBrush(QColor(_MUTED_FG)))
                pi.setBackground(QBrush(QColor(_PROD_BG)))
                pi.setFlags(pi.flags() & ~Qt.ItemIsSelectable)
                tbl.setItem(pr, 0, pi)
                for c in range(1, 4):
                    tbl.setItem(pr, c, _make_empty(_PROD_BG))
                combo = _styled_combo(locales, local_v)
                tbl.setCellWidget(pr, 4, combo)
                combos_for_venta.append(combo)
            else:
                for it in items:
                    pr = tbl.rowCount()
                    tbl.insertRow(pr)
                    tbl.setItem(
                        pr,
                        0,
                        _prod_item(
                            f"   ↳  {it.get('producto_nombre') or it.get('nombre') or 'Producto'}"
                        ),
                    )
                    tbl.setItem(
                        pr,
                        1,
                        _prod_item(
                            it.get("producto_color") or it.get("color") or "",
                            muted=True,
                        ),
                    )
                    tbl.setItem(
                        pr,
                        2,
                        _prod_item(
                            it.get("producto_medida") or it.get("medida") or "",
                            muted=True,
                        ),
                    )
                    tbl.setItem(
                        pr, 3, _prod_item(str(it.get("cantidad") or "1"), muted=True)
                    )
                    combo = _styled_combo(locales, local_v)
                    tbl.setCellWidget(pr, 4, combo)
                    combos_for_venta.append(combo)

            order_combos[vid] = combos_for_venta

        layout.addWidget(tbl)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Imprimir remitos")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() != QDialog.Accepted:
            return None

        return {
            vid: {idx: combo.currentText() for idx, combo in enumerate(combos)}
            for vid, combos in order_combos.items()
        }

    def _get_locales_list(self) -> list:
        """Retorna la lista de locales disponibles."""
        locales = ["Cane", "Estacion", "Glew", "Longchamps", "Vidriera"]
        try:
            from models.firestore_db import get_all_locals

            db_locales = [l for l in (get_all_locals() or []) if l]
            if db_locales:
                locales = db_locales
        except Exception:
            pass
        return locales

    def _seleccionar_origen_remito(self, venta_id: int) -> dict | None:
        """Muestra diálogo para asignar local de origen por producto antes de imprimir remito.
        Retorna {item_index: local_name} o None si se cancela."""
        venta = vm.get_venta_detalle(int(venta_id))
        if not venta:
            return {}
        items = venta.get("items") or []
        if not items:
            return {}

        locales = self._get_locales_list()
        # Usar el local de la venta como default
        default_local = (venta.get("local") or "").strip()
        if default_local not in locales and default_local:
            locales.insert(0, default_local)

        dlg = QDialog(self)
        dlg.setWindowTitle("Origen de mercadería - ¿De dónde sale cada producto?")
        dlg.resize(900, 500)
        dlg.setMinimumSize(700, 400)
        lay = QVBoxLayout(dlg)

        info = QLabel("Seleccioná el local de origen de cada producto:")
        info.setStyleSheet(
            f"color:{_T('TEXT', '#ECECF1')}; font-weight:700; font-size:13px;"
        )
        lay.addWidget(info)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ["Producto", "Color", "Medida", "Cantidad", "Sale de (local)"]
        )
        table.setRowCount(0)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)

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
                "QHeaderView::section{background:#141420;color:#C9A040;font-weight:700;padding:6px;"
                "border:none;border-bottom:1px solid #3e3e44;}"
            )

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.resizeSection(0, 280)
        header.resizeSection(1, 110)
        header.resizeSection(2, 110)
        header.resizeSection(3, 80)
        header.resizeSection(4, 160)

        combos = []
        for idx, it in enumerate(items):
            row = table.rowCount()
            table.insertRow(row)
            nombre = it.get("producto_nombre") or it.get("nombre") or "Producto"
            color = it.get("producto_color") or it.get("color") or ""
            medida = it.get("producto_medida") or it.get("medida") or ""
            cantidad = str(it.get("cantidad") or "1")
            table.setItem(row, 0, QTableWidgetItem(nombre))
            table.setItem(row, 1, QTableWidgetItem(color))
            table.setItem(row, 2, QTableWidgetItem(medida))
            table.setItem(row, 3, QTableWidgetItem(cantidad))
            combo = _styled_combo(locales, default_local)
            table.setCellWidget(row, 4, combo)
            combos.append(combo)

        lay.addWidget(table)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Imprimir remito")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.Accepted:
            return None

        return {idx: combo.currentText() for idx, combo in enumerate(combos)}

    def _crear_ruta(self):
        """Diálogo con un envío por sección y un local de origen por producto.
        La ruta resultante pasa primero por los locales a buscar mercadería,
        luego entrega a cada cliente."""
        rows = self.pendientes_model._rows
        if not rows:
            QMessageBox.information(self, "Crear Ruta", "No hay envíos pendientes.")
            return

        locales = self._get_locales_list()

        _local_addresses = {
            "Cane": "Miguel Cané 508, Glew, Buenos Aires, Argentina",
            "Estacion": "Almafuerte 45, Glew, Buenos Aires, Argentina",
            "Glew": "Av. Hipólito Yrigoyen 19861, Glew, Buenos Aires, Argentina",
            "Longchamps": "Av. Hipólito Yrigoyen 19051, Longchamps, Buenos Aires, Argentina",
            "Vidriera": "Av. Hipólito Yrigoyen 21890, Glew, Buenos Aires, Argentina",
        }

        # ── Cargar detalle de productos de cada venta ───────────────────────
        orders_full = []
        for v in rows:
            try:
                full = vm.get_venta_detalle(int(v.get("id") or 0))
                orders_full.append(full if full else v)
            except Exception:
                orders_full.append(v)

        # ── Colores para separar bloques de envíos ──────────────────────────
        _HDR_BG = _T("CARD", "#232327")
        _HDR_FG = _T("GOLD", PRIMARY)
        _PROD_BG = _T("BG_ALT", "#1a1a22")
        _PROD_FG = _T("TEXT", "#ECECF1")
        _MUTED_FG = _T("TEXT_MUTED", "#a0a0a8")

        # ── Diálogo ──────────────────────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle("Crear Ruta — Seleccionar envíos y origen de productos")
        dlg.resize(980, 580)
        dlg.setMinimumSize(860, 480)
        layout = QVBoxLayout(dlg)

        lbl = QLabel(
            "Activá los envíos a incluir y elegí de qué local sale cada producto."
            " La ruta pasará primero a buscar la mercadería y luego entregará."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color:{_HDR_FG}; font-weight:bold; font-size:12px; padding:4px 0;"
        )
        layout.addWidget(lbl)

        tbl = QTableWidget()
        # Cols: ✓ | Producto/Cliente | Color | Medida | Cant | Sale de
        tbl.setColumnCount(6)
        tbl.setHorizontalHeaderLabels(
            [
                "✓",
                "Producto  /  Cliente — Dirección",
                "Color",
                "Medida",
                "Cant.",
                "Sale de (local)",
            ]
        )
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.NoSelection)
        tbl.setWordWrap(False)
        try:
            import app_theme as _at_r

            _dk = _at_r.is_dark_mode()
            _cp = _at_r._palette(_dk)
            tbl.setStyleSheet(
                f"QTableWidget{{background:{_cp.get('SURFACE', _PROD_BG)};color:{_cp.get('TEXT', _PROD_FG)};"
                f"border:1px solid {_cp.get('BORDER','#3e3e44')};border-radius:8px;gridline-color:{_cp.get('BORDER','#3e3e44')};}}"
                f"QTableWidget::item{{padding:4px 8px;}}"
                f"QHeaderView::section{{background:{_cp.get('TH_BG','#141420')};color:{_cp.get('GOLD', PRIMARY)};"
                f"font-weight:700;padding:5px;border:none;border-bottom:2px solid {_cp.get('GOLD', PRIMARY)};}}"
            )
        except Exception:
            tbl.setStyleSheet(
                f"QTableWidget{{background:{_PROD_BG};color:{_PROD_FG};"
                "border:1px solid #3e3e44;border-radius:8px;gridline-color:#3e3e44;}}"
                "QTableWidget::item{padding:4px 8px;}"
                f"QHeaderView::section{{background:#141420;color:{PRIMARY};"
                "font-weight:700;padding:5px;border:none;border-bottom:2px solid #C9A040;}}"
            )

        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.resizeSection(0, 36)
        hdr.resizeSection(1, 340)
        hdr.resizeSection(2, 100)
        hdr.resizeSection(3, 90)
        hdr.resizeSection(4, 55)
        hdr.resizeSection(5, 145)
        tbl.verticalHeader().setDefaultSectionSize(28)

        # order_entries: list of (QCheckBox, venta_full, [QComboBox per product])
        order_entries = []

        def _prod_item(txt: str, muted: bool = False) -> QTableWidgetItem:
            """Crea un QTableWidgetItem con el estilo de fila de producto."""
            i = QTableWidgetItem(txt)
            i.setForeground(QBrush(QColor(_MUTED_FG if muted else _PROD_FG)))
            i.setBackground(QBrush(QColor(_PROD_BG)))
            i.setFlags(i.flags() & ~Qt.ItemIsSelectable)
            return i

        def _set_row_bg(row_idx: int, bg: str, fg: str):
            for col in range(tbl.columnCount()):
                it = tbl.item(row_idx, col)
                if it:
                    it.setBackground(QBrush(QColor(bg)))
                    it.setForeground(QBrush(QColor(fg)))

        def _make_empty_item(bg: str) -> QTableWidgetItem:
            it = QTableWidgetItem("")
            it.setBackground(QBrush(QColor(bg)))
            it.setFlags(it.flags() & ~Qt.ItemIsSelectable)
            return it

        for venta in orders_full:
            nombre = venta.get("cliente_nombre") or ""
            direccion = self._format_direccion(venta)
            local_v = (venta.get("local") or "").strip()
            items = venta.get("items") or []

            # ── fila de cabecera del envío ──────────────────────────────────
            hr = tbl.rowCount()
            tbl.insertRow(hr)
            tbl.setRowHeight(hr, 32)

            # checkbox en col 0
            cb_w = QWidget()
            cb_w.setStyleSheet(f"background:{_HDR_BG};")
            cb_l = QHBoxLayout(cb_w)
            cb_l.setContentsMargins(6, 0, 0, 0)
            cb = QCheckBox()
            cb.setChecked(True)
            cb_l.addWidget(cb)
            tbl.setCellWidget(hr, 0, cb_w)

            # texto del cliente en col 1 (span visual)
            hdr_txt = f"  {nombre}  —  {direccion}"
            hi = QTableWidgetItem(hdr_txt)
            hi.setFont(QFont("Segoe UI", 10, QFont.Bold))
            hi.setForeground(QBrush(QColor(_HDR_FG)))
            hi.setBackground(QBrush(QColor(_HDR_BG)))
            hi.setFlags(hi.flags() & ~Qt.ItemIsSelectable)
            tbl.setItem(hr, 1, hi)
            for c in range(2, 6):
                tbl.setItem(hr, c, _make_empty_item(_HDR_BG))

            # ── filas de productos ──────────────────────────────────────────
            combos_for_order = []
            if not items:
                # Sin detalle: una fila genérica con combo
                pr = tbl.rowCount()
                tbl.insertRow(pr)
                prod_lbl = QTableWidgetItem("   (productos no detallados)")
                prod_lbl.setForeground(QBrush(QColor(_MUTED_FG)))
                prod_lbl.setBackground(QBrush(QColor(_PROD_BG)))
                prod_lbl.setFlags(prod_lbl.flags() & ~Qt.ItemIsSelectable)
                tbl.setItem(pr, 1, prod_lbl)
                for c in [0, 2, 3, 4]:
                    tbl.setItem(pr, c, _make_empty_item(_PROD_BG))
                combo = _styled_combo(locales, local_v)
                tbl.setCellWidget(pr, 5, combo)
                combos_for_order.append(combo)
            else:
                for it in items:
                    pr = tbl.rowCount()
                    tbl.insertRow(pr)
                    prod_nombre = (
                        it.get("producto_nombre") or it.get("nombre") or "Producto"
                    )
                    prod_color = it.get("producto_color") or it.get("color") or ""
                    prod_medida = it.get("producto_medida") or it.get("medida") or ""
                    prod_cant = str(it.get("cantidad") or "1")

                    tbl.setItem(pr, 0, _make_empty_item(_PROD_BG))
                    tbl.setItem(pr, 1, _prod_item(f"   ↳  {prod_nombre}"))
                    tbl.setItem(pr, 2, _prod_item(prod_color, muted=True))
                    tbl.setItem(pr, 3, _prod_item(prod_medida, muted=True))
                    tbl.setItem(pr, 4, _prod_item(prod_cant, muted=True))

                    combo = _styled_combo(locales, local_v)
                    tbl.setCellWidget(pr, 5, combo)
                    combos_for_order.append(combo)

            # Conectar checkbox → enable/disable combos de este bloque
            _gold = _T("GOLD", PRIMARY)
            _bg = _T("CARD", "#232327")
            _fg = _T("TEXT", "#ECECF1")

            def _on_check(state, _combos=combos_for_order, _g=_gold, _b=_bg, _f=_fg):
                enabled = state == Qt.Checked
                for _c in _combos:
                    _c.setEnabled(enabled)
                    if not enabled:
                        _c.setStyleSheet(
                            "QComboBox{color:#555555;background:#1a1a1a;border:1px solid #444;"
                            "padding:3px 8px;border-radius:4px;font-size:12px;min-width:110px;}"
                            "QComboBox::drop-down{border:none;width:22px;}"
                        )
                    else:
                        _c.setStyleSheet(
                            f"QComboBox{{color:{_f};background:{_b};border:1px solid {_g};"
                            "padding:3px 8px;border-radius:4px;font-size:12px;min-width:110px;}"
                            f"QComboBox::drop-down{{border:none;width:22px;}}"
                            f"QComboBox QAbstractItemView{{color:{_f};background:{_b};"
                            f"selection-background-color:{_g};selection-color:#111;"
                            "border:1px solid #C9A040;outline:none;padding:2px;}}"
                        )

            cb.stateChanged.connect(_on_check)

            order_entries.append((cb, venta, combos_for_order))

        layout.addWidget(tbl)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Generar ruta →")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() != QDialog.Accepted:
            return

        # ── Recopilar selección ─────────────────────────────────────────────
        # Para cada envío activo: qué locales de origen tiene cada producto
        selected_orders = [
            (venta, combos) for cb, venta, combos in order_entries if cb.isChecked()
        ]
        if not selected_orders:
            QMessageBox.warning(self, "Crear Ruta", "No seleccionaste ningún envío.")
            return

        # ── Construir paradas de la ruta ────────────────────────────────────
        # Locales únicos de donde hay que ir a buscar (en orden de aparición)
        seen_locals_ordered = []
        for _, combos in selected_orders:
            for combo in combos:
                loc = combo.currentText().strip()
                if loc and loc not in seen_locals_ordered:
                    seen_locals_ordered.append(loc)

        if not seen_locals_ordered:
            QMessageBox.warning(
                self, "Crear Ruta", "No hay locales de origen definidos."
            )
            return

        # Punto de salida = primer local con productos
        start_local = seen_locals_ordered[0]
        start_address = _local_addresses.get(
            start_local, f"{start_local}, Buenos Aires, Argentina"
        )

        # Paradas intermedias: resto de locales de búsqueda + entregas a clientes
        branch_stops = [
            _local_addresses.get(loc, f"{loc}, Buenos Aires, Argentina")
            for loc in seen_locals_ordered[1:]
        ]

        delivery_stops = []
        for venta, _ in selected_orders:
            calle = str(venta.get("cliente_calle") or "").strip()
            numero = str(venta.get("cliente_numero") or "").strip()
            localidad = str(venta.get("cliente_localidad") or "").strip()
            addr = " ".join(p for p in [calle, numero] if p)
            if localidad:
                addr = f"{addr}, {localidad}" if addr else localidad
            if addr:
                delivery_stops.append(f"{addr}, Buenos Aires, Argentina")

        if not delivery_stops:
            QMessageBox.warning(
                self, "Crear Ruta", "Los envíos seleccionados no tienen dirección."
            )
            return

        all_stops = branch_stops + delivery_stops  # primero busca, luego entrega

        import urllib.parse

        origin_enc = urllib.parse.quote(start_address)
        dest_enc = urllib.parse.quote(all_stops[-1])
        mid_stops = all_stops[:-1]

        if mid_stops:
            mid_enc = "|".join(urllib.parse.quote(w) for w in mid_stops)
            maps_url = (
                f"https://www.google.com/maps/dir/?api=1"
                f"&origin={origin_enc}&destination={dest_enc}"
                f"&waypoints={mid_enc}&travelmode=driving"
            )
        else:
            maps_url = (
                f"https://www.google.com/maps/dir/?api=1"
                f"&origin={origin_enc}&destination={dest_enc}&travelmode=driving"
            )

        # ── Resumen textual ─────────────────────────────────────────────────
        resumen_lines = [f"🏪 <b>Sale de: {start_local}</b>"]
        for loc in seen_locals_ordered[1:]:
            resumen_lines.append(f"🏪 Busca en: <b>{loc}</b>")
        for venta, combos in selected_orders:
            nombre = venta.get("cliente_nombre") or "cliente"
            dir_fmt = self._format_direccion(venta) or "(sin dirección)"
            items = venta.get("items") or []
            resumen_lines.append(f"<br>📦 <b>{nombre}</b> — {dir_fmt}")
            for idx, it in enumerate(items):
                pnombre = it.get("producto_nombre") or it.get("nombre") or "producto"
                ploc = combos[idx].currentText() if idx < len(combos) else "?"
                resumen_lines.append(
                    f"&nbsp;&nbsp;&nbsp;↳ {pnombre} <span style='color:{_HDR_FG}'>({ploc})</span>"
                )

        # ── Generar QR ──────────────────────────────────────────────────────
        try:
            import tempfile

            import qrcode

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=6,
                border=2,
            )
            qr.add_data(maps_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            img.save(tmp.name)
            tmp.close()
            qr_path = tmp.name
        except Exception as e:
            QMessageBox.warning(self, "Crear Ruta", f"No se pudo generar el QR: {e}")
            return

        # ── Mostrar resultado: QR + resumen ─────────────────────────────────
        qr_dlg = QDialog(self)
        qr_dlg.setWindowTitle("Ruta generada ✓")
        qr_dlg.setMinimumWidth(740)
        qr_layout = QHBoxLayout(qr_dlg)
        qr_layout.setContentsMargins(14, 14, 14, 14)
        qr_layout.setSpacing(16)

        # Izquierda: resumen scrolleable
        left_w = QWidget()
        left_vl = QVBoxLayout(left_w)
        left_vl.setContentsMargins(0, 0, 0, 0)

        title_l = QLabel("<b style='font-size:13px;'>Resumen de la ruta</b>")
        title_l.setStyleSheet(f"color:{_HDR_FG};")
        left_vl.addWidget(title_l)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        inner = QLabel("<br>".join(resumen_lines))
        inner.setWordWrap(True)
        inner.setTextFormat(Qt.RichText)
        inner.setStyleSheet(
            f"color:{_PROD_FG}; background:{_HDR_BG};"
            "border-radius:8px; padding:10px; font-size:11px; line-height:1.5;"
        )
        inner.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(inner)
        left_vl.addWidget(scroll, 1)

        open_btn = QPushButton("🗺  Abrir en navegador")
        open_btn.setStyleSheet(
            f"background:{_T('GOLD',PRIMARY)}; color:#111; font-weight:bold; padding:8px 14px;"
            "border-radius:6px; margin-top:6px;"
        )
        open_btn.clicked.connect(lambda: self._open_url(maps_url))
        left_vl.addWidget(open_btn)

        close_btn = QPushButton("Cerrar")
        close_btn.setStyleSheet("padding:6px 14px; border-radius:6px; margin-top:4px;")
        close_btn.clicked.connect(qr_dlg.accept)
        left_vl.addWidget(close_btn)

        qr_layout.addWidget(left_w, 1)

        # Derecha: QR
        right_vl = QVBoxLayout()
        scan_l = QLabel("Escaneá con el celular:")
        scan_l.setAlignment(Qt.AlignCenter)
        scan_l.setStyleSheet(f"color:{_MUTED_FG}; font-size:11px;")
        right_vl.addWidget(scan_l)
        qr_lbl = QLabel()
        pix = _QPixmap(qr_path)
        qr_lbl.setPixmap(
            pix.scaled(290, 290, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        qr_lbl.setAlignment(Qt.AlignCenter)
        right_vl.addWidget(qr_lbl)
        right_vl.addStretch()
        qr_layout.addLayout(right_vl)

        qr_dlg.exec()

        try:
            os.remove(qr_path)
        except Exception:
            pass

    def _open_url(self, url: str):
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            pass

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
        venta = vm.get_venta_detalle(int(venta_id))
        items = (venta or {}).get("items") or []

        # Si ya fue entregada, los items tienen entrega_local guardado → no preguntar
        ya_entregada = bool(
            (venta or {}).get("entrega_entregado")
            or all(it.get("entrega_local_entregado") for it in items if items)
        )

        if ya_entregada and items:
            default_local = (venta or {}).get("local") or self.local or ""
            items_origen = {
                idx: (it.get("entrega_local") or it.get("stock_local") or default_local)
                for idx, it in enumerate(items)
            }
        else:
            # Pendiente de entrega → preguntar de qué local sale cada producto
            items_origen = self._seleccionar_origen_remito(int(venta_id))
            if items_origen is None:
                return

        ok, path_or_msg = vm.generar_pdf_remito(
            int(venta_id), items_origen=items_origen
        )
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

            combo = _styled_combo(allowed, default_local)
            combo.setFixedWidth(140)
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

        if dlg.exec() != QDialog.Accepted:
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
    data_loaded = Signal(int, list, list, list)

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
        ventas = [
            v
            for v in (ventas or [])
            if int(v.get("incluye_envio") or 0) == 1
            and (v.get("local") or "").strip() != "Pagina Web"
        ]
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
