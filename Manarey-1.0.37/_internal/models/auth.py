"""módulo de autenticación: hashing y verificación de contraseñas.

Usa passlib (bcrypt) para hashear/validar contraseñas. Provee utilidades
para verificar y para detectar si un hash necesita ser actualizado.
"""
import bcrypt


def hash_password(password: str) -> str:
    # bcrypt expects bytes; limit to 72 bytes is enforced by bcrypt
    pw = password.encode("utf-8")
    hashed = bcrypt.hashpw(pw, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def needs_rehash(hashed_password: str) -> bool:
    # For simplicity no automatic rehashing logic here; return False
    return False
