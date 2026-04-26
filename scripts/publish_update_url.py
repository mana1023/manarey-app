#!/usr/bin/env python
"""
Publica una actualizacion en la tabla app_updates usando una URL externa.

Uso:
  python scripts/publish_update_url.py --version 1.0.5 --download-url https://... --changelog "Notas"
"""
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from models import update_center  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publicar actualizacion con URL externa."
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--download-url", required=True)
    parser.add_argument("--changelog", default="")
    parser.add_argument("--checksum", default="")
    parser.add_argument("--mandatory", action="store_true")
    args = parser.parse_args()

    ok = update_center.publish_update(
        version=args.version,
        download_url=args.download_url,
        changelog=args.changelog,
        checksum=args.checksum,
        mandatory=args.mandatory,
    )
    if not ok:
        print("No se pudo guardar la actualizacion en app_updates.", file=sys.stderr)
        sys.exit(1)

    print("OK")


if __name__ == "__main__":
    main()
