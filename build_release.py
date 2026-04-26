#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para construir y empaquetar una actualización compilada.

Esto:
1. Ejecuta PyInstaller
2. Prepara los archivos compilados
3. Crea un ZIP listo para subir

Uso:
    python build_release.py --spec Manarey.spec
"""

import argparse
import io
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# Fix encoding para PowerShell Windows
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def run_command(cmd, description=""):
    """Ejecuta un comando y reporta errores."""
    print(f"\n▶ {description}")
    print(f"  $ {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al ejecutar: {e}")
        return False


def build_release(spec_file: str, output_dir: str = None) -> bool:
    """
    Construye un release compilado y empaquetado.
    """
    try:
        spec_path = Path(spec_file).resolve()

        if not spec_path.exists():
            print(f"❌ Error: No se encontró {spec_file}")
            return False

        # Detectar versión
        version = "0.0.0"
        version_file = spec_path.parent / "version.py"
        if version_file.exists():
            with open(version_file, "r") as f:
                for line in f:
                    if "__version__" in line and "=" in line:
                        version = line.split("=")[1].strip().strip("'\"")
                        break

        print(f"\n{'='*60}")
        print(f"📦 Compilando Manarey v{version}")
        print(f"{'='*60}")

        # 1. Limpiar builds anteriores
        print("\n🧹 Limpiando compilaciones anteriores...")
        for folder in ["build", "dist", "__pycache__"]:
            folder_path = spec_path.parent / folder
            if folder_path.exists():
                shutil.rmtree(folder_path)
                print(f"   Eliminado: {folder}")

        # 2. Ejecutar PyInstaller
        if not run_command(
            [sys.executable, "-m", "PyInstaller", str(spec_path)],
            "Compilando con PyInstaller...",
        ):
            return False

        # 3. Verificar resultado
        dist_dir = spec_path.parent / "dist"
        if not dist_dir.exists():
            print(f"❌ Error: No se creó carpeta dist/")
            return False

        # Encontrar carpeta compilada (suele ser Manarey si el spec lo especifica)
        compiled_app = dist_dir / "Manarey"
        if not compiled_app.exists():
            # Buscar cualquier carpeta en dist
            subdirs = [d for d in dist_dir.iterdir() if d.is_dir()]
            if subdirs:
                compiled_app = subdirs[0]
            else:
                print(f"❌ Error: No se encontró la carpeta compilada en dist/")
                return False

        print(f"✓ Compilacion completa: {compiled_app}")

        # 4. Preparar carpeta de release
        release_folder = spec_path.parent / f"Manarey-{version}"
        if release_folder.exists():
            shutil.rmtree(release_folder)

        # Copiar archivos compilados
        print(f"\n📋 Preparando carpeta de release...")
        shutil.copytree(compiled_app, release_folder)
        print(f"   Copiado a: {release_folder}")

        # Copiar archivos adicionales importantes
        important_files = ["version.py", "README.md", "LICENSE.txt"]

        for file in important_files:
            src = spec_path.parent / file
            if src.exists():
                dst = release_folder / file
                shutil.copy2(src, dst)
                print(f"   Incluido: {file}")

        # 5. Crear ZIP
        zip_name = f"Manarey-{version}.zip"
        if output_dir:
            zip_path = Path(output_dir) / zip_name
            os.makedirs(output_dir, exist_ok=True)
        else:
            zip_path = spec_path.parent / zip_name

        print(f"\n📦 Creando archivo ZIP...")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            file_count = 0
            for root, dirs, files in os.walk(release_folder):
                # No incluir carpetas de cache
                dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git"}]

                for file in files:
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(release_folder.parent)
                    zf.write(file_path, rel_path)
                    file_count += 1

                    if file_count % 100 == 0:
                        print(f"   {file_count} archivos...")

            print(f"\n✓ ZIP creado exitosamente!")
            print(f"   Archivo: {zip_path}")
            print(f"   Tamaño: {zip_path.stat().st_size / (1024*1024):.2f} MB")
            print(f"   Archivos: {file_count}")

        # 6. Mostrar instrucciones
        print(f"\n{'='*60}")
        print(f"✓ Release listo para distribuir")
        print(f"{'='*60}")
        print(f"\n📤 Próximos pasos:")
        print(f"   1. Sube {zip_path} a Supabase Storage")
        print(f"   2. Copia la URL pública del archivo")
        print(f"   3. Registra en la BD con:")
        print(f"\nSQL:")
        print(
            f"""
INSERT INTO updates (version, download_url, changelog, published_at, mandatory, force_after_days)
VALUES (
  '{version}',
  'https://YOUR_SUPABASE_URL/storage/v1/object/public/releases/{zip_name}',
  'Cambios aquí',
  NOW(),
  false,
  2
);
        """
        )

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Construir y empaquetar una release de Manarey"
    )
    parser.add_argument(
        "--spec",
        "-s",
        default="Manarey.spec",
        help="Archivo .spec de PyInstaller (default: Manarey.spec)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Carpeta de salida para el ZIP (default: misma carpeta del spec)",
    )

    args = parser.parse_args()

    success = build_release(args.spec, args.output)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
