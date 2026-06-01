"""GestiÃ³n de proveedores y compras."""
import logging
from typing import Any, Dict, List, Optional

from models.db import get_connection as get_conn
from models.db import is_postgres
from models.db import put_connection as put_conn

logger = logging.getLogger(__name__)


def _ph():
    return "%s" if is_postgres() else "?"


# â”€â”€ Proveedores â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def list_proveedores(solo_activos: bool = True) -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        where = "WHERE activo=TRUE" if solo_activos else ""
        cur.execute(
            f"SELECT id,nombre,telefono,email,direccion,notas,activo,created_at "
            f"FROM proveedores {where} ORDER BY nombre"
        )
        cols = [
            "id",
            "nombre",
            "telefono",
            "email",
            "direccion",
            "notas",
            "activo",
            "created_at",
        ]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        logger.exception("Error listando proveedores")
        return []
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def save_proveedor(
    nombre: str,
    telefono: str = "",
    email: str = "",
    direccion: str = "",
    notas: str = "",
    proveedor_id: Optional[int] = None,
) -> Optional[int]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        if proveedor_id:
            cur.execute(
                f"UPDATE proveedores SET nombre={ph},telefono={ph},email={ph},"
                f"direccion={ph},notas={ph} WHERE id={ph}",
                (
                    nombre.strip(),
                    telefono.strip(),
                    email.strip(),
                    direccion.strip(),
                    notas.strip(),
                    int(proveedor_id),
                ),
            )
            conn.commit()
            return proveedor_id
        if is_postgres():
            cur.execute(
                f"INSERT INTO proveedores (nombre,telefono,email,direccion,notas) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph}) RETURNING id",
                (
                    nombre.strip(),
                    telefono.strip(),
                    email.strip(),
                    direccion.strip(),
                    notas.strip(),
                ),
            )
            pid = (cur.fetchone() or [None])[0]
        else:
            cur.execute(
                f"INSERT INTO proveedores (nombre,telefono,email,direccion,notas) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph})",
                (
                    nombre.strip(),
                    telefono.strip(),
                    email.strip(),
                    direccion.strip(),
                    notas.strip(),
                ),
            )
            pid = cur.lastrowid
        conn.commit()
        return pid
    except Exception:
        logger.exception("Error guardando proveedor")
        return None
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def toggle_proveedor_activo(proveedor_id: int) -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"UPDATE proveedores SET activo=NOT activo WHERE id={ph}", (proveedor_id,)
        )
        conn.commit()
        return True
    except Exception:
        logger.exception("Error toggling proveedor")
        return False
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


# â”€â”€ Compras â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def crear_compra(
    proveedor_id: int,
    local: str,
    usuario: str,
    items: List[Dict],
    notas: str = "",
) -> Optional[int]:
    """items: [{'producto_id':int,'producto_nombre':str,'cantidad':int,'precio_unitario':float}]"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        total = sum(
            int(i.get("cantidad", 0)) * float(i.get("precio_unitario", 0))
            for i in items
        )

        if is_postgres():
            cur.execute(
                f"INSERT INTO compras (proveedor_id,local,usuario,total,notas) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph}) RETURNING id",
                (int(proveedor_id), local, usuario, float(total), notas.strip()),
            )
            compra_id = (cur.fetchone() or [None])[0]
        else:
            cur.execute(
                f"INSERT INTO compras (proveedor_id,local,usuario,total,notas) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph})",
                (int(proveedor_id), local, usuario, float(total), notas.strip()),
            )
            compra_id = cur.lastrowid

        for item in items:
            cant = int(item.get("cantidad", 0))
            precio = float(item.get("precio_unitario", 0))
            cur.execute(
                f"INSERT INTO detalle_compras "
                f"(compra_id,producto_id,producto_nombre,cantidad,precio_unitario,subtotal) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
                (
                    compra_id,
                    item.get("producto_id"),
                    item.get("producto_nombre", ""),
                    cant,
                    precio,
                    cant * precio,
                ),
            )

        conn.commit()
        return compra_id
    except Exception:
        logger.exception("Error creando compra")
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def confirmar_recepcion(compra_id: int, usuario: str) -> bool:
    """Marca la compra como recibida e incrementa stock."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"SELECT dc.producto_id, dc.producto_nombre, dc.cantidad, c.local "
            f"FROM detalle_compras dc JOIN compras c ON c.id=dc.compra_id "
            f"WHERE dc.compra_id={ph}",
            (int(compra_id),),
        )
        items = cur.fetchall()
        cur.execute(
            f"UPDATE compras SET estado='recibida' WHERE id={ph}", (int(compra_id),)
        )
        cur.execute(
            f"UPDATE detalle_compras SET recibido=1 WHERE compra_id={ph}",
            (int(compra_id),),
        )
        conn.commit()
        # Incrementar stock via stock_model para mantener el historial
        try:
            from models import stock_model as sm

            for pid, pnombre, cant, local in items:
                if pid and cant > 0:
                    sm.increment_stock(
                        pid,
                        cant,
                        local,
                        usuario,
                        detalle=f"Compra #{compra_id}: {pnombre}",
                        motivo="compra",
                    )
        except Exception:
            logger.exception("Error incrementando stock desde compra")
        return True
    except Exception:
        logger.exception("Error confirmando recepciÃ³n")
        return False
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def list_compras(local: str = "", limit: int = 100) -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        wheres = []
        params: list = []
        if local and local not in ("Todos", "Todos los locales"):
            wheres.append(f"c.local={ph}")
            params.append(local)
        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        cur.execute(
            f"SELECT c.id,p.nombre,c.local,c.usuario,c.fecha,c.total,c.estado,c.notas "
            f"FROM compras c LEFT JOIN proveedores p ON p.id=c.proveedor_id "
            f"{where_sql} ORDER BY c.fecha DESC LIMIT {limit}",
            tuple(params),
        )
        cols = [
            "id",
            "proveedor",
            "local",
            "usuario",
            "fecha",
            "total",
            "estado",
            "notas",
        ]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        logger.exception("Error listando compras")
        return []
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def get_detalle_compra(compra_id: int) -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"SELECT id,producto_nombre,cantidad,precio_unitario,subtotal,recibido "
            f"FROM detalle_compras WHERE compra_id={ph} ORDER BY id",
            (int(compra_id),),
        )
        cols = [
            "id",
            "producto_nombre",
            "cantidad",
            "precio_unitario",
            "subtotal",
            "recibido",
        ]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        logger.exception("Error obteniendo detalle compra")
        return []
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass
