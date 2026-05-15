# views/main_local.py — Menú principal de local, estilo Mueblería Manarey
import json
import os
import threading
from datetime import datetime

from PyQt5.QtCore import QByteArray, QObject, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

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
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from models import problemas_model as pm

try:
    import app_theme as _theme

    _DARK = _theme.is_dark_mode
    _BG = lambda: _theme.get_palette_value("BG")
except Exception:
    _DARK = lambda: True
    _BG = lambda: "#0f0f14"

GOLD = "#C9A040"
GOLD_LIGHT = "#e8c860"
GOLD_DARK = "#8a6820"


# ══════════════════════════════════════════════════════════════════════════════
#  Fondo ornamental con borde dorado (QPainter)
# ══════════════════════════════════════════════════════════════════════════════
class OrnateBackground(QWidget):
    """Widget central con fondo oscuro y marco dorado ornamental."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        dark = _DARK()
        w, h = self.width(), self.height()

        # Fondo con gradiente
        grad = QLinearGradient(0, 0, w, h)
        if dark:
            grad.setColorAt(0.0, QColor("#131318"))
            grad.setColorAt(0.5, QColor("#0f0f14"))
            grad.setColorAt(1.0, QColor("#161620"))
        else:
            grad.setColorAt(0.0, QColor("#FFF8EC"))
            grad.setColorAt(0.5, QColor("#F9EDCF"))
            grad.setColorAt(1.0, QColor("#F5E5BC"))
        p.fillRect(self.rect(), QBrush(grad))

        m = 10  # margen exterior
        pad = 6  # distancia entre líneas
        i = m + pad  # margen interior

        gold = QColor(GOLD)
        gold_dim = QColor(GOLD_DARK) if dark else QColor("#c9a040")

        # Línea exterior fina
        p.setPen(QPen(gold_dim, 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawRect(m, m, w - 2 * m, h - 2 * m)

        # Línea interior principal
        p.setPen(QPen(gold, 2.0))
        p.drawRect(i, i, w - 2 * i, h - 2 * i)

        # Ornamentos en esquinas (diamante)
        d = 12
        corners = [(i, i), (w - i, i), (i, h - i), (w - i, h - i)]
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(gold))
        for cx, cy in corners:
            path = QPainterPath()
            path.moveTo(cx, cy - d)
            path.lineTo(cx + d, cy)
            path.lineTo(cx, cy + d)
            path.lineTo(cx - d, cy)
            path.closeSubpath()
            p.drawPath(path)

        # Mini líneas decorativas en lados
        p.setPen(QPen(gold_dim, 1.0))
        mx, my = w // 2, h // 2
        seg = 28
        for x in [mx - seg, mx + seg]:
            p.drawLine(x, i, x, i + 6)
            p.drawLine(x, h - i - 6, x, h - i)
        for y in [my - seg, my + seg]:
            p.drawLine(i, y, i + 6, y)
            p.drawLine(w - i - 6, y, w - i, y)

        p.end()


# ══════════════════════════════════════════════════════════════════════════════
#  Tarjeta de menú
# ══════════════════════════════════════════════════════════════════════════════
class MenuCard(QFrame):
    """Tarjeta de menú estilo imagen — fondo oscuro, borde dorado, ícono grande."""

    def __init__(self, icon: str, title: str, color: str = GOLD):
        super().__init__()
        self.color = color
        self._base_title = title
        self._hovered = False

        self.setMinimumSize(160, 170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 110))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)

        self._set_style(False)

        # Layout
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(16, 22, 16, 20)
        self._lay.setSpacing(14)
        self._lay.setAlignment(Qt.AlignCenter)

        # Ícono — más grande
        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setStyleSheet("background: transparent; font-size: 54px;")
        self._lay.addWidget(self._icon_lbl)

        # Título
        self._title_lbl = QLabel(title)
        self._title_lbl.setAlignment(Qt.AlignCenter)
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        c_title = "#F8F1E7" if _DARK() else "#2B2108"
        self._title_lbl.setStyleSheet(
            f"color: {c_title}; background: transparent; line-height: 130%;"
        )
        self._lay.addWidget(self._title_lbl)

    def _card_colors(self, hovered: bool):
        dark = _DARK()
        if dark:
            bg = "#252532" if hovered else "#1c1c28"
            border = GOLD if hovered else GOLD_DARK
            bw = "2px" if hovered else "1.5px"
        else:
            bg = "#F5E9CE" if hovered else "#FFF5E1"
            border = "#B8922E" if hovered else "#E8D8B8"
            bw = "2px" if hovered else "1.5px"
        return bg, border, bw

    def _set_style(self, hovered: bool):
        bg, border, bw = self._card_colors(hovered)
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: 14px;"
            f"border: {bw} solid {border}; }}"
        )
        shadow = self.graphicsEffect()
        if shadow:
            shadow.setBlurRadius(30 if hovered else 20)
            shadow.setColor(QColor(0, 0, 0, 140 if hovered else 110))

    def enterEvent(self, e):
        self._set_style(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._set_style(False)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if hasattr(self, "click_callback"):
            self.click_callback()
        super().mousePressEvent(e)

    def set_title_badge(self, count: int):
        text = f"{self._base_title} ({count})" if count else self._base_title
        self._title_lbl.setText(text)

    def adjust_compact(self, level: int):
        """Ajusta tamaño según nivel: 0=normal, 1=medio, 2=compacto."""
        if level == 2:
            self.setMinimumSize(140, 110)
            self._icon_lbl.setStyleSheet("background: transparent; font-size: 30px;")
            self._title_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self._lay.setContentsMargins(10, 10, 10, 10)
            self._lay.setSpacing(6)
        elif level == 1:
            self.setMinimumSize(150, 140)
            self._icon_lbl.setStyleSheet("background: transparent; font-size: 40px;")
            self._title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
            self._lay.setContentsMargins(12, 16, 12, 14)
            self._lay.setSpacing(10)
        else:
            self.setMinimumSize(160, 170)
            self._icon_lbl.setStyleSheet("background: transparent; font-size: 54px;")
            self._title_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
            self._lay.setContentsMargins(16, 22, 16, 20)
            self._lay.setSpacing(14)

    def refresh_theme(self):
        self._set_style(False)
        c = "#F8F1E7" if _DARK() else "#2B2108"
        self._title_lbl.setStyleSheet(
            f"color: {c}; background: transparent; line-height: 130%;"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Botón de barra de navegación superior
# ══════════════════════════════════════════════════════════════════════════════
class NavButton(QPushButton):
    def __init__(self, icon: str, label: str, active: bool = False):
        super().__init__(f"  {icon}  {label}")
        self.setCursor(Qt.PointingHandCursor)
        self._active = active
        self._refresh()

    def _refresh(self):
        dark = _DARK()
        c_text = "#F8F1E7" if dark else "#1a1208"
        c_active = GOLD
        c_hover = "rgba(201,160,64,0.15)"
        c_active_bg = "rgba(201,160,64,0.12)"
        if self._active:
            self.setStyleSheet(
                f"QPushButton {{ background: {c_active_bg}; color: {c_active};"
                f"border: none; border-bottom: 2px solid {c_active};"
                f"font-size: 13px; font-weight: 700; padding: 0 18px; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {c_text};"
                f"border: none; border-bottom: 2px solid transparent;"
                f"font-size: 13px; font-weight: 500; padding: 0 18px; }}"
                f"QPushButton:hover {{ background: {c_hover}; color: {c_active}; }}"
            )


# ══════════════════════════════════════════════════════════════════════════════
#  Ventana principal
# ══════════════════════════════════════════════════════════════════════════════
class LocalWindow(QMainWindow):
    """Panel principal de local — estilo Mueblería Manarey."""

    _update_found = pyqtSignal(str)  # version string

    def __init__(self, username: str, role: str, local: str):
        super().__init__()
        self.username = username
        self.role = role or "local"
        self.local = local or ""
        self.child = None
        self._skip_quit = False

        self.setWindowTitle(f"Manarey — {self.local}")
        self.setProperty("manarey_no_scale", True)
        self.setProperty("manarey_no_autoresize", True)
        self.setProperty("manarey_no_kiosk", True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setMinimumSize(760, 520)

        self._initial_maximize_pending = True
        self._presence_timer = None
        self._restore_window_state()

        self.setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────────
    def setup_ui(self):
        # Fondo base
        self._bg_widget = OrnateBackground()
        self.setCentralWidget(self._bg_widget)

        root = QVBoxLayout(self._bg_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.root = root

        root.addWidget(self._build_nav_bar())
        root.addWidget(self._build_brand_area(), 0, Qt.AlignHCenter)

        # Grid de tarjetas — toma todo el espacio restante (stretch=1)
        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(40, 4, 40, 4)
        self._cards_layout.setSpacing(0)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(16)
        self._grid.setVerticalSpacing(16)
        self._cards_layout.addLayout(self._grid)
        root.addWidget(self._cards_container, 1)  # stretch=1: llena todo

        # Footer pegado al fondo, sin stretch extra encima
        root.addWidget(self._build_footer(), 0, Qt.AlignHCenter)
        root.addWidget(self._build_status_bar())

        # Crear tarjetas
        self._create_cards()

        # Timers
        self._start_presence_pings()
        self._update_found.connect(self._on_update_found)
        QTimer.singleShot(1500, self._check_updates)
        self._messages_timer = QTimer(self)
        self._messages_timer.timeout.connect(self._update_messages_badge)
        self._messages_timer.start(60_000)
        QTimer.singleShot(2000, self._update_messages_badge)
        threading.Thread(target=self._prefetch_stock, daemon=True).start()

    def _build_nav_bar(self) -> QFrame:
        dark = _DARK()
        bar_bg = "#141420" if dark else "#F5E9CE"
        border = "rgba(201,160,64,0.25)" if dark else "rgba(198,168,91,0.4)"
        c_text = "#F8F1E7" if dark else "#2B2B2B"
        c_muted = "#a0a0a8" if dark else "#7A7A7A"

        bar = QFrame()
        bar.setObjectName("nav_bar")
        bar.setFixedHeight(50)
        bar.setStyleSheet(
            f"QFrame#nav_bar {{ background: {bar_bg};"
            f"border-bottom: 1px solid {border}; }}"
        )

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 12, 0)
        lay.setSpacing(0)

        # Tabs izquierda
        self._nav_inicio = NavButton("🏠", "Inicio", active=True)
        self._nav_inicio.clicked.connect(self._on_nav_inicio)
        lay.addWidget(self._nav_inicio)

        self._nav_config = NavButton("⚙️", "Configuración")
        self._nav_config.clicked.connect(self.open_settings)
        lay.addWidget(self._nav_config)

        self._nav_logout = NavButton("🚪", "Cerrar sesión")
        self._nav_logout.clicked.connect(self._go_login)
        # Estilo rojo para distinguirlo
        self._nav_logout.setStyleSheet(
            "QPushButton { background: transparent; color: #e07070;"
            "border: none; border-bottom: 2px solid transparent;"
            "font-size: 13px; font-weight: 500; padding: 0 18px; }"
            "QPushButton:hover { background: rgba(220,50,50,0.12);"
            "color: #ff9090; border-bottom: 2px solid #f87171; }"
        )
        lay.addWidget(self._nav_logout)

        lay.addStretch()

        # Botón de actualización disponible (oculto hasta detectar update)
        self._nav_update_btn = QPushButton("⬆  Actualizar")
        self._nav_update_btn.setCursor(Qt.PointingHandCursor)
        self._nav_update_btn.setFixedHeight(34)
        self._nav_update_btn.hide()
        self._nav_update_btn.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "    stop:0 #B8913A, stop:1 #D6B36A);"
            "  color: #0f0f14; font-size: 12px; font-weight: 700;"
            "  border: none; border-radius: 8px; padding: 0 16px; margin: 6px 8px 6px 0;"
            "}"
            "QPushButton:hover { background: #E8C86A; }"
            "QPushButton:pressed { background: #A07828; }"
        )
        self._nav_update_btn.clicked.connect(self._open_update_dialog)
        lay.addWidget(self._nav_update_btn)

        # Usuario + controles derecha
        self._user_lbl_nav = QLabel(f"Usuario: {self.username}  ▾")
        self._user_lbl_nav.setStyleSheet(
            f"color: {c_muted}; font-size: 12px; padding: 0 12px;"
        )
        lay.addWidget(self._user_lbl_nav)

        btn_min = QPushButton("⎯")
        btn_min.setFixedSize(36, 36)
        btn_min.setCursor(Qt.PointingHandCursor)
        btn_min.setToolTip("Minimizar")
        if dark:
            btn_min.setStyleSheet(
                "QPushButton { background: rgba(255,255,255,0.07); color: #c0c0c8;"
                "border: 1px solid rgba(255,255,255,0.10); border-radius: 10px;"
                "font-size: 15px; font-weight: 900; }"
                "QPushButton:hover { background: rgba(255,255,255,0.16); color: white;"
                "border-color: rgba(255,255,255,0.25); }"
                "QPushButton:pressed { background: rgba(255,255,255,0.05); }"
            )
        else:
            btn_min.setStyleSheet(
                "QPushButton { background: rgba(0,0,0,0.06); color: #5a4020;"
                "border: 1px solid rgba(0,0,0,0.15); border-radius: 10px;"
                "font-size: 15px; font-weight: 900; }"
                "QPushButton:hover { background: rgba(0,0,0,0.14); color: #2B2B2B;"
                "border-color: rgba(0,0,0,0.25); }"
            )
        btn_min.clicked.connect(self.showMinimized)
        lay.addWidget(btn_min)
        self._btn_min = btn_min

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(36, 36)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setToolTip("Cerrar")
        btn_close.setStyleSheet(
            "QPushButton { background: rgba(220,50,50,0.18); color: #ff9090;"
            "border: 1px solid rgba(220,50,50,0.35); border-radius: 10px;"
            "font-size: 13px; font-weight: 900; }"
            "QPushButton:hover { background: #c0392b; color: white;"
            "border-color: #c0392b; }"
            "QPushButton:pressed { background: #922b21; }"
        )
        btn_close.clicked.connect(self.close)
        lay.addWidget(btn_close)
        self._btn_close = btn_close

        self._nav_bar = bar
        return bar

    def _build_brand_area(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignHCenter)

        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet("background: transparent;")

        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "assets",
            "images",
            "logo_manarey_brand.png",
        )
        self._logo_pixmap_orig = QPixmap(logo_path)
        if not self._logo_pixmap_orig.isNull():
            pixmap = self._logo_pixmap_orig.scaledToWidth(240, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pixmap)
        else:
            logo_lbl.setText("♛  MANAREY")
            logo_lbl.setFont(QFont("Segoe UI", 36, QFont.Black))
            logo_lbl.setStyleSheet(f"color: {GOLD}; background: transparent;")

        self._logo_lbl = logo_lbl
        self._apply_brand_shadow(logo_lbl)
        lay.addWidget(logo_lbl)
        return w

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignHCenter)

        footer_lbl = QLabel()
        footer_lbl.setAlignment(Qt.AlignCenter)
        footer_lbl.setStyleSheet("background: transparent;")

        footer_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "assets",
            "images",
            "menu_footer.png",
        )
        self._footer_pixmap_orig = QPixmap(footer_path)
        if not self._footer_pixmap_orig.isNull():
            pixmap = self._footer_pixmap_orig.scaledToWidth(
                420, Qt.SmoothTransformation
            )
            footer_lbl.setPixmap(pixmap)
        else:
            footer_lbl.setText("🛋️  🏮  🪑\n— Menú del Sistema —")
            footer_lbl.setFont(QFont("Georgia", 13))
            footer_lbl.setStyleSheet(f"color: {GOLD}; background: transparent;")

        self._footer_lbl = footer_lbl
        self._apply_brand_shadow(footer_lbl)
        lay.addWidget(footer_lbl)
        return w

    def _apply_brand_shadow(self, lbl: QLabel):
        """Sombra que contrasta con el fondo actual: dorada en oscuro, marrón en claro."""
        dark = _DARK()
        shadow = QGraphicsDropShadowEffect()
        if dark:
            shadow.setBlurRadius(22)
            shadow.setColor(QColor(201, 160, 64, 140))  # dorado suave
            shadow.setOffset(0, 3)
        else:
            shadow.setBlurRadius(18)
            shadow.setColor(
                QColor(80, 45, 5, 200)
            )  # marrón oscuro — contrasta con crema
            shadow.setOffset(0, 2)
        lbl.setGraphicsEffect(shadow)

    def _build_status_bar(self) -> QFrame:
        dark = _DARK()
        bar_bg = "#0f0f14" if dark else "#F5E9CE"
        border = "rgba(201,160,64,0.15)" if dark else "rgba(198,168,91,0.3)"
        c_muted = "#505060" if dark else "#7A7A7A"

        bar = QFrame()
        bar.setObjectName("status_bar")
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            f"QFrame#status_bar {{ background: {bar_bg};"
            f"border-top: 1px solid {border}; }}"
        )

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(0)

        fecha = datetime.now().strftime("%d/%m/%Y")
        left = QLabel(
            f"Usuario: {self.username}  |  Sucursal: {self.local}  |  Fecha: {fecha}"
        )
        left.setStyleSheet(
            f"color: {c_muted}; font-size: 11px; background: transparent;"
        )
        lay.addWidget(left)
        self._status_left_lbl = left

        lay.addStretch()

        try:
            from version import __version__

            ver_text = f"Versión {__version__}"
        except Exception:
            ver_text = "Versión 1.0"
        right = QLabel(ver_text)
        right.setStyleSheet(
            f"color: {c_muted}; font-size: 11px; background: transparent;"
        )
        lay.addWidget(right)
        self._status_right_lbl = right

        self._status_bar = bar
        return bar

    def _create_cards(self):
        """Crea las 6 tarjetas en el orden de la imagen."""
        cards_def = [
            ("🧾", "Emisión de Boleta", GOLD, self.open_boleta),
            ("📦", "Gestión de Stock", GOLD, self.open_stock),
            ("🚚", "Envíos", GOLD, self.open_envios),
            ("💬", "Informar Problemas", GOLD, self.open_problemas),
            ("📈", "Historial de Ventas", GOLD, self.open_ventas_history),
            ("📋", "Historial de Movimientos", GOLD, self.open_history),
        ]

        self.menu_cards = []
        for icon, title, color, callback in cards_def:
            card = MenuCard(icon, title, color)
            card.click_callback = callback
            if title == "Informar Problemas":
                self.card_problemas = card
            self.menu_cards.append(card)

        self._reflow_cards()

    # ── Navegación top ────────────────────────────────────────────────────────
    def _on_nav_inicio(self):
        pass  # ya estamos en inicio

    # ── Layout responsivo ─────────────────────────────────────────────────────
    def _card_columns(self) -> int:
        w = max(1, self.width())
        if w < 700:
            return 1
        if w < 1100:
            return 2
        return 3

    def _reflow_cards(self):
        if not hasattr(self, "_grid"):
            return
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        cols = self._card_columns()
        cards = getattr(self, "menu_cards", [])
        for idx, card in enumerate(cards):
            self._grid.addWidget(card, idx // cols, idx % cols)
        # Columnas y filas con stretch igual → tarjetas llenan todo el espacio
        for col in range(cols):
            self._grid.setColumnStretch(col, 1)
        n_rows = (len(cards) + cols - 1) // cols
        for row in range(n_rows):
            self._grid.setRowStretch(row, 1)

    def _apply_responsive_layout(self):
        try:
            w = max(1, self.width())
            h = max(1, self.height())

            # ── Márgenes y espaciado horizontal ──────────────────────────────
            if w < 860:
                self._cards_layout.setContentsMargins(24, 0, 24, 0)
                h_gap = 10
            elif w < 1280:
                self._cards_layout.setContentsMargins(40, 0, 40, 0)
                h_gap = 14
            else:
                self._cards_layout.setContentsMargins(60, 0, 60, 0)
                h_gap = 18

            # ── Nivel de compacidad según altura disponible ───────────────────
            # Deducir espacio fijo: navbar(50) + statusbar(36) = 86px
            usable = h - 86
            if usable < 480:
                compact = 2  # muy compacto: icono 30px, min_h 110
                logo_w = 140
                footer_w = 0  # ocultar footer
                v_gap = 8
            elif usable < 620:
                compact = 1  # medio: icono 40px, min_h 140
                logo_w = 180
                footer_w = 220
                v_gap = 10
            else:
                compact = 0  # normal: icono 54px, min_h 170
                logo_w = 240
                footer_w = 420
                v_gap = h_gap

            self._grid.setHorizontalSpacing(h_gap)
            self._grid.setVerticalSpacing(v_gap)

            # ── Logo ──────────────────────────────────────────────────────────
            if hasattr(self, "_logo_lbl") and hasattr(self, "_logo_pixmap_orig"):
                if not self._logo_pixmap_orig.isNull():
                    px = self._logo_pixmap_orig.scaledToWidth(
                        logo_w, Qt.SmoothTransformation
                    )
                    self._logo_lbl.setPixmap(px)

            # ── Footer ────────────────────────────────────────────────────────
            if hasattr(self, "_footer_lbl"):
                if footer_w == 0:
                    self._footer_lbl.hide()
                else:
                    self._footer_lbl.show()
                    if (
                        hasattr(self, "_footer_pixmap_orig")
                        and not self._footer_pixmap_orig.isNull()
                    ):
                        px = self._footer_pixmap_orig.scaledToWidth(
                            footer_w, Qt.SmoothTransformation
                        )
                        self._footer_lbl.setPixmap(px)

            # ── Tarjetas ──────────────────────────────────────────────────────
            for card in getattr(self, "menu_cards", []):
                if hasattr(card, "adjust_compact"):
                    card.adjust_compact(compact)

            self._reflow_cards()
        except Exception:
            pass

    # ── Navegación a sub-vistas ───────────────────────────────────────────────
    def _push_child(self, win, title: str):
        self.child = win
        self.child.setWindowTitle(title)

        # Propagar tema actual a la sub-vista
        try:
            import app_theme as _at

            _at.apply_to_app()  # refresca QApplication global
            ss = _at.build_stylesheet(_at.is_dark_mode(), _at.get_font_size_px())
            win.setStyleSheet(ss)  # base para widgets sin estilo propio
            # Notificar a vistas que soportan refresh_theme
            if hasattr(win, "refresh_theme"):
                win.refresh_theme()
        except Exception:
            pass

        def back():
            try:
                self.child.hide()
            except Exception:
                pass
            self.child = None
            self.show()
            self.raise_()
            self.activateWindow()

        if hasattr(self.child, "back_command") and self.child.back_command is None:
            self.child.back_command = back
        if hasattr(self.child, "set_back_command"):
            try:
                self.child.set_back_command(back)
            except Exception:
                pass

        self.hide()
        self.child.show()

    def on_back(self):
        if self.child:
            try:
                self.child.hide()
            except Exception:
                pass
        self.child = None
        self.show()
        self.raise_()
        self.activateWindow()

    # ── Helpers de navegación con caché de vistas ────────────────────────────
    def _get_prebuilt(self, key):
        """Devuelve la vista precargada si existe, o None."""
        return getattr(self, "_prebuilt", {}).get(key)

    def _open_view(self, key, title, builder, refresher=None):
        """
        Abre una vista secundaria usando la instancia precargada si está disponible
        (navegación instantánea), o la construye en el momento como fallback.
        `refresher` es un callable opcional que recibe la vista para recargar datos.
        """
        try:
            win = self._get_prebuilt(key)
            if win is not None:
                # Resetear back_command para que _push_child lo fije fresco
                if hasattr(win, "back_command"):
                    win.back_command = None
                if refresher:
                    try:
                        refresher(win)
                    except Exception:
                        pass
            else:
                win = builder()
            self._push_child(win, title)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir {title}:\n{e}")

    # ── Prefetch ──────────────────────────────────────────────────────────────
    def _prefetch_stock(self):
        """Precarga el stock del local en background para que abra al instante."""
        try:
            local = getattr(self, "local", None)
            if not local:
                return
            from views.stock_view import _stock_module_cache

            if local in _stock_module_cache:
                return
            from models import stock_model as sm

            products = sm.get_stock_filtered(local, "", "", [], "", "", "")
            _stock_module_cache[local] = list(products or [])
        except Exception:
            pass

    # ── Acciones de tarjetas ──────────────────────────────────────────────────
    def open_stock(self):
        self._open_view(
            "stock",
            "Gestión de Stock",
            lambda: __import__("views.stock_view", fromlist=["StockView"]).StockView(
                self.username, self.role, self.local, back_command=self.on_back
            ),
            refresher=lambda w: w.load_data(),
        )

    def open_history(self):
        self._open_view(
            "history",
            "Historial de Movimientos",
            lambda: __import__(
                "views.history_view", fromlist=["HistoryWindow"]
            ).HistoryWindow(
                self.username, self.role, self.local, back_command=self.on_back
            ),
            refresher=lambda w: w._fetch(),
        )

    def open_ventas_history(self):
        self._open_view(
            "ventas",
            "Historial de Ventas",
            lambda: __import__(
                "views.ventas_history_view", fromlist=["VentasWindow"]
            ).VentasWindow(
                self.username, self.role, self.local, back_command=self.on_back
            ),
            refresher=lambda w: w.cargar_ventas(),
        )

    def open_boleta(self):
        self._open_view(
            "boleta",
            "Emitir Boleta",
            lambda: __import__("views.boleta_view", fromlist=["BoletaView"]).BoletaView(
                self.username, self.role, self.local, back_command=None
            ),
        )

    def open_envios(self):
        self._open_view(
            "envios",
            "Envíos",
            lambda: __import__(
                "views.envios_view", fromlist=["EnviosWindow"]
            ).EnviosWindow(
                self.username, self.role, self.local, back_command=self.on_back
            ),
            refresher=lambda w: w.load_data(),
        )

    def open_problemas(self):
        self._open_view(
            "problemas",
            "Informar Problemas",
            lambda: __import__(
                "views.problemas_view", fromlist=["ProblemasWindow"]
            ).ProblemasWindow(
                self.username, self.role, self.local, back_command=self.on_back
            ),
            refresher=lambda w: w.load_data(),
        )
        QTimer.singleShot(1200, self._update_messages_badge)

    def refresh_theme(self):
        """Reconstruye estilos del menú cuando cambia el tema."""
        try:
            dark = _DARK()
            # Repintar fondo ornamental
            if hasattr(self, "_bg_widget"):
                self._bg_widget.update()

            # Actualizar nav bar
            if hasattr(self, "_nav_bar"):
                bar_bg = "#141420" if dark else "#F5E9CE"
                border = "rgba(201,160,64,0.25)" if dark else "rgba(198,168,91,0.4)"
                self._nav_bar.setStyleSheet(
                    f"QFrame#nav_bar {{ background: {bar_bg};"
                    f"border-bottom: 1px solid {border}; }}"
                )

            # Actualizar botones de nav
            for btn in [
                getattr(self, "_nav_inicio", None),
                getattr(self, "_nav_config", None),
            ]:
                if btn and hasattr(btn, "_refresh"):
                    btn._refresh()

            # Botones minimize/close
            if hasattr(self, "_btn_min"):
                if dark:
                    self._btn_min.setStyleSheet(
                        "QPushButton { background: rgba(255,255,255,0.07); color: #c0c0c8;"
                        "border: 1px solid rgba(255,255,255,0.10); border-radius: 10px;"
                        "font-size: 15px; font-weight: 900; }"
                        "QPushButton:hover { background: rgba(255,255,255,0.16); color: white; }"
                    )
                else:
                    self._btn_min.setStyleSheet(
                        "QPushButton { background: rgba(0,0,0,0.06); color: #5a4020;"
                        "border: 1px solid rgba(0,0,0,0.15); border-radius: 10px;"
                        "font-size: 15px; font-weight: 900; }"
                        "QPushButton:hover { background: rgba(0,0,0,0.14); color: #2B2B2B; }"
                    )

            # User label
            c_muted = "#a0a0a8" if dark else "#7A7A7A"
            if hasattr(self, "_user_lbl_nav"):
                self._user_lbl_nav.setStyleSheet(
                    f"color: {c_muted}; font-size: 12px; padding: 0 12px;"
                )

            # Status bar
            if hasattr(self, "_status_bar"):
                bar_bg = "#0f0f14" if dark else "#F5E9CE"
                border = "rgba(201,160,64,0.15)" if dark else "rgba(198,168,91,0.3)"
                self._status_bar.setStyleSheet(
                    f"QFrame#status_bar {{ background: {bar_bg};"
                    f"border-top: 1px solid {border}; }}"
                )
            c_muted2 = "#505060" if dark else "#7A7A7A"
            for lbl in [
                getattr(self, "_status_left_lbl", None),
                getattr(self, "_status_right_lbl", None),
            ]:
                if lbl:
                    lbl.setStyleSheet(
                        f"color: {c_muted2}; font-size: 11px; background: transparent;"
                    )

            # Logo y footer — actualizar sombra según tema
            for lbl in [
                getattr(self, "_logo_lbl", None),
                getattr(self, "_footer_lbl", None),
            ]:
                if lbl:
                    self._apply_brand_shadow(lbl)

            # Cards
            for card in getattr(self, "menu_cards", []):
                if hasattr(card, "refresh_theme"):
                    card.refresh_theme()
        except Exception:
            pass

    def open_settings(self):
        try:
            from views.settings_dialog import SettingsDialog

            dlg = SettingsDialog(self)
            if dlg.exec_():
                self.refresh_theme()  # rebuild all menu chrome
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir ajustes:\n{e}")

    # ── Badges y mensajes ─────────────────────────────────────────────────────
    def _update_messages_badge(self):
        try:
            if not hasattr(self, "card_problemas"):
                return
            unread = pm.count_local_unread(self.local)
            self.card_problemas.set_title_badge(unread)
        except Exception:
            pass

    # ── Eventos de ventana ────────────────────────────────────────────────────
    def closeEvent(self, event):
        try:
            if self.child:
                self.child.close()
        except Exception:
            pass
        self._persist_window_state()
        super().closeEvent(event)
        if not self._skip_quit:
            try:
                from PyQt5.QtWidgets import QApplication

                QApplication.quit()
            except Exception:
                pass

    def showEvent(self, event):
        super().showEvent(event)
        if self._initial_maximize_pending:
            self._initial_maximize_pending = False
            QTimer.singleShot(0, self._force_fill_screen)
            return
        self._apply_responsive_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _force_fill_screen(self):
        try:
            screen = self.screen()
            if screen is not None:
                geo = screen.geometry()
                self.setGeometry(geo)
            self.showFullScreen()
        except Exception:
            pass
        QTimer.singleShot(0, self._apply_responsive_layout)
        QTimer.singleShot(120, self._apply_responsive_layout)

    # ── Persistencia de ventana ───────────────────────────────────────────────
    def _prefs_path(self):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, "Manarey", "user_prefs.json")
        return os.path.join(
            os.path.expanduser("~"), ".manarey_prefs", "user_prefs.json"
        )

    def _restore_window_state(self):
        try:
            p_path = self._prefs_path()
            if not os.path.exists(p_path):
                return
            with open(p_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            prefs = data.get("main_local_window", {})
            geo = prefs.get("geometry")
            if geo:
                arr = QByteArray.fromBase64(geo.encode())
                if not arr.isEmpty():
                    self.restoreGeometry(arr)
            if prefs.get("maximized"):
                self.showMaximized()
        except Exception:
            pass

    def _persist_window_state(self):
        try:
            p_path = self._prefs_path()
            os.makedirs(os.path.dirname(p_path), exist_ok=True)
            data = {}
            if os.path.exists(p_path):
                with open(p_path, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
            data["main_local_window"] = {
                "geometry": bytes(self.saveGeometry().toBase64()).decode(),
                "maximized": bool(self.isMaximized()),
            }
            with open(p_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # ── Login ─────────────────────────────────────────────────────────────────
    def _go_login(self):
        try:
            if self.child:
                self.child.close()
        except Exception:
            pass
        try:
            from views.login_view import LoginWindow

            self._login_win = LoginWindow(skip_autologin=True, prev_window=self)
            self._login_win.show()
            self.hide()
        except Exception as e:
            import traceback

            traceback.print_exc()
            self.close()

    # ── Presencia ─────────────────────────────────────────────────────────────
    def _start_presence_pings(self):
        try:
            from PyQt5.QtCore import QTimer as _QT

            from models import user_model

            def ping():
                try:
                    user_model.update_last_seen(self.username)
                except Exception:
                    pass

            ping()
            self._presence_timer = _QT(self)
            self._presence_timer.setInterval(60_000)
            self._presence_timer.timeout.connect(ping)
            self._presence_timer.start()
        except Exception:
            pass

    # ── Actualizaciones ───────────────────────────────────────────────────────
    def _check_updates(self):
        """Lanza la verificación de updates en un hilo de fondo para no bloquear la UI."""

        def _worker():
            try:
                from updater import get_pending_update, refresh_update_state

                manifest = refresh_update_state()
                if not manifest:
                    manifest = get_pending_update()
                if not manifest or not manifest.get("version"):
                    return
                version = manifest["version"]
                try:
                    self._update_found.emit(version)
                except Exception:
                    pass
            except Exception:
                pass

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _on_update_found(self, version: str):
        """Slot en el hilo principal: muestra el botón de actualización."""
        try:
            if hasattr(self, "_nav_update_btn"):
                self._nav_update_btn.setText(f"⬆  Actualizar a v{version}")
                self._nav_update_btn.show()
        except Exception:
            pass

    def _open_update_dialog(self):
        """Abre el diálogo de instalación de la actualización pendiente."""
        try:
            from ui.ui_update_dialog import UpdateDialog as AppUpdateDialog
            from updater import get_pending_update

            pending = get_pending_update()
            if not pending:
                return
            from updater import get_current_version, start_update_from_pending

            dlg = AppUpdateDialog(self)
            dlg.set_update_info(
                version=pending.get("version", ""),
                changelog=pending.get("changelog", ""),
                mandatory=bool(pending.get("mandatory")),
                current_version=get_current_version(),
            )
            if dlg.exec_() == AppUpdateDialog.Accepted:
                start_update_from_pending(parent_widget=self)
        except Exception as exc:
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "Error", f"No se pudo abrir la actualización:\n{exc}"
            )

    # ── StatusTile (compatibilidad) ───────────────────────────────────────────
    @property
    def status_messages(self):
        return None

    @property
    def status_updates(self):
        return None
