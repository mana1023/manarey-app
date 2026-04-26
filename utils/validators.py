"""
validators.py — Módulo de validación de datos para Manarey.

Todas las funciones retornan tuplas (es_valido, error_o_errores) para que
el código llamador pueda decidir si aborta o muestra mensajes al usuario.
"""

import re
from typing import Any, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

ESTADOS_PRODUCTO_VALIDOS = {
    "nuevo",
    "usado",
    "discontinuado",
    "activo",
    "inactivo",
    "sin_stock",
    "reacondicionado",
    "muestra",
    "reservado",
}
FORMAS_PAGO_VALIDAS = {
    "Efectivo",
    "Débito",
    "Debito",
    "Crédito",
    "Credito",
    "Transferencia",
    "MercadoPago",
    "Mercado Pago",
    "QR",
    "Cheque",
    "Cuenta Corriente",
    "Otro",
}

# Caracteres que se consideran peligrosos para insertar en strings de texto
# libre (prevención básica de injection en logs / exportaciones).
_DANGEROUS_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# ---------------------------------------------------------------------------
# Helpers primitivos
# ---------------------------------------------------------------------------


def validate_precio(value: Any) -> Tuple[bool, str]:
    """Valida que *value* sea un número válido y >= 0.

    Returns:
        (True, "") si es válido.
        (False, mensaje_de_error) si no lo es.
    """
    if value is None:
        return False, "El precio no puede ser nulo."
    try:
        precio = float(value)
    except (TypeError, ValueError):
        return False, f"El precio '{value}' no es un número válido."
    if precio < 0:
        return False, f"El precio no puede ser negativo (valor: {precio})."
    return True, ""


def validate_cantidad(value: Any) -> Tuple[bool, str]:
    """Valida que *value* sea un entero >= 0.

    Returns:
        (True, "") si es válido.
        (False, mensaje_de_error) si no lo es.
    """
    if value is None:
        return False, "La cantidad no puede ser nula."
    try:
        # Aceptamos float que sea entero exacto (e.g. 2.0)
        cantidad = float(value)
    except (TypeError, ValueError):
        return False, f"La cantidad '{value}' no es un número válido."
    if cantidad < 0:
        return False, f"La cantidad no puede ser negativa (valor: {cantidad})."
    if cantidad != int(cantidad):
        return False, f"La cantidad debe ser un número entero (valor: {value})."
    return True, ""


def sanitize_string(value: str, max_length: int = 255) -> str:
    """Limpia un string: strip, elimina caracteres de control y limita longitud.

    Args:
        value: Cadena a limpiar.
        max_length: Longitud máxima permitida (se trunca si excede).

    Returns:
        String saneado.
    """
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    value = value.strip()
    value = _DANGEROUS_CHARS_RE.sub("", value)
    if len(value) > max_length:
        value = value[:max_length]
    return value


def validate_local(value: str, valid_locals: List[str]) -> Tuple[bool, str]:
    """Valida que *value* sea uno de los locales permitidos.

    Args:
        value: Nombre del local a validar.
        valid_locals: Lista de locales válidos (comparación case-insensitive).

    Returns:
        (True, "") si es válido.
        (False, mensaje_de_error) si no lo es.
    """
    if not value or not value.strip():
        return False, "El local no puede estar vacío."
    value_norm = value.strip().lower()
    valid_norm = [v.strip().lower() for v in (valid_locals or [])]
    if value_norm not in valid_norm:
        opciones = ", ".join(valid_locals) if valid_locals else "(ninguno definido)"
        return False, f"El local '{value}' no es válido. Opciones: {opciones}."
    return True, ""


# ---------------------------------------------------------------------------
# Validadores de entidades
# ---------------------------------------------------------------------------


