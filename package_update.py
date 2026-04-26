#!/usr/bin/env python3
"""
Script para empaquetar actualizaciones en formato ZIP.

Uso:
    python package_update.py --source "C:\Temp\Manarey-1.0.5" --version "1.0.5"
"""

import argparse
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path


def create_update_zip(
    source_dir: str, output_name: str = None, version: str = None
) -> bool:
    """
    Crea un archivo ZIP con la actualización.

    Args:
        source_dir: Carpeta con los archivos de la actualización
        output_name: Nombre del archivo ZIP (default: Manarey-{version}.zip)
        version: Versión (se detecta de version.py si no se proporciona)

    Returns:
        True si se creó exitosamente
    """
    try:
        source_path = Path(source_dir).resolve()

        if not source_path.exists() or not source_path.is_dir():
            print(f"❌ Error: La carpeta no existe: {source_dir}")
            return False

        # Detectar versión de version.py si no se proporciona
        if not version:
            version_file = source_path / "version.py"
            if version_file.exists():
                with open(version_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    for line in content.split("\n"):
                        if "__version__" in line and "=" in line:
                            version = line.split("=")[1].strip().strip("\"'")
                            print(f"✓ Versión detectada: {version}")
                            break

        if not version or version == "0.0.0":
            print("❌ Error: No se pudo detectar la versión. Especifica --version")
            return False

        # Nombre del ZIP
        if not output_name:
            output_name = f"Manarey-{version}.zip"

        output_path = Path(output_name).resolve()

        print(f"\n📦 Empaquetando actualizacion:")
        print(f"   Origen: {source_path}")
        print(f"   Destino: {output_path}")
        print(f"   Versión: {version}")

        # Crear ZIP
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            file_count = 0
            skip_count = 0

            # Carpetas a saltar
            skip_dirs = {"__pycache__", "logs", ".git", ".env"}
            skip_files = {".pyc", ".pyo", ".pyd", ".so"}
            skip_names = {"user_prefs.json", "config.json", ".env", ".gitignore"}

            folder_name = source_path.name  # Nombre de la carpeta raíz en el ZIP

            for root, dirs, files in os.walk(source_path):
                # Filtrar directorios a saltar
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                for file in files:
                    file_path = Path(root) / file

                    # Saltar archivos
                    if file in skip_names or any(
                        file.endswith(ext) for ext in skip_files
                    ):
                        skip_count += 1
                        continue

                    # Ruta relativa desde la carpeta raíz
                    rel_path = file_path.relative_to(source_path.parent)

                    zf.write(file_path, rel_path)
                    file_count += 1

                    # Mostrar progreso cada 50 archivos
                    if file_count % 50 == 0:
                        print(f"   {file_count} archivos empaquetados...")

            print(f"\n✓ ZIP creado exitosamente!")
            print(f"   Archivos incluidos: {file_count}")
            print(f"   Archivos saltados: {skip_count}")
            print(f"   Tamaño: {output_path.stat().st_size / (1024*1024):.2f} MB")

            return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Empaquetar actualizaciones para Manarey en formato ZIP"
    )
    parser.add_argument(
        "--source",
        "-s",
        required=True,
        help="Carpeta con los archivos de la actualización (e.g., C:\\Temp\\Manarey-1.0.5)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Nombre del archivo ZIP (default: Manarey-{version}.zip)",
    )
    parser.add_argument(
        "--version",
        "-v",
        default=None,
        help="Versión (se detecta de version.py si no se especifica)",
    )

    args = parser.parse_args()

    success = create_update_zip(args.source, args.output, args.version)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
