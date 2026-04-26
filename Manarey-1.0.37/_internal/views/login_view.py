# views/login_view_modern.py

# Login moderno y responsivo para Manarey (PyQt5)

# Mejorado: eye-button dentro del password, error inline animado, loading button,

# responsive (oculta panel izquierdo en pantallas pequeÃÂ±as), focus outline accesible, input icons, theme stub.


import json
import os
import re
import sys

from PyQt5.QtCore import (
    QByteArray,
    QEasingCurve,
    QEvent,
    QMargins,
    QPropertyAnimation,
    QRect,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

try:
    import app_theme as _theme

    def _T(k, fallback):
        return _theme.get_palette_value(k) or fallback

except ImportError:

    def _T(k, fallback):
        return fallback


# ── Constantes de color dinámicas (se recalculan al arrancar) ────────────────
def _colors():
    return {
        "DORADO": _T("GOLD", "#C9A040"),
        "DARK": _T("BG", "#1f1f22"),
        "CARD": _T("CARD", "#232327"),
        "BORDER": _T("BORDER", "#34343a"),
        "TEXT": _T("TEXT", "#ECECF1"),
        "MUTED": _T("TEXT_MUTED", "#c9c9cf"),
        "BG": _T("BG", "#0f0f14"),
        "BG_ALT": _T("BG_ALT", "#1a1a22"),
        "CARD_BG": _T("CARD", "#1a1a22"),
        "CARD_BORDER": _T("BORDER", "rgba(201,160,64,0.18)"),
        "ACCENT": _T("GOLD", "#C9A040"),
        "TEXT_MUTED": _T("TEXT_MUTED", "#a0a0a8"),
        "PRIMARY": _T("GOLD", "#C9A040"),
        "GREEN": "#5E8B6F",
    }


_c = _colors()
DORADO = _c["DORADO"]
DARK = _c["DARK"]
CARD = _c["CARD"]
BORDER = _c["BORDER"]
TEXT = _c["TEXT"]
MUTED = _c["MUTED"]
BG = _c["BG"]
BG_ALT = _c["BG_ALT"]
CARD_BG = _c["CARD_BG"]
CARD_BORDER = _c["CARD_BORDER"]
ACCENT = _c["ACCENT"]
TEXT_MUTED = _c["TEXT_MUTED"]
PRIMARY = _c["PRIMARY"]
# ─────────────────────────────────────────────────────────────────────────────


from PyQt5.QtWidgets import (
    QAction,
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

# Ensure project root is importable when running this file directly

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import auth as auth_mod
from models import db

# Debug flag: activa informaciÃÂ³n adicional en la ventana de login

DEBUG = os.environ.get("MANAREY_DEBUG", "0") == "1"


# --------------------------

# Palette / Defaults

# --------------------------

PRIMARY = "#D6B36A"
PRIMARY_LIGHT = "#EBD7AA"
PRIMARY_DARK = "#A8863A"
ERROR_RED = "#D98383"
LINE = "rgba(214,179,106,0.22)"
SOFT = "#2E272B"


def _INPUT_BG():
    try:
        return "rgba(255,255,255,0.07)" if _theme.is_dark_mode() else "#FFFDF5"
    except Exception:
        return "rgba(255,255,255,0.07)"


_APPDATA = os.environ.get("APPDATA")
if _APPDATA:
    PREFS_DIR = os.path.join(_APPDATA, "Manarey")
else:
    PREFS_DIR = os.path.join(os.path.expanduser("~"), ".manarey_prefs")
PREFS_PATH = os.path.join(PREFS_DIR, "user_prefs.json")

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))


def _logs_dir() -> str:
    """Usar %LOCALAPPDATA% en instalados, y /logs del repo en dev."""
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
        return os.path.join(base, "Manarey", "logs")
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))


# --------------------------

# Utility: assets

# --------------------------


def asset_path(*parts):
    p = os.path.join(ASSETS_DIR, *parts)

    return p if os.path.exists(p) else None


