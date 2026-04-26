"""Componente para mostrar notificaciones toast."""

from PyQt5.QtCore import QPoint, QPropertyAnimation, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath
from PyQt5.QtWidgets import QFrame, QLabel


class Toast(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Configuración visual
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(
            """
            QFrame {
                background-color: #2D3748;
                color: white;
                border-radius: 8px;
                padding: 12px 20px;
            }
        """
        )

        # Label para el mensaje
        self.label = QLabel(self)
        self.label.setStyleSheet("color: white; font-size: 13px;")
        self.label.setAlignment(Qt.AlignCenter)

        # Timer para auto-ocultar
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.hide)

        # Animación de fade
        self.opacity = 1.0
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)

    def show_message(self, message, duration=2000):
        """Muestra un mensaje por la duración especificada (ms)."""
        # Configurar mensaje
        self.label.setText(message)
        self.label.adjustSize()
        self.adjustSize()

        # Centrar en la ventana padre
        if self.parent():
            pos = self.parent().rect().center()
            global_pos = self.parent().mapToGlobal(pos)
            self.move(
                global_pos.x() - self.width() // 2, global_pos.y() - self.height() // 2
            )

        # Mostrar con fade in
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.show()
        self.animation.start()

        # Programar ocultamiento
        self.timer.start(duration)

    def hide(self):
        """Oculta el toast con animación."""
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        try:
            self.animation.finished.disconnect()
        except Exception:
            pass
        self.animation.finished.connect(super().hide)
        self.animation.start()

    def paintEvent(self, event):
        """Dibuja el fondo con sombra."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Dibujar sombra
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 30))
        path = QPainterPath()
        path.addRoundedRect(4, 4, self.width() - 8, self.height() - 8, 8, 8)
        painter.drawPath(path)

        # Dibujar fondo
        painter.setBrush(QColor(45, 55, 72))
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width() - 4, self.height() - 4, 8, 8)
        painter.drawPath(path)
