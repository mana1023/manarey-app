"""Copia de seguridad COMPLETA de la base Postgres (Supabase).

Hace un pg_dump en formato comprimido (-Fc), que se restaura con pg_restore.
Guarda las copias en una carpeta FUERA del repo (por defecto
%USERPROFILE%\\Manarey_Backups) y borra las viejas dejando solo las ultimas N.

Uso:
    python scripts/backup_postgres.py

Config por variables de entorno (opcionales):
    MANAREY_BACKUP_DIR    carpeta donde guardar (default: ~/Manarey_Backups)
    MANAREY_BACKUP_KEEP   cuantas copias conservar (default: 30)
    PG_DUMP_PATH          ruta a pg_dump.exe si no esta en el PATH

Pensado para correr solo todos los dias con el Programador de tareas de Windows.
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.db import DB_URL  # noqa: E402

KEEP = int(os.environ.get("MANAREY_BACKUP_KEEP", "30"))

# Candidatos donde suele estar pg_dump en Windows (ademas del PATH).
_PG_DUMP_CANDIDATES = [
    os.environ.get("PG_DUMP_PATH", ""),
    "pg_dump",
    r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe",
    r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
    r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
]


def _hallar_pg_dump() -> str:
    for cand in _PG_DUMP_CANDIDATES:
        if not cand:
            continue
        if cand == "pg_dump":
            encontrado = shutil.which("pg_dump")
            if encontrado:
                return encontrado
        elif os.path.exists(cand):
            return cand
    raise SystemExit(
        "No se encontro pg_dump. Instala las herramientas de PostgreSQL o "
        "define PG_DUMP_PATH con la ruta a pg_dump.exe."
    )


def _carpeta_backups() -> Path:
    base = os.environ.get("MANAREY_BACKUP_DIR")
    if not base:
        base = str(Path.home() / "Manarey_Backups")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _entorno_con_password(url: str) -> tuple:
    """Arma el entorno para pg_dump con la contraseña en PGPASSWORD, asi no
    queda en la linea de comandos (visible en la lista de procesos)."""
    u = urlparse(url)
    env = os.environ.copy()
    if u.password:
        env["PGPASSWORD"] = unquote(u.password)
    env.setdefault("PGSSLMODE", "require")  # Supabase exige SSL
    return env, u


def _rotar(carpeta: Path):
    copias = sorted(carpeta.glob("manarey_*.dump"))
    sobran = len(copias) - KEEP
    for viejo in copias[: max(0, sobran)]:
        try:
            viejo.unlink()
            print(f"Borrada copia vieja: {viejo.name}")
        except OSError as e:
            print(f"No se pudo borrar {viejo.name}: {e}")


def main():
    if not DB_URL:
        raise SystemExit("No hay DATABASE_URL configurada (revisa config.json).")

    pg_dump = _hallar_pg_dump()
    carpeta = _carpeta_backups()
    env, u = _entorno_con_password(DB_URL)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = carpeta / f"manarey_{ts}.dump"

    host = u.hostname or ""
    puerto = str(u.port or 5432)
    usuario = unquote(u.username or "")
    basedatos = (u.path or "/postgres").lstrip("/") or "postgres"

    cmd = [
        pg_dump,
        "-h",
        host,
        "-p",
        puerto,
        "-U",
        usuario,
        "-d",
        basedatos,
        "-Fc",  # formato custom, comprimido y restaurable
        "--no-owner",
        "--no-privileges",
        "-f",
        str(destino),
    ]
    print(f"Respaldando {basedatos} en {host} -> {destino.name} ...")
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        # limpiar el archivo parcial si quedo
        if destino.exists():
            destino.unlink()
        print(res.stderr.strip())
        raise SystemExit(f"pg_dump fallo (codigo {res.returncode}).")

    tam = destino.stat().st_size
    if tam < 1024:
        destino.unlink()
        raise SystemExit("La copia salio vacia; algo anduvo mal.")
    print(f"Copia OK: {destino}  ({round(tam / 1_000_000, 1)} MB)")

    _rotar(carpeta)
    print(f"Listo. Se conservan las ultimas {KEEP} copias en {carpeta}")


if __name__ == "__main__":
    main()
