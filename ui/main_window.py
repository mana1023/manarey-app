from PySide6.QtWidgets import QMainWindow, QStackedWidget

from ui.login_window import LoginWindow
from ui.menu_window import MenuWindow
from ui.stock_view import StockView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sistema de Gestión Manarey")
        self.resize(1024, 768)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Initialize windows
        self.login_window = LoginWindow(self.handle_login_success)
        self.menu_window = None
        self.stock_view = None

        self.stacked_widget.addWidget(self.login_window)

    def handle_login_success(self, user_role):
        """Callback when login is successful"""
        if self.menu_window is None:
            self.menu_window = MenuWindow(
                user_role,
                on_stock_click=self.show_stock_view,
                on_logout=self.show_login_view,
            )
            self.stacked_widget.addWidget(self.menu_window)

        if self.stacked_widget.currentWidget() != self.menu_window:
            self.stacked_widget.setCurrentWidget(self.menu_window)

    def show_stock_view(self):
        """Show stock management view"""
        if self.stock_view is None:
            self.stock_view = StockView(
                location="Principal",
                user_role="admin",  # You should pass the actual user role
                on_back=self.show_menu_view,
            )
            self.stacked_widget.addWidget(self.stock_view)

        self.stacked_widget.setCurrentWidget(self.stock_view)

    def show_menu_view(self):
        """Return to main menu"""
        self.stacked_widget.setCurrentWidget(self.menu_window)

    def show_login_view(self):
        """Return to login screen"""
        self.stacked_widget.setCurrentWidget(self.login_window)
