"""Capa de compatibilidad Firestore re-implementada sobre PostgreSQL/Supabase.

Las vistas legacy (Dashboard global) importan estas funciones. Aquí se
redirigen a la base SQL usando models.db para entregar datos reales.
"""
import logging
from contextlib import contextmanager
from datetime import date, datetime

try:
    from models import db
except Exception:
    db = None

logger = logging.getLogger(__name__)

SERVER_TIMESTAMP = "firestore_removed"


# -------------------------
# Helpers internos
# -------------------------
@contextmanager
def _get_conn():
    conn = None
    try:
        if db is None:
            raise RuntimeError("Backend SQL no disponible")
        conn = db.get_connection()
        yield conn
    finally:
        try:
            if conn and hasattr(db, "put_connection"):
                db.put_connection(conn)
        except Exception:
            pass


def _parse_date(value) -> date | None:
    try:
        if isinstance(value, (datetime, date)):
            return value.date() if isinstance(value, datetime) else value
        return datetime.fromisoformat(str(value).replace("Z", "")).date()
    except Exception:
        return None


def _ph():
    """Placeholder según backend."""
    try:
        if db and hasattr(db, "is_postgres") and db.is_postgres():
            return "%s"
    except Exception:
        pass
    return "?"


def _cast_ts(col: str) -> str:
    """Casting seguro a texto para timestamps (Postgres vs SQLite)."""
    try:
        if db and hasattr(db, "is_postgres") and db.is_postgres():
            return f"COALESCE({col}::text,'')"
    except Exception:
        pass
    return f"COALESCE({col},'')"


# -------------------------
# Usuarios
# -------------------------
def get_user_by_username(username):
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(
                f"SELECT username, role, local FROM usuarios WHERE username={ph} LIMIT 1",
                (username,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"username": row[0], "role": row[1], "local": row[2]}
    except Exception as e:
        logger.error(f"get_user_by_username error: {e}")
        return None


def add_user(data):
    logger.warning("add_user no implementado en capa SQL")
    return None


def update_user(user_id, data):
    logger.warning("update_user no implementado en capa SQL")
    return None


def list_users():
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT username, role, local FROM usuarios ORDER BY username ASC"
            )
            rows = cur.fetchall()
            return [
                {
                    "username": r[0],
                    "nombre": r[0],
                    "rol": r[1],
                    "local": r[2],
                    "last_login": None,
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"list_users error: {e}")
        return []


# -------------------------
# Productos / Stock
# -------------------------
def list_products_by_local(local, *args, **kwargs):
    """Devuelve productos para un local. Si local está vacío o 'Todos', devuelve todos."""
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            ph = _ph()
            params = []
            where = ""
            if local and local not in ("Todos", "Todos los locales"):
                where = f"WHERE local={ph}"
                params.append(local)
            has_material = True
            has_fabricante = True
            sql = f"""
                SELECT id, nombre, COALESCE(material,''), categoria, COALESCE(fabricante,''), COALESCE(medida,''), estado, COALESCE(color,''),
                       COALESCE(cantidad,0), COALESCE(precio_venta,0), local,
                       COALESCE(precio_costo,0), codigo, descripcion, {_cast_ts('updated_at')}, {_cast_ts('created_at')},
                       COALESCE(is_combo,0)
                FROM productos
                {where}
                ORDER BY nombre ASC
            """
            try:
                if params:
                    cur.execute(sql, tuple(params))
                else:
                    cur.execute(sql)
            except Exception:
                has_fabricante = False
                sql = f"""
                    SELECT id, nombre, COALESCE(material,''), categoria, COALESCE(medida,''), estado, COALESCE(color,''),
                           COALESCE(cantidad,0), COALESCE(precio_venta,0), local,
                           COALESCE(precio_costo,0), codigo, descripcion, {_cast_ts('updated_at')}, {_cast_ts('created_at')},
                           COALESCE(is_combo,0)
                    FROM productos
                    {where}
                    ORDER BY nombre ASC
                """
                try:
                    if params:
                        cur.execute(sql, tuple(params))
                    else:
                        cur.execute(sql)
                except Exception:
                    has_material = False
                    sql = f"""
                        SELECT id, nombre, categoria, COALESCE(medida,''), estado, COALESCE(color,''),
                               COALESCE(cantidad,0), COALESCE(precio_venta,0), local,
                               COALESCE(precio_costo,0), codigo, descripcion, {_cast_ts('updated_at')}, {_cast_ts('created_at')},
                               COALESCE(is_combo,0)
                        FROM productos
                        {where}
                        ORDER BY nombre ASC
                    """
                    if params:
                        cur.execute(sql, tuple(params))
                    else:
                        cur.execute(sql)
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "nombre": r[1],
                    "material": r[2] if has_material else None,
                    "categoria": r[3] if has_material else r[2],
                    "fabricante": (
                        r[4]
                        if (has_material and has_fabricante)
                        else (None if not has_material else "")
                    ),
                    "medida": r[5]
                    if (has_material and has_fabricante)
                    else (r[4] if has_material else r[3]),
                    "estado": r[6]
                    if (has_material and has_fabricante)
                    else (r[5] if has_material else r[4]),
                    "color": r[7]
                    if (has_material and has_fabricante)
                    else (r[6] if has_material else r[5]),
                    "cantidad": r[8]
                    if (has_material and has_fabricante)
                    else (r[7] if has_material else r[6]),
                    "precio_venta": r[9]
                    if (has_material and has_fabricante)
                    else (r[8] if has_material else r[7]),
                    "local": r[10]
                    if (has_material and has_fabricante)
                    else (r[9] if has_material else r[8]),
                    "precio_costo": r[11]
                    if (has_material and has_fabricante)
                    else (r[10] if has_material else r[9]),
                    "codigo": r[12]
                    if (has_material and has_fabricante)
                    else (r[11] if has_material else r[10]),
                    "descripcion": r[13]
                    if (has_material and has_fabricante)
                    else (r[12] if has_material else r[11]),
                    "updated_at": r[14]
                    if (has_material and has_fabricante)
                    else (r[13] if has_material else r[12]),
                    "created_at": r[15]
                    if (has_material and has_fabricante)
                    else (r[14] if has_material else r[13]),
                    "is_combo": int(
                        r[16]
                        if (has_material and has_fabricante)
                        else (r[15] if has_material else r[14]) or 0
                    ),
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"list_products_by_local error: {e}")
        return []


