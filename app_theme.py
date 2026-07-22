# app_theme.py — Gestor global de tema (oscuro/claro) y tamaño de letra
# flake8: noqa — este archivo genera QSS/CSS en f-strings; los ; y : son sintaxis CSS, no Python
import json
import os

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

# Tamaños de letra disponibles
FONT_SIZES = {
    "xs": 11,
    "sm": 12,
    "md": 14,
    "lg": 16,
    "xl": 19,
}
FONT_SIZE_LABELS = {
    "xs": "Muy chica",
    "sm": "Chica",
    "md": "Normal",
    "lg": "Grande",
    "xl": "Muy grande",
}
FONT_SIZE_KEYS = ["xs", "sm", "md", "lg", "xl"]


def _prefs_path() -> str:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "Manarey", "user_prefs.json")
    return os.path.join(os.path.expanduser("~"), ".manarey_prefs", "user_prefs.json")


def load_prefs() -> dict:
    try:
        path = _prefs_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}


def save_pref(key: str, value):
    try:
        path = _prefs_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
            except Exception:
                pass
        data[key] = value
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def is_dark_mode() -> bool:
    return bool(load_prefs().get("dark_mode", True))


def get_font_size_key() -> str:
    return load_prefs().get("font_size", "md")


def get_font_size_px() -> int:
    return FONT_SIZES.get(get_font_size_key(), 14)


# ── Paleta oscura ─────────────────────────────────────────────────────────────
_DARK = {
    "BG": "#0f0f14",
    "BG_ALT": "#1a1a22",
    "SURFACE": "#1c1c28",
    "CARD": "#1c1c27",
    "TEXT": "#F8F1E7",
    "TEXT_MUTED": "#a0a0a8",
    "BORDER": "#3e3e44",
    "BORDER_H": "#5a5a64",
    "GOLD": "#C9A040",
    "GOLD_DIM": "#8a6820",
    "INPUT_BG": "#252530",
    "TH_BG": "#141420",
    "ROW_ODD": "#1c1c27",
    "ROW_EVEN": "#222229",
    "SEL_BG": "rgba(201,160,64,0.22)",
    "SCROLLBAR": "#3e3e44",
    "DANGER": "#ef4444",
    "SUCCESS": "#22c55e",
}

# ── Paleta clara (crema cálida) ──────────────────────────────────────────────
_LIGHT = {
    "BG": "#FFF8EC",  # crema mantequilla — fondo principal
    "BG_ALT": "#F5E9CE",  # crema más oscura — nav/áreas alternativas
    "SURFACE": "#FFFDF5",  # blanco cálido — paneles/widgets
    "CARD": "#FFF5E1",  # crema suave — cards/formularios
    "TEXT": "#2B2108",  # marrón muy oscuro (más cálido que gris puro)
    "TEXT_MUTED": "#7A6A50",  # marrón/ocre apagado — texto secundario
    "BORDER": "#EAD9B8",  # borde crema/dorado suave
    "BORDER_H": "#C6A85B",  # dorado en hover
    "GOLD": "#B8922E",  # dorado más saturado en fondo claro
    "GOLD_DIM": "#D4AE5A",  # dorado suave
    "INPUT_BG": "#FFFDF5",  # blanco cálido para inputs
    "TH_BG": "#FDF0D8",  # crema tostada — cabecera de tabla
    "ROW_ODD": "#FFFCF3",  # fila impar — casi blanco cálido
    "ROW_EVEN": "#F9EEDA",  # fila par — crema más marcada
    "SEL_BG": "rgba(184,146,46,0.16)",
    "SCROLLBAR": "#D4AE5A80",
    "DANGER": "#B01A1A",
    "SUCCESS": "#145C30",
}


def _palette(dark: bool) -> dict:
    return _DARK if dark else _LIGHT


