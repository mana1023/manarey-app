# models/sql_utils.py
"""
Utilidades mínimas para validar identificadores SQL y listas de SET.
Reintroducido para el modo PostgreSQL/Supabase.
"""
import re

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_safe_identifier(name: str) -> bool:
    """Devuelve True si el identificador es seguro (sin espacios ni símbolos)."""
    return isinstance(name, str) and bool(_IDENT_RE.match(name))


def validate_sets_list(sets):
    """Valida una lista de clausulas SET en forma 'campo=?' o 'campo=%s'."""
    if not isinstance(sets, (list, tuple)):
        raise ValueError("sets debe ser lista/tupla")
    for s in sets:
        if not isinstance(s, str) or "=" not in s:
            raise ValueError(f"SET inválido: {s!r}")
        field = s.split("=")[0].strip()
        if not is_safe_identifier(field):
            raise ValueError(f"Identificador inválido en SET: {field!r}")