class LoginWorker(QThread):
    ok = pyqtSignal(object)

    error = pyqtSignal(str)

    def __init__(self, username):
        super().__init__()

        self._username = username

    def run(self):
        try:
            conn = db.get_connection()

            cur = conn.cursor()

            # Usa placeholder correcto seg?n backend
            ph = "%s" if db.is_postgres() else "?"

            cur.execute(
                f"SELECT username, password, role, local FROM usuarios WHERE username={ph} LIMIT 1",
                (self._username,),
            )

            row = cur.fetchone()

            db.put_connection(conn) if hasattr(db, "put_connection") else conn.close()

            if row:
                # row puede ser tuple o dict-like

                user = {
                    "username": row[0] if isinstance(row, tuple) else row["username"],
                    "password": row[1] if isinstance(row, tuple) else row["password"],
                    "role": row[2] if isinstance(row, tuple) else row["role"],
                    "local": row[3] if isinstance(row, tuple) else row["local"],
                }

                self.ok.emit(user)

            else:
                self.ok.emit(None)

        except Exception as e:
            import traceback

            traceback.print_exc()  # Para debug

            self.error.emit(str(e))


# Username validation: letras, nÃÂºmeros, underscore, espacios y algunos sÃÂ­mbolos comunes

USERNAME_RE = re.compile(r"^[\w\s@.+-]{1,150}$")


# --------------------------

# Styles centralizados

# --------------------------


def global_styles(bg=None):
    try:
        dark = _theme.is_dark_mode()
    except Exception:
        dark = True
    if bg is None:
        bg = _T("BG", "#0f0f14" if dark else "#FFF8EC")
    if dark:
        grad = (
            f"qradialgradient(cx:0.18, cy:0.12, radius:1.1,"
            f"fx:0.18, fy:0.12,"
            f"stop:0 rgba(214,179,106,0.12),"
            f"stop:0.34 rgba(77,59,43,0.10),"
            f"stop:0.62 {bg},"
            f"stop:1 #110F10)"
        )
    else:
        grad = (
            f"qradialgradient(cx:0.18, cy:0.12, radius:1.1,"
            f"fx:0.18, fy:0.12,"
            f"stop:0 rgba(214,179,106,0.08),"
            f"stop:0.4 #FFF5E2,"
            f"stop:1 #FFF8EC)"
        )
    return f"""
    QMainWindow {{
        background: {grad};
    }}
    QLabel#muted {{ color: {_T('TEXT_MUTED', '#c9c9cf' if dark else '#7A6A50')}; }}
    """


# --------------------------

# Logo widget (fallback incluido)

# --------------------------


def create_logo_widget():
    logo = QLabel()

    logo.setFixedSize(140, 140)

    logo.setAlignment(Qt.AlignCenter)

    logo.setAttribute(Qt.WA_TranslucentBackground)

    logo_path = asset_path("images", "logo_manarey.png") or asset_path(
        "images", "logo_manarey.svg"
    )

    if logo_path:
        pix = QPixmap(logo_path)

        if not pix.isNull():
            pix = pix.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            logo.setPixmap(pix)

            return logo

    # Fallback: logo generado simple

    pix = QPixmap(140, 140)

    pix.fill(Qt.transparent)

    painter = QPainter(pix)

    painter.setRenderHints(QPainter.Antialiasing)

    painter.setBrush(QColor(PRIMARY))

    painter.setPen(Qt.NoPen)

    painter.drawRoundedRect(0, 0, 140, 140, 28, 28)

    painter.setPen(QColor("white"))

    painter.setFont(QFont("Inter", 30, QFont.Bold))

    painter.drawText(pix.rect(), Qt.AlignCenter, "M")

    painter.end()

    logo.setPixmap(pix)

    return logo


# --------------------------

# ModernLineEdit: estilo y focus effect

# --------------------------


