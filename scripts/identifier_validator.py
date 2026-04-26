"""
Pequeño helper para validar identificadores SQL seguros.
Se usa para evitar interpolaciones peligrosas en consultas donde no
se pueden usar parámetros (p. ej. nombres de tabla/columna).
"""
import re

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_safe_identifier(name: str) -> bool:
    """Devuelve True si `name` es un identificador seguro (letra/_ seguido de letras/dígitos/_).

    Acepta str no vacío. Devuelve False para None o cadenas que no casan.
    """
    if not isinstance(name, str):
        return False
    return bool(_IDENT_RE.match(name))
