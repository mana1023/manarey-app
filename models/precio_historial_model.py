"""Registro de cambios de precio de productos."""
import logging
from typing import Any, Dict, List

from models.db import get_connection as get_conn
from models.db import is_postgres
from models.db import put_connection as put_conn

logger = logging.getLogger(__name__)


def _ph():
    return "%s" if is_postgres() else "?"


def registrar_cambio(
    producto_id: int,
    local: str,
    usuario: str,
    precio_costo_ant: float,
    precio_costo_nuevo: float,
    precio_venta_ant: float,
    precio_venta_nuevo: float,
    motivo: str = "",
) -> bool:
    if (
        abs(precio_costo_ant - precio_costo_nuevo) < 0.01
        and abs(precio_venta_ant - precio_venta_nuevo) < 0.01
    ):
        return True  # sin cambio real
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"INSERT INTO precio_historial "
            f"(producto_id,local,usuario,precio_costo_anterior,precio_costo_nuevo,"
            f"precio_venta_anterior,precio_venta_nuevo,motivo) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            (
                int(producto_id),
                local,
                usuario,
                float(precio_costo_ant),
                float(precio_costo_nuevo),
                float(precio_venta_ant),
                float(precio_venta_nuevo),
                motivo.strip(),
            ),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception("Error registrando cambio de precio")
        return False
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def get_historial_producto(producto_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"SELECT id,local,usuario,precio_costo_anterior,precio_costo_nuevo,"
            f"precio_venta_anterior,precio_venta_nuevo,fecha,motivo "
            f"FROM precio_historial WHERE producto_id={ph} "
            f"ORDER BY fecha DESC LIMIT {limit}",
            (int(producto_id),),
        )
        cols = [
            "id",
            "local",
            "usuario",
            "costo_ant",
            "costo_nuevo",
            "venta_ant",
            "venta_nuevo",
            "fecha",
            "motivo",
        ]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        logger.exception("Error obteniendo historial de precios")
        return []
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def get_historial_global(local: str = "", limit: int = 200) -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        wheres = []
        params: list = []
        if local and local not in ("Todos", "Todos los locales"):
            wheres.append(f"ph.local={ph}")
            params.append(local)
        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        cur.execute(
            f"SELECT ph.id, p.nombre, ph.local, ph.usuario, "
            f"ph.precio_costo_anterior, ph.precio_costo_nuevo, "
            f"ph.precio_venta_anterior, ph.precio_venta_nuevo, ph.fecha, ph.motivo "
            f"FROM precio_historial ph "
            f"LEFT JOIN productos p ON p.id=ph.producto_id "
            f"{where_sql} ORDER BY ph.fecha DESC LIMIT {limit}",
            tuple(params),
        )
        cols = [
            "id",
            "producto",
            "local",
            "usuario",
            "costo_ant",
            "costo_nuevo",
            "venta_ant",
            "venta_nuevo",
            "fecha",
            "motivo",
        ]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        logger.exception("Error obteniendo historial global de precios")
        return []
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass
