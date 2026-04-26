"""
ui_update_dialog.py — Diálogo de actualización rediseñado
"""

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _ss(*parts):
    return " ".join(parts)


GOLD = "#D6B36A"
GOLD_DARK = "#A88445"
GOLD_SOFT = "rgba(214,179,106,0.15)"
BG_MAIN = "#12100E"
BG_CARD = "#1C1813"
BG_INPUT = "#252018"
BORDER = "rgba(214,179,106,0.22)"
TEXT = "#F5ECD8"
MUTED = "#9A8A72"
GREEN = "#4CAF7D"
GREEN_BG = "rgba(76,175,125,0.12)"


# ─── Botón animado (pulso dorado) ─────────────────────────────────────────────


class PulsingButton(QPushButton):
    """Botón con borde que pulsa suavemente en dorado."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._alpha = 80
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._pulse_tick)
        self._direction = 1
        self._anim_timer.start(30)

    def _pulse_tick(self):
        self._alpha += self._direction * 4
        if self._alpha >= 220:
            self._direction = -1
        elif self._alpha <= 60:
            self._direction = 1
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(214, 179, 106, self._alpha))
        pen.setWidth(2)
        painter.setPen(pen)
        r = self.rect().adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(r, 12, 12)
        painter.end()

    def stop_pulse(self):
        self._anim_timer.stop()


# ─── Diálogo principal ────────────────────────────────────────────────────────


class UpdateDialog(QDialog):
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva versión disponible")
        self.setModal(True)
        self.setFixedWidth(520)
        self.cancelled = False
        self._current_version = ""
        self._new_version = ""
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {BG_MAIN};
                border: 1.5px solid {BORDER};
                border-radius: 20px;
            }}
            QLabel {{ background: transparent; border: none; color: {TEXT}; }}
            QTextEdit {{
                background: {BG_INPUT};
                border: 1px solid {BORDER};
                border-radius: 10px;
                color: {TEXT};
                font-size: 12px;
                padding: 8px;
                selection-background-color: {GOLD};
                selection-color: #1a1208;
            }}
            QScrollBar:vertical {{
                background: {BG_CARD}; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {GOLD_DARK}; border-radius: 3px; min-height: 30px;
            }}
        """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── HEADER ────────────────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(
            f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #1E1810, stop:0.6 #2A2018, stop:1 #1A1408);
                border-bottom: 1px solid {BORDER};
                border-radius: 20px;
            }}
        """
        )
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(28, 24, 28, 20)
        h_lay.setSpacing(10)

        top_row = QHBoxLayout()
        icon_lbl = QLabel("⬆️")
        icon_lbl.setStyleSheet("font-size: 28px;")
        top_row.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("Nueva versión disponible")
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: 900; color: {GOLD};")
        title_col.addWidget(title_lbl)

        self._subtitle_lbl = QLabel("Detectando versión...")
        self._subtitle_lbl.setStyleSheet(f"font-size: 12px; color: {MUTED};")
        title_col.addWidget(self._subtitle_lbl)

        top_row.addLayout(title_col)
        top_row.addStretch()
        h_lay.addLayout(top_row)

        # Pastilla de versiones  v1.0.48 → v1.0.49
        self._version_pill = QFrame()
        self._version_pill.setStyleSheet(
            f"""
            QFrame {{
                background: {GOLD_SOFT};
                border: 1px solid rgba(214,179,106,0.35);
                border-radius: 10px;
            }}
        """
        )
        pill_lay = QHBoxLayout(self._version_pill)
        pill_lay.setContentsMargins(14, 8, 14, 8)
        pill_lay.setSpacing(10)

        self._lbl_cur = QLabel("v?.?.?")
        self._lbl_cur.setStyleSheet(
            f"font-size: 13px; color: {MUTED}; font-weight: 600;"
        )

        arrow = QLabel("→")
        arrow.setStyleSheet(f"font-size: 16px; color: {GOLD}; font-weight: 900;")

        self._lbl_new = QLabel("v?.?.?")
        self._lbl_new.setStyleSheet(
            f"font-size: 15px; color: {GREEN}; font-weight: 900; letter-spacing: 0.5px;"
        )

        pill_lay.addStretch()
        pill_lay.addWidget(self._lbl_cur)
        pill_lay.addWidget(arrow)
        pill_lay.addWidget(self._lbl_new)
        pill_lay.addStretch()

        h_lay.addWidget(self._version_pill)
        root.addWidget(header)

        # ── CUERPO ────────────────────────────────────────────────────────────
        body = QVBoxLayout()
        body.setContentsMargins(28, 20, 28, 24)
        body.setSpacing(14)

        # Advertencias previas
        pre_frame = QFrame()
        pre_frame.setStyleSheet(
            f"""
            QFrame {{
                background: rgba(214,179,106,0.07);
                border: 1px solid rgba(214,179,106,0.18);
                border-radius: 10px;
            }}
        """
        )
        pre_lay = QVBoxLayout(pre_frame)
        pre_lay.setContentsMargins(14, 10, 14, 10)
        pre_lay.setSpacing(4)

        pre_title = QLabel("⚠️  Antes de instalar")
        pre_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {GOLD};")
        pre_lay.addWidget(pre_title)

        for txt in [
            "Cerrá Manarey en todas las PCs del negocio",
            "Asegurate de tener conexión a internet",
            "No apagues la PC mientras instala",
        ]:
            lbl = QLabel(f"• {txt}")
            lbl.setStyleSheet(f"font-size: 11px; color: {MUTED}; padding-left: 6px;")
            pre_lay.addWidget(lbl)

        body.addWidget(pre_frame)

        # Changelog
        notes_lbl = QLabel("Cambios en esta versión")
        notes_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {GOLD};")
        body.addWidget(notes_lbl)

        self.changelog = QTextEdit()
        self.changelog.setReadOnly(True)
        self.changelog.setMinimumHeight(90)
        self.changelog.setMaximumHeight(130)
        body.addWidget(self.changelog)

        # Barra de progreso (oculta al inicio)
        self._progress_frame = QFrame()
        self._progress_frame.setStyleSheet("background: transparent; border: none;")
        prog_lay = QVBoxLayout(self._progress_frame)
        prog_lay.setContentsMargins(0, 0, 0, 0)
        prog_lay.setSpacing(6)

        self.progress_label = QLabel("Descargando...")
        self.progress_label.setStyleSheet(f"font-size: 11px; color: {MUTED};")
        prog_lay.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                border: none;
                border-radius: 5px;
                background: {BG_INPUT};
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {GOLD_DARK}, stop:1 {GOLD});
                border-radius: 5px;
            }}
        """
        )
        prog_lay.addWidget(self.progress_bar)
        self._progress_frame.setVisible(False)
        body.addWidget(self._progress_frame)

        # Botones
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_later = QPushButton("Más tarde")
        self.btn_later.setFixedHeight(44)
        self.btn_later.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {MUTED};
                border: 1.5px solid rgba(214,179,106,0.25);
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background: rgba(214,179,106,0.08);
                border-color: {GOLD};
                color: {TEXT};
            }}
            QPushButton:disabled {{ opacity: 0.4; }}
        """
        )
        self.btn_later.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.btn_later)

        self.btn_install = PulsingButton("⬆️   Instalar ahora")
        self.btn_install.setFixedHeight(44)
        self.btn_install.setStyleSheet(
            f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #EBD7AA, stop:0.45 {GOLD}, stop:1 {GOLD_DARK});
                color: #1A1208;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 900;
                padding: 0 28px;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #F5E5BB, stop:0.45 #E0C070, stop:1 #B89450);
            }}
            QPushButton:pressed {{
                background: {GOLD_DARK};
            }}
            QPushButton:disabled {{
                background: #3A3228;
                color: #6A5A42;
            }}
        """
        )
        self.btn_install.clicked.connect(self._on_install)
        btn_row.addWidget(self.btn_install)

        # Sombra dorada al botón instalar
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(214, 179, 106, 100))
        shadow.setOffset(0, 4)
        self.btn_install.setGraphicsEffect(shadow)

        body.addLayout(btn_row)
        root.addLayout(body)

    # ── API pública ────────────────────────────────────────────────────────────

    def set_update_info(self, version, changelog, mandatory=False, current_version=""):
        self._new_version = version
        self._current_version = current_version

        cur_display = f"v{current_version}" if current_version else "actual"
        self._subtitle_lbl.setText(f"Instalando actualizará tu sistema a v{version}")
        self._lbl_cur.setText(cur_display)
        self._lbl_new.setText(f"v{version}")

        self.changelog.setPlainText(
            changelog or "Mejoras de rendimiento, estabilidad y correcciones."
        )
        self.btn_install.setText(f"⬆️   Instalar v{version}")

        if mandatory:
            self.btn_later.setEnabled(False)
            self.btn_later.setText("Obligatoria")
            self.changelog.append(
                "\n\n⚠️ ACTUALIZACIÓN OBLIGATORIA\nDebés instalarla para continuar usando la app."
            )

    def show_progress(self):
        self.btn_install.setEnabled(False)
        self.btn_install.stop_pulse()
        self.btn_later.setEnabled(False)
        self._progress_frame.setVisible(True)
        self.adjustSize()

    def update_progress(self, done, total, stage="download"):
        if total > 0:
            pct = int(done * 100 / total)
            self.progress_bar.setValue(pct)
            if stage == "download":
                mb_d = done // (1024 * 1024)
                mb_t = total // (1024 * 1024)
                self.progress_label.setText(
                    f"Descargando... {pct}%  ({mb_d} MB de {mb_t} MB)"
                )
            elif stage == "extract":
                self.progress_label.setText(
                    f"Instalando... {pct}%  ({done} de {total} archivos)"
                )

    def _on_install(self):
        self.accept()

    def _on_cancel(self):
        self.cancelled = True
        self.reject()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


# ─── Diálogo de progreso ──────────────────────────────────────────────────────


class UpdateProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instalando actualización")
        self.setModal(True)
        self.setFixedWidth(440)
        self.cancelled = False
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {BG_MAIN};
                border: 1.5px solid {BORDER};
                border-radius: 18px;
            }}
            QLabel {{ background: transparent; border: none; color: {TEXT}; }}
        """
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 24)
        lay.setSpacing(16)

        # Header
        row = QHBoxLayout()
        icon = QLabel("⚙️")
        icon.setStyleSheet("font-size: 26px;")
        row.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel("Instalando actualización")
        title.setStyleSheet(f"font-size: 16px; font-weight: 900; color: {GOLD};")
        col.addWidget(title)
        self.status_label = QLabel("Descargando archivos...")
        self.status_label.setStyleSheet(f"font-size: 12px; color: {MUTED};")
        col.addWidget(self.status_label)
        row.addLayout(col)
        row.addStretch()
        lay.addLayout(row)

        # Barra
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                border: none;
                border-radius: 6px;
                background: {BG_INPUT};
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {GOLD_DARK}, stop:1 {GOLD});
                border-radius: 6px;
            }}
        """
        )
        lay.addWidget(self.progress_bar)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet(
            f"font-size: 11px; color: {MUTED}; text-align: center;"
        )
        self.info_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.info_label)

        lay.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {MUTED};
                border: 1.5px solid rgba(214,179,106,0.25);
                border-radius: 10px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(214,179,106,0.08);
                color: {TEXT};
            }}
        """
        )
        self.btn_cancel.clicked.connect(self._on_cancel)
        lay.addWidget(self.btn_cancel)

    def update_progress(self, done, total, stage="download"):
        if total > 0:
            pct = int(done * 100 / total)
            self.progress_bar.setValue(pct)
            if stage == "download":
                mb_d = done // (1024 * 1024)
                mb_t = total // (1024 * 1024)
                self.status_label.setText("Descargando actualización...")
                self.info_label.setText(f"{pct}%  ·  {mb_d} MB de {mb_t} MB")
            elif stage == "extract":
                self.status_label.setText("Instalando archivos...")
                self.info_label.setText(f"{pct}%  ·  {done} de {total} archivos")

    def start_install_phase(self):
        """Cambia a la fase de instalación: barra indeterminada, sin cancelar."""
        self.progress_bar.setMaximum(0)  # indeterminate (spinner)
        self.progress_bar.setValue(0)
        self.status_label.setText("Instalando actualización...")
        self.info_label.setText(
            "Esto puede tardar 1-2 minutos. La app se reiniciará sola al terminar."
        )
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.hide()
        self.adjustSize()

    def _on_cancel(self):
        self.cancelled = True
        self.reject()
