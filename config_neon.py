# Configuración de conexión a Neon Postgres
import os

NEON_DB_HOST = os.getenv("NEON_DB_HOST", "TU_HOST_NEON")
NEON_DB_PORT = int(os.getenv("NEON_DB_PORT", "5432"))
NEON_DB_NAME = os.getenv("NEON_DB_NAME", "TU_DB_NEON")
NEON_DB_USER = os.getenv("NEON_DB_USER", "TU_USUARIO_NEON")
NEON_DB_PASS = os.getenv("NEON_DB_PASS", "TU_PASSWORD_NEON")

DATABASE_URL = f"postgresql://{NEON_DB_USER}:{NEON_DB_PASS}@{NEON_DB_HOST}:{NEON_DB_PORT}/{NEON_DB_NAME}"
