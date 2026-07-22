# styles.py
from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsEffect


class Colors:
    PRIMARY = "#D6B36A"
    PRIMARY_DARK = "#A88445"
    PRIMARY_LIGHT = "#EBD7AA"
    PRIMARY_SOFT = "#F3E8CF"

    BACKGROUND = "#161314"
    BACKGROUND_ELEVATED = "#1E191B"
    SURFACE = "#241F22"
    SURFACE_LIGHT = "#2E272B"
    OVERLAY = "#393136"

    TEXT_PRIMARY = "#F8F1E7"
    TEXT_SECONDARY = "#D1C2B2"
    TEXT_MUTED = "#A99686"

    SUCCESS = "#5E8B6F"
    SUCCESS_LIGHT = "#7FA28B"
    WARNING = "#C79A52"
    ERROR = "#C56A6A"
    INFO = "#7697B8"

    BORDER = "#43383E"
    BORDER_LIGHT = "#5A4C54"
    BORDER_FOCUS = "#D6B36A"

    TABLE_HEADER = "#2B2428"
    TABLE_ROW_ODD = "#241F22"
    TABLE_ROW_EVEN = "#2A2328"
    TABLE_SELECTION = "#5A4A39"
    TABLE_HIGHLIGHT = "#4B3D31"


CARD_STYLE = f"""
    background: {Colors.SURFACE};
    border: 1px solid {Colors.BORDER};
    border-radius: 18px;
    color: {Colors.TEXT_PRIMARY};
"""

INPUT_STYLE = f"""
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {Colors.SURFACE};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 14px;
        padding: 11px 15px;
        font-size: 14px;
        font-weight: 500;
        selection-background-color: {Colors.TABLE_SELECTION};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {Colors.PRIMARY};
        background: {Colors.SURFACE_LIGHT};
    }}
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        background: {Colors.SURFACE_LIGHT};
        color: {Colors.TEXT_MUTED};
        border-color: {Colors.BORDER};
    }}
"""

BUTTON_PRIMARY = f"""
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {Colors.PRIMARY_LIGHT}, stop:0.55 {Colors.PRIMARY}, stop:1 {Colors.PRIMARY_DARK});
        color: #1D1715;
        border: none;
        border-radius: 16px;
        padding: 13px 24px;
        font-weight: 800;
        font-size: 14px;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {Colors.PRIMARY_SOFT}, stop:0.5 {Colors.PRIMARY_LIGHT}, stop:1 {Colors.PRIMARY});
    }}
    QPushButton:pressed {{
        background: {Colors.PRIMARY_DARK};
    }}
    QPushButton:disabled {{
        background: {Colors.SURFACE_LIGHT};
        color: {Colors.TEXT_MUTED};
    }}
"""

BUTTON_SECONDARY = f"""
    QPushButton {{
        background: rgba(255,255,255,0.02);
        color: {Colors.PRIMARY};
        border: 1px solid {Colors.BORDER_LIGHT};
        border-radius: 16px;
        padding: 11px 20px;
        font-weight: 700;
        font-size: 14px;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background: rgba(214,179,106,0.08);
        border-color: {Colors.PRIMARY};
        color: {Colors.PRIMARY_LIGHT};
    }}
    QPushButton:pressed {{
        background: {Colors.OVERLAY};
        border-color: {Colors.PRIMARY_DARK};
        color: {Colors.PRIMARY_DARK};
    }}
    QPushButton:disabled {{
        background: {Colors.SURFACE};
        color: {Colors.TEXT_MUTED};
        border-color: {Colors.BORDER};
    }}
"""

BUTTON_DANGER = f"""
    QPushButton {{
        background: {Colors.ERROR};
        color: white;
        border: none;
        border-radius: 16px;
        padding: 11px 20px;
        font-weight: 700;
        font-size: 14px;
    }}
    QPushButton:hover {{
        background: #B65555;
    }}
    QPushButton:pressed {{
        background: #984747;
    }}
"""

