"""models/config_security.py

Ofuscacion liviana de la URL de base de datos en config.json.
No es cifrado real pero evita que la contrasena sea legible a simple vista
en el archivo de configuracion de cada local.

Usa XOR con una clave derivada del nombre de maquina + salt fijo.
Cada maquina genera una clave distinta, por lo que el config.json
de una PC no funciona si se copia a otra.
"""
import base64
import hashlib
import json
import os
from pathlib import Path

_SALT = b"Manarey_cfg_v1"


def _machine_key() -> bytes:
    machine = (
        os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "Manarey"
    ).encode("utf-8")
    return hashlib.sha256(machine + _SALT).digest()


def encode_url(url: str) -> str:
    """Ofusca una URL con XOR + base64 usando clave de la maquina."""
    data = url.encode("utf-8")
    key = _machine_key()
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.b64encode(xored).decode("ascii")


def decode_url(enc: str) -> str:
    """Decodifica una URL ofuscada con encode_url."""
    xored = base64.b64decode(enc.encode("ascii"))
    key = _machine_key()
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(xored)).decode("utf-8")


def migrate_config(config_path: Path) -> bool:
    """
    Si config.json tiene 'database_url' en texto plano, lo ofusca y guarda
    como 'database_url_enc', eliminando la version legible.
    Retorna True si se hizo la migracion.
    """
    try:
        if not config_path.exists():
            return False
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        plain = cfg.get("database_url", "").strip()
        if not plain or cfg.get("database_url_enc"):
            return False
        cfg["database_url_enc"] = encode_url(plain)
        del cfg["database_url"]
        config_path.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return True
    except Exception:
        return False