class ModernLineEdit(QLineEdit):
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)

        self.setPlaceholderText(placeholder)

        self.setMinimumHeight(52)

        self.setFont(QFont("Segoe UI Variable", 11))

        self._focused = False

        self._shadow = None

        self.update_style(False)

    def update_style(self, focused: bool):
        try:
            dark = _theme.is_dark_mode()
        except Exception:
            dark = True
        input_bg = _INPUT_BG()
        text_color = _T("TEXT", "#ECECF1" if dark else "#2B2108")
        border = (
            PRIMARY if focused else ("rgba(248,241,231,0.08)" if dark else "#EAD9B8")
        )

        self.setStyleSheet(
            f"""

            QLineEdit {{

                background: {input_bg};

                color: {text_color};

                border: 1px solid {border};

                border-radius: 16px;

                padding: 14px 16px;

                font-weight: 500;

            }}

            QLineEdit:focus {{

                border: 1px solid {PRIMARY};

            }}

        """
        )

        # Add subtle shadow when focused for keyboard users (accessibility)

        if focused:
            eff = QGraphicsDropShadowEffect(self)

            eff.setBlurRadius(20)

            eff.setOffset(0, 8)

            eff.setColor(QColor(214, 179, 106, 40))

            self.setGraphicsEffect(eff)

            self._shadow = eff

        else:
            self.setGraphicsEffect(None)

            self._shadow = None

    def focusInEvent(self, e):
        self._focused = True

        self.update_style(True)

        super().focusInEvent(e)

    def focusOutEvent(self, e):
        self._focused = False

        self.update_style(False)

        super().focusOutEvent(e)


# --------------------------

# Password input

# --------------------------


class PasswordLineEdit(ModernLineEdit):
    def __init__(self, placeholder="Contraseña", parent=None):
        super().__init__(placeholder, parent)
        self.setEchoMode(QLineEdit.Password)


# --------------------------

# AccentButton (primary/secondary) con shadow

# --------------------------


class AccentButton(QPushButton):
    def __init__(self, text, primary=True):
        super().__init__(text)

        self.setCursor(Qt.PointingHandCursor)

        self.setMinimumHeight(52)

        self.setFont(QFont("Segoe UI Variable", 11, QFont.Bold))

        self.primary = primary

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.update_style()

        shadow = QGraphicsDropShadowEffect(blurRadius=18, xOffset=0, yOffset=6)

        shadow.setColor(QColor(0, 0, 0, 120))

        self.setGraphicsEffect(shadow)

    def update_style(self):
        if self.primary:
            self.setStyleSheet(
                f"""

                QPushButton {{

                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {PRIMARY_LIGHT}, stop:0.55 {PRIMARY}, stop:1 {PRIMARY_DARK});

                    color: #1d1715;

                    border: none;

                    border-radius: 16px;

                    padding: 13px 18px;

                }}

                QPushButton:hover {{

                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #f3e8cf, stop:0.5 {PRIMARY_LIGHT}, stop:1 {PRIMARY});

                }}

                QPushButton:pressed {{

                    background: {PRIMARY};

                }}

                QPushButton:disabled {{

                    opacity: 0.6;

                }}

            """
            )

        else:
            self.setStyleSheet(
                f"""

                QPushButton {{

                    background: rgba(255,255,255,0.02);

                    color: {PRIMARY};

                    border: 1px solid {LINE};

                    border-radius: 16px;

                    padding: 13px 18px;

                }}

                QPushButton:hover {{

                    background: rgba(214,179,106,0.08);

                    border-color: rgba(214,179,106,0.35);

                    color: {PRIMARY_LIGHT};

                }}

            """
            )


# --------------------------

# GlassCard (tarjeta central)

# --------------------------


