import json
import logging
import sqlite3
import threading
import time
import uuid
from queue import Full, Queue

from models import db
from models.sql_utils import is_safe_identifier

logger = logging.getLogger(__name__)

ALLOWED_FIELDS = {
    "nombre",
    "material",
    "categoria",
    "medida",
    "color",
    "precio_venta",
    "precio_costo",
    "cantidad",
    "fabricante",
    "codigo",
}

_PRODUCT_SCHEMA_OK = False
_PRODUCT_SCHEMA_LOCK = threading.Lock()


def _ensure_material_column():
    """Asegura que la columna material exista en productos (Postgres/SQLite)."""
    global _PRODUCT_SCHEMA_OK
    if _PRODUCT_SCHEMA_OK:
        return
    with _PRODUCT_SCHEMA_LOCK:
        if _PRODUCT_SCHEMA_OK:
            return
        conn = None
        try:
            conn = _get_conn()
            cur = conn.cursor()
            if isinstance(conn, sqlite3.Connection):
                cur.execute("PRAGMA table_info(productos)")
                cols = {r[1] for r in cur.fetchall()}
                if "material" not in cols:
                    cur.execute("ALTER TABLE productos ADD COLUMN material TEXT")
            else:
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name='productos' AND column_name='material'
                    """
                )
                exists = cur.fetchone() is not None
                if not exists:
                    cur.execute(
                        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS material TEXT"
                    )
            try:
                conn.commit()
            except Exception:
                pass
            _PRODUCT_SCHEMA_OK = True
        except Exception as e:
            logger.warning(f"No se pudo asegurar columna material: {e}")
        finally:
            if conn is not None:
                try:
                    db.put_connection(conn)
                except Exception:
                    pass


# Commit async to avoid UI blocks
_commit_queue = Queue(maxsize=500)
_commit_worker_started = False


def _start_commit_worker():
    global _commit_worker_started
    if _commit_worker_started:
        return

    def _worker():
        while True:
            conn = _commit_queue.get()
            if conn is None:
                break
            try:
                conn.commit()
            except Exception as e:
                logger.error(f"Commit error: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
            finally:
                try:
                    db.put_connection(conn)
                except Exception:
                    pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    _commit_worker_started = True


def _enqueue_commit(conn):
    """Queue a commit; the worker returns the connection to the pool."""
    try:
        _commit_queue.put(conn, timeout=0.2)
        return
    except Full:
        # Fallback: commit en el hilo actual para evitar crecer indefinidamente
        try:
            conn.commit()
        except Exception as e:
            logger.error(f"Commit fallback error: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                db.put_connection(conn)
            except Exception:
                pass


# Start worker on import
_start_commit_worker()


def _ph(conn):
    return "?" if isinstance(conn, sqlite3.Connection) else "%s"


def _get_conn():
    return db.get_connection()


def execute_increment(payload):
    """Increment/decrement stock in Postgres without blocking the UI."""
    conn = _get_conn()
    should_return_conn = True
    try:
        pid = payload.get("producto_id")
        delta = int(payload.get("delta") or 0)
        local = payload.get("local") or ""
        usuario = payload.get("usuario") or "sistema"
        detalle = payload.get("detalle") or ""
        motivo = payload.get("motivo") or ""
        if not pid or delta == 0:
            db.put_connection(conn)
            return False, "Payload invalido"

        ph = _ph(conn)
        cur = conn.cursor()
        cur.execute(
            f"""
            UPDATE productos
               SET cantidad = cantidad + {ph},
                   updated_at = CURRENT_TIMESTAMP
             WHERE id = {ph} AND ({ph} = '' OR local = {ph})
         RETURNING cantidad, local
            """,
            (delta, pid, local, local),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return False, "Producto no encontrado"
        new_qty, effective_local = row

        cur.execute(
            f"""
            INSERT INTO historial_stock
            (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},CURRENT_TIMESTAMP,{ph},{ph},0,{ph})
            """,
            (
                pid,
                "ajuste" if delta > 0 else "baja",
                detalle,
                delta,
                usuario,
                effective_local,
                motivo,
                json.dumps({"delta": delta, "new_qty": new_qty}),
                payload.get("grupo_id"),
            ),
        )
        _enqueue_commit(conn)
        should_return_conn = False
        return True, f"Cantidad modificada: {delta} (ahora {new_qty})"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"execute_increment failed: {e}")
        return False, f"Error: {e}"
    finally:
        if should_return_conn:
            try:
                db.put_connection(conn)
            except Exception:
                pass


def execute_add_product(payload):
    """Add or increment a product in Postgres."""
    _ensure_material_column()
    conn = _get_conn()
    should_return_conn = True
    try:
        nombre = (payload.get("nombre") or "").strip()
        material = (payload.get("material") or "").strip().lower()
        categoria = (payload.get("categoria") or "").strip()
        medida = (payload.get("medida") or "") or None
        codigo = (payload.get("codigo") or "").strip() or None
        estado = (payload.get("estado") or "Nuevo").strip()
        color = (payload.get("color") or "") or None
        fabricante = (payload.get("fabricante") or "").strip()
        cantidad = int(payload.get("cantidad") or 0)
        precio_venta = float(payload.get("precio_venta") or 0)
        local = (payload.get("local") or "").strip()
        usuario = payload.get("usuario") or "sistema"
        force_update = bool(payload.get("force_update", False))

        if not nombre or not categoria or not local:
            db.put_connection(conn)
            return False, "Payload invalido para add_product"
        if cantidad < 0:
            db.put_connection(conn)
            return False, "Cantidad no puede ser negativa"

        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(
            f"""
            SELECT id, cantidad FROM productos
             WHERE nombre={ph} AND COALESCE(material,'')=COALESCE({ph},'') AND categoria={ph} AND COALESCE(medida,'')=COALESCE({ph},'')
               AND estado={ph} AND COALESCE(color,'')=COALESCE({ph},'') AND local={ph}
               AND COALESCE(fabricante,'')=COALESCE({ph},'')
               AND COALESCE(codigo,'')=COALESCE({ph},'')
             LIMIT 1
            """,
            (
                nombre,
                material,
                categoria,
                medida,
                estado,
                color,
                local,
                fabricante,
                codigo,
            ),
        )
        row = cur.fetchone()

        if row:
            pid, old_qty = row
            delta = cantidad if force_update else cantidad
            new_qty = int(old_qty) + delta
            cur.execute(
                f"""
                UPDATE productos
                   SET cantidad={ph}, precio_venta={ph}, updated_at=CURRENT_TIMESTAMP
                 WHERE id={ph}
                """,
                (new_qty, precio_venta, pid),
            )
            cur.execute(
                f"""
                INSERT INTO historial_stock
                (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
                VALUES ({ph},'ajuste',{ph},{ph},{ph},{ph},CURRENT_TIMESTAMP,{ph},{ph},0,{ph})
                """,
                (
                    pid,
                    "add_product",
                    delta,
                    usuario,
                    local,
                    payload.get("motivo", ""),
                    json.dumps({"delta": delta, "new_qty": new_qty}),
                    payload.get("grupo_id"),
                ),
            )
            try:
                conn.commit()
            finally:
                try:
                    db.put_connection(conn)
                except Exception:
                    pass
            should_return_conn = False
            return True, f"Producto actualizado (+{delta})"
        else:
            cur.execute(
                f"""
                INSERT INTO productos
                (nombre, material, categoria, medida, estado, color, cantidad, precio_venta, local, created_at, updated_at, fabricante, codigo)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,{ph},{ph})
                RETURNING id
                """,
                (
                    nombre,
                    material,
                    categoria,
                    medida,
                    estado,
                    color,
                    cantidad,
                    precio_venta,
                    local,
                    fabricante,
                    codigo,
                ),
            )
            pid = cur.fetchone()[0]
            cur.execute(
                f"""
                INSERT INTO historial_stock
                (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
                VALUES ({ph},'ingreso',{ph},{ph},{ph},{ph},CURRENT_TIMESTAMP,{ph},{ph},0,{ph})
                """,
                (
                    pid,
                    "add_product",
                    cantidad,
                    usuario,
                    local,
                    payload.get("motivo", ""),
                    json.dumps({"delta": cantidad, "new_qty": cantidad}),
                    payload.get("grupo_id"),
                ),
            )
            try:
                conn.commit()
            finally:
                try:
                    db.put_connection(conn)
                except Exception:
                    pass
            should_return_conn = False
            return True, "Producto agregado"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"execute_add_product failed: {e}")
        return False, f"Error: {e}"
    finally:
        if should_return_conn:
            try:
                db.put_connection(conn)
            except Exception:
                pass


def execute_update_field(payload):
    """Update a field and sync to equivalent products."""
    conn = _get_conn()
    should_return_conn = True
    try:
        pid = payload.get("producto_id")
        field = payload.get("field")
        value = payload.get("value")
        usuario = payload.get("usuario") or "sistema"
        local = payload.get("local") or ""
        motivo = payload.get("motivo") or ""

        if not pid or not field or field not in ALLOWED_FIELDS:
            db.put_connection(conn)
            return False, "ID o campo invalido"
        if not is_safe_identifier(field):
            db.put_connection(conn)
            return False, "Campo invalido"
        if field == "material":
            _ensure_material_column()

        cur = conn.cursor()
        ph = _ph(conn)

        cur.execute(
            f"SELECT nombre,COALESCE(material,''),categoria,COALESCE(medida,''),estado,COALESCE(color,''),local,{field} FROM productos WHERE id={ph}",
            (pid,),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return False, "Producto no encontrado"
        (
            current_nombre,
            current_material,
            current_cat,
            current_med,
            current_estado,
            current_color,
            current_local,
            old_field_value,
        ) = row

        cur.execute(
            f"UPDATE productos SET {field}={ph}, updated_at=CURRENT_TIMESTAMP WHERE id={ph} AND ({ph}='' OR local={ph})",
            (value, pid, local, local),
        )
        if cur.rowcount == 0:
            conn.rollback()
            return False, "Producto no encontrado"

        cur.execute(
            f"""
            INSERT INTO historial_stock
            (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
            VALUES ({ph},'cambio_campo',{ph},NULL,{ph},{ph},CURRENT_TIMESTAMP,{ph},{ph},0,{ph})
            """,
            (
                pid,
                f"update_field:{field}",
                usuario,
                local,
                motivo,
                json.dumps(
                    {"field": field, "old": old_field_value, "new": value}, default=str
                ),
                payload.get("grupo_id"),
            ),
        )

        if field in ("nombre", "material", "categoria", "fabricante", "medida"):
            cur.execute(
                f"""
                UPDATE productos
                   SET {field}={ph}, updated_at=CURRENT_TIMESTAMP
                 WHERE nombre={ph} AND COALESCE(material,'')=COALESCE({ph},'') AND categoria={ph} AND COALESCE(medida,'')=COALESCE({ph},'')
                   AND estado={ph} AND COALESCE(color,'')=COALESCE({ph},'') AND id<> {ph}
                """,
                (
                    value,
                    current_nombre,
                    current_material,
                    current_cat,
                    current_med,
                    current_estado,
                    current_color,
                    pid,
                ),
            )

        if field in ("precio_venta", "precio_costo"):
            cur.execute(
                f"""
                UPDATE productos
                   SET {field}={ph}, updated_at=CURRENT_TIMESTAMP
                 WHERE nombre={ph} AND COALESCE(material,'')=COALESCE({ph},'') AND categoria={ph} AND COALESCE(medida,'')=COALESCE({ph},'')
                   AND estado={ph} AND COALESCE(color,'')=COALESCE({ph},'') AND id<> {ph}
                """,
                (
                    value,
                    current_nombre,
                    current_material,
                    current_cat,
                    current_med,
                    current_estado,
                    current_color,
                    pid,
                ),
            )

        _enqueue_commit(conn)
        should_return_conn = False
        return True, "Campo actualizado"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"execute_update_field failed: {e}")
        return False, f"Error: {e}"
    finally:
        if should_return_conn:
            try:
                db.put_connection(conn)
            except Exception:
                pass


def execute_delete_product(payload):
    """Delete a product and its history."""
    conn = _get_conn()
    should_return_conn = True
    try:
        pid = payload.get("producto_id")
        local = payload.get("local") or ""
        usuario = payload.get("usuario") or "sistema"
        if not pid:
            db.put_connection(conn)
            return False, "ID de producto invalido"

        ph = _ph(conn)
        cur = conn.cursor()

        cur.execute(
            f"DELETE FROM historial_stock WHERE producto_id={ph}",
            (pid,),
        )
        cur.execute(
            f"DELETE FROM productos WHERE id={ph} AND ({ph}='' OR local={ph})",
            (pid, local, local),
        )
        if cur.rowcount == 0:
            conn.rollback()
            return False, "Producto no encontrado en este local"

        _enqueue_commit(conn)
        should_return_conn = False
        logger.info(
            f"Producto {pid} eliminado por {usuario} en local {local or 'cualquiera'}"
        )
        return True, "Producto eliminado"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"execute_delete_product failed: {e}")
        return False, f"Error: {e}"
    finally:
        if should_return_conn:
            try:
                db.put_connection(conn)
            except Exception:
                pass


def execute_transfer(payload):
    """Transfer stock between locals atomically."""
    conn = _get_conn()
    should_return_conn = True
    try:
        pid = payload.get("producto_id")
        cantidad = int(payload.get("cantidad") or 0)
        from_local = payload.get("from_local") or payload.get("local") or ""
        to_local = payload.get("to_local") or ""
        usuario = payload.get("usuario") or "sistema"
        if not pid or not cantidad or not to_local:
            db.put_connection(conn)
            return False, "Payload invalido para transfer"

        cur = conn.cursor()
        ph = _ph(conn)
        cur.execute(
            f"""
            UPDATE productos
               SET cantidad = cantidad - {ph}, updated_at = CURRENT_TIMESTAMP
             WHERE id={ph} AND local={ph} AND cantidad >= {ph}
         RETURNING cantidad
            """,
            (cantidad, pid, from_local, cantidad),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return False, "Stock insuficiente en origen"
        new_qty_src = row[0]

        cur.execute(
            f"""
            SELECT id, cantidad FROM productos
             WHERE nombre={ph} AND categoria={ph} AND COALESCE(medida,'')=COALESCE({ph},'')
               AND estado={ph} AND COALESCE(color,'')=COALESCE({ph},'') AND local={ph}
             LIMIT 1
            """,
            (
                payload.get("nombre"),
                payload.get("categoria"),
                payload.get("medida"),
                payload.get("estado"),
                payload.get("color"),
                to_local,
            ),
        )
        dest_row = cur.fetchone()
        if dest_row:
            dest_pid, dest_qty = dest_row
            new_qty_dst = int(dest_qty) + cantidad
            cur.execute(
                f"UPDATE productos SET cantidad={ph}, updated_at=CURRENT_TIMESTAMP WHERE id={ph}",
                (new_qty_dst, dest_pid),
            )
        else:
            cur.execute(
                f"""
                INSERT INTO productos
                (nombre, categoria, medida, estado, color, cantidad, precio_venta, local, created_at, updated_at)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                RETURNING id
                """,
                (
                    payload.get("nombre"),
                    payload.get("categoria"),
                    payload.get("medida"),
                    payload.get("estado"),
                    payload.get("color"),
                    cantidad,
                    payload.get("precio_venta") or 0,
                    to_local,
                ),
            )
            dest_pid = cur.fetchone()[0]
            new_qty_dst = cantidad

        grupo_id = payload.get("grupo_id") or str(uuid.uuid4())
        meta_out = {
            "from_local": from_local,
            "to_local": to_local,
            "moved": cantidad,
            "old_qty": int(new_qty_src) + cantidad,
            "new_qty": int(new_qty_src),
        }
        meta_in = {
            "from_local": from_local,
            "to_local": to_local,
            "moved": cantidad,
            "old_qty": int(new_qty_dst) - cantidad,
            "new_qty": int(new_qty_dst),
        }
        motivo = payload.get("motivo", "")
        cur.execute(
            f"""
            INSERT INTO historial_stock
            (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
            VALUES
            ({ph},'transferencia',{ph},{ph},{ph},{ph},CURRENT_TIMESTAMP,{ph},{ph},0,{ph}),
            ({ph},'transferencia',{ph},{ph},{ph},{ph},CURRENT_TIMESTAMP,{ph},{ph},0,{ph})
            """,
            (
                pid,
                f"salida a {to_local}",
                -cantidad,
                usuario,
                from_local,
                motivo,
                json.dumps(meta_out),
                grupo_id,
                dest_pid,
                f"entrada desde {from_local}",
                cantidad,
                usuario,
                to_local,
                motivo,
                json.dumps(meta_in),
                grupo_id,
            ),
        )
        _enqueue_commit(conn)
        should_return_conn = False
        return True, "Transferencia completada"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"execute_transfer failed: {e}")
        return False, f"Error: {e}"
    finally:
        if should_return_conn:
            try:
                db.put_connection(conn)
            except Exception:
                pass


def enqueue_op(op_type, payload):
    """Backward compatibility wrapper."""
    if op_type in ("increment", "decrement"):
        if op_type == "decrement":
            delta = int(payload.get("delta") or 0)
            payload["delta"] = -abs(delta)
        return execute_increment(payload)
    if op_type == "add_product":
        return execute_add_product(payload)
    if op_type == "update_field":
        return execute_update_field(payload)
    logger.error(f"Unknown operation: {op_type}")
    return False, f"Unknown operation: {op_type}"


def get_queue_count() -> int:
    """Compatibility: no external queue."""
    return 0


def process_queue_once(limit: int = 10):
    """Compatibility: no external queue."""
    return 0
