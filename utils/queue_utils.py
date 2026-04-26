"""Utilidades para manejo de cola de operaciones."""

import logging
import time
from functools import wraps
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


def with_retry(max_retries: int = 3, base_delay: float = 1.0) -> Any:
    """
    Decorador que implementa reintentos exponenciales para operaciones de cola.

    Args:
        max_retries: Número máximo de reintentos
        base_delay: Retardo base entre reintentos (se multiplica exponencialmente)
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs) -> Tuple[bool, str]:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = str(e)
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)  # Retardo exponencial
                        logger.warning(
                            f"Reintentando {func.__name__} en {delay:.1f}s ({attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"Error final en {func.__name__}: {e}")
            return False, f"Error después de {max_retries} intentos: {last_error}"

        return wrapper

    return decorator


def format_queue_error(error: Optional[str]) -> str:
    """Formatea mensaje de error para mostrar al usuario."""
    if not error:
        return "Error desconocido"

    # Limpiar mensajes comunes de DB
    error = error.replace("UNIQUE constraint failed", "Ya existe un registro")
    error = error.replace("FOREIGN KEY constraint failed", "Referencia inválida")
    error = error.replace("CHECK constraint failed", "Validación fallida")

    # Limitar longitud
    if len(error) > 100:
        error = error[:97] + "..."

    return error
