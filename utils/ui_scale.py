"""utils/ui_scale.py

Utilidades de escala de la UI.

Desde la migracion a Qt6/PySide6 el escalado por DPI es NATIVO: Qt escala
la interfaz segun el DPI del monitor automaticamente (con la politica
HighDpiScaleFactorRoundingPolicy.PassThrough fijada en app.py). Por eso el
modo "auto" ya NO multiplica fuentes ni tamanos a mano — hacerlo se sumaria
al escalado de Qt y agrandaria todo al doble.

Se mantiene:
  * El override manual de escala (preferencia del usuario, un numero fijo),
    para quien quiera agrandar/achicar por encima del DPI nativo.
  * `scale()` / `scale_font()`, que respetan ese override (o pasan el valor
    tal cual cuando la escala es 1.0).
  * El modo kiosco (pantalla completa) y el auto-fit de ventanas principales.
"""
from typing import Tuple

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMainWindow, QWidget

SCALE: float = 1.0


def apply_global_scale(
    app,
    base: Tuple[int, int] = (1920, 1440),
    min_scale: float = 0.9,
    max_scale: float = 1.8,
    override_scale=None,
) -> float:
    """Fija la escala global de la app.

    - Si el usuario definio un override numerico, se respeta y se aplica a la
      fuente global (escala deliberada por encima del DPI nativo de Qt6).
    - En modo "auto" no se toca la fuente: Qt6 ya escala por DPI. SCALE queda
      en 1.0 y `scale()`/`scale_font()` pasan los valores sin alterar.

    Los parametros base/min_scale/max_scale se conservan por compatibilidad
    con las llamadas existentes, pero solo acotan el override manual.
    """
    global SCALE
    try:
        if override_scale and str(override_scale) != "auto":
            try:
                val = float(override_scale)
                # Acotar el override a un rango sensato
                SCALE = max(min_scale, min(max_scale, val))
                try:
                    f: QFont = app.font()
                    f.setPointSizeF(max(8.0, f.pointSizeF() * SCALE))
                    app.setFont(f)
                except Exception:
                    pass
                app.setProperty("manarey_scale", SCALE)
                return SCALE
            except Exception:
                pass

        # Modo auto: DPI nativo de Qt6, sin escalado manual.
        SCALE = 1.0
        try:
            app.setProperty("manarey_scale", SCALE)
        except Exception:
            pass
        return SCALE
    except Exception:
        SCALE = 1.0
        return SCALE


def scale(value: float) -> int:
    """Escala un valor numerico (p. ej. dimensiones) y devuelve entero."""
    try:
        return int(round(float(value) * SCALE))
    except Exception:
        return int(round(value))


def scale_font(point_size: float) -> float:
    """Devuelve un tamano de fuente escalado (float)."""
    try:
        return float(point_size) * SCALE
    except Exception:
        return float(point_size)


class _WindowScaler(QObject):
    """Event filter para ventanas top-level.

    Ya NO re-escala fuentes ni tamanos de widgets (eso lo hace Qt6 por DPI).
    Solo conserva el comportamiento de ventana: modo kiosco (pantalla
    completa) y auto-fit / clamp de ventanas principales al mostrarse.
    """

    def __init__(self, app, screen_min_width: int = 1600, parent=None):
        super().__init__(parent)
        self.app = app
        self.screen_min_width = screen_min_width

    def eventFilter(self, obj, event):
        try:
            if (
                event.type() == QEvent.Show
                and isinstance(obj, QWidget)
                and obj.isWindow()
            ):
                # Modo kiosco: pantalla completa para ventanas principales
                try:
                    if self.app.property("manarey_kiosk") and isinstance(
                        obj, QMainWindow
                    ):
                        if obj.property("manarey_no_kiosk"):
                            return super().eventFilter(obj, event)
                        if not obj.property("manarey_kiosk_applied"):
                            obj.setProperty("manarey_kiosk_applied", True)
                            obj.showFullScreen()
                except Exception:
                    pass

                # Auto-fit / redimension inicial de ventanas principales
                try:
                    if obj.property("manarey_no_autoresize"):
                        return super().eventFilter(obj, event)
                    if isinstance(obj, QMainWindow):
                        screen = obj.screen() or self.app.primaryScreen()
                        if screen:
                            geo = screen.availableGeometry()
                            if self.app.property("manarey_auto_fit"):
                                try:
                                    obj.setGeometry(geo)
                                    obj.showFullScreen()
                                except Exception:
                                    try:
                                        obj.resize(geo.width(), geo.height())
                                    except Exception:
                                        pass
                            else:
                                size = screen.size()
                                w, h = size.width(), size.height()
                                cur_w, cur_h = obj.width(), obj.height()
                                target_w = int(w * 0.92)
                                target_h = int(h * 0.92)
                                if cur_w < int(w * 0.75) or cur_h < int(h * 0.75):
                                    try:
                                        obj.resize(target_w, target_h)
                                    except Exception:
                                        pass
                except Exception:
                    pass

                # Evitar que la ventana exceda el area disponible
                try:
                    if not obj.isFullScreen():
                        screen = obj.screen() or self.app.primaryScreen()
                        if screen:
                            geo = screen.availableGeometry()
                            if obj.width() > geo.width() or obj.height() > geo.height():
                                obj.resize(
                                    min(obj.width(), geo.width()),
                                    min(obj.height(), geo.height()),
                                )
                except Exception:
                    pass
        except Exception:
            pass
        return super().eventFilter(obj, event)


def install_window_scaler(app, screen_min_width: int = 1600):
    """Instala el event filter de comportamiento de ventana (kiosco/auto-fit)."""
    try:
        scaler = _WindowScaler(app, screen_min_width=screen_min_width)
        app.installEventFilter(scaler)
        # Guardar referencia para que no sea recolectado
        app.setProperty("manarey_window_scaler", scaler)
        return scaler
    except Exception:
        return None
