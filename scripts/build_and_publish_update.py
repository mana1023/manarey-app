#!/usr/bin/env python
"""
Build + upload + publicar actualización en Supabase.

Pasos:
  1) Asegúrate de tener PyInstaller instalado y, si quieres NSIS/zip, define cómo empaquetas.
  2) Exporta variables:
       SUPABASE_URL=https://<project>.supabase.co
       SUPABASE_SERVICE_KEY=<service_role>
       SUPABASE_BUCKET=updates   (opcional, default updates)
  3) Ejecuta:
       python scripts/build_and_publish_update.py --version 1.0.0 --changelog "Notas" [--mandatory]

Qué hace:
  - Corre PyInstaller usando Manarey.spec (si existe) o app.py.
  - Crea un zip de dist/Manarey (o el nombre de carpeta generado).
  - Sube el zip al bucket y publica la entrada en app_updates con la URL pública.

Nota:
  - Requiere requests y PyInstaller disponibles en tu entorno.
  - No se incrusta la service_key en el repo; se toma de env vars.
"""
import argparse
import mimetypes
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional

import requests

sys.path.append(str(Path(__file__).resolve().parent.parent))
from models import update_center  # noqa: E402


def run_pyinstaller(project_root: Path) -> Path:
    """Ejecuta PyInstaller y devuelve la carpeta de salida (dist/<name>)."""
    spec = project_root / "Manarey.spec"
    if spec.exists():
        cmd = ["pyinstaller", str(spec)]
        build_name = spec.stem
    else:
        cmd = ["pyinstaller", "--noconfirm", "--clean", str(project_root / "app.py")]
        build_name = "dist/app"
    print("Ejecutando:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=project_root)
    # Inferir carpeta dentro de dist
    dist_dir = project_root / "dist"
    # tomar la última carpeta modificada
    candidates = sorted(
        [p for p in dist_dir.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError("No se encontró carpeta en dist/")
    return candidates[0]


def make_zip(folder: Path, version: str) -> Path:
    """Crea un zip de la carpeta de distribución."""
    zip_path = folder.parent / f"{folder.name}-{version}.zip"
    print(f"Empaquetando {folder} -> {zip_path}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in folder.rglob("*"):
            zf.write(file, file.relative_to(folder))
    return zip_path


def upload_file(
    supabase_url: str,
    service_key: str,
    bucket: str,
    file_path: Path,
    object_name: Optional[str] = None,
) -> str:
    """Sube archivo a Supabase Storage y devuelve URL pública."""
    if not object_name:
        object_name = file_path.name
    content_type, _ = mimetypes.guess_type(file_path.name)
    content_type = content_type or "application/octet-stream"
    with file_path.open("rb") as f:
        data = f.read()
    upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{object_name}"
    headers = {"Authorization": f"Bearer {service_key}", "Content-Type": content_type}
    resp = requests.post(upload_url, headers=headers, data=data)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Upload falló: {resp.status_code} {resp.text}")
    return f"{supabase_url}/storage/v1/object/public/{bucket}/{object_name}"


def read_version(project_root: Path) -> str:
    """Lee __version__ de version.py"""
    version_file = project_root / "version.py"
    ns = {}
    exec(version_file.read_text(encoding="utf-8"), ns, ns)
    return ns.get("__version__", "0.0.0")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version", help="Versión a publicar. Si se omite, usa version.py"
    )
    parser.add_argument("--changelog", default="", help="Notas de la versión")
    parser.add_argument("--checksum", default="", help="Checksum opcional")
    parser.add_argument(
        "--mandatory", action="store_true", help="Marcar como obligatoria"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Saltar build y usar último artefacto en dist/",
    )
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    bucket = os.environ.get("SUPABASE_BUCKET", "updates")
    if not supabase_url or not service_key:
        print(
            "Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en el entorno.", file=sys.stderr
        )
        sys.exit(1)

    root = Path(__file__).resolve().parent.parent
    version = args.version or read_version(root)

    if args.skip_build:
        dist_dir = max((root / "dist").iterdir(), key=lambda p: p.stat().st_mtime)
    else:
        dist_dir = run_pyinstaller(root)
    zip_path = make_zip(dist_dir, version)

    print("Subiendo artefacto...")
    public_url = upload_file(supabase_url, service_key, bucket, zip_path)
    print("URL pública:", public_url)

    print("Publicando en app_updates...")
    ok = update_center.publish_update(
        version=version,
        download_url=public_url,
        changelog=args.changelog,
        checksum=args.checksum,
        mandatory=args.mandatory,
    )
    if not ok:
        print("No se pudo guardar en app_updates", file=sys.stderr)
        sys.exit(1)
    print("Listo. Versión publicada:", version)


if __name__ == "__main__":
    main()
