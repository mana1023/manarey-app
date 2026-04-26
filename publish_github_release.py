#!/usr/bin/env python3
"""
Publicar actualización en GitHub Releases

Uso:
    python publish_github_release.py --version 1.0.5 --file Manarey-1.0.5.zip
    
Variables de entorno requeridas:
    GITHUB_REPO = "usuario/repo"
    GITHUB_TOKEN = "tu_token_github"
"""

import argparse
import json
import os
import sys
from pathlib import Path


def publish_release(
    version: str, zip_file: str, changelog: str = None, mandatory: bool = False
) -> bool:
    """Publish release to GitHub"""
    try:
        # Obtener credenciales
        repo = os.environ.get("GITHUB_REPO")
        token = os.environ.get("GITHUB_TOKEN")

        if not repo or not token:
            print("❌ Error: GITHUB_REPO y GITHUB_TOKEN requeridos")
            print("   Configura variables de entorno:")
            print("   $env:GITHUB_REPO = 'usuario/repo'")
            print("   $env:GITHUB_TOKEN = 'tu_token'")
            return False

        zip_path = Path(zip_file).resolve()
        if not zip_path.exists():
            print(f"❌ Error: No se encontró {zip_file}")
            return False

        # Importar requests
        try:
            import requests
        except ImportError:
            print("❌ Error: requests no instalado. Ejecuta: pip install requests")
            return False

        print(f"\n📤 Publicando en GitHub Releases")
        print(f"   Repo: {repo}")
        print(f"   Versión: {version}")
        print(f"   Archivo: {zip_path}")
        print(f"   Tamaño: {zip_path.stat().st_size / (1024*1024):.2f} MB")

        # Crear o actualizar release
        tag = f"v{version}"
        release_url = f"https://api.github.com/repos/{repo}/releases"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # Preparar changelog
        if not changelog:
            changelog = f"Versión {version}"
        if mandatory:
            changelog += "\n\n⚠️ ACTUALIZACIÓN OBLIGATORIA"

        # 1. Obtener release existente o crear nueva
        print(f"   Buscando release {tag}...")

        # Buscar si ya existe
        resp = requests.get(f"{release_url}/tags/{tag}", headers=headers, timeout=10)

        if resp.status_code == 200:
            # Ya existe, actualizar
            print(f"   ✓ Release {tag} ya existe, actualizando...")
            release_data = resp.json()
            release_id = release_data["id"]
            upload_url = release_data.get("upload_url", "").replace("{?name,label}", "")

            resp = requests.patch(
                f"{release_url}/{release_id}",
                headers=headers,
                json={
                    "tag_name": tag,
                    "name": f"Manarey {version}",
                    "body": changelog,
                    "draft": False,
                    "prerelease": False,
                },
                timeout=10,
            )

            if resp.status_code != 200:
                print(f"❌ Error actualizando release: {resp.status_code}")
                print(resp.text)
                return False

            # Obtener upload_url de la respuesta actualizada
            upload_url = resp.json().get("upload_url", "").replace("{?name,label}", "")
        else:
            # Crear nueva
            print(f"   Creando release {tag}...")
            resp = requests.post(
                release_url,
                headers=headers,
                json={
                    "tag_name": tag,
                    "name": f"Manarey {version}",
                    "body": changelog,
                    "draft": False,
                    "prerelease": False,
                },
                timeout=10,
            )

            if resp.status_code != 201:
                print(f"❌ Error creando release: {resp.status_code}")
                print(resp.text)
                return False

            release_data = resp.json()
            release_id = release_data["id"]
            upload_url = release_data.get("upload_url", "").replace("{?name,label}", "")

        # 2. Subir archivo
        print(f"   Subiendo archivo {zip_path.name}...")

        if not upload_url:
            print(f"❌ Error: No se obtuvo upload_url de GitHub")
            return False

        with open(zip_path, "rb") as f:
            upload_headers = {
                "Authorization": f"token {token}",
                "Content-Type": "application/octet-stream",
            }

            resp = requests.post(
                upload_url,
                headers=upload_headers,
                params={"name": zip_path.name},
                data=f,
                timeout=600,
            )

            if resp.status_code not in (201, 200):
                print(f"❌ Error subiendo archivo: {resp.status_code}")
                print(resp.text)
                return False

        print(f"✓ Release publicada exitosamente!")
        print(f"\n📊 Detalles:")
        print(f"   Versión: {version}")
        print(f"   Release: v{version}")
        print(f"   Archivo: {zip_path.name}")
        print(f"   URL: https://github.com/{repo}/releases/tag/v{version}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Publicar actualización en GitHub Releases"
    )
    parser.add_argument("--version", "-v", required=True, help="Versión (e.g., 1.0.5)")
    parser.add_argument("--file", "-f", required=True, help="Archivo ZIP a subir")
    parser.add_argument("--changelog", "-c", default=None, help="Notas de cambios")
    parser.add_argument(
        "--mandatory", "-m", action="store_true", help="Marcar como obligatoria"
    )

    args = parser.parse_args()

    success = publish_release(args.version, args.file, args.changelog, args.mandatory)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
