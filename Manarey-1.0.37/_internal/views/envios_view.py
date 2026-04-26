# views/envios_view.py
import os
import platform
import subprocess

from PyQt5.QtCore import QAbstractTableModel, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont
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

BG = "#0f172a"
BG_ALT = "#111827"
TEXT = "#e5e7eb"
PRIMARY = "#ffc107"
GREEN = "#10b981"


class EnviosTableModel(QAbstractTableModel):
    HEADERS = [
        "Remito",
        "Fecha",
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
                return str(v.get("local") or "")
            if col == 3:
                return str(v.get("entrega_local") or "")
            if col == 4:
                return str(v.get("cliente_nombre") or "")
            if col == 5:
                return str(v.get("_direccion_fmt") or "")
            if col == 6:
                return str(v.get("_pago_envio_fmt") or "")
            if col == 7:
                return ""

        if role == Qt.TextAlignmentRole:
            if col in (0, 2, 3, 6):
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
        self.setWindowTitle("Envios")
        self.resize(1100, 780)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Envios")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet(f"color:{PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        if self.back_command:
            back_btn = QPushButton("Volver")
            back_btn.clicked.connect(self.back_command)
            header.addWidget(back_btn)
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
        pendientes_label.setStyleSheet(f"color:{TEXT};")
        pendientes_header.addWidget(pendientes_label)
        pendientes_header.addStretch()
        self.print_all_btn = QPushButton("Imprimir todo")
        self.print_all_btn.clicked.connect(self._on_bulk_print_clicked)
        pendientes_header.addWidget(self.print_all_btn)
        layout.addLayout(pendientes_header)

        self.table_pendientes = QTableView()
        self.pendientes_model = EnviosTableModel([], self)
        self.table_pendientes.setModel(self.pendientes_model)
        self._setup_table(self.table_pendientes)
        self.table_pendientes.clicked.connect(self._on_pendientes_cell_clicked)
        layout.addWidget(self.table_pendientes)

        entregados_label = QLabel("Entregados")
        entregados_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        entregados_label.setStyleSheet(f"color:{TEXT};")
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
        table.verticalHeader().setDefaultSectionSize(38)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setStyleSheet(
            f"""
            QTableView {{
                background: {BG};
                alternate-background-color: {BG_ALT};
                color: {TEXT};
                gridline-color: #334155;
                border: 1px solid #1f2937;
                border-radius: 10px;
            }}
            QTableView::item {{
                color: {TEXT};
                padding: 6px 10px;
                background: {BG};
            }}
            QTableView::item:alternate {{
                background: {BG_ALT};
            }}
            QTableView::item:selected {{
                background: {PRIMARY};
                color: #111827;
            }}
            QHeaderView::section {{
                background: {BG};
                color: {TEXT};
                font-weight: 700;
                padding: 10px;
                border: none;
                border-bottom: 2px solid {PRIMARY};
            }}
        """
        )
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Interactive)
        header.resizeSection(7, 220)

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

    def _on_envios_loaded(self, load_id, pendientes, entregados):
        if load_id != self._current_load_id:
            return
        self._fill_table(self.table_pendientes, pendientes, entregado=False)
        self._fill_table(self.table_entregados, entregados, entregado=True)

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
            v["_pago_envio_fmt"] = f"Si ({fp_envio})" if fp_envio else "No"
            rows.append(v)

        model = (
            self.pendientes_model
            if table is self.table_pendientes
            else self.entregados_model
        )
        model.set_rows(rows)

        # Botones de accion en columna 7
        for row_idx, venta in enumerate(rows):
            actions = QWidget()
            actions.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(actions)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            btn_print = QPushButton("Imprimir")
            btn_print.setStyleSheet(
                "background:#1f2937;color:#e5e7eb;font-weight:800;"
                "border-radius:8px;padding:6px 12px;"
            )
            btn_print.setMinimumWidth(90)
            btn_print.clicked.connect(
                lambda _=None, vid=venta.get("id"): self.imprimir_remito(vid)
            )
            row_layout.addWidget(btn_print)

            if entregado:
                btn_cancel = QPushButton("Anular entrega")
                btn_cancel.setStyleSheet(
                    "background:#dc2626;color:white;font-weight:700;"
                )
                btn_cancel.clicked.connect(
                    lambda _=None, vid=venta.get("id"): self.anular_entrega(vid)
                )
                row_layout.addWidget(btn_cancel)
            else:
                btn_deliver = QPushButton("Entregar")
                btn_deliver.setStyleSheet(
                    "background:#16a34a;color:white;font-weight:800;"
                    "border-radius:8px;padding:6px 12px;"
                )
                btn_deliver.setMinimumWidth(90)
                btn_deliver.clicked.connect(
                    lambda _=None, vid=venta.get("id"): self.marcar_entregado(vid)
                )
                row_layout.addWidget(btn_deliver)

            row_layout.addStretch()
            table.setIndexWidget(model.index(row_idx, 7), actions)

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
        self.load_data()

    def _seleccionar_locales_entrega(self, items: list, locals_list: list, venta: dict):
        dlg = QDialog(self)
        dlg.setWindowTitle("Entregar - Seleccionar local")
        dlg.resize(1200, 680)
        dlg.setMinimumSize(1100, 620)
        lay = QVBoxLayout(dlg)

        info = QLabel("Selecciona el local desde donde sale cada producto:")
        info.setStyleSheet(f"color:{TEXT}; font-weight:700;")
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
        table.setRowCount(len(items))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setStyleSheet(
            "QTableWidget{background:#111827;color:#e5e7eb;border:1px solid #1f2937;border-radius:8px;}"
            "QHeaderView::section{background:#0b1220;color:#e5e7eb;font-weight:700;padding:6px;border:none;}"
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

        combo_refs = []
        for row, it in enumerate(items):
            nombre = it.get("producto_nombre") or it.get("nombre") or "Producto"
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

            combo = QComboBox()
            combo.addItems(locals_list or [""])
            if default_local in locals_list:
                combo.setCurrentText(default_local)
            combo.setFixedWidth(120)
            table.setCellWidget(row, 7, combo)
            combo_refs.append((combo, it))

        lay.addWidget(table)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Confirmar")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        lay.addWidget(btns)

        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec_() != QDialog.Accepted:
            return None

        selections = []
        for combo, it in combo_refs:
            local_sel = combo.currentText()
            selections.append(
                {
                    "detalle_id": it.get("id"),
                    "producto_id": it.get("producto_id"),
                    "cantidad": it.get("cantidad"),
                    "local": local_sel,
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


class EnviosLoadWorker(QThread):
    data_loaded = pyqtSignal(int, list, list)

    def __init__(self, search: str, load_id: int, parent=None):
        super().__init__(parent)
        self.search = search
        self.load_id = load_id

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            ventas = vhm.get_ventas_por_local(
                "Todos", filtro_fecha="todo", search=self.search
            )
        except Exception:
            ventas = []
        ventas = [v for v in (ventas or []) if int(v.get("incluye_envio") or 0) == 1]
        pendientes = []
        entregados = []
        for v in ventas:
            if int(v.get("entrega_entregado") or 0) == 1:
                entregados.append(v)
            else:
                pendientes.append(v)

        pendientes.sort(key=lambda v: str(v.get("fecha") or ""), reverse=True)
        entregados.sort(
            key=lambda v: str(v.get("entrega_fecha") or v.get("fecha") or ""),
            reverse=True,
        )
        try:
            if self.isInterruptionRequested():
                return
            self.data_loaded.emit(self.load_id, pendientes, entregados)
        except Exception:
            pass