def get_all_locals():
    """Devuelve la lista de locales distintos en productos."""
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT local FROM productos ORDER BY local ASC")
            return [r[0] for r in cur.fetchall() if r and r[0]]
    except Exception as e:
        logger.error(f"get_all_locals error: {e}")
        return []


def get_stock_status(*args, **kwargs):
    """Resumen rápido de stock: bajo y agotado."""
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM productos WHERE COALESCE(cantidad,0) <= 0"
            )
            agotado = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM productos WHERE COALESCE(cantidad,0) > 0 AND COALESCE(cantidad,0) <= 5"
            )
            bajo = cur.fetchone()[0]
        return {"stock_agotado": agotado or 0, "stock_bajo": bajo or 0}
    except Exception as e:
        logger.error(f"get_stock_status error: {e}")
        return {"stock_agotado": 0, "stock_bajo": 0}


def add_product(*args, **kwargs):
    logger.warning("add_product no implementado en capa SQL")
    return None


def update_product(*args, **kwargs):
    logger.warning("update_product no implementado en capa SQL")
    return None


def get_product(product_id):
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            ph = _ph()
            try:
                cur.execute(
                    f"""
                    SELECT id, nombre, material, categoria, medida, estado, color, cantidad, precio_venta, local
                    FROM productos WHERE id={ph}
                    """,
                    (product_id,),
                )
                has_material = True
            except Exception:
                cur.execute(
                    f"""
                    SELECT id, nombre, categoria, medida, estado, color, cantidad, precio_venta, local
                    FROM productos WHERE id={ph}
                    """,
                    (product_id,),
                )
                has_material = False
            r = cur.fetchone()
            if not r:
                return None
            return {
                "id": r[0],
                "nombre": r[1],
                "material": r[2] if has_material else None,
                "categoria": r[3] if has_material else r[2],
                "medida": r[4] if has_material else r[3],
                "estado": r[5] if has_material else r[4],
                "color": r[6] if has_material else r[5],
                "cantidad": r[7] if has_material else r[6],
                "precio_venta": r[8] if has_material else r[7],
                "local": r[9] if has_material else r[8],
            }
    except Exception as e:
        logger.error(f"get_product error: {e}")
        return None


def add_historial(*args, **kwargs):
    logger.warning("add_historial no implementado en capa SQL")
    return None


def list_historial_by_local(local, *args, **kwargs):
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(
                f"""
                SELECT id, producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo
                FROM historial_stock
                WHERE local={ph}
                ORDER BY created_at DESC, id DESC
                LIMIT 200
                """,
                (local,),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "producto_id": r[1],
                    "accion": r[2],
                    "detalle": r[3],
                    "cantidad": r[4],
                    "usuario": r[5],
                    "local": r[6],
                    "created_at": r[7],
                    "motivo": r[8],
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"list_historial_by_local error: {e}")
        return []


