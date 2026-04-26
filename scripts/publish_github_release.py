#!/usr/bin/env python
"""
Publica un release en GitHub y sube un asset.

Requiere:
  - requests
  - Variables de entorno:
      GITHUB_TOKEN -> token con permisos de repo
      GITHUB_REPO  -> owner/repo (ej: mana1023/manarey-updates)
"""
import argparse
import os
import sys
from pathlib import Path
from typing import Optional

import requests


def _api_headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_release_by_tag(repo: str, token: str, tag: str) -> Optional[dict]:
    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    resp = requests.get(url, headers=_api_headers(token), timeout=30)
    if resp.status_code == 200:
        return resp.json()
    return None


def _create_release(repo: str, token: str, tag: str, name: str, body: str) -> dict:
    url = f"https://api.github.com/repos/{repo}/releases"
    payload = {
        "tag_name": tag,
        "name": name,
        "body": body or "",
        "draft": False,
        "prerelease": False,
    }
    resp = requests.post(url, headers=_api_headers(token), json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Fallo crear release: {resp.status_code} {resp.text}")
    return resp.json()


def _delete_asset_if_exists(repo: str, token: str, release: dict, name: str) -> None:
    assets = release.get("assets") or []
    for a in assets:
        if a.get("name") == name and a.get("id"):
            url = f"https://api.github.com/repos/{repo}/releases/assets/{a['id']}"
            requests.delete(url, headers=_api_headers(token), timeout=30)
            return


def _upload_asset(upload_url: str, token: str, file_path: Path, name: str) -> dict:
    """Sube un asset al release de GitHub usando streaming (evita cargar todo en RAM).

    Reintenta hasta 3 veces si hay error de red (timeout, conexión cortada).
    """
    upload_url = upload_url.split("{", 1)[0]
    url = f"{upload_url}?name={name}"
    headers = _api_headers(token)
    headers["Content-Type"] = "application/octet-stream"

    last_err = None
    for attempt in range(1, 4):
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    url,
                    headers=headers,
                    data=f,
                    timeout=600,  # 10 min — archivos grandes en conexiones lentas
                )
            if resp.status_code not in (200, 201):
                raise RuntimeError(
                    f"Fallo upload asset: {resp.status_code} {resp.text[:200]}"
                )
            return resp.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            print(
                f"   Intento {attempt}/3 fallo: {e}. Reintentando...", file=sys.stderr
            )
            import time

            time.sleep(5 * attempt)  # backoff: 5s, 10s, 15s
        except Exception as e:
            raise e

    raise RuntimeError(f"No se pudo subir el asset tras 3 intentos: {last_err}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publicar release en GitHub y subir asset."
    )
    parser.add_argument("--file", required=True, help="Ruta al instalador.")
    parser.add_argument("--tag", required=True, help="Tag del release (ej: v1.0.5).")
    parser.add_argument("--name", default="", help="Nombre del release.")
    parser.add_argument("--body", default="", help="Notas del release.")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    if not token or not repo:
        print("Faltan variables: GITHUB_TOKEN y GITHUB_REPO", file=sys.stderr)
        sys.exit(1)

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Archivo no encontrado: {file_path}", file=sys.stderr)
        sys.exit(1)

    tag = args.tag
    name = args.name or tag
    body = args.body or ""

    release = _get_release_by_tag(repo, token, tag)
    if not release:
        release = _create_release(repo, token, tag, name, body)

    _delete_asset_if_exists(repo, token, release, file_path.name)
    asset = _upload_asset(release["upload_url"], token, file_path, file_path.name)
    url = asset.get("browser_download_url")
    if not url:
        print("No se pudo obtener browser_download_url", file=sys.stderr)
        sys.exit(1)

    # Imprimir SOLO la URL para que PowerShell la capture
    print(url)


if __name__ == "__main__":
    main()