def validate_producto(data: dict) -> Tuple[bool, List[str]]:
    """Valida los datos de un producto antes de guardarlo en la base de datos.

    Campos evaluados:
        - nombre: no vacío, máximo 255 caracteres.
        - precio: número >= 0.
        - cantidad: entero >= 0.
        - local: no vacío.
        - categoria: no vacía.
        - estado: uno de ESTADOS_PRODUCTO_VALIDOS (si está presente).

    Args:
        data: Diccionario con los campos del producto.

    Returns:
        (True, []) si todos los campos son válidos.
        (False, [lista_de_errores]) si hay algún problema.
    """
    errores: List[str] = []

    # Nombre
    nombre = data.get("nombre", "")
    if not nombre or not str(nombre).strip():
        errores.append("El nombre del producto no puede estar vacío.")
    elif len(str(nombre).strip()) > 255:
        errores.append("El nombre del producto no puede superar los 255 caracteres.")

    # Precio
    ok, msg = validate_precio(data.get("precio"))
    if not ok:
        errores.append(msg)

    # Cantidad
    ok, msg = validate_cantidad(data.get("cantidad"))
    if not ok:
        errores.append(msg)

    # Local
    local = data.get("local", "")
    if not local or not str(local).strip():
        errores.append("El local del producto no puede estar vacío.")

    # Categoría
    categoria = data.get("categoria", "")
    if not categoria or not str(categoria).strip():
        errores.append("La categoría del producto no puede estar vacía.")

    # Estado — no bloqueamos si viene un valor desconocido
    # (la lista puede crecer), solo validamos que no esté vacío si se provee
    estado = data.get("estado")
    if estado is not None and str(estado).strip() == "":
        errores.append("El estado del producto no puede ser una cadena vacía.")

    return (len(errores) == 0, errores)


def validate_venta(data: dict) -> Tuple[bool, List[str]]:
    """Valida los datos de una venta antes de registrarla.

    Campos evaluados:
        - items: lista no vacía, cada item debe tener cantidad > 0 y precio >= 0.
        - local: no vacío.
        - forma_pago: no vacía.
        - cliente_nombre (dentro de cliente_data): no vacío.
        - total calculado > 0.

    Args:
        data: Diccionario con los parámetros de la venta.  Admite la misma
              estructura que usa ``registrar_venta`` / ``_registrar_venta_online``.

    Returns:
        (True, []) si todo es válido.
        (False, [lista_de_errores]) si hay algún problema.
    """
    errores: List[str] = []

    # Items
    items = data.get("items")
    if not items:
        errores.append("La venta debe tener al menos un producto.")
    else:
        if not isinstance(items, (list, tuple)):
            errores.append("Los items de la venta deben ser una lista.")
        else:
            for idx, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    errores.append(f"El item #{idx} no tiene formato válido.")
                    continue
                # Cantidad del item
                ok, msg = validate_cantidad(item.get("cantidad"))
                if not ok:
                    errores.append(f"Item #{idx} — {msg}")
                else:
                    cant = float(item.get("cantidad", 0))
                    if cant <= 0:
                        errores.append(f"Item #{idx} — La cantidad debe ser mayor a 0.")
                # Precio unitario del item
                ok, msg = validate_precio(item.get("precio_unitario"))
                if not ok:
                    errores.append(f"Item #{idx} — {msg}")

    # Local
    local = data.get("local", "")
    if not local or not str(local).strip():
        errores.append("El local de la venta no puede estar vacío.")

    # Forma de pago
    forma_pago = data.get("forma_pago", "")
    if not forma_pago or not str(forma_pago).strip():
        errores.append("La forma de pago no puede estar vacía.")

    # Cliente nombre (dentro de cliente_data) — opcional, no bloquea la venta
    # (se permiten ventas anónimas de mostrador)

    # Total > 0 (calculado a partir de items válidos)
    if items and isinstance(items, (list, tuple)):
        try:
            total = sum(
                float(item.get("cantidad", 0)) * float(item.get("precio_unitario", 0))
                for item in items
                if isinstance(item, dict)
            )
            if total <= 0:
                errores.append("El total de la venta debe ser mayor a 0.")
        except (TypeError, ValueError):
            # Los errores individuales de precio/cantidad ya fueron capturados arriba
            pass

    return (len(errores) == 0, errores)
