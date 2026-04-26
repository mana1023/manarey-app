import json
import os
from pathlib import Path

# config.py
# Como relanzar la app luego de aplicar la actualizacion
APP_MAIN_CMD = ["python", "app.py"]

# Lista de locales para el selector "ver stock de otros locales"
DEFAULT_LOCALES = ["Cane", "Vidriera", "Longchamps", "Glew", "Estacion"]
LOCALES = DEFAULT_LOCALES[:]


def get_locales(extra=None):
    """Devuelve locales configurados, con fallback seguro y sin duplicados."""
    locales = list(DEFAULT_LOCALES)
    config_path = Path(__file__).resolve().parent / "config.json"
    try:
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            locales_info = data.get("locales_info", {})
            if isinstance(locales_info, dict):
                for local in locales_info.keys():
                    if isinstance(local, str) and local.strip():
                        locales.append(local.strip())
    except Exception:
        pass

    if extra:
        for local in extra:
            if isinstance(local, str) and local.strip():
                locales.append(local.strip())

    seen = set()
    result = []
    for local in locales:
        clean = (local or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


# ================= PDF SETTINGS =================
# Primary and fallback logo relative paths from project root
PDF_LOGO_PRIMARY = ("assets", "images", "logo_Manarey_modern.png")
PDF_LOGO_FALLBACK = ("media", "manarey_logo.png")

# Logo placement: 'footer-right' or 'header-left'
PDF_LOGO_POSITION = "footer-right"

# Default logo size and vertical offset (points)
PDF_LOGO_WIDTH_PT = 420.0
PDF_LOGO_Y_OFFSET = 8.0

# Date format for PDFs
PDF_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
