from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LoginWindow(QWidget):
    def __init__(self, on_success_callback):
        super().__init__()
        self.on_success_callback = on_success_callback
        self.setWindowTitle("Manarey - Login")
        self.resize(400, 300)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        # Title
        title = QLabel("MANAREY STOCK")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setStyleSheet("color: #C9A040;")
        layout.addWidget(title)

        # Username field
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuario")
        self.username_input.setStyleSheet(
            "padding: 10px; font-size: 16px; border-radius: 5px; border: 1px solid #ccc;"
        )
        layout.addWidget(self.username_input)

        # Password field
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Contraseña")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(
            "padding: 10px; font-size: 16px; border-radius: 5px; border: 1px solid #ccc;"
        )
        layout.addWidget(self.password_input)

        # Login button
        login_btn = QPushButton("INGRESAR")
        login_btn.setStyleSheet(
            "background-color: #C9A040; color: white; padding: 12px; "
            "font-size: 16px; font-weight: bold; border-radius: 5px;"
        )
        login_btn.clicked.connect(self._handle_login)
        layout.addWidget(login_btn)

        self.setLayout(layout)

    def _handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "Error", "Por favor complete todos los campos")
            return

        # Authenticate user (replace with actual authentication)
        if username == "admin" and password == "admin":
            self.on_success_callback("admin")
        else:
            QMessageBox.warning(self, "Error", "Credenciales incorrectas")
