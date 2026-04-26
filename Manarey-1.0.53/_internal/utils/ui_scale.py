"""utils/ui_scale.py

Centraliza el cálculo del factor de escala para pantallas grandes
y utilidades para escalar valores y fuentes en la UI.
"""
from typing import Tuple

from PyQt5.QtCore import QEvent, QObject, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMainWindow, QSizePolicy, QWidget

SCALE: float = 1.0


def _compute_scale(
    screen_size: Tuple[int, int],
    base: Tuple[int, int] = (1920, 1440),
    min_scale: float = 0.9,
    max_scale: float = 1.8,
) -> float:
    bw, bh = base
    w, h = screen_size
    try:
        factor_w = float(w) / float(bw)
        factor_h = float(h) / float(bh)
        scale = (factor_w + factor_h) / 2.0
        if scale < min_scale:
            return min_scale
        if scale > max_scale:
            return max_scale
        return scale
    except Exception:
        return 1.0


def apply_global_scale(
    app,
    base: Tuple[int, int] = (1920, 1440),
    min_scale: float = 0.9,
    max_scale: float = 1.8,
    override_scale=None,
) -> float:
    """Calcula y aplica escala global a la `app`.

    Retorna el factor de escala calculado.
    """
    global SCALE
    try:
        # Check override first
        if override_scale and str(override_scale) != "auto":
            try:
                SCALE = float(override_scale)
                # Apply font scaling
                try:
                    f: QFont = app.font()
                    f.setPointSizeF(max(8.0, f.pointSizeF() * SCALE))
                    app.setFont(f)
                except Exception:
                    pass
                app.setProperty("manarey_scale", SCALE)
                return SCALE
            except:
                pass

        screen = app.primaryScreen()
        if not screen:
            SCALE = 1.0
            return SCALE
        size = screen.size()
        w, h = int(size.width()), int(size.height())
        SCALE = _compute_scale(
            (w, h), base=base, min_scale=min_scale, max_scale=max_scale
        )
        # Escalar fuente global
        try:
            f: QFont = app.font()
            f.setPointSizeF(max(8.0, f.pointSizeF() * SCALE))
            app.setFont(f)
        except Exception:
            pass
        # Guardar propiedad accesible desde Qt
        try:
            app.setProperty("manarey_scale", SCALE)
        except Exception:
            pass
        return SCALE
    except Exception:
        SCALE = 1.0
        return SCALE


def scale(value: float) -> int:
    """Escala un valor numérico (p. ej. dimensiones) y devuelve entero."""
    try:
        return int(round(float(value) * SCALE))
    except Exception:
        return int(round(value))


def scale_font(point_size: float) -> float:
    """Devuelve un tamaño de fuente escalado (float)."""
    try:
        return float(point_size) * SCALE
    except Exception:
        return float(point_size)


