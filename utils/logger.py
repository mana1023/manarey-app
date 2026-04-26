"""
utils/logger.py - Logger estructurado para Manarey.

Caracteristicas:
- RotatingFileHandler en %LOCALAPPDATA%\Manarey\logs\manarey.log (5 MB x 3 archivos)
- StreamHandler en consola cuando no esta empaquetado (desarrollo)
- Formato: 2026-04-24 10:30:15 | ERROR | stock_view.py:245 | mensaje
- Singleton: los handlers se instalan una sola vez
- get_logger(name) -> Logger configurado
- log_exception(logger, msg, exc) -> loguea con traceback completo
"""

import logging
import logging.handlers
import os
import sys
import traceback

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB por archivo
_LOG_BACKUP_COUNT = 3  # conservar 3 archivos rotados
_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_ROOT_LOGGER_NAME = "manarey"

# Flag de singleton: True cuando los handlers ya fueron instalados
_configured = False


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _log_file_path() -> str:
    """Devuelve la ruta absoluta al archivo de log."""
    local_appdata = os.environ.get("LOCALAPPDATA") or os.path.join(
        os.path.expanduser("~"), "AppData", "Local"
    )
    log_dir = os.path.join(local_appdata, "Manarey", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "manarey.log")


def _is_development() -> bool:
    """True cuando la app NO esta empaquetada con PyInstaller."""
    return not getattr(sys, "frozen", False)


def _configure_root_logger() -> None:
    """Instala handlers en el logger raiz de Manarey. Se ejecuta una sola vez."""
    global _configured
    if _configured:
        return
    _configured = True

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    root = logging.getLogger(_ROOT_LOGGER_NAME)
    # Solo configurar si aun no tiene handlers propios (evita duplicados cuando
    # logging_config.setup_logging() ya fue llamado antes).
    if root.handlers:
        return

    root.setLevel(logging.DEBUG if _is_development() else logging.INFO)

    # --- Rotating file handler ---
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            _log_file_path(),
            maxBytes=_LOG_MAX_BYTES,
            backupCount=_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except Exception as exc:  # noqa: BLE001
        # Si no se puede abrir el archivo de log, no crashear la app
        print(f"[logger] No se pudo crear RotatingFileHandler: {exc}", file=sys.stderr)

    # --- Console handler (solo en desarrollo) ---
    if _is_development():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------


def get_logger(name: str) -> logging.Logger:
    """
    Devuelve un logger configurado bajo el namespace 'manarey.<name>'.

    Si name ya contiene 'manarey.' como prefijo se usa tal cual para no
    duplicar el prefijo.

    Ejemplo:
        logger = get_logger("stock_view")
        logger.info("Stock cargado")
    """
    _configure_root_logger()

    if name.startswith(_ROOT_LOGGER_NAME + ".") or name == _ROOT_LOGGER_NAME:
        full_name = name
    else:
        full_name = f"{_ROOT_LOGGER_NAME}.{name}"

    return logging.getLogger(full_name)


def log_exception(logger: logging.Logger, msg: str, exc: BaseException) -> None:
    """
    Loguea una excepcion con traceback completo al nivel ERROR.

    Ejemplo:
        try:
            ...
        except Exception as e:
            log_exception(logger, "Fallo al guardar producto", e)
    """
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error("%s\n%s", msg, tb_str)