def list_historial_all(*args, **kwargs):
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo
                FROM historial_stock
                ORDER BY created_at DESC, id DESC
                LIMIT 500
                """
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "producto_id": r[1],
                    "accion": r[2],
                    "detalle": r[3],
                    "cantidad": r[4],
                    "usuario": r[5],
                    "local": r[6],
                    "created_at": r[7],
                    "motivo": r[8],
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"list_historial_all error: {e}")
        return []


# -------------------------
# Ventas
# -------------------------
def add_venta(*args, **kwargs):
    logger.warning("add_venta no implementado en capa SQL")
    return None


def list_ventas(limit: int = 50, start_date=None, end_date=None, *args, **kwargs):
    """Devuelve ventas (boletas) recientes, opcionalmente filtradas por rango de fechas."""
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            ph = _ph()
            where = []
            params = []
            if start_date:
                where.append(f"fecha >= {ph}")
                params.append(str(start_date))
            if end_date:
                where.append(f"fecha <= {ph}")
                params.append(str(end_date))
            where_sql = ("WHERE " + " AND ".join(where)) if where else ""
            has_estado = False
            sql = f"""
                SELECT id, numero_venta, fecha, cliente_nombre, cliente_telefono, cliente_calle, cliente_numero,
                       cliente_localidad, total, vendedor, local, forma_pago, tipo_pago, monto_pagado, monto_pendiente, estado
                FROM ventas
                {where_sql}
                ORDER BY id DESC
                LIMIT {ph}
            """
            params.append(limit)
            try:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
                has_estado = True
            except Exception:
                sql = f"""
                    SELECT id, numero_venta, fecha, cliente_nombre, cliente_telefono, cliente_calle, cliente_numero,
                           cliente_localidad, total, vendedor, local, forma_pago, tipo_pago, monto_pagado, monto_pendiente
                    FROM ventas
                    {where_sql}
                    ORDER BY id DESC
                    LIMIT {ph}
                """
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
            ventas = []
            for r in rows:
                cliente = {
                    "nombre": r[3],
                    "telefono": r[4],
                    "calle": r[5],
                    "numero": r[6],
                    "localidad": r[7],
                }
                pago = {
                    "tipo_abono": r[12] or r[11],
                    "monto_pagado": r[13],
                    "monto_pendiente": r[14],
                }
                ventas.append(
                    {
                        "id": r[0],
                        "numero_venta": r[1],
                        "fecha": r[2],
                        "cliente": cliente,
                        "total": r[8],
                        "vendedor": r[9],
                        "local": r[10],
                        "pago": pago,
                        "estado": r[15] if has_estado and len(r) > 15 else None,
                    }
                )
            return ventas
    except Exception as e:
        logger.error(f"list_ventas error: {e}")
        return []


def get_stock_status_by_local(local: str) -> dict:
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE COALESCE(cantidad,0)<=0),
                    COUNT(*) FILTER (WHERE COALESCE(cantidad,0)>0 AND COALESCE(cantidad,0)<=5)
                FROM productos
                WHERE local={ph}
                """,
                (local,),
            )
            agotado, bajo = cur.fetchone()
            return {"stock_agotado": agotado or 0, "stock_bajo": bajo or 0}
    except Exception:
        return {"stock_agotado": 0, "stock_bajo": 0}


def get_sales_stats(start_date=None, end_date=None):
    """Estadísticas simples: total de ventas y unidades vendidas."""
    try:
        start_d = _parse_date(start_date) or date.min
        end_d = _parse_date(end_date) or date.max
        venta_ids = []
        total_ventas = 0.0

        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, total, fecha FROM ventas")
            for vid, total, fecha in cur.fetchall():
                d = _parse_date(fecha)
                if d and start_d <= d <= end_d:
                    venta_ids.append(vid)
                    total_ventas += float(total or 0)

            total_productos = 0
            if venta_ids:
                ph = ",".join(["%s"] * len(venta_ids))
                cur.execute(
                    f"SELECT COALESCE(SUM(cantidad),0) FROM detalle_ventas WHERE venta_id IN ({ph})",
                    tuple(venta_ids),
                )
                total_productos = int(cur.fetchone()[0] or 0)

        return {"total_ventas": total_ventas, "total_productos": total_productos}
    except Exception as e:
        logger.error(f"get_sales_stats error: {e}")
        return {"total_ventas": 0, "total_productos": 0}


def list_top_products(limit: int = 5):
    """Productos más vendidos (por cantidad) usando detalle_ventas."""
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(
                f"""
                SELECT producto_nombre, SUM(cantidad) AS qty
                FROM detalle_ventas
                GROUP BY producto_nombre
                ORDER BY qty DESC
                LIMIT {ph}
                """,
                (limit,),
            )
            rows = cur.fetchall()
            return [{"producto": r[0], "cantidad": int(r[1] or 0)} for r in rows]
    except Exception as e:
        logger.error(f"list_top_products error: {e}")
        return []


# -------------------------
# Queue placeholders (no-op)
# -------------------------
def firestore_get_queue_count():
    return 0


def firestore_get_queue_items(*args, **kwargs):
    return []


def firestore_mark_queue_item_done(*args, **kwargs):
    return None


def firestore_mark_queue_item_failed(*args, **kwargs):
    return None


def firestore_mark_queue_item_retry(*args, **kwargs):
    return None


def firestore_process_queue_once(*args, **kwargs):
    return None


def firestore_execute_increment(*args, **kwargs):
    return None


def firestore_execute_add_product(*args, **kwargs):
    return None


# -------------------------
# Watchers (no-op)
# -------------------------
def watch_products(*args, **kwargs):
    return None


def watch_historial(*args, **kwargs):
    return None
