# views/settings_dialog.py — Configuración: tema oscuro/claro + tamaño de letra
import json
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import app_theme


# ── Toggle switch personalizado ────────────────────────────────────────────────
class ToggleSwitch(QWidget):
    """Switch oscuro/claro estilo moderno."""

    def __init__(self, checked=True, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._callbacks = []
        self.setFixedSize(64, 32)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool):
        self._checked = bool(value)
        self.update()

    def addCallback(self, fn):
        self._callbacks.append(fn)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self.update()
        for fn in self._callbacks:
            try:
                fn(self._checked)
            except Exception:
                pass

    def paintEvent(self, event):
        from PySide6.QtGui import QColor, QPainter, QPen

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        radius = h / 2

        # Track
        track_color = QColor("#C9A040") if self._checked else QColor("#4a4a55")
        p.setPen(Qt.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(0, 0, w, h, radius, radius)

        # Icons on track
        p.setPen(QPen(QColor("white"), 1.5))
        p.setFont(QFont("Segoe UI", 9))
        if self._checked:
            p.drawText(6, 0, w // 2 - 4, h, Qt.AlignCenter, "🌙")
        else:
            p.drawText(w // 2, 0, w // 2 - 4, h, Qt.AlignCenter, "☀️")

        # Handle
        handle_x = w - h + 3 if self._checked else 3
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("white"))
        p.drawEllipse(handle_x, 3, h - 6, h - 6)
        p.end()


# ── Diálogo principal ──────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración")
        self.setModal(True)
        self.setFixedWidth(440)

        self._dark = app_theme.is_dark_mode()
        self._font_key = app_theme.get_font_size_key()

        self._apply_own_style()
        self._build_ui()

    # ── Fondo pintado directamente — no depende del stylesheet global ──────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self._COLORS[self._dark]["bg"]))
        p.end()

    # Colores por tema — espejo de app_theme._LIGHT / _DARK
    _COLORS = {
        True: {  # dark
            "bg": "#1a1a22",
            "surface": "#252530",
            "text": "#F8F1E7",
            "muted": "#a0a0a8",
            "border": "#3e3e44",
            "gold": "#C9A040",
            "preview_bg": "#252530",
        },
        False: {  # light — crema cálida
            "bg": "#FFF8EC",
            "surface": "#FFFDF5",
            "text": "#2B2108",
            "muted": "#7A6A50",
            "border": "#EAD9B8",
            "gold": "#B8922E",
            "preview_bg": "#FFF5E1",
        },
    }

    def _apply_own_style(self):
        col = self._COLORS[self._dark]
        c_bg = col["bg"]
        c_surface = col["surface"]
        c_text = col["text"]
        c_muted = col["muted"]
        c_border = col["border"]
        c_gold = col["gold"]

        # El fondo del diálogo lo pinta paintEvent() directamente.
        # El stylesheet solo necesita controlar los widgets hijos.
        self.setStyleSheet(
            f"""
            QLabel    {{ color: {c_text}; background: transparent; }}
            QFrame    {{ color: {c_text}; background: transparent; }}
            QWidget   {{ background: transparent; color: {c_text}; }}
            QPushButton {{
                background: {c_surface};
                color: {c_text};
                border: 1px solid {c_border};
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 700;
            }}
            QPushButton:hover {{ border-color: {c_gold}; color: {c_gold}; }}
            QPushButton#btn_primary {{
                background: {c_gold};
                color: #1a1208;
                border: none;
            }}
            QPushButton#btn_primary:hover {{ background: #D4A840; }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {c_border};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 20px; height: 20px;
                margin: -7px 0;
                background: {c_gold};
                border-radius: 10px;
            }}
            QSlider::sub-page:horizontal {{
                background: {c_gold};
                border-radius: 3px;
            }}
        """
        )
        self.update()  # dispara paintEvent → redibuja el fondo

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        c_gold = self._COLORS[self._dark]["gold"]
        lbl.setStyleSheet(
            f"color: {c_gold}; font-size: 10px; font-weight: 900; letter-spacing: 1.5px;"
        )
        return lbl

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        c_border = self._COLORS[self._dark]["border"]
        line.setStyleSheet(f"background: {c_border}; max-height: 1px; border: none;")
        return line

    def _build_ui(self):
        col = self._COLORS[self._dark]
        c_text = col["text"]
        c_muted = col["muted"]

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(18)

        # ── Título ────────────────────────────────────────────────────────────
        title = QLabel("⚙️  Configuración")
        title.setFont(QFont("Segoe UI", 16, QFont.Black))
        title.setStyleSheet(f"color: {c_text}; font-size: 16px; font-weight: 900;")
        root.addWidget(title)

        root.addWidget(self._separator())

        # ── Tema ──────────────────────────────────────────────────────────────
        root.addWidget(self._section_label("Apariencia"))

        theme_row = QHBoxLayout()
        theme_row.setSpacing(14)

        moon_lbl = QLabel("Modo oscuro")
        moon_lbl.setStyleSheet(f"color: {c_text}; font-weight: 600;")
        theme_row.addWidget(moon_lbl)
        theme_row.addStretch()

        self.toggle = ToggleSwitch(checked=self._dark)
        self.toggle.addCallback(self._on_toggle_theme)
        theme_row.addWidget(self.toggle)

        sun_lbl = QLabel("Modo claro")
        sun_lbl.setStyleSheet(f"color: {c_muted};")
        theme_row.addWidget(sun_lbl)

        root.addLayout(theme_row)

        self.theme_hint = QLabel(
            "Modo oscuro activo" if self._dark else "Modo claro activo"
        )
        self.theme_hint.setStyleSheet(f"color: {c_muted}; font-size: 11px;")
        root.addWidget(self.theme_hint)

        root.addWidget(self._separator())

        # ── Tamaño de letra ───────────────────────────────────────────────────
        root.addWidget(self._section_label("Tamaño de letra"))

        keys = app_theme.FONT_SIZE_KEYS
        idx = keys.index(self._font_key) if self._font_key in keys else 2

        font_header = QHBoxLayout()
        self.font_size_label = QLabel(
            f"{app_theme.FONT_SIZE_LABELS[self._font_key]}  "
            f"({app_theme.FONT_SIZES[self._font_key]}px)"
        )
        self.font_size_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.font_size_label.setStyleSheet(f"color: {col['gold']}; font-weight: 700;")
        font_header.addWidget(self.font_size_label)
        font_header.addStretch()
        root.addLayout(font_header)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(len(keys) - 1)
        self.slider.setValue(idx)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(1)
        self.slider.setPageStep(1)
        self.slider.setSingleStep(1)
        self.slider.valueChanged.connect(self._on_slider)
        root.addWidget(self.slider)

        # Etiquetas debajo del slider
        tick_row = QHBoxLayout()
        tick_row.setContentsMargins(0, 0, 0, 0)
        for key in keys:
            lbl = QLabel(app_theme.FONT_SIZE_LABELS[key])
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {c_muted}; font-size: 10px;")
            tick_row.addWidget(lbl)
        root.addLayout(tick_row)

        # Preview de texto
        self.preview_label = QLabel("Así se verá el texto en el programa")
        self.preview_label.setAlignment(Qt.AlignCenter)
        _px0 = app_theme.FONT_SIZES[self._font_key]
        self.preview_label.setStyleSheet(
            f"color: {c_text}; background: {col['preview_bg']};"
            f" border-radius: 8px; padding: 10px; font-size: {_px0}px;"
        )
        root.addWidget(self.preview_label)

        root.addWidget(self._separator())

        # ── Escala de resolución ──────────────────────────────────────────────
        root.addWidget(self._section_label("Escala de resolución"))
        scale_hint = QLabel("Los cambios de escala requieren reiniciar la aplicación.")
        scale_hint.setStyleSheet(f"color: {c_muted}; font-size: 11px;")
        scale_hint.setWordWrap(True)
        root.addWidget(scale_hint)

        scale_keys = ["auto", "1.0", "1.25", "1.5", "1.75"]
        scale_labels = ["Automático", "100%", "125%", "150%", "175%"]
        current_scale = self._load_pref("scale_preference", "auto")
        self._scale_key = current_scale

        scale_row = QHBoxLayout()
        scale_row.setSpacing(8)
        self._scale_btns = {}
        for k, lbl_text in zip(scale_keys, scale_labels):
            btn = QPushButton(lbl_text)
            btn.setCheckable(True)
            btn.setChecked(k == current_scale)
            btn.setCursor(Qt.PointingHandCursor)
            if k == current_scale:
                btn.setStyleSheet(
                    f"background: {col['gold']}; color: #1a1208; border: none; "
                    "border-radius: 6px; padding: 5px 10px; font-weight: 800;"
                )
            else:
                btn.setStyleSheet(
                    f"background: {col['surface']}; color: {c_muted};"
                    f" border: 1px solid {col['border']};"
                    "border-radius: 6px; padding: 5px 10px; font-weight: 600;"
                )
            btn.clicked.connect(lambda checked, key=k: self._on_scale_btn(key))
            self._scale_btns[k] = btn
            scale_row.addWidget(btn)
        root.addLayout(scale_row)

        root.addWidget(self._separator())

        # ── Botones ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_apply = QPushButton("Aplicar cambios")
        btn_apply.setObjectName("btn_primary")
        btn_apply.setCursor(Qt.PointingHandCursor)
        btn_apply.clicked.connect(self._apply_and_close)
        btn_row.addWidget(btn_apply)

        root.addLayout(btn_row)

    # ── Callbacks ──────────────────────────────────────────────────────────────
    def _on_toggle_theme(self, checked: bool):
        self._dark = checked
        self.theme_hint.setText(
            'Modo oscuro activo — se aplicará al cerrar con "Aplicar cambios"'
            if checked
            else 'Modo claro activo — se aplicará al cerrar con "Aplicar cambios"'
        )
        # Actualizar preview_label con el tema nuevo
        col = self._COLORS[self._dark]
        px = app_theme.FONT_SIZES[self._font_key]
        self.preview_label.setStyleSheet(
            f"color: {col['text']}; background: {col['preview_bg']};"
            f" border-radius: 8px; padding: 10px; font-size: {px}px;"
        )
        # Solo re-estilizar ESTE diálogo (no la app entera)
        self._apply_own_style()
        self._refresh_dynamic_labels()

    def _on_slider(self, value: int):
        col = self._COLORS[self._dark]
        keys = app_theme.FONT_SIZE_KEYS
        self._font_key = keys[value]
        px = app_theme.FONT_SIZES[self._font_key]
        self.font_size_label.setText(
            f"{app_theme.FONT_SIZE_LABELS[self._font_key]}  ({px}px)"
        )
        self.preview_label.setStyleSheet(
            f"color: {col['text']}; background: {col['preview_bg']};"
            f" border-radius: 8px; padding: 10px; font-size: {px}px;"
        )

    def _on_scale_btn(self, key: str):
        self._scale_key = key
        col = self._COLORS[self._dark]
        for k, btn in self._scale_btns.items():
            if k == key:
                btn.setStyleSheet(
                    f"background: {col['gold']}; color: #1a1208; border: none;"
                    " border-radius: 6px; padding: 5px 10px; font-weight: 800;"
                )
            else:
                btn.setStyleSheet(
                    f"background: {col['surface']}; color: {col['muted']};"
                    f" border: 1px solid {col['border']};"
                    " border-radius: 6px; padding: 5px 10px; font-weight: 600;"
                )

    def _refresh_dynamic_labels(self):
        """Actualiza widgets con estilos inline que no heredan del stylesheet del diálogo."""
        try:
            col = self._COLORS[self._dark]
            c_muted = col["muted"]
            c_gold = col["gold"]
            c_border = col["border"]
            c_surface = col["surface"]

            # Hint del toggle
            self.theme_hint.setStyleSheet(f"color: {c_muted}; font-size: 11px;")

            # Label de tamaño de fuente
            self.font_size_label.setStyleSheet(f"color: {c_gold}; font-weight: 700;")

            # Section labels (detectados por letter-spacing en su stylesheet)
            for child in self.findChildren(QLabel):
                if "letter-spacing" in child.styleSheet():
                    child.setStyleSheet(
                        f"color: {c_gold}; font-size: 10px;"
                        " font-weight: 900; letter-spacing: 1.5px;"
                    )

            # Separadores
            for child in self.findChildren(QFrame):
                if child.frameShape() == QFrame.HLine:
                    child.setStyleSheet(
                        f"background: {c_border}; max-height: 1px; border: none;"
                    )

            # Botones de escala
            for k, btn in self._scale_btns.items():
                if k == self._scale_key:
                    btn.setStyleSheet(
                        f"background: {c_gold}; color: #1a1208; border: none;"
                        " border-radius: 6px; padding: 5px 10px; font-weight: 800;"
                    )
                else:
                    btn.setStyleSheet(
                        f"background: {c_surface}; color: {c_muted};"
                        f" border: 1px solid {c_border};"
                        " border-radius: 6px; padding: 5px 10px; font-weight: 600;"
                    )
        except Exception:
            pass

    def _apply_and_close(self):
        # Guardar prefs
        app_theme.save_pref("dark_mode", self._dark)
        app_theme.save_pref("font_size", self._font_key)
        app_theme.save_pref("scale_preference", self._scale_key)

        # Aplicar globalmente
        app_theme.apply_to_app()

        self.accept()

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _load_pref(self, key: str, default=None):
        return app_theme.load_prefs().get(key, default)
