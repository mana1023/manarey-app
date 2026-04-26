#!/usr/bin/env python3
"""
Script para subir y registrar actualizaciones en Supabase.

Esto automatiza:
1. Subir ZIP a Supabase Storage
2. Obtener URL pública
3. Registrar en tabla de updates

Uso:
    python deploy_update.py --zip Manarey-1.0.5.zip --changelog "Cambios importantes"
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path


def deploy_update(
    zip_file: str, changelog: str = None, mandatory: bool = False, force_days: int = 2
) -> bool:
    """
    Despliega una actualización a Supabase.

    Args:
        zip_file: Ruta al archivo ZIP
        changelog: Notas de cambios
        mandatory: Si es obligatoria
        force_days: Días antes de hacer obligatoria
    """
    try:
        zip_path = Path(zip_file).resolve()

        if not zip_path.exists():
            print(f"❌ Error: No se encontró {zip_file}")
            return False

        # Detectar versión del nombre del ZIP
        version = None
        if "-" in zip_path.stem:
            version = zip_path.stem.split("-")[-1]

        if not version:
            print(
                "❌ Error: No se pudo detectar versión del nombre. Usa formato 'Manarey-X.Y.Z.zip'"
            )
            return False

        print(f"\n{'='*60}")
        print(f"📤 Desplegando actualización")
        print(f"{'='*60}")
        print(f"   Versión: {version}")
        print(f"   Archivo: {zip_path}")
        print(f"   Tamaño: {zip_path.stat().st_size / (1024*1024):.2f} MB")
        print(f"   Obligatoria: {'Sí' if mandatory else 'No'}")
        if not mandatory:
            print(f"   Forzar en: {force_days} días")

        # Importar cliente Supabase
        try:
            import supabase
            from supabase import create_client
        except ImportError:
            print("\n❌ Error: Se requiere instalar 'supabase'")
            print("   pip install supabase")
            return False

        # Cargar credenciales
        try:
            from config_supabase import SUPABASE_KEY, SUPABASE_URL
        except ImportError:
            try:
                import json

                with open("config.json", "r") as f:
                    cfg = json.load(f)
                    SUPABASE_URL = cfg.get("SUPABASE_URL")
                    SUPABASE_KEY = cfg.get("SUPABASE_KEY")
            except:
                print("❌ Error: No se encontraron credenciales de Supabase")
                print(
                    "   Configura SUPABASE_URL y SUPABASE_KEY en config.json o config_supabase.py"
                )
                return False

        if not SUPABASE_URL or not SUPABASE_KEY:
            print("❌ Error: SUPABASE_URL o SUPABASE_KEY no están configurados")
            return False

        # Conectar a Supabase
        print(f"\n🔗 Conectando a Supabase...")
        try:
            client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("   ✓ Conectado")
        except Exception as e:
            print(f"❌ Error conectando: {e}")
            return False

        # Subir archivo
        print(f"\n📤 Subiendo archivo...")
        try:
            bucket_name = "releases"
            file_name = zip_path.name

            with open(zip_path, "rb") as f:
                response = client.storage.from_(bucket_name).upload(
                    file=f,
                    path=file_name,
                    file_options={"content-type": "application/zip"},
                )

            # Obtener URL pública
            download_url = client.storage.from_(bucket_name).get_public_url(file_name)

            print(f"   ✓ Archivo subido")
            print(f"   URL: {download_url}")

        except Exception as e:
            print(f"❌ Error subiendo: {e}")
            return False

        # Registrar en BD
        print(f"\n💾 Registrando en base de datos...")
        try:
            from models import update_center

            # Si existe una versión anterior, desactivarla
            try:
                client.table("updates").update(
                    {"mandatory": False, "force_after_days": 999}  # Desactivar
                ).eq("version", version).execute()
            except:
                pass

            # Insertar nueva actualización
            new_update = {
                "version": version,
                "download_url": download_url,
                "changelog": changelog or f"Actualización a versión {version}",
                "published_at": datetime.now().isoformat(),
                "mandatory": mandatory,
                "force_after_days": force_days,
            }

            result = client.table("updates").insert(new_update).execute()

            print(f"   ✓ Registrado en BD")
            print(f"\n✓ Actualización desplegada exitosamente!")
            print(f"\nDetalles:")
            print(f"   Versión: {version}")
            print(f"   URL: {download_url}")
            print(f"   Obligatoria: {mandatory}")
            print(f"   Forzar en: {force_days} días")

            return True

        except Exception as e:
            print(f"❌ Error registrando: {e}")
            import traceback

            traceback.print_exc()
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Desplegar actualización a Supabase")
    parser.add_argument(
        "--zip",
        "-z",
        required=True,
        help="Archivo ZIP de la actualización (e.g., Manarey-1.0.5.zip)",
    )
    parser.add_argument(
        "--changelog", "-c", default=None, help="Notas de cambios (markdown)"
    )
    parser.add_argument(
        "--mandatory",
        "-m",
        action="store_true",
        help="Marcar como actualización obligatoria",
    )
    parser.add_argument(
        "--force-days",
        "-f",
        type=int,
        default=2,
        help="Días antes de forzar instalación (default: 2)",
    )

    args = parser.parse_args()

    success = deploy_update(args.zip, args.changelog, args.mandatory, args.force_days)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
