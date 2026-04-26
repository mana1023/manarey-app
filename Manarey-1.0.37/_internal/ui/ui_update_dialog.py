"""
ui_update_dialog.py - Diálogo de actualización integrado en la app
"""

import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class UpdateDialog(QDialog):
    """Diálogo de actualización con interfaz integrada en la app"""
    
    closed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Actualización Disponible")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(430)
        self.cancelled = False
        self._setup_ui()
        self._apply_styling()
    
    def _setup_ui(self):
        """Construir interfaz"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Título
        title = QLabel("Actualización Disponible")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #C9A040;")
        layout.addWidget(title)
        
        # Información de versión
        self.info_label = QLabel("Detectando actualización...")
        self.info_label.setFont(QFont("Segoe UI", 11))
        self.info_label.setStyleSheet("color: #E0E0E0;")
        layout.addWidget(self.info_label)
        
        # Antes de actualizar
        pre_label = QLabel("Antes de actualizar:")
        pre_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pre_label.setStyleSheet("color: #C9A040;")
        layout.addWidget(pre_label)

        self.pre_update = QTextEdit()
        self.pre_update.setReadOnly(True)
        self.pre_update.setMaximumHeight(110)
        self.pre_update.setFont(QFont("Segoe UI", 9))
        self.pre_update.setStyleSheet("background-color: #111217; color: #E0E0E0; border: 1px solid #444; border-radius: 4px;")
        self.pre_update.setPlainText(
            "1) Cierra Manarey en todas las PCs antes de instalar.
"
            "2) Asegurate de tener internet estable.
"
            "3) No apagues la PC durante la instalacion.
"
            "4) Si estas en una venta en curso, finalizala antes de actualizar.
"
        )
        layout.addWidget(self.pre_update)
        
        # Notas de cambios
        notes_label = QLabel("Cambios Incluidos:")
        notes_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        notes_label.setStyleSheet("color: #C9A040;")
        layout.addWidget(notes_label)
        
        self.changelog = QTextEdit()
        self.changelog.setReadOnly(True)
        self.changelog.setMaximumHeight(120)
        self.changelog.setFont(QFont("Segoe UI", 10))
        self.changelog.setStyleSheet(
            "background-color: #1a1a20; "
            "color: #E0E0E0; "
            "border: 1px solid #444; "
            "border-radius: 4px;"
        )
        layout.addWidget(self.changelog)
        
        # Barra de progreso (inicialmente oculta)
        self.progress_label = QLabel("Descargando...")
        self.progress_label.setFont(QFont("Segoe UI", 10))
        self.progress_label.setStyleSheet("color: #999;")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(self._get_progress_style())
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Botones
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.btn_install = QPushButton("Instalar Ahora")
        self.btn_install.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.btn_install.setMinimumWidth(150)
        self.btn_install.setStyleSheet(self._get_button_style_primary())
        self.btn_install.clicked.connect(self._on_install)
        button_layout.addWidget(self.btn_install)
        
        self.btn_later = QPushButton("Más Tarde")
        self.btn_later.setFont(QFont("Segoe UI", 11))
        self.btn_later.setMinimumWidth(120)
        self.btn_later.setStyleSheet(self._get_button_style_secondary())
        self.btn_later.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.btn_later)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _apply_styling(self):
        """Aplicar estilos a la ventana"""
        self.setStyleSheet(
            "QDialog { "
            "background-color: #0f0f14; "
            "border: 1px solid #333; "
            "border-radius: 8px; "
            "}"
        )
    
    def _get_button_style_primary(self):
        """Estilo para botón primario"""
        return (
            "QPushButton { "
            "background-color: #C9A040; "
            "color: #000; "
            "border: none; "
            "border-radius: 6px; "
            "padding: 10px 20px; "
            "font-weight: bold; "
            "} "
            "QPushButton:hover { "
            "background-color: #D4B555; "
            "} "
            "QPushButton:pressed { "
            "background-color: #B89030; "
            "} "
            "QPushButton:disabled { "
            "background-color: #666; "
            "color: #999; "
            "}"
        )
    
    def _get_button_style_secondary(self):
        """Estilo para botón secundario"""
        return (
            "QPushButton { "
            "background-color: #333; "
            "color: #E0E0E0; "
            "border: 1px solid #555; "
            "border-radius: 6px; "
            "padding: 10px 20px; "
            "} "
            "QPushButton:hover { "
            "background-color: #444; "
            "border: 1px solid #666; "
            "} "
            "QPushButton:pressed { "
            "background-color: #222; "
            "}"
        )
    
    def _get_progress_style(self):
        """Estilo para barra de progreso"""
        return (
            "QProgressBar { "
            "border: 1px solid #444; "
            "border-radius: 4px; "
            "background-color: #1a1a20; "
            "height: 25px; "
            "} "
            "QProgressBar::chunk { "
            "background-color: #C9A040; "
            "border-radius: 3px; "
            "}"
        )
    
    def set_update_info(self, version, changelog, mandatory=False):
        """Establecer información de actualización"""
        self.info_label.setText(f"Nueva versión disponible: {version}")
        self.changelog.setPlainText(changelog or "Mejoras de rendimiento, estabilidad y correcciones.")
        
        if mandatory:
            self.btn_later.setEnabled(False)
            self.btn_later.setText("Obligatoria")
            warn_label = QLabel("⚠️ Esta actualización es obligatoria")
            warn_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")
            # Insertar advertencia en el changelog
            self.changelog.insertPlainText("\n\n⚠️ ACTUALIZACIÓN OBLIGATORIA\nDebes instalarla para continuar usando la app.")
    
    def show_progress(self):
        """Mostrar barra de progreso"""
        self.btn_install.setEnabled(False)
        self.btn_later.setEnabled(False)
        self.progress_label.setVisible(True)
        self.progress_bar.setVisible(True)
    
    def update_progress(self, done, total, stage="download"):
        """Actualizar barra de progreso"""
        if total > 0:
            pct = int(done * 100 / total)
            self.progress_bar.setValue(pct)
            
            if stage == "download":
                mb_done = done // (1024*1024)
                mb_total = total // (1024*1024)
                self.progress_label.setText(f"Descargando... {pct}% ({mb_done} MB de {mb_total} MB)")
            elif stage == "extract":
                self.progress_label.setText(f"Instalando... {pct}% ({done} de {total} archivos)")
    
    def _on_install(self):
        """Botón instalar"""
        self.accept()
    
    def _on_cancel(self):
        """Botón cancelar/más tarde"""
        self.cancelled = True
        self.reject()
    
    def closeEvent(self, event):
        """Al cerrar la ventana"""
        self.closed.emit()
        super().closeEvent(event)


class UpdateProgressDialog(QDialog):
    """Diálogo solo de progreso para instalación"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instalando Actualización")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMinimumHeight(200)
        self.cancelled = False
        self._setup_ui()
        self._apply_styling()
    
    def _setup_ui(self):
        """Construir interfaz"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Título
        title = QLabel("Instalando Actualización")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #C9A040;")
        layout.addWidget(title)
        
        # Etapa y porcentaje
        self.status_label = QLabel("Descargando archivos...")
        self.status_label.setFont(QFont("Segoe UI", 11))
        self.status_label.setStyleSheet("color: #E0E0E0;")
        layout.addWidget(self.status_label)
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(self._get_progress_style())
        layout.addWidget(self.progress_bar)
        
        # Información
        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Segoe UI", 10))
        self.info_label.setStyleSheet("color: #999;")
        layout.addWidget(self.info_label)
        
        layout.addStretch()
        
        # Botón cancelar
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setFont(QFont("Segoe UI", 11))
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.setStyleSheet(self._get_button_style())
        self.btn_cancel.clicked.connect(self._on_cancel)
        layout.addWidget(self.btn_cancel)
        
        self.setLayout(layout)
    
    def _apply_styling(self):
        """Aplicar estilos"""
        self.setStyleSheet(
            "QDialog { "
            "background-color: #0f0f14; "
            "border: 1px solid #333; "
            "border-radius: 8px; "
            "}"
        )
    
    def _get_button_style(self):
        """Estilo de botón"""
        return (
            "QPushButton { "
            "background-color: #333; "
            "color: #E0E0E0; "
            "border: 1px solid #555; "
            "border-radius: 6px; "
            "padding: 8px 16px; "
            "} "
            "QPushButton:hover { "
            "background-color: #444; "
            "} "
            "QPushButton:pressed { "
            "background-color: #222; "
            "}"
        )
    
    def _get_progress_style(self):
        """Estilo de progreso"""
        return (
            "QProgressBar { "
            "border: 1px solid #444; "
            "border-radius: 4px; "
            "background-color: #1a1a20; "
            "height: 25px; "
            "} "
            "QProgressBar::chunk { "
            "background-color: #C9A040; "
            "border-radius: 3px; "
            "}"
        )
    
    def update_progress(self, done, total, stage="download"):
        """Actualizar progreso"""
        if total > 0:
            pct = int(done * 100 / total)
            self.progress_bar.setValue(pct)
            
            if stage == "download":
                self.status_label.setText("Descargando actualización...")
                mb_done = done // (1024*1024)
                mb_total = total // (1024*1024)
                self.info_label.setText(f"{pct}% ({mb_done} MB de {mb_total} MB)")
            elif stage == "extract":
                self.status_label.setText("Instalando archivos...")
                self.info_label.setText(f"{pct}% ({done} de {total} archivos)")
    
    def _on_cancel(self):
        """Cancelar"""
        self.cancelled = True
        self.reject()