class GlassCard(QFrame):
    def __init__(self):
        super().__init__()
        self._apply_style()
        shadow = QGraphicsDropShadowEffect(blurRadius=48, xOffset=0, yOffset=18)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(shadow)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def _apply_style(self):
        try:
            dark = _theme.is_dark_mode()
        except Exception:
            dark = True
        if dark:
            self.setStyleSheet(
                f"""
                QFrame {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(36, 31, 34, 0.97),
                        stop:1 rgba(28, 24, 26, 0.96));
                    border: 1px solid rgba(214, 179, 106, 0.18);
                    border-radius: 26px;
                }}
                QFrame:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 rgba(39, 33, 36, 0.98),
                        stop:1 rgba(31, 26, 29, 0.98));
                    border: 1px solid rgba(235, 215, 170, 0.28);
                }}
                """
            )
        else:
            self.setStyleSheet(
                f"""
                QFrame {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 #FFFDF5,
                        stop:1 #FFF5E1);
                    border: 1px solid rgba(184, 146, 46, 0.30);
                    border-radius: 26px;
                }}
                QFrame:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 #FFFFFF,
                        stop:1 #FFF8EC);
                    border: 1px solid rgba(184, 146, 46, 0.50);
                }}
                """
            )


# --------------------------

# LoginWindow (principal)

# --------------------------


