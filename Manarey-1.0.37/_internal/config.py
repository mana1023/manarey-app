import os

# config.py
# Cómo relanzar la app luego de aplicar la actualización
APP_MAIN_CMD = ["python", "app.py"]

# Lista de locales para el selector "ver stock de otros locales"
LOCALES = ["Cane", "Vidriera", "Longchamps", "Glew"]

# ================= PDF SETTINGS =================
# Primary and fallback logo relative paths from project root
PDF_LOGO_PRIMARY = ("assets", "images", "logo_manarey.png")
PDF_LOGO_FALLBACK = ("media", "manarey_logo.png")

# Logo placement: 'footer-right' or 'header-left'
PDF_LOGO_POSITION = "footer-right"

# Default logo size and vertical offset (points)
PDF_LOGO_WIDTH_PT = 90.0
PDF_LOGO_Y_OFFSET = 8.0

# Date format for PDFs
PDF_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
