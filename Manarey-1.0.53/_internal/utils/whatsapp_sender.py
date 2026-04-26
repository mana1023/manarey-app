"""
Envío automático de mensajes de WhatsApp para la app de escritorio Manarey.

Usa la API oficial de Meta (WhatsApp Cloud API).
Cada sucursal tiene su propio número configurado en config.json bajo:

  "whatsapp": {
    "api_token": "EAAxxxxxxx",          ← token global de Meta Business
    "phone_number_ids": {
      "Cane":       "12345678901234",   ← Phone Number ID de la sucursal Cané
      "Longchamps": "98765432109876",   ← Phone Number ID de Longchamps
      "Vidriera":   "11111111111111",
      "Estacion":   "22222222222222",
      "Glew":       "33333333333333"
    }
  }

Si api_token o el phone_number_id del local no están configurados,
la función silenciosamente no envía nada (nunca bloquea la venta).
"""

import json
import logging
import os
import re
import threading
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────────────────────────────────────────


def _load_wa_config() -> dict:
    """Lee la sección 'whatsapp' de config.json."""
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "config.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("whatsapp", {})
    except Exception:
        return {}


def _get_branch_phone_number_id(local_name: str, wa_config: dict) -> str:
    """
    Devuelve el phone_number_id de Meta para la sucursal indicada.
    Hace búsqueda case-insensitive y tolerante a variaciones de nombre.
    """
    ids: dict = wa_config.get("phone_number_ids", {})
    local_lower = (local_name or "").lower().strip()

    # Búsqueda exacta (case-insensitive)
    for key, val in ids.items():
        if key.lower().strip() == local_lower:
            return (val or "").strip()

    # Búsqueda parcial
    for key, val in ids.items():
        if local_lower in key.lower() or key.lower() in local_lower:
            return (val or "").strip()

    return ""


# ──────────────────────────────────────────────────────────────────────────────
# Normalización de teléfono argentino → E.164
# ──────────────────────────────────────────────────────────────────────────────


def normalize_arg_phone(phone: str) -> str | None:
    """
    Convierte cualquier formato de teléfono argentino al E.164 para Meta API.
    Ejemplos:
      "11 3250-7516"        → "5491132507516"
      "011 4555-1234"       → "5491145551234"
      "+54 9 11 3250-7516"  → "5491132507516"
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None

    if digits.startswith("54"):
        if not digits.startswith("549"):
            digits = "549" + digits[2:]
        return digits

    if digits.startswith("0"):
        digits = digits[1:]
    if digits.startswith("15"):
        digits = digits[2:]

    return "549" + digits


# ──────────────────────────────────────────────────────────────────────────────
# Envío real vía Meta API
# ──────────────────────────────────────────────────────────────────────────────


def send_whatsapp_message(
    to_phone: str, message: str, phone_number_id: str, api_token: str
) -> bool:
    """
    Envía un mensaje de texto por WhatsApp.
    Usa urllib (sin dependencias externas).
    """
    to = normalize_arg_phone(to_phone)
    if not to or len(to) < 10:
        return False

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    body = json.dumps(
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": message},
        }
    ).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        logger.warning(
            "WhatsApp API error %s: %s",
            e.code,
            e.read().decode("utf-8", errors="ignore"),
        )
        return False
    except Exception as e:
        logger.error("WhatsApp send error: %s", e)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Historial del cliente
# ──────────────────────────────────────────────────────────────────────────────


def count_previous_paid_orders(phone: str, exclude_venta_id=None) -> int:
    """
    Cuenta cuántas ventas completadas tiene este teléfono en la DB,
    excluyendo la venta actual. Sirve para saber si es cliente nuevo o recurrente.
    Compara los últimos 8 dígitos del teléfono para ser tolerante a formatos.
    """
    try:
        from models.db import get_connection as get_conn
        from models.db import is_postgres
        from models.db import put_connection as put_conn

        digits = re.sub(r"\D", "", phone or "")
        if len(digits) < 6:
            return 0
        last8 = digits[-8:]

        ph = "%s" if is_postgres() else "?"
        conn = get_conn()
        try:
            cur = conn.cursor()
            sql = (
                f"SELECT COUNT(*) FROM ventas "
                f"WHERE cliente_telefono LIKE {ph} AND estado = 'completada'"
            )
            params: list = [f"%{last8}%"]

            if exclude_venta_id is not None:
                sql += f" AND id != {ph}"
                params.append(int(exclude_venta_id))

            cur.execute(sql, params)
            row = cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            put_conn(conn)
    except Exception as e:
        logger.error("Error contando ventas previas: %s", e)
        return 0


# ──────────────────────────────────────────────────────────────────────────────
# Construcción de mensajes
# ──────────────────────────────────────────────────────────────────────────────


def _fmt_pesos(total: float) -> str:
    """Formatea un número como pesos argentinos: $125.000"""
    try:
        return f"${int(total):,}".replace(",", ".")
    except Exception:
        return f"${total}"


def _build_purchase_message(
    nombre: str, numero_venta: str, total: float, is_first: bool
) -> str:
    primer_nombre = (nombre or "").split()[0] if nombre else "cliente"
    total_str = _fmt_pesos(total)

    if is_first:
        return (
            f"¡Hola {primer_nombre}! 🎉 Registramos tu compra *{numero_venta}* por *{total_str}*.\n\n"
            f"Como es tu primera compra, en breve te vamos a agendar para que puedas "
            f"ver nuestros estados y consultarnos directamente desde acá.\n\n"
            f"¡Gracias por elegir *Manarey*! 🛋️"
        )
    else:
        return (
            f"¡Hola {primer_nombre}! Gracias por volver a elegirnos 🛋️\n\n"
            f"Registramos tu compra *{numero_venta}* por *{total_str}*. "
            f"En breve nos comunicamos para coordinar. ¡Hasta pronto!"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Punto de entrada público (fire-and-forget en hilo separado)
# ──────────────────────────────────────────────────────────────────────────────


def send_purchase_message_async(
    phone: str,
    nombre: str,
    numero_venta: str,
    total: float,
    local_name: str,
    venta_id=None,
) -> None:
    """
    Envía el mensaje de WhatsApp al cliente en un hilo daemon.
    Nunca lanza excepciones hacia el llamador.

    El mensaje se envía DESDE el número de WhatsApp de la sucursal que
    registró la venta (cada sucursal tiene su phone_number_id en config.json).
    """
    if not phone:
        return

    def _worker():
        try:
            wa = _load_wa_config()
            api_token = (wa.get("api_token") or "").strip()
            phone_number_id = _get_branch_phone_number_id(local_name, wa)

            if not api_token or not phone_number_id:
                logger.debug(
                    "WhatsApp no configurado para sucursal '%s', omitiendo.", local_name
                )
                return

            prev = count_previous_paid_orders(phone, exclude_venta_id=venta_id)
            msg = _build_purchase_message(
                nombre, numero_venta, total, is_first=(prev == 0)
            )

            ok = send_whatsapp_message(phone, msg, phone_number_id, api_token)
            if ok:
                logger.info(
                    "WhatsApp enviado a %s (orden %s, sucursal %s)",
                    phone,
                    numero_venta,
                    local_name,
                )
            else:
                logger.warning("WhatsApp falló para %s", phone)
        except Exception as exc:
            logger.error("Error en send_purchase_message_async: %s", exc)

    threading.Thread(target=_worker, daemon=True).start()
