# views/settings_dialog.py
import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustes de Pantalla")
        self.setModal(True)
        self.setMinimumWidth(350)
        self.setStyleSheet(
            """
            QDialog { background: #1a1a22; color: white; }
            QLabel { color: #e0e0e0; font-family: 'Segoe UI'; }
            QComboBox { 
                padding: 8px; 
                border-radius: 6px; 
                background: #2a2a35; 
                color: white; 
                border: 1px solid #444;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
        """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        # Title
        title = QLabel("Configuración de Resolución")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "Elige el tamaño de la interfaz. Los cambios se aplicarán al reiniciar la aplicación."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a0a0b0; font-size: 12px;")
        layout.addWidget(desc)

        # Scale Selector
        layout.addWidget(QLabel("Escala de interfaz:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(
            [
                "Automático (Recomendado)",
                "100% (Pequeño - 1366x768)",
                "125% (Mediano)",
                "150% (Grande)",
                "175% (Muy Grande)",
            ]
        )
        layout.addWidget(self.scale_combo)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Guardar y Reiniciar")
        btn_save.setStyleSheet("background: #C9A040; color: #1a1a22;")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self.save_and_close)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(
            "background: transparent; color: #a0a0b0; border: 1px solid #444;"
        )
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        self.load_current_setting()

    def get_prefs_path(self):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, "Manarey", "user_prefs.json")
        return os.path.join(
            os.path.expanduser("~"), ".manarey_prefs", "user_prefs.json"
        )

    def load_current_setting(self):
        try:
            path = self.get_prefs_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    scale = data.get("scale_preference", "auto")

                    map_val = {"auto": 0, "1.0": 1, "1.25": 2, "1.5": 3, "1.75": 4}
                    self.scale_combo.setCurrentIndex(map_val.get(str(scale), 0))
        except Exception:
            pass

    def save_and_close(self):
        idx = self.scale_combo.currentIndex()
        val_map = {0: "auto", 1: "1.0", 2: "1.25", 3: "1.5", 4: "1.75"}
        choice = val_map.get(idx, "auto")

        try:
            path = self.get_prefs_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)

            data = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except:
                    pass

            data["scale_preference"] = choice

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            QMessageBox.information(
                self,
                "Guardado",
                "La configuración se ha guardado.\nPor favor reinicia la aplicación para aplicar los cambios.",
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo guardar la configuración: {e}"
            )