BUTTON_CIRCLE = f"""
    QPushButton {{
        background: {Colors.PRIMARY};
        color: #1D1715;
        border: none;
        border-radius: 20px;
        width: 40px;
        height: 40px;
        font-weight: 900;
        font-size: 16px;
    }}
    QPushButton:hover {{
        background: {Colors.PRIMARY_LIGHT};
    }}
    QPushButton:pressed {{
        background: {Colors.PRIMARY_DARK};
    }}
"""

TABLE_STYLE = f"""
    QTableWidget {{
        background: {Colors.SURFACE};
        color: {Colors.TEXT_PRIMARY};
        gridline-color: {Colors.BORDER};
        border: 1px solid {Colors.BORDER};
        border-radius: 18px;
        selection-background-color: {Colors.TABLE_SELECTION};
        font-size: 13px;
    }}
    QTableWidget::item {{
        padding: 10px 8px;
        border-bottom: 1px solid {Colors.BORDER};
    }}
    QTableWidget::item:selected {{
        background: {Colors.TABLE_SELECTION};
        color: {Colors.TEXT_PRIMARY};
    }}
    QTableWidget::item:hover {{
        background: {Colors.SURFACE_LIGHT};
    }}
    QHeaderView::section {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {Colors.TABLE_HEADER}, stop:1 {Colors.SURFACE});
        color: {Colors.PRIMARY};
        font-weight: 800;
        font-size: 14px;
        padding: 14px 10px;
        border: none;
        border-bottom: 1px solid {Colors.BORDER_LIGHT};
        border-right: 1px solid {Colors.BORDER};
    }}
    QHeaderView::section:hover {{
        background: {Colors.OVERLAY};
    }}
"""

ADMIN_STYLE_SHEET = f"""
    QMainWindow, QDialog, QWidget {{
        background-color: {Colors.BACKGROUND};
        color: {Colors.TEXT_PRIMARY};
    }}

    QTabWidget::pane {{
        border: 1px solid {Colors.BORDER};
        border-radius: 12px;
        padding: 8px;
        background: {Colors.BACKGROUND_ELEVATED};
    }}

    QTabBar::tab {{
        background: {Colors.SURFACE};
        color: {Colors.TEXT_SECONDARY};
        border: 1px solid {Colors.BORDER};
        padding: 10px 18px;
        margin-right: 6px;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
    }}

    QTabBar::tab:selected, QTabBar::tab:hover {{
        background: {Colors.SURFACE_LIGHT};
        color: {Colors.TEXT_PRIMARY};
        border-color: {Colors.BORDER_LIGHT};
    }}

    QPushButton {{
        background-color: {Colors.SURFACE_LIGHT};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_LIGHT};
        border-radius: 12px;
        padding: 8px 14px;
        min-width: 88px;
    }}

    QPushButton:hover {{
        background-color: {Colors.OVERLAY};
    }}

    QPushButton:pressed {{
        background-color: {Colors.TABLE_HIGHLIGHT};
    }}

    QPushButton:disabled {{
        background-color: {Colors.SURFACE};
        color: {Colors.TEXT_MUTED};
    }}

    QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit {{
        background-color: {Colors.SURFACE};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 12px;
        padding: 8px 12px;
        min-height: 30px;
    }}

    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
        border: 1px solid {Colors.PRIMARY};
        background: {Colors.SURFACE_LIGHT};
    }}

    QCheckBox, QRadioButton {{
        spacing: 6px;
        color: {Colors.TEXT_SECONDARY};
    }}

    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px;
        height: 16px;
    }}

    QCheckBox::indicator:unchecked, QRadioButton::indicator:unchecked {{
        border: 1px solid {Colors.BORDER_LIGHT};
        background: {Colors.SURFACE};
        border-radius: 5px;
    }}

    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        border: 1px solid {Colors.PRIMARY};
        background: {Colors.PRIMARY};
        border-radius: 5px;
    }}

    QGroupBox {{
        border: 1px solid {Colors.BORDER};
        border-radius: 14px;
        margin-top: 12px;
        padding-top: 22px;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {Colors.PRIMARY};
    }}

    QStatusBar {{
        background-color: {Colors.SURFACE};
        color: {Colors.TEXT_SECONDARY};
        border-top: 1px solid {Colors.BORDER};
    }}

    QToolBar {{
        background-color: {Colors.BACKGROUND_ELEVATED};
        border: none;
        border-bottom: 1px solid {Colors.BORDER};
        spacing: 6px;
        padding: 8px;
    }}

    QLabel {{
        color: {Colors.TEXT_PRIMARY};
    }}

    QScrollBar:vertical {{
        border: none;
        background: {Colors.SURFACE};
        width: 12px;
        margin: 0;
        border-radius: 6px;
    }}

    QScrollBar::handle:vertical {{
        background: {Colors.BORDER_LIGHT};
        min-height: 28px;
        border-radius: 6px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {Colors.PRIMARY_DARK};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        border: none;
        background: none;
        height: 0;
    }}

    .status-success {{ color: {Colors.SUCCESS_LIGHT}; }}
    .status-warning {{ color: {Colors.WARNING}; }}
    .status-error {{ color: {Colors.ERROR}; }}
"""

