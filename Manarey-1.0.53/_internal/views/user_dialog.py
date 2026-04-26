"""Diálogo simple para agregar o editar usuarios (solo PostgreSQL/Supabase)."""
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from models import auth as auth_mod
from models import user_model

logger = logging.getLogger(__name__)


class UserDialog(QDialog):
    """Dialog de administración de usuarios."""

    def __init__(self, parent=None, username=None, edit_mode=False):
        super().__init__(parent)
        self.username = username
        self.edit_mode = edit_mode

        self.setWindowTitle("Editar Usuario" if edit_mode else "Agregar Usuario")
        self.setMinimumWidth(420)

        self._build_ui()

        if self.edit_mode and self.username:
            self.load_user_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Nombre de usuario")
        self.username_edit.setEnabled(not self.edit_mode)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Contraseña (deja vacío para no cambiar)")
        self.password_edit.setEchoMode(QLineEdit.Password)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre completo")

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("correo@ejemplo.com")

        self.role_combo = QComboBox()
        self.role_combo.addItem("Vendedor", "vendedor")
        self.role_combo.addItem("Administrador", "admin")

        self.local_combo = QComboBox()
        for local in ("Cane", "Vidriera", "Longchamps", "Glew"):
            self.local_combo.addItem(local, local)

        self.active_check = QCheckBox("Usuario activo")
        self.active_check.setChecked(True)

        form.addRow("Usuario*:", self.username_edit)
        form.addRow("Contraseña:" + ("" if self.edit_mode else "*"), self.password_edit)
        form.addRow("Nombre*:", self.name_edit)
        form.addRow("Email:", self.email_edit)
        form.addRow("Rol*:", self.role_combo)
        form.addRow("Local*:", self.local_combo)
        form.addRow("", self.active_check)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        save_btn = QPushButton("Guardar")
        cancel_btn = QPushButton("Cancelar")
        save_btn.clicked.connect(self.save_user)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def load_user_data(self):
        try:
            user = user_model.get_user_by_username(self.username)
            if not user:
                QMessageBox.warning(self, "Error", "Usuario no encontrado")
                self.reject()
                return
            self.username_edit.setText(user.get("username", ""))
            role_index = self.role_combo.findData(user.get("role", "vendedor"))
            if role_index >= 0:
                self.role_combo.setCurrentIndex(role_index)
            local_index = self.local_combo.findData(user.get("local", ""))
            if local_index >= 0:
                self.local_combo.setCurrentIndex(local_index)
        except Exception as e:
            logger.error("Error cargando usuario: %s", e)
            QMessageBox.critical(self, "Error", f"No se pudo cargar el usuario: {e}")
            self.reject()

    def _validate(self) -> bool:
        if not self.username_edit.text().strip():
            QMessageBox.warning(self, "Validación", "El usuario es obligatorio")
            return False
        if not self.edit_mode and not self.password_edit.text().strip():
            QMessageBox.warning(self, "Validación", "La contraseña es obligatoria")
            return False
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validación", "El nombre es obligatorio")
            return False
        email = self.email_edit.text().strip()
        if email and "@" not in email:
            QMessageBox.warning(self, "Validación", "El correo no es válido")
            return False
        return True

    def save_user(self):
        if not self._validate():
            return
        try:
            user_data = {
                "username": self.username_edit.text().strip(),
                "role": self.role_combo.currentData(),
                "local": self.local_combo.currentData(),
            }
            password = self.password_edit.text().strip()
            if password:
                user_data["password"] = auth_mod.hash_password(password)

            if self.edit_mode:
                if user_model.update_user_dual(self.username, user_data):
                    QMessageBox.information(self, "Éxito", "Usuario actualizado")
                    self.accept()
                else:
                    QMessageBox.warning(self, "Error", "No se pudo actualizar")
            else:
                if user_model.get_user_by_username(user_data["username"]):
                    QMessageBox.warning(
                        self, "Error", "Ya existe un usuario con ese nombre"
                    )
                    return
                if user_model.add_user_dual(user_data):
                    QMessageBox.information(self, "Éxito", "Usuario agregado")
                    self.accept()
                else:
                    QMessageBox.warning(self, "Error", "No se pudo agregar")
        except Exception as e:
            logger.error("Error guardando usuario: %s", e)
            QMessageBox.critical(self, "Error", f"No se pudo guardar el usuario: {e}")