class LoginWindow(QMainWindow):
    def __init__(self, skip_autologin: bool = False):
        super().__init__()
        self._skip_autologin = bool(skip_autologin)

        self.setWindowTitle("Manarey — Iniciar sesión")
        self.setProperty("manarey_no_scale", True)
        self.setProperty("manarey_no_autoresize", False)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        self.setMinimumSize(760, 520)
        self.resize(1040, 680)

        self.setStyleSheet(global_styles())

        # init_db() no es necesario con Firestore

        self._anim = None

        self.right_widget = None

        self.left_widget = None

        self._loading = False

        self._login_thread = None

        self.setup_ui()

        self._load_prefs()

        self._window_restored = self._restore_window_state()
        if not self._window_restored:
            self.center()

    def center(self):
        qr = self.frameGeometry()

        cp = self.screen().availableGeometry().center()

        qr.moveCenter(cp)

        self.move(qr.topLeft())

    def setup_ui(self):
        central = QWidget()

        self.setCentralWidget(central)

        layout = QHBoxLayout(central)

        layout.setContentsMargins(34, 34, 34, 34)

        layout.setSpacing(32)

        # --- Panel izquierdo (branding) ---

        left = QWidget()

        self.left_widget = left
        try:
            _lft_dark = _theme.is_dark_mode()
        except Exception:
            _lft_dark = True
        if _lft_dark:
            _lft_bg = "rgba(255,255,255,0.015)"
            _lft_border = "rgba(214,179,106,0.08)"
        else:
            _lft_bg = "rgba(255,248,230,0.60)"
            _lft_border = "rgba(184,146,46,0.18)"
        left.setStyleSheet(
            f"background: {_lft_bg}; border: 1px solid {_lft_border}; border-radius: 28px;"
        )

        left_layout = QVBoxLayout(left)

        left_layout.setContentsMargins(36, 36, 28, 36)

        left_layout.setSpacing(16)

        logo = create_logo_widget()

        left_layout.addWidget(logo, alignment=Qt.AlignTop | Qt.AlignHCenter)

        title = QLabel("Manarey")

        title.setFont(QFont("Georgia", 30, QFont.Bold))

        title.setStyleSheet(f"color: {_T('TEXT', '#ECECF1')};")

        title.setAlignment(Qt.AlignCenter)

        left_layout.addWidget(title)

        subtitle = QLabel(
            "Gestion de locales, stock y ventas con una presencia mas fina y serena."
        )

        subtitle.setFont(QFont("Inter", 11))

        subtitle.setObjectName("muted")

        subtitle.setStyleSheet(f"color: {_T('TEXT_MUTED', '#c9c9cf')};")

        subtitle.setAlignment(Qt.AlignCenter)

        subtitle.setWordWrap(True)

        left_layout.addWidget(subtitle)

        left_layout.addSpacerItem(QSpacerItem(20, 10))

        promo = QLabel(
            "Una experiencia mas delicada, clara y enfocada en lectura, ritmo visual y confianza operativa."
        )

        promo.setStyleSheet(
            f"color: {_T('TEXT_MUTED', '#c9c9cf')}; font-size: 13px; line-height: 1.45em;"
        )

        promo.setWordWrap(True)

        promo.setAlignment(Qt.AlignTop)

        left_layout.addWidget(promo)

        left_layout.addStretch()

        version = QLabel("Manarey  sistema comercial")

        version.setStyleSheet(
            f"color: {_T('TEXT_MUTED', '#c9c9cf')}; font-size: 11px; letter-spacing: 1px; text-transform: uppercase;"
        )

        version.setAlignment(Qt.AlignCenter)

        left_layout.addWidget(version)

        layout.addWidget(left, 1)

        # --- Panel derecho (login form) ---

        right = GlassCard()

        right.setMaximumWidth(540)

        self.right_widget = right

        right_layout = QVBoxLayout(right)

        right_layout.setContentsMargins(38, 38, 38, 38)

        right_layout.setSpacing(16)

        # Header

        header = QLabel("Iniciar sesión")

        header.setFont(QFont("Georgia", 20, QFont.Bold))

        header.setStyleSheet(
            f"color: {_T('TEXT', '#ECECF1')}; padding-bottom: 10px; border-bottom: 1px solid {LINE};"
        )

        right_layout.addWidget(header)

        hint = QLabel("Ingresa tu usuario y contraseña para acceder al sistema")

        hint.setStyleSheet(f"color: {_T('TEXT_MUTED', '#c9c9cf')}; font-size: 12px;")

        right_layout.addWidget(hint)
        hint.setText(
            "Ingresa tu usuario y contrasena para acceder al sistema con una sesion segura."
        )
        hint.setStyleSheet(
            f"color: {_T('TEXT_MUTED', '#c9c9cf')}; font-size: 12px; line-height: 1.4em;"
        )

        # Inputs (user + password)

        user_row = QVBoxLayout()

        self.user_input = ModernLineEdit("Usuario")
        # Asegurar que el input permita mayusculas en cualquier PC/teclado
        try:
            self.user_input.setInputMethodHints(Qt.ImhNone)
        except Exception:
            pass

        # optional leading icon

        user_icon = asset_path("icons", "user.svg") or asset_path("icons", "user.png")

        if user_icon:
            act = QAction(QIcon(user_icon), "", self.user_input)

            self.user_input.addAction(act, QLineEdit.LeadingPosition)

        user_row.addWidget(self.user_input)

        right_layout.addLayout(user_row)

        pwd_row = QVBoxLayout()

        self.pass_input = PasswordLineEdit("Contraseña")
        # Asegurar que el input permita mayusculas en cualquier PC/teclado
        try:
            self.pass_input.setInputMethodHints(Qt.ImhNone)
        except Exception:
            pass

        pwd_row.addWidget(self.pass_input)

        self.show_pass_check = QCheckBox("Mostrar contraseña")
        self.show_pass_check.setStyleSheet(f"color: {_T('TEXT_MUTED', '#c9c9cf')};")
        self.show_pass_check.toggled.connect(
            lambda checked: self.pass_input.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        pwd_row.addWidget(self.show_pass_check)

        right_layout.addLayout(pwd_row)

        # Inline error label (animated)

        self.error_label = QLabel("")

        self.error_label.setStyleSheet(f"color: {ERROR_RED}; font-size: 12px;")

        self.error_label.setVisible(False)

        # opacity effect for nice fade

        from PyQt5.QtWidgets import QGraphicsOpacityEffect

        self._error_opacity = QGraphicsOpacityEffect()

        self.error_label.setGraphicsEffect(self._error_opacity)

        self._error_opacity.setOpacity(0.0)

        right_layout.addWidget(self.error_label)
        self.error_label.setStyleSheet(
            f"color: {ERROR_RED}; font-size: 12px; padding: 2px 2px 0 2px;"
        )

        # remember + forgot

        aux_row = QHBoxLayout()

        self.remember = QCheckBox("Recordarme")

        self.remember.setStyleSheet(f"color: {_T('TEXT_MUTED', '#c9c9cf')};")

        aux_row.addWidget(self.remember)

        aux_row.addStretch()

        forgot = QPushButton("Olvide mi contraseña")
        forgot.setCursor(Qt.PointingHandCursor)
        forgot.setStyleSheet(
            f"color: {_T('TEXT_MUTED', '#c9c9cf')}; background: transparent; border: none;"
        )
        forgot.clicked.connect(self.forgot_password)
        aux_row.addWidget(forgot)

        right_layout.addLayout(aux_row)

        # Login button + secondary actions

        btn_row = QHBoxLayout()

        self.login_btn = AccentButton("Iniciar sesion", primary=True)

        self.login_btn.clicked.connect(self.on_login)

        btn_row.addWidget(self.login_btn)

        right_layout.addLayout(btn_row)

        # small footer note

        info = QLabel("Acceso seguro:  administra los locales y el stock desde aqui.")

        info.setStyleSheet(f"color: {_T('TEXT_MUTED', '#c9c9cf')}; font-size: 12px;")

        right_layout.addWidget(info)
        info.setText("Acceso seguro para ventas, stock, entregas y control diario.")
        info.setStyleSheet(
            f"color: {_T('TEXT_MUTED', '#c9c9cf')}; font-size: 12px; padding-top: 6px;"
        )

        # Etiqueta de depuracion (visible solo si MANAREY_DEBUG=1 en el entorno)

        if DEBUG:
            try:
                conn = db.get_connection()

                cur = conn.cursor()

                cur.execute("SELECT COUNT(*) FROM usuarios")

                user_count = cur.fetchone()[0]

                db.put_connection(conn) if hasattr(
                    db, "put_connection"
                ) else conn.close()

            except Exception:
                user_count = "err"

            self.debug_label = QLabel(f"DEBUG: DB=Postgres | usuarios={user_count}")

            self.debug_label.setStyleSheet(
                f"color: {_T('TEXT_MUTED', '#c9c9cf')}; font-size: 10px;"
            )

            right_layout.addWidget(self.debug_label)

        layout.addWidget(right, 1)

        # Enter para login

        self.user_input.returnPressed.connect(self.on_login)

        self.pass_input.returnPressed.connect(self.on_login)

        # adapt responsiveness when resizing window

        self.centralWidget().installEventFilter(self)

    def _load_prefs(self):
        """Carga usuario recordado desde user_prefs.json (si existe)."""
        try:
            if os.path.exists(PREFS_PATH):
                with open(PREFS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                remembered = data.get("remember", False)
                username = data.get("username", "")
                role = data.get("role")
                local = data.get("local")
                if remembered and username:
                    self.user_input.setText(username)
                    self.remember.setChecked(True)
                    if role and local and not self._skip_autologin:
                        self._autoload_user = {
                            "username": username,
                            "role": role,
                            "local": local,
                        }
                        QTimer.singleShot(50, self._auto_login)
        except Exception:
            pass

    def _save_prefs(
        self, remember: bool, username: str, role: str = None, local: str = None
    ):
        """Guarda la preferencia de usuario recordado."""
        try:
            os.makedirs(PREFS_DIR, exist_ok=True)
            data = {
                "remember": bool(remember),
                "username": username if remember else "",
                "role": role if remember else None,
                "local": local if remember else None,
            }
            if os.path.exists(PREFS_PATH):
                try:
                    with open(PREFS_PATH, "r", encoding="utf-8") as _f:
                        existing = json.load(_f)
                    if isinstance(existing, dict):
                        data = {**existing, **data}
                except Exception:
                    pass
            with open(PREFS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _restore_window_state(self):
        """Restaura tamaño/posición del login si estaba recordado."""

        try:
            if not os.path.exists(PREFS_PATH):
                return False

            with open(PREFS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            win = data.get("login_window", {})

            geo = win.get("geometry")

            if geo:
                arr = QByteArray.fromBase64(geo.encode())

                if not arr.isEmpty():
                    self.restoreGeometry(arr)

            if win.get("maximized") and not self.property("manarey_no_autoresize"):
                self.showMaximized()

            return bool(geo)

        except Exception:
            return False

    def _persist_window_state(self):
        """Guarda geometría/tamaño de la ventana."""
        try:
            os.makedirs(PREFS_DIR, exist_ok=True)
            data = {}
            if os.path.exists(PREFS_PATH):
                try:
                    with open(PREFS_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                except Exception:
                    data = {}
            data["login_window"] = {
                "geometry": bytes(self.saveGeometry().toBase64()).decode(),
                "maximized": bool(self.isMaximized()),
            }
            with open(PREFS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _auto_login(self):
        """Intenta abrir directamente la vista según datos recordados."""
        try:
            user = getattr(self, "_autoload_user", None)
            if not user:
                return
            if user.get("role") == "admin":
                self._open_admin(user)
            else:
                self._open_local(user)
        except Exception:
            pass

    def closeEvent(self, event):
        self._persist_window_state()
        super().closeEvent(event)
        try:
            from PyQt5.QtWidgets import QApplication

            QApplication.quit()
        except Exception:
            pass

    def eventFilter(self, watched, event):
        # Hide left panel if width small

        if event.type() == QEvent.Resize or event.type() == QEvent.LayoutRequest:
            w = self.centralWidget().width()

            if self.left_widget:
                if w < 820:
                    self.left_widget.setVisible(False)

                else:
                    self.left_widget.setVisible(True)
            if self.right_widget:
                if w < 900:
                    self.right_widget.setMaximumWidth(16777215)
                else:
                    self.right_widget.setMaximumWidth(540)

        return super().eventFilter(watched, event)

    # simple anim in for card

    def anim_in(self, widget):
        geom = widget.geometry()

        start = QRect(geom.x() + 40, geom.y(), geom.width(), geom.height())

        widget.setGeometry(start)

        anim = QPropertyAnimation(widget, b"geometry", self)

        anim.setStartValue(start)

        anim.setEndValue(geom)

        anim.setDuration(420)

        anim.setEasingCurve(QEasingCurve.OutCubic)

        anim.start()

        self._anim = anim

    def showEvent(self, event):
        super().showEvent(event)

        if self.right_widget:
            QTimer.singleShot(120, lambda: self.anim_in(self.right_widget))

    # Inline error with fade animation

    def show_error(self, message, timeout=2000):
        self.error_label.setText(message)

        self.error_label.setVisible(True)

        anim = QPropertyAnimation(self._error_opacity, b"opacity", self)

        anim.setStartValue(0.0)

        anim.setEndValue(1.0)

        anim.setDuration(220)

        anim.start()

        # hide after timeout

        def fade_out():
            a = QPropertyAnimation(self._error_opacity, b"opacity", self)

            a.setStartValue(1.0)

            a.setEndValue(0.0)

            a.setDuration(240)

            a.start()

            # actually hide after animation

            QTimer.singleShot(260, lambda: self.error_label.setVisible(False))

        QTimer.singleShot(timeout, fade_out)

    def forgot_password(self):
        # Keep it simple and non-intrusive

        self.show_error(
            "Contacta al administrador para recuperar tus credenciales", timeout=3500
        )

    # Loading UX

    def set_loading(self, loading=True):
        self._loading = loading

        self.login_btn.setEnabled(not loading)

        self.user_input.setEnabled(not loading)

        self.pass_input.setEnabled(not loading)

        if loading:
            self.login_btn.setText("Ingresando...")

        else:
            self.login_btn.setText("Iniciar sesión")

    # Login flow: quick UI feedback then DB lookup

    def on_login(self):
        if self._loading:
            return  # ignore clicks while loading

        username = self.user_input.text().strip()

        password = self.pass_input.text().strip()

        if not username or not password:
            self.show_error("Por favor completa todos los campos")

            return

        self.set_loading(True)

        try:
            if self._login_thread and self._login_thread.isRunning():
                return

        except Exception:
            pass

        self._login_thread = LoginWorker(username)

        self._login_thread.ok.connect(
            lambda row: self._on_login_row(username, password, row)
        )

        self._login_thread.error.connect(self._on_login_error)

        self._login_thread.start()

    def _on_login_error(self, msg: str):
        self.set_loading(False)

        # Mensaje mÃÂ¡s ÃÂºtil cuando la excepciÃÂ³n indica que falta el driver de Postgres

        try:
            lowered = (msg or "").lower()

        except Exception:
            lowered = ""

        if "psycopg2" in lowered or "psycopg" in lowered:
            # Mensaje amigable para usuarios finales

            self.show_error(
                "Configurado PostgreSQL pero falta el driver psycopg2. Instala psycopg2-binary."
            )

            return

        # En modo debug mostramos el mensaje real para facilitar diagnÃÂ³stico

        if DEBUG and msg:
            self.show_error(f"Error de conexiopn: {msg}")

        else:
            self.show_error(
                "Error de conexion a la base de datos (revisa logs/auth.log)"
            )

    def _on_login_row(self, username: str, password: str, row):
        def _auth_log(attempt_user: str, reason: str):
            try:
                logs_dir = _logs_dir()

                os.makedirs(logs_dir, exist_ok=True)

                path = os.path.join(logs_dir, "auth.log")

                with open(path, "a", encoding="utf-8") as f:
                    from datetime import datetime

                    f.write(
                        f"{datetime.now().isoformat()}\tuser={attempt_user}\treason={reason}\n"
                    )

            except Exception:
                pass

        try:
            if not row:
                self.show_error("Usuario o contraseña incorrectos")

                self.set_loading(False)

                return

            # Recuperar password/hash desde row (compatible con tuple, dict o sqlite3.Row)
            stored = row["password"] if not isinstance(row, tuple) else row[1]
            stored_str = "" if stored is None else str(stored)

            verified = False
            try:
                if auth_mod:
                    verified = auth_mod.verify_password(password, stored_str)
                    if (
                        not verified and stored_str == password
                    ):  # compatibilidad con texto plano legado
                        verified = True
                else:
                    verified = stored_str == password
            except Exception as e:
                _auth_log(username, f"verification_error: {str(e)}")
                self.show_error("Error al verificar contraseña")
                return

            if not verified:
                _auth_log(username, "password_mismatch")

                self.show_error("Usuario o contraseña incorrectos")

                return

            if auth_mod and auth_mod.needs_rehash(stored):
                # Rehash opcional (no persistimos automticamente para evitar fallas silenciosas)

                pass

            user = {
                "username": row["username"] if not isinstance(row, tuple) else row[0],
                "role": row["role"] if not isinstance(row, tuple) else row[2],
                "local": row["local"] if not isinstance(row, tuple) else row[3],
            }

            try:
                self._save_prefs(
                    self.remember.isChecked(),
                    username,
                    user.get("role"),
                    user.get("local"),
                )

            except Exception:
                pass
            try:
                from models import user_model

                user_model.update_last_seen(user["username"])
            except Exception:
                pass

            if user["role"] == "admin":
                self._open_admin(user)

            else:
                self._open_local(user)

        except Exception as e:
            _auth_log(username, f"unexpected_error: {str(e)}")

            self.show_error(f"Error inesperado durante el login: {str(e)}")

        finally:
            self.set_loading(False)

            try:
                if self._login_thread:
                    self._login_thread.quit()

                    self._login_thread = None

            except Exception:
                pass

    def _open_admin(self, user: dict):
        """Abre la ventana principal de admin."""

        try:
            from views.main_admin import MainAdminWindow

            w = MainAdminWindow(user)

            # Mantener referencia para evitar GC
            self._child_window = w
            w.show()

            self.close()

        except Exception as e:
            self.show_error(f"Error al abrir admin: {e}")

    def _open_local(self, user: dict):
        """Abre la ventana principal de local."""

        try:
            from views.main_local import LocalWindow

            w = LocalWindow(
                user.get("username", ""),
                user.get("role", "local"),
                user.get("local", ""),
            )

            # Mantener referencia para evitar GC
            self._child_window = w
            w.show()

            self.close()

        except Exception as e:
            self.show_error(f"Error al abrir local: {e}")