MAIN_STYLE_SHEET = f"""
    * {{
        font-family: 'Segoe UI Variable', 'Segoe UI', 'Trebuchet MS', sans-serif;
        font-size: 14px;
    }}

    QMainWindow {{
        background: {Colors.BACKGROUND};
        color: {Colors.TEXT_PRIMARY};
    }}

    QWidget {{
        color: {Colors.TEXT_PRIMARY};
        background: transparent;
    }}

    QLabel {{
        color: {Colors.TEXT_PRIMARY};
        background: transparent;
    }}

    {INPUT_STYLE}
    {TABLE_STYLE}

    QComboBox QAbstractItemView {{
        background: {Colors.SURFACE};
        color: {Colors.TEXT_PRIMARY};
        selection-background-color: {Colors.TABLE_SELECTION};
        border: 1px solid {Colors.BORDER};
        border-radius: 12px;
        outline: none;
        padding: 6px;
    }}

    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid {Colors.PRIMARY};
        width: 0;
        height: 0;
    }}

    QScrollBar:vertical {{
        background: {Colors.SURFACE};
        width: 12px;
        border-radius: 6px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: {Colors.BORDER_LIGHT};
        border-radius: 6px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {Colors.PRIMARY};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QToolTip {{
        background: {Colors.OVERLAY};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_LIGHT};
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 12px;
    }}

    QDialog {{
        background: {Colors.SURFACE};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER_LIGHT};
        border-radius: 18px;
    }}

    QFrame[frameShape="4"] {{
        color: {Colors.BORDER};
        background: {Colors.BORDER};
        height: 1px;
        border: none;
    }}
"""


class AnimatedButton:
    @staticmethod
    def add_hover_animation(button):
        def on_enter(event):
            try:
                event.accept()
            except Exception:
                pass

        def on_leave(event):
            try:
                event.accept()
            except Exception:
                pass

        button.enterEvent = on_enter
        button.leaveEvent = on_leave


class ThemeManager:
    @staticmethod
    def get_stylesheet():
        return STYLE_SHEET

    @staticmethod
    def apply_card_style(widget):
        widget.setStyleSheet(CARD_STYLE)

    @staticmethod
    def apply_primary_button(button):
        button.setStyleSheet(BUTTON_PRIMARY)
        AnimatedButton.add_hover_animation(button)

    @staticmethod
    def apply_secondary_button(button):
        button.setStyleSheet(BUTTON_SECONDARY)

    @staticmethod
    def apply_danger_button(button):
        button.setStyleSheet(BUTTON_DANGER)

    @staticmethod
    def apply_circle_button(button):
        button.setStyleSheet(BUTTON_CIRCLE)


STYLE_SHEET = MAIN_STYLE_SHEET + "\n" + ADMIN_STYLE_SHEET
