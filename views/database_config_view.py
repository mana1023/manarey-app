# views/database_config_view.py
# Ventana de configuración de base de datos (SQLite local vs PostgreSQL/Supabase)

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
)


class DatabaseConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Base de Datos - Manarey")
        self.setModal(True)
        self.setMinimumSize(700, 600)
        self.config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config.json"
        )
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Título
        title = QLabel("🗄️ Configuración de Base de Datos")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #FFC107; margin-bottom: 10px;")
        layout.addWidget(title)

        # Descripción
        desc = QLabel(
            "Elegí dónde querés almacenar los datos de Manarey.\n"
            "Podés cambiar esto en cualquier momento desde Configuración."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #E5E7EB; font-size: 13px; margin-bottom: 15px;")
        layout.addWidget(desc)

        # Opciones de base de datos
        self.db_group = QButtonGroup(self)

        # Opción 1: SQLite Local
        self.radio_sqlite = QRadioButton("🖥️ Base de Datos Local (SQLite)")
        self.radio_sqlite.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.radio_sqlite.setStyleSheet("color: white; padding: 10px;")
        self.db_group.addButton(self.radio_sqlite, 1)
        layout.addWidget(self.radio_sqlite)

        sqlite_info = QLabel(
            "✓ Cada computadora tiene su propia base de datos\n"
            "✓ No requiere internet\n"
            "✓ Velocidad máxima\n"
            "✗ No se sincroniza entre PCs"
        )
        sqlite_info.setStyleSheet(
            "color: #94A3B8; font-size: 11px; margin-left: 30px; margin-bottom: 10px;"
        )
        layout.addWidget(sqlite_info)

        # Separador
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setStyleSheet("background: #374151; margin: 10px 0;")
        layout.addWidget(line1)

        # Opción 2: PostgreSQL/Supabase
        self.radio_postgres = QRadioButton(
            "☁️ Base de Datos en la Nube (PostgreSQL/Supabase)"
        )
        self.radio_postgres.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.radio_postgres.setStyleSheet("color: white; padding: 10px;")
        self.db_group.addButton(self.radio_postgres, 2)
        layout.addWidget(self.radio_postgres)

        postgres_info = QLabel(
            "✓ Sincronización automática entre todas las PCs\n"
            "✓ Acceso desde cualquier lugar\n"
            "✓ Backups automáticos\n"
            "✓ Plan gratuito: 500MB (≈200,000 productos)"
        )
        postgres_info.setStyleSheet(
            "color: #94A3B8; font-size: 11px; margin-left: 30px; margin-bottom: 10px;"
        )
        layout.addWidget(postgres_info)

        # Campo para URL de conexión
        url_label = QLabel("URL de Conexión PostgreSQL:")
        url_label.setStyleSheet("color: #FFC107; font-weight: bold; margin-top: 10px;")
        layout.addWidget(url_label)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "postgresql://user:password@host:5432/database"
        )
        self.url_input.setStyleSheet(
            """
            QLineEdit {
                background: #1F2937;
                color: white;
                border: 2px solid #374151;
                border-radius: 8px;
                padding: 12px;
                font-size: 12px;
                font-family: 'Consolas', monospace;
            }
            QLineEdit:focus {
                border-color: #FFC107;
            }
        """
        )
        self.url_input.setEnabled(False)
        layout.addWidget(self.url_input)

        # Instrucciones de Supabase
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(150)
        instructions.setStyleSheet(
            """
            QTextEdit {
                background: #111827;
                color: #D1D5DB;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 10px;
                font-size: 11px;
            }
        """
        )
        instructions.setHtml(
            """
        <b style="color: #FFC107;">📝 Cómo obtener la URL de Supabase (GRATIS):</b><br><br>
        <b>1.</b> Entrá a <a href="https://supabase.com" style="color: #60A5FA;">https://supabase.com</a> y creá una cuenta (gratis)<br>
        <b>2.</b> Hacé clic en "New Project" (Nuevo Proyecto)<br>
        <b>3.</b> Elegí un nombre, contraseña y región (usa "South America" si está disponible)<br>
        <b>4.</b> Esperá 2 minutos a que se cree el proyecto<br>
        <b>5.</b> Andá a <b>Settings → Database → Connection String → URI</b><br>
        <b>6.</b> Copiá la URL completa (postgresql://postgres.xxxxx...)<br>
        <b>7.</b> Pegala arriba y hacé clic en Guardar<br><br>
        <b style="color: #10B981;">✓ Listo! Todas las PCs con esta URL compartirán la misma base de datos</b>
        """
        )
        layout.addWidget(instructions)

        # Conectar señales
        self.radio_sqlite.toggled.connect(self.on_type_changed)
        self.radio_postgres.toggled.connect(self.on_type_changed)

        # Botones
        buttons = QHBoxLayout()
        buttons.addStretch()

        test_btn = QPushButton("🔌 Probar Conexión")
        test_btn.setStyleSheet(
            """
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #2563EB;
            }
            QPushButton:disabled {
                background: #374151;
                color: #6B7280;
            }
        """
        )
        test_btn.clicked.connect(self.test_connection)
        buttons.addWidget(test_btn)

        save_btn = QPushButton("💾 Guardar y Continuar")
        save_btn.setStyleSheet(
            """
            QPushButton {
                background: #10B981;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #059669;
            }
        """
        )
        save_btn.clicked.connect(self.save_and_close)
        buttons.addWidget(save_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setStyleSheet(
            """
            QPushButton {
                background: #374151;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #4B5563;
            }
        """
        )
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        layout.addLayout(buttons)

        # Estilo general
        self.setStyleSheet(
            """
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1F2937, stop:1 #111827);
            }
        """
        )

    def on_type_changed(self):
        is_postgres = self.radio_postgres.isChecked()
        self.url_input.setEnabled(is_postgres)

    def load_config(self):
        """Carga configuración existente"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    db_type = config.get("database_type", "sqlite")
                    db_url = config.get("database_url", "")

                    if db_type == "postgresql" and db_url:
                        self.radio_postgres.setChecked(True)
                        self.url_input.setText(db_url)
                    else:
                        self.radio_sqlite.setChecked(True)
            else:
                self.radio_sqlite.setChecked(True)
        except Exception:
            self.radio_sqlite.setChecked(True)

    def test_connection(self):
        """Prueba la conexión a PostgreSQL"""
        if not self.radio_postgres.isChecked():
            QMessageBox.information(
                self, "Info", "SQLite local no requiere prueba de conexión"
            )
            return

        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Ingresá la URL de conexión primero")
            return

        try:
            import psycopg2

            conn = psycopg2.connect(url)
            conn.close()
            QMessageBox.information(
                self,
                "✅ Conexión Exitosa",
                "La conexión a PostgreSQL funciona correctamente!\n\n"
                "Podés guardar y continuar.",
            )
        except ImportError:
            QMessageBox.warning(
                self,
                "⚠️ Falta Dependencia",
                "Necesitás instalar psycopg2-binary para usar PostgreSQL.\n\n"
                "Ejecutá en terminal:\n"
                "pip install psycopg2-binary",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "❌ Error de Conexión",
                f"No se pudo conectar a PostgreSQL:\n\n{str(e)}\n\n"
                "Verificá que la URL sea correcta.",
            )

    def save_and_close(self):
        """Guarda configuración y cierra"""
        config = {}

        if self.radio_postgres.isChecked():
            url = self.url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "Error", "Ingresá la URL de PostgreSQL")
                return
            if not url.startswith("postgresql://") and not url.startswith(
                "postgres://"
            ):
                QMessageBox.warning(
                    self,
                    "Error",
                    "La URL debe comenzar con postgresql:// o postgres://",
                )
                return
            config["database_type"] = "postgresql"
            config["database_url"] = url

            # Advertencia de migración
            reply = QMessageBox.question(
                self,
                "⚠️ Migración de Datos",
                "Si ya tenés datos en SQLite local, necesitarás migrarlos.\n\n"
                "¿Querés continuar con PostgreSQL?\n\n"
                "(Se creará una guía de migración después)",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        else:
            config["database_type"] = "sqlite"
            config["database_url"] = ""

        # Guardar
        try:
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)

            # Establecer variable de entorno para esta sesión
            if config["database_type"] == "postgresql":
                os.environ["DATABASE_URL"] = config["database_url"]
            else:
                os.environ.pop("DATABASE_URL", None)

            QMessageBox.information(
                self,
                "✅ Guardado",
                "Configuración guardada correctamente.\n\n"
                "Reiniciá la aplicación para aplicar los cambios.",
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar: {str(e)}")


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = DatabaseConfigDialog()
    dialog.exec()
