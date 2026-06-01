"""CRM bÃ¡sico: clientes de la mueblerÃ­a."""
import logging
from typing import Any, Dict, List, Optional

from models.db import get_connection as get_conn
from models.db import is_postgres
from models.db import put_connection as put_conn

logger = logging.getLogger(__name__)


def _ph():
    return "%s" if is_postgres() else "?"


def upsert_cliente_desde_venta(nombre: str, telefono: str) -> Optional[int]:
    """Crea o devuelve el id de un cliente por telÃ©fono."""
    if not nombre or not telefono:
        return None
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"SELECT id FROM clientes WHERE telefono={ph} LIMIT 1", (telefono.strip(),)
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                f"UPDATE clientes SET nombre={ph}, updated_at=NOW() WHERE id={ph}",
                (nombre.strip(), row[0]),
            )
            conn.commit()
            return row[0]
        cur.execute(
            f"INSERT INTO clientes (nombre, telefono) VALUES ({ph},{ph}) RETURNING id",
            (nombre.strip(), telefono.strip()),
        )
        cid = (cur.fetchone() or [None])[0]
        conn.commit()
        return cid
    except Exception:
        logger.exception("Error upserting cliente")
        return None
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def list_clientes(search: str = "") -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        if search:
            like = f"%{search.strip()}%"
            cur.execute(
                f"SELECT id,nombre,telefono,email,notas,created_at FROM clientes "
                f"WHERE nombre ILIKE {ph} OR telefono ILIKE {ph} "
                f"ORDER BY nombre LIMIT 200",
                (like, like),
            )
        else:
            cur.execute(
                "SELECT id,nombre,telefono,email,notas,created_at FROM clientes "
                "ORDER BY nombre LIMIT 200"
            )
        cols = ["id", "nombre", "telefono", "email", "notas", "created_at"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        logger.exception("Error listando clientes")
        return []
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def get_cliente_historial(cliente_id: int) -> List[Dict[str, Any]]:
    """Ventas asociadas al telÃ©fono del cliente."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"SELECT telefono FROM clientes WHERE id={ph} LIMIT 1", (cliente_id,)
        )
        row = cur.fetchone()
        if not row:
            return []
        telefono = row[0]
        cur.execute(
            f"SELECT id, numero_venta, fecha, total, forma_pago, estado, local "
            f"FROM ventas WHERE cliente_telefono={ph} ORDER BY fecha DESC LIMIT 100",
            (telefono,),
        )
        cols = ["id", "numero_venta", "fecha", "total", "forma_pago", "estado", "local"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        logger.exception("Error obteniendo historial de cliente")
        return []
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def save_cliente(nombre: str, telefono: str, email: str = "", notas: str = "") -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"SELECT id FROM clientes WHERE telefono={ph} LIMIT 1", (telefono.strip(),)
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                f"UPDATE clientes SET nombre={ph},email={ph},notas={ph},updated_at=NOW() "
                f"WHERE id={ph}",
                (nombre.strip(), email.strip(), notas.strip(), row[0]),
            )
        else:
            cur.execute(
                f"INSERT INTO clientes (nombre,telefono,email,notas) VALUES ({ph},{ph},{ph},{ph})",
                (nombre.strip(), telefono.strip(), email.strip(), notas.strip()),
            )
        conn.commit()
        return True
    except Exception:
        logger.exception("Error guardando cliente")
        return False
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def get_cliente_stats(cliente_id: int) -> Dict[str, Any]:
    """Total gastado, cantidad de compras, Ãºltima visita."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"SELECT telefono FROM clientes WHERE id={ph} LIMIT 1", (cliente_id,)
        )
        row = cur.fetchone()
        if not row:
            return {}
        telefono = row[0]
        cur.execute(
            f"SELECT COUNT(*), COALESCE(SUM(total),0), MAX(fecha) "
            f"FROM ventas WHERE cliente_telefono={ph} AND estado!='cancelada'",
            (telefono,),
        )
        r = cur.fetchone() or (0, 0, None)
        return {"cantidad": int(r[0] or 0), "total": float(r[1] or 0), "ultima": r[2]}
    except Exception:
        logger.exception("Error obteniendo stats de cliente")
        return {}
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass
