from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class MenuWindow(QWidget):
    def __init__(self, user_role, on_stock_click, on_logout):
        super().__init__()
        self._user_role = user_role
        self._on_stock_click = on_stock_click
        self._on_logout = on_logout
        self._setup_ui(user_role, on_stock_click, on_logout)

    def _setup_ui(self, user_role, on_stock_click, on_logout):
        layout = QVBoxLayout()
        layout.setSpacing(30)
        layout.setContentsMargins(20, 20, 20, 20)

        # Welcome message
        welcome = QLabel(f"Bienvenido, {user_role.capitalize()}")
        welcome.setFont(QFont("Arial", 20))
        welcome.setStyleSheet("color: #C9A040;")
        layout.addWidget(welcome, alignment=Qt.AlignCenter)

        # Spacer
        layout.addSpacing(20)

        # Stock button
        stock_btn = QPushButton("GESTIÓN DE STOCK")
        stock_btn.setFont(QFont("Arial", 14, QFont.Bold))
        stock_btn.setMinimumHeight(60)
        stock_btn.setStyleSheet(
            "background-color: #C9A040; color: #000; padding: 15px; "
            "font-size: 18px; font-weight: bold; border-radius: 8px;"
        )
        stock_btn.clicked.connect(on_stock_click)
        layout.addWidget(stock_btn)

        # Reports button (only for admin)
        if user_role == "admin":
            reports_btn = QPushButton("INFORMES")
            reports_btn.setFont(QFont("Arial", 14, QFont.Bold))
            reports_btn.setMinimumHeight(60)
            reports_btn.setStyleSheet(
                "background-color: #C9A040; color: #000; padding: 15px; "
                "font-size: 18px; font-weight: bold; border-radius: 8px;"
            )
            layout.addWidget(reports_btn)

        # Spacer
        layout.addStretch()

        # Bottom buttons row
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        # Logout button
        logout_btn = QPushButton("CERRAR SESIÓN")
        logout_btn.setFont(QFont("Arial", 10, QFont.Bold))
        logout_btn.setMinimumHeight(40)
        logout_btn.setStyleSheet(
            "background-color: #8B0000; color: white; padding: 8px; "
            "font-size: 11px; border-radius: 5px;"
        )
        logout_btn.clicked.connect(on_logout)
        bottom_layout.addWidget(logout_btn)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)
