#!/usr/bin/env python
"""
Sube un instalador/zip al bucket de Supabase y publica la versión en app_updates.

Uso:
  SUPABASE_SERVICE_KEY=... python scripts/publish_update.py \
      --file dist/Manarey-Setup.exe \
      --version 1.0.0 \
      --changelog "Notas de la versión" \
      [--mandatory]

Requiere:
  - requests
  - Variables de entorno:
      SUPABASE_URL          -> https://<project>.supabase.co   (ej: https://etnsbiyfiaqsfkerovef.supabase.co)
      SUPABASE_SERVICE_KEY  -> service_role key (NO la distribuyas)
"""
import argparse
import mimetypes
import os
import sys
from pathlib import Path
from typing import Optional

import requests

# Reusar publish_update en app_updates
sys.path.append(str(Path(__file__).resolve().parent.parent))
from models import update_center  # noqa: E402


def upload_file(
    supabase_url: str,
    service_key: str,
    bucket: str,
    file_path: Path,
    object_name: Optional[str] = None,
) -> str:
    """
    Sube un archivo a Supabase Storage y devuelve la URL pública.
    Asume bucket público.
    """
    if not object_name:
        object_name = file_path.name

    content_type, _ = mimetypes.guess_type(file_path.name)
    content_type = content_type or "application/octet-stream"

    with file_path.open("rb") as f:
        data = f.read()

    # Upload endpoint
    upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{object_name}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "Content-Type": content_type,
    }

    resp = requests.post(upload_url, headers=headers, data=data)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Falló upload: {resp.status_code} {resp.text}")

    public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{object_name}"
    return public_url


def main():
    parser = argparse.ArgumentParser(
        description="Publicar actualización en Supabase (Storage + app_updates)."
    )
    parser.add_argument("--file", required=True, help="Ruta al instalador/zip a subir.")
    parser.add_argument(
        "--version", required=True, help="Versión a publicar (ej. 1.2.3)."
    )
    parser.add_argument("--changelog", default="", help="Notas de la versión.")
    parser.add_argument("--checksum", default="", help="Checksum (sha256) opcional.")
    parser.add_argument(
        "--mandatory",
        action="store_true",
        help="Marcar la actualización como obligatoria.",
    )
    parser.add_argument(
        "--bucket",
        default="updates",
        help="Bucket de Supabase Storage (default: updates).",
    )
    parser.add_argument(
        "--object",
        default=None,
        help="Nombre/clave destino en el bucket (default: filename).",
    )
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not supabase_url or not service_key:
        print("Faltan variables: SUPABASE_URL y SUPABASE_SERVICE_KEY", file=sys.stderr)
        sys.exit(1)

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Archivo no encontrado: {file_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Subiendo {file_path} a bucket {args.bucket}...")
    public_url = upload_file(
        supabase_url, service_key, args.bucket, file_path, args.object
    )
    print(f"Archivo subido. URL pública:\n{public_url}")

    print("Publicando en app_updates...")
    ok = update_center.publish_update(
        version=args.version,
        download_url=public_url,
        changelog=args.changelog,
        checksum=args.checksum,
        mandatory=args.mandatory,
    )
    if not ok:
        print("No se pudo guardar la actualización en app_updates.", file=sys.stderr)
        sys.exit(1)

    print(f"Actualización publicada: v{args.version}")
    print("Listo. Los clientes verán el aviso en el próximo arranque.")


if __name__ == "__main__":
    main()