def build_stylesheet(dark: bool = True, font_px: int = 14) -> str:
    c = _palette(dark)
    return f"""
* {{
    font-family: 'Segoe UI Variable', 'Segoe UI', 'Trebuchet MS', sans-serif;
    font-size: {font_px}px;
    color: {c['TEXT']};
}}
QMainWindow, QDialog {{
    background: {c['BG']};
}}
QWidget {{
    background: {c['BG']};
    color: {c['TEXT']};
}}
QFrame {{
    color: {c['TEXT']};
    background: {c['BG']};
}}
QLabel {{
    color: {c['TEXT']};
    background: transparent;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {c['INPUT_BG']};
    color: {c['TEXT']};
    border: 1px solid {c['BORDER']};
    border-radius: 8px;
    padding: 7px 11px;
    font-size: {font_px}px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {c['GOLD']};
}}
QLineEdit:disabled, QComboBox:disabled {{
    color: {c['TEXT_MUTED']};
}}
QComboBox QAbstractItemView {{
    background: {c['INPUT_BG']};
    color: {c['TEXT']};
    selection-background-color: {c['SEL_BG']};
    border: 1px solid {c['BORDER']};
    outline: none;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {c['GOLD']};
}}
QTableWidget {{
    background: {c['SURFACE']};
    alternate-background-color: {c['ROW_EVEN']};
    color: {c['TEXT']};
    gridline-color: {c['BORDER']};
    border: 1px solid {c['BORDER']};
    border-radius: 10px;
    selection-background-color: {c['SEL_BG']};
    font-size: {font_px}px;
    outline: none;
}}
QTableWidget::item {{ padding: 10px 8px; border-bottom: 1px solid {c['BORDER']}; }}
QTableWidget::item:selected {{ background: {c['SEL_BG']}; color: {c['TEXT']}; }}
QTableWidget::item:hover {{ background: {'rgba(255,255,255,0.04)' if dark else 'rgba(0,0,0,0.04)'}; }}
QHeaderView::section {{
    background: {c['TH_BG']};
    color: {c['GOLD']};
    font-weight: 800;
    font-size: {max(font_px - 1, 10)}px;
    padding: 12px 8px;
    border: none;
    border-bottom: 2px solid {c['GOLD']};
    border-right: 1px solid {c['BORDER']};
}}
QHeaderView::section:hover {{ background: {c['BG_ALT']}; }}
QPushButton {{
    background: {c['SURFACE']};
    color: {c['TEXT']};
    border: 1px solid {c['BORDER']};
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 700;
    font-size: {font_px}px;
}}
QPushButton:hover {{ background: {c['BG_ALT']}; border-color: {c['BORDER_H']}; }}
QPushButton:pressed {{ background: {c['BG']}; }}
QPushButton:disabled {{ color: {c['TEXT_MUTED']}; }}
QScrollBar:vertical {{
    background: {'#0f0f14' if dark else c['BG_ALT']};
    width: 10px;
    border-radius: 5px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['SCROLLBAR']};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['GOLD']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {'#0f0f14' if dark else c['BG_ALT']};
    height: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    background: {c['SCROLLBAR']};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {c['GOLD']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QToolTip {{
    background: {c['SURFACE']};
    color: {c['TEXT']};
    border: 1px solid {c['BORDER_H']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {max(font_px - 1, 10)}px;
}}
QMessageBox {{ background: {c['SURFACE']}; }}
QGroupBox {{
    color: {c['TEXT_MUTED']};
    border: 1px solid {c['BORDER']};
    border-radius: 10px;
    margin-top: 8px;
    padding: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {c['TEXT_MUTED']};
}}
QCheckBox {{ color: {c['TEXT']}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c['BORDER_H']};
    border-radius: 4px;
    background: {c['INPUT_BG']};
}}
QCheckBox::indicator:checked {{
    background: {c['GOLD']};
    border-color: {c['GOLD']};
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: {c['BORDER']};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 18px;
    height: 18px;
    margin: -6px 0;
    background: {c['GOLD']};
    border-radius: 9px;
}}
QSlider::sub-page:horizontal {{
    background: {c['GOLD']};
    border-radius: 3px;
}}
QScrollArea {{
    background: {c['BG']};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: {c['BG']};
}}
QTabWidget::pane {{
    background: {c['SURFACE']};
    border: 1px solid {c['BORDER']};
    border-radius: 8px;
}}
QTabBar::tab {{
    background: {c['BG_ALT']};
    color: {c['TEXT']};
    padding: 7px 16px;
    border: 1px solid {c['BORDER']};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {c['SURFACE']};
    color: {c['GOLD']};
    border-bottom: 2px solid {c['GOLD']};
}}
QTabBar::tab:hover {{
    background: {c['SURFACE']};
    color: {c['GOLD']};
}}
QMenuBar {{
    background: {c['BG']};
    color: {c['TEXT']};
}}
QMenuBar::item:selected {{
    background: {c['BG_ALT']};
}}
QMenu {{
    background: {c['SURFACE']};
    color: {c['TEXT']};
    border: 1px solid {c['BORDER']};
}}
QMenu::item:selected {{
    background: {c['SEL_BG']};
}}
QDateEdit {{
    background: {c['INPUT_BG']};
    color: {c['TEXT']};
    border: 1px solid {c['BORDER']};
    border-radius: 8px;
    padding: 7px 11px;
}}
QDateEdit:focus {{
    border-color: {c['GOLD']};
}}
QAbstractScrollArea {{
    background: {c['BG']};
}}
"""


def apply_to_app():
    """Aplica tema y tamaño de letra a la aplicación completa."""
    try:
        dark = is_dark_mode()
        font_px = get_font_size_px()
        app = QApplication.instance()
        if app:
            app.setFont(QFont("Segoe UI", font_px))
            c = _palette(dark)
            base_ss = build_stylesheet(dark, font_px)
            # Añadir regla explícita para QMainWindow background
            extra = f"\nQMainWindow {{ background: {c['BG']}; }}\n"
            app.setStyleSheet(base_ss + extra)
            # Propagar refresh_theme() a todas las ventanas abiertas
            for w in app.topLevelWidgets():
                try:
                    if callable(getattr(w, "refresh_theme", None)):
                        w.refresh_theme()
                except Exception:
                    pass
    except Exception:
        pass


def get_palette_value(key: str) -> str:
    """Devuelve el valor de color del palette actual."""
    dark = is_dark_mode()
    return _palette(dark).get(key, "")