class _WindowScaler(QObject):
    """Event filter que aplica escala a ventanas top-level al mostrarse.

    Marca cada ventana escalada con la propiedad 'manarey_scaled' para evitar repetir.
    """

    def __init__(self, app, screen_min_width: int = 1600, parent=None):
        super().__init__(parent)
        self.app = app
        self.screen_min_width = screen_min_width
        # Per-window stored data: {window: {'base_w': int, 'orig_sizes': {id(widget): (w,h)}}}
        self._window_data = {}

    def eventFilter(self, obj, event):
        try:
            # On show: register original sizes for children and apply initial font scaling
            if (
                event.type() == QEvent.Show
                and isinstance(obj, QWidget)
                and obj.isWindow()
            ):
                # Kiosk mode: force fullscreen for main windows to hide taskbar
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

                if obj.property("manarey_no_scale"):
                    return super().eventFilter(obj, event)
                # Sólo realizar la inicialización una vez por ventana
                if obj.property("manarey_scaled"):
                    return super().eventFilter(obj, event)
                obj.setProperty("manarey_scaled", True)

                # Register base width and original sizes for children
                try:
                    base_w = max(300, obj.width())
                    data = {"base_w": base_w, "orig_sizes": {}}
                    for w in obj.findChildren(QWidget):
                        try:
                            ow, oh = w.width(), w.height()
                            # store only positive sizes
                            if ow > 0 or oh > 0:
                                data["orig_sizes"][id(w)] = (ow, oh)
                        except Exception:
                            continue
                    self._window_data[id(obj)] = data
                except Exception:
                    pass

                # Escalar la fuente de la ventana por el SCALE global
                try:
                    f = obj.font()
                    f.setPointSizeF(max(8.0, f.pointSizeF() * SCALE))
                    obj.setFont(f)
                except Exception:
                    pass

                # Redimensionar ventanas principales segÃºn pantalla
                try:
                    if obj.property("manarey_no_autoresize"):
                        return super().eventFilter(obj, event)
                    if isinstance(obj, QMainWindow):
                        screen = obj.screen() or self.app.primaryScreen()
                        if screen:
                            geo = screen.availableGeometry()
                            if self.app.property("manarey_auto_fit"):
                                # Llenar toda la pantalla disponible
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

                # En pantallas pequeÃ±as, asegurar que la ventana no exceda el Ã¡rea disponible
                try:
                    if not obj.isFullScreen():
                        screen = obj.screen() or self.app.primaryScreen()
                        if screen:
                            geo = screen.availableGeometry()
                            max_w = geo.width()
                            max_h = geo.height()
                            if obj.width() > max_w or obj.height() > max_h:
                                obj.resize(
                                    min(obj.width(), max_w), min(obj.height(), max_h)
                                )
                except Exception:
                    pass

            # On resize: adapt child widgets sizes and fonts relative to stored originals
            if (
                event.type() == QEvent.Resize
                and isinstance(obj, QWidget)
                and obj.isWindow()
            ):
                if obj.property("manarey_no_scale"):
                    return super().eventFilter(obj, event)
                try:
                    win_data = self._window_data.get(id(obj))
                    if not win_data:
                        return super().eventFilter(obj, event)
                    base_w = win_data.get("base_w", max(300, obj.width()))
                    cur_w = max(1, obj.width())
                    factor = float(cur_w) / float(base_w)
                    # Permitir escalar hacia arriba y hacia abajo libremente
                    factor = max(0.5, min(2.5, factor))

                    # Apply font scaling to whole window
                    try:
                        f = obj.font()
                        f.setPointSizeF(max(7.0, f.pointSizeF() * factor))
                        obj.setFont(f)
                    except Exception:
                        pass

                    # Resize child widgets that had original sizes
                    for w in obj.findChildren(QWidget):
                        try:
                            orig = win_data["orig_sizes"].get(id(w))
                            if not orig:
                                continue
                            ow, oh = orig
                            # Only adjust fixed-like widgets (heuristic: original width > 20)
                            if ow and ow > 20:
                                try:
                                    new_w = int(max(24, round(ow * factor)))
                                    w.setFixedWidth(new_w)
                                except Exception:
                                    pass
                            if oh and oh > 16:
                                try:
                                    new_h = int(max(16, round(oh * factor)))
                                    # only set fixed height if the widget previously had a small height
                                    w.setFixedHeight(new_h)
                                except Exception:
                                    pass
                        except Exception:
                            continue
                except Exception:
                    pass

        except Exception:
            pass
        return super().eventFilter(obj, event)


def install_window_scaler(app, screen_min_width: int = 1600):
    """Instala un event filter en la `app` para escalar automáticamente todas las ventanas mostradas."""
    try:
        scaler = _WindowScaler(app, screen_min_width=screen_min_width)
        app.installEventFilter(scaler)
        # Guardar referencia para que no sea recolectado
        app.setProperty("manarey_window_scaler", scaler)
        return scaler
    except Exception:
        return None
