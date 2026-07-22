"""
utils/error_handler.py - Manejador global de errores no capturados para Manarey.

Provee:
- setup_global_error_handler(app): instala sys.excepthook y threading.excepthook
- handle_thread_exception(args): hook para errores en threads
- ErrorReporter.report(context, exc): reporte manual desde cualquier modulo
"""

import sys
import threading
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from utils.logger import get_logger, log_exception

_logger = get_logger("error_handler")

# Mensaje amigable que ve el usuario en el dialogo
_USER_MESSAGE = "Ocurrió un error inesperado.\n" "El equipo técnico fue notificado."
_USER_TITLE = "Error inesperado"


# ---------------------------------------------------------------------------
# Dialogo de notificacion al usuario
# ---------------------------------------------------------------------------


def _show_error_dialog(detail: str = "") -> None:
    """
    Muestra un QMessageBox informativo sin cerrar la aplicacion.
    Seguro para llamar desde el hilo principal; desde otros hilos usa
    QMetaObject.invokeMethod o una senal.
    """
    try:
        app = QApplication.instance()
        if app is None:
            return  # No hay app Qt activa, no podemos mostrar dialogo

        msg_box = QMessageBox()
        msg_box.setWindowTitle(_USER_TITLE)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText(_USER_MESSAGE)
        if detail:
            # Detalle tecnico colapsado (no asusta al usuario)
            msg_box.setDetailedText(detail[:2000])  # limitar longitud
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec()
    except Exception:
        # Si el dialogo mismo falla, no crashear
        pass


# ---------------------------------------------------------------------------
# Hook para excepciones no capturadas en el hilo principal
# ---------------------------------------------------------------------------


def _excepthook(exc_type, exc_value, exc_tb):
    """
    Reemplaza sys.excepthook. Loguea la excepcion y notifica al usuario.
    La aplicacion NO se cierra.
    """
    # Ignorar KeyboardInterrupt para no bloquear Ctrl+C en desarrollo
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _logger.error("Excepcion no capturada (hilo principal):\n%s", tb_str)

    _show_error_dialog(tb_str)


# ---------------------------------------------------------------------------
# Hook para excepciones en threads secundarios
# ---------------------------------------------------------------------------


def handle_thread_exception(args) -> None:
    """
    Hook para threading.excepthook (Python 3.8+).

    Instalar con:
        threading.excepthook = handle_thread_exception

    'args' es un objeto con atributos:
        exc_type, exc_value, exc_traceback, thread
    """
    # Ignorar SystemExit y KeyboardInterrupt
    if args.exc_type is None or issubclass(
        args.exc_type, (SystemExit, KeyboardInterrupt)
    ):
        return

    thread_name = getattr(args, "thread", None)
    thread_name = thread_name.name if thread_name else "desconocido"

    tb_str = "".join(
        traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
    )
    _logger.error("Excepcion no capturada en thread '%s':\n%s", thread_name, tb_str)

    # Notificar al usuario desde el hilo principal via QMetaObject si es posible
    try:
        from PySide6.QtCore import QMetaObject, Qt

        app = QApplication.instance()
        if app is not None:
            # Encolar en el event loop principal
            QMetaObject.invokeMethod(
                app,
                "_manarey_show_thread_error",
                Qt.QueuedConnection,
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# ErrorReporter: reporte manual desde cualquier modulo
# ---------------------------------------------------------------------------


class ErrorReporter:
    """
    Utilidad estatica para reportar errores desde cualquier parte del codigo.

    Ejemplo:
        try:
            guardar_venta(datos)
        except Exception as e:
            ErrorReporter.report("guardar_venta", e)
    """

    @staticmethod
    def report(context: str, exc: Exception) -> None:
        """
        Loguea 'exc' con contexto descriptivo y opcionalmente notifica al usuario.

        Args:
            context: descripcion de donde ocurrio el error (ej. "stock_view.cargar")
            exc: la excepcion capturada
        """
        module_logger = get_logger(f"reporter.{context}")
        log_exception(module_logger, f"Error en [{context}]", exc)


# ---------------------------------------------------------------------------
# Setup principal
# ---------------------------------------------------------------------------


def setup_global_error_handler(app: QApplication) -> None:
    """
    Instala los handlers globales de error en la aplicacion Qt.

    Debe llamarse despues de crear QApplication y antes de exec_().

    Args:
        app: la instancia de QApplication
    """
    # Instalar excepthook del hilo principal
    sys.excepthook = _excepthook

    # Instalar hook de threads (Python 3.8+)
    if hasattr(threading, "excepthook"):
        threading.excepthook = handle_thread_exception

    # Metodo auxiliar en QApplication para mostrar dialogo desde threads
    # (se invoca via QMetaObject.invokeMethod con QueuedConnection)
    def _manarey_show_thread_error():
        _show_error_dialog()

    # Adjuntar el metodo a la instancia de app en runtime
    import types

    app._manarey_show_thread_error = types.MethodType(  # type: ignore[attr-defined]
        lambda self: _show_error_dialog(), app
    )

    _logger.info("Global error handler instalado correctamente")
