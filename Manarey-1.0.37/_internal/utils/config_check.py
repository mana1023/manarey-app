"""utils/config_check.py
Comprobaciones ligeras de configuración y variables de entorno para ayudar a detectar
malconfiguraciones en despliegue o desarrollo.

Este módulo exporta `check_config()` que realiza comprobaciones no-fatal y devuelve
una lista con advertencias (vacía si no hay problemas). También imprime las advertencias
por consola para mejorar visibilidad en arranque.
"""
import base64
import os


def _is_fernet_key(k: str) -> bool:
    try:
        # Fernet keys are urlsafe base64-encoded 32 bytes -> length 44
        if not isinstance(k, str):
            return False
        if len(k) != 44:
            return False
        base64.urlsafe_b64decode(k)
        return True
    except Exception:
        return False


def check_config() -> list:
    """Ejecuta comprobaciones no-fatal y devuelve una lista de advertencias.

    Imprime las advertencias en stdout para visibilidad en el arranque.
    """
    problems = []
    bk = os.environ.get("MANAREY_BACKUP_KEY")
    if bk and not _is_fernet_key(bk):
        problems.append(
            "MANAREY_BACKUP_KEY parece inválida (debe ser una clave Fernet urlsafe base64 de 44 caracteres)."
        )

    if os.environ.get("MANAREY_DEBUG", "0") == "1":
        problems.append("MANAREY_DEBUG=1 activo: no habilitar en producción.")

    sp = os.environ.get("MANAREY_SQLITE_PATH")
    if sp and not os.path.isabs(sp):
        problems.append(
            "MANAREY_SQLITE_PATH no es absoluta; usar rutas absolutas en despliegues."
        )

    dburl = os.environ.get("DATABASE_URL", "").strip()
    if dburl and not (
        dburl.startswith("postgres://") or dburl.startswith("postgresql://")
    ):
        problems.append("DATABASE_URL está definida pero no parece apuntar a Postgres.")

    if problems:
        print("⚠ Advertencias de configuración:")
        for p in problems:
            print(" -", p)

    return problems
