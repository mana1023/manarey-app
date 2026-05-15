import json
import logging
import sqlite3
import threading
import time
import uuid
from datetime import datetime
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

# Caché de columnas con TTL para evitar consultar information_schema en cada operación
_PRODUCT_COLUMNS_CACHE: set = set()
_PRODUCT_COLUMNS_CACHE_TIME: float = 0.0
_PRODUCT_COLUMNS_CACHE_TTL: float = 300.0  # 5 minutos


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


def _now_local() -> str:
    try:
        return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_product_columns(conn, cur) -> set:
    global _PRODUCT_COLUMNS_CACHE, _PRODUCT_COLUMNS_CACHE_TIME
    now = time.time()
    if (
        _PRODUCT_COLUMNS_CACHE
        and (now - _PRODUCT_COLUMNS_CACHE_TIME) < _PRODUCT_COLUMNS_CACHE_TTL
    ):
        return _PRODUCT_COLUMNS_CACHE
    try:
        if isinstance(conn, sqlite3.Connection):
            cur.execute("PRAGMA table_info(productos)")
            result = {r[1] for r in cur.fetchall()}
        else:
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='productos'"
            )
            result = {r[0] for r in cur.fetchall()}
        _PRODUCT_COLUMNS_CACHE = result
        _PRODUCT_COLUMNS_CACHE_TIME = now
        return result
    except Exception:
        return _PRODUCT_COLUMNS_CACHE or set()


def _get_all_locals(conn, cur) -> list:
    try:
        cur.execute("SELECT DISTINCT local FROM productos ORDER BY local ASC")
        return [r[0] for r in cur.fetchall() if r and r[0]]
    except Exception:
        return []


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


def _replicate_product_to_all_locals(payload: dict) -> int:
    """Replica un producto nuevo a todos los locales con cantidad 0."""
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        ph = _ph(conn)

        nombre = (payload.get("nombre") or "").strip()
        material = (payload.get("material") or "").strip().lower()
        categoria = (payload.get("categoria") or "").strip()
        medida = (payload.get("medida") or "") or None
        estado = (payload.get("estado") or "Nuevo").strip()
        color = (payload.get("color") or "") or None
        fabricante = (payload.get("fabricante") or "").strip()
        codigo = (payload.get("codigo") or "").strip() or None
        precio_venta = float(payload.get("precio_venta") or 0)
        precio_costo = float(payload.get("precio_costo") or 0)
        if not nombre or not categoria:
            return 0

        cols_set = _get_product_columns(conn, cur)
        all_locals = [str(l).strip() for l in _get_all_locals(conn, cur) if l]
        if not all_locals:
            return 0
        all_locals = [
            l for l in all_locals if l and l not in ("Todos", "Todos los locales")
        ]
        if not all_locals:
            return 0

        # buscar locales existentes para este producto
        where = [
            f"nombre={ph}",
            f"categoria={ph}",
            f"COALESCE(medida,'')=COALESCE({ph},'')",
            f"estado={ph}",
            f"COALESCE(color,'')=COALESCE({ph},'')",
        ]
        params = [nombre, categoria, medida, estado, color]
        if "material" in cols_set:
            where.append(f"COALESCE(material,'')=COALESCE({ph},'')")
            params.append(material)
        if "fabricante" in cols_set:
            where.append(f"COALESCE(fabricante,'')=COALESCE({ph},'')")
            params.append(fabricante)
        if "codigo" in cols_set:
            where.append(f"COALESCE(codigo,'')=COALESCE({ph},'')")
            params.append(codigo)
        cur.execute(
            f"SELECT local FROM productos WHERE {' AND '.join(where)}", tuple(params)
        )
        existing_locals = {str(r[0]).strip() for r in cur.fetchall() if r and r[0]}

        missing = [l for l in all_locals if l not in existing_locals]
        if not missing:
            return 0

        insert_cols = ["nombre"]
        if "material" in cols_set:
            insert_cols.append("material")
        insert_cols += ["categoria", "medida", "estado", "color"]
        if "fabricante" in cols_set:
            insert_cols.append("fabricante")
        if "codigo" in cols_set:
            insert_cols.append("codigo")
        insert_cols.append("cantidad")
        if "precio_costo" in cols_set:
            insert_cols.append("precio_costo")
        insert_cols.append("precio_venta")
        insert_cols.append("local")
        if "created_at" in cols_set:
            insert_cols.append("created_at")
        if "updated_at" in cols_set:
            insert_cols.append("updated_at")
        if "is_combo" in cols_set:
            insert_cols.append("is_combo")

        placeholders = ",".join([ph] * len(insert_cols))
        insert_sql = (
            f"INSERT INTO productos ({', '.join(insert_cols)}) VALUES ({placeholders})"
        )
        now = _now_local()

        inserted = 0
        for target_local in missing:
            vals = []
            for col in insert_cols:
                if col == "nombre":
                    vals.append(nombre)
                elif col == "material":
                    vals.append(material)
                elif col == "categoria":
                    vals.append(categoria)
                elif col == "medida":
                    vals.append(medida)
                elif col == "estado":
                    vals.append(estado)
                elif col == "color":
                    vals.append(color)
                elif col == "fabricante":
                    vals.append(fabricante)
                elif col == "codigo":
                    vals.append(codigo)
                elif col == "cantidad":
                    vals.append(0)
                elif col == "precio_costo":
                    vals.append(precio_costo)
                elif col == "precio_venta":
                    vals.append(precio_venta)
                elif col == "local":
                    vals.append(target_local)
                elif col == "created_at":
                    vals.append(now)
                elif col == "updated_at":
                    vals.append(now)
                elif col == "is_combo":
                    vals.append(0)
            cur.execute(insert_sql, tuple(vals))
            inserted += 1

        try:
            conn.commit()
        except Exception:
            pass
        return inserted
    except Exception as e:
        try:
            if conn is not None:
                conn.rollback()
        except Exception:
            pass
        logger.warning(f"_replicate_product_to_all_locals error: {e}")
        return 0
    finally:
        if conn is not None:
            try:
                db.put_connection(conn)
            except Exception:
                pass


def _merge_duplicates_for_product(conn, pid):
    """Detecta y combina filas de producto idénticas en el mismo local.

    Si tras una actualización un producto queda con los mismos valores que
    otra fila (mismo nombre, material, categoria, medida, estado, color,
    fabricante, codigo y local) entonces eliminamos la/el
    duplicado(s) sumando su cantidad en la fila "maestra".
    """
    try:
        cur = conn.cursor()
        ph = _ph(conn)

        # obtener valores actuales del producto
        cur.execute(
            f"SELECT nombre, COALESCE(material,''), categoria, COALESCE(medida,''), "
            f"estado, COALESCE(color,''), COALESCE(fabricante,''), COALESCE(codigo,''), "
            f"precio_venta, local, cantidad FROM productos WHERE id={ph}",
            (pid,),
        )
        row = cur.fetchone()
        if not row:
            return
        (
            nombre,
            material,
            categoria,
            medida,
            estado,
            color,
            fabricante,
            codigo,
            precio_venta,
            local,
            cantidad,
        ) = row
        # buscar duplicados en el mismo local
        cur.execute(
            f"""
            SELECT id, cantidad
              FROM productos
             WHERE nombre={ph} AND COALESCE(material,'')={ph}
               AND categoria={ph} AND COALESCE(medida,'')={ph}
               AND estado={ph} AND COALESCE(color,'')={ph}
               AND COALESCE(fabricante,'')={ph}
               AND COALESCE(codigo,'')={ph}
               AND local={ph}
               AND id<> {ph}
            """,
            (
                nombre,
                material,
                categoria,
                medida,
                estado,
                color,
                fabricante,
                codigo,
                local,
                pid,
            ),
        )
        duplicates = cur.fetchall()
        if not duplicates:
            return
        total_extra = sum(int(r[1] or 0) for r in duplicates)
        dup_ids = [r[0] for r in duplicates]
        # mover historial y borrar filas duplicadas
        for dup in dup_ids:
            cur.execute(
                f"UPDATE historial_stock SET producto_id={ph} WHERE producto_id={ph}",
                (pid, dup),
            )
        placeholders = ",".join([ph] * len(dup_ids))
        cur.execute(
            f"DELETE FROM productos WHERE id IN ({placeholders})",
            tuple(dup_ids),
        )
        if total_extra:
            cur.execute(
                f"UPDATE productos SET cantidad = cantidad + {ph} WHERE id={ph}",
                (total_extra, pid),
            )
    except Exception:
        # no queremos que una fusión fallida bloquee la operación principal
        logger.exception("Error merging duplicate products")


def _norm_merge_txt(val) -> str:
    try:
        s = ("" if val is None else str(val)).strip().lower()
    except Exception:
        return ""
    return "" if s == "-" else s


def _try_merge_codigo_conflict(payload):
    """Fallback: resolver conflicto de codigo unico fusionando si el producto es el mismo."""
    conn = None
    try:
        pid = int(payload.get("producto_id") or 0)
    except Exception:
        pid = 0
    if pid <= 0:
        return False, ""

    try:
        conn = _get_conn()
        cur = conn.cursor()
        ph = _ph(conn)
        new_codigo = _norm_merge_txt(payload.get("value"))
        if not new_codigo:
            return False, ""

        cur.execute(
            f"""
            SELECT COALESCE(nombre,''), COALESCE(material,''), COALESCE(categoria,''), COALESCE(medida,''),
                   COALESCE(estado,''), COALESCE(color,''), COALESCE(fabricante,''), COALESCE(local,''), COALESCE(cantidad,0)
              FROM productos
             WHERE id={ph}
            """,
            (pid,),
        )
        src = cur.fetchone()
        if not src:
            return False, ""

        (
            src_nombre,
            src_material,
            src_cat,
            src_med,
            src_estado,
            src_color,
            src_fab,
            src_local,
            src_qty,
        ) = src
        cur.execute(
            f"""
            SELECT id, COALESCE(nombre,''), COALESCE(material,''), COALESCE(categoria,''), COALESCE(medida,''),
                   COALESCE(estado,''), COALESCE(color,''), COALESCE(fabricante,''), COALESCE(cantidad,0)
              FROM productos
             WHERE LOWER(TRIM(COALESCE(local,'')))=LOWER(TRIM({ph}))
               AND LOWER(TRIM(COALESCE(codigo,'')))=LOWER(TRIM({ph}))
               AND id<> {ph}
             ORDER BY id
             LIMIT 1
            """,
            (src_local, new_codigo, pid),
        )
        dst = cur.fetchone()
        if not dst:
            return False, ""

        dst_id = int(dst[0] or 0)
        same_identity = (
            _norm_merge_txt(dst[1]) == _norm_merge_txt(src_nombre)
            and _norm_merge_txt(dst[2]) == _norm_merge_txt(src_material)
            and _norm_merge_txt(dst[3]) == _norm_merge_txt(src_cat)
            and _norm_merge_txt(dst[4]) == _norm_merge_txt(src_med)
            and _norm_merge_txt(dst[5]) == _norm_merge_txt(src_estado)
            and _norm_merge_txt(dst[6]) == _norm_merge_txt(src_color)
            and _norm_merge_txt(dst[7]) == _norm_merge_txt(src_fab)
        )
        if not same_identity:
            parts = [
                p for p in [dst[1], dst[3], dst[4], dst[6]] if str(p or "").strip()
            ]
            desc = " - ".join(parts) if parts else f"ID {dst_id}"
            return (
                False,
                f"El codigo '{new_codigo}' ya existe en {src_local or 'este local'} para {desc}",
            )

        cur.execute(
            f"UPDATE historial_stock SET producto_id={ph} WHERE producto_id={ph}",
            (dst_id, pid),
        )
        cur.execute(
            f"DELETE FROM productos WHERE id={ph}",
            (pid,),
        )
        cur.execute(
            f"UPDATE productos SET cantidad = cantidad + {ph}, updated_at=CURRENT_TIMESTAMP WHERE id={ph}",
            (int(src_qty or 0), dst_id),
        )
        conn.commit()
        return True, "Campo actualizado"
    except Exception:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        logger.exception("No se pudo resolver conflicto de codigo fusionando")
        return False, ""
    finally:
        if conn is not None:
            try:
                db.put_connection(conn)
            except Exception:
                pass


def execute_increment(payload):
    """Increment/decrement stock in Postgres without blocking the UI."""
    conn = _get_conn()
    should_return_conn = True
    try:
        pid = payload.get("producto_id")
        delta = int(payload.get("delta") or 0)
        local = payload.get("local") or ""
        if isinstance(local, str) and local.strip().lower() in (
            "sin local",
            "sin_local",
        ):
            local = ""
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
            pid = row[0]
            try:
                db.put_connection(conn)
            except Exception:
                pass
            should_return_conn = False
            return False, f"Ese producto ya existe. ID={pid}"
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
            try:
                _replicate_product_to_all_locals(payload)
            except Exception:
                pass
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
        # some callers accidentally pass the pseudo-local label
        # used for the consolidated view; treat it as empty so the
        # query doesn't fail to match the intended row.
        if isinstance(local, str) and local.strip() in ("Todos", "Todos los locales"):
            local = ""
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
            f"SELECT nombre,COALESCE(material,''),categoria,COALESCE(medida,''),estado,COALESCE(color,''),"
            f"COALESCE(fabricante,''),COALESCE(codigo,''),precio_venta,local,COALESCE(cantidad,0),{field} "
            f"FROM productos WHERE id={ph}",
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
            current_fabricante,
            current_codigo,
            current_precio,
            current_local,
            current_qty,
            old_field_value,
        ) = row

        # Si se está cambiando el código y ya existe un producto idéntico con ese código,
        # fusionar cantidades e historial en lugar de bloquear.
        if field == "codigo":

            def _norm_txt(val) -> str:
                try:
                    s = ("" if val is None else str(val)).strip().lower()
                except Exception:
                    return ""
                return "" if s == "-" else s

            new_codigo = _norm_txt(value)
            n_nombre = _norm_txt(current_nombre)
            n_material = _norm_txt(current_material)
            n_cat = _norm_txt(current_cat)
            n_med = _norm_txt(current_med)
            n_estado = _norm_txt(current_estado)
            n_color = _norm_txt(current_color)
            n_fab = _norm_txt(current_fabricante)
            # Buscar duplicado idéntico en el mismo local
            target_local = current_local or ""
            if isinstance(target_local, str) and target_local.strip():
                cur.execute(
                    f"""
                    SELECT id, cantidad
                      FROM productos
                     WHERE LOWER(TRIM(COALESCE(nombre,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(material,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(categoria,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(medida,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(estado,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(color,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(fabricante,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(codigo,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(local,'')))=LOWER(TRIM({ph}))
                       AND id<> {ph}
                    """,
                    (
                        n_nombre,
                        n_material,
                        n_cat,
                        n_med,
                        n_estado,
                        n_color,
                        n_fab,
                        new_codigo,
                        target_local,
                        pid,
                    ),
                )
            else:
                cur.execute(
                    f"""
                    SELECT id, cantidad
                      FROM productos
                     WHERE LOWER(TRIM(COALESCE(nombre,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(material,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(categoria,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(medida,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(estado,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(color,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(fabricante,'')))=LOWER(TRIM({ph}))
                       AND LOWER(TRIM(COALESCE(codigo,'')))=LOWER(TRIM({ph}))
                       AND (local IS NULL OR TRIM(COALESCE(local,''))='')
                       AND id<> {ph}
                    """,
                    (
                        n_nombre,
                        n_material,
                        n_cat,
                        n_med,
                        n_estado,
                        n_color,
                        n_fab,
                        new_codigo,
                        pid,
                    ),
                )
            dup = cur.fetchone()
            if dup:
                dup_id, dup_qty = dup[0], int(dup[1] or 0)
                # mover historial y borrar fila duplicada
                cur.execute(
                    f"UPDATE historial_stock SET producto_id={ph} WHERE producto_id={ph}",
                    (dup_id, pid),
                )
                cur.execute(
                    f"DELETE FROM productos WHERE id={ph}",
                    (pid,),
                )
                cur.execute(
                    f"UPDATE productos SET cantidad = cantidad + {ph}, updated_at=CURRENT_TIMESTAMP WHERE id={ph}",
                    (int(current_qty or 0), dup_id),
                )
                _enqueue_commit(conn)
                should_return_conn = False
                return True, "Campo actualizado"

            # Si el codigo ya lo usa otro producto distinto en el mismo local, abortar con
            # un mensaje claro antes de que lo rechace el indice unico de Postgres.
            if new_codigo:
                if isinstance(target_local, str) and target_local.strip():
                    cur.execute(
                        f"""
                        SELECT id, COALESCE(nombre,''), COALESCE(material,''), COALESCE(categoria,''), COALESCE(medida,''), COALESCE(estado,''), COALESCE(color,''), COALESCE(fabricante,'')
                          FROM productos
                         WHERE LOWER(TRIM(COALESCE(local,'')))=LOWER(TRIM({ph}))
                           AND LOWER(TRIM(COALESCE(codigo,'')))=LOWER(TRIM({ph}))
                           AND id <> {ph}
                         ORDER BY id
                         LIMIT 1
                        """,
                        (target_local, new_codigo, pid),
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT id, COALESCE(nombre,''), COALESCE(material,''), COALESCE(categoria,''), COALESCE(medida,''), COALESCE(estado,''), COALESCE(color,''), COALESCE(fabricante,'')
                          FROM productos
                         WHERE (local IS NULL OR TRIM(COALESCE(local,''))='')
                           AND LOWER(TRIM(COALESCE(codigo,'')))=LOWER(TRIM({ph}))
                           AND id <> {ph}
                         ORDER BY id
                         LIMIT 1
                        """,
                        (new_codigo, pid),
                    )
                conflict = cur.fetchone()
                if conflict:
                    conflict_id = int(conflict[0] or 0)
                    same_identity = (
                        _norm_txt(conflict[1]) == n_nombre
                        and _norm_txt(conflict[2]) == n_material
                        and _norm_txt(conflict[3]) == n_cat
                        and _norm_txt(conflict[4]) == n_med
                        and _norm_txt(conflict[5]) == n_estado
                        and _norm_txt(conflict[6]) == n_color
                        and _norm_txt(conflict[7]) == n_fab
                    )
                    if same_identity:
                        cur.execute(
                            f"UPDATE historial_stock SET producto_id={ph} WHERE producto_id={ph}",
                            (conflict_id, pid),
                        )
                        cur.execute(
                            f"DELETE FROM productos WHERE id={ph}",
                            (pid,),
                        )
                        cur.execute(
                            f"UPDATE productos SET cantidad = cantidad + {ph}, updated_at=CURRENT_TIMESTAMP WHERE id={ph}",
                            (int(current_qty or 0), conflict_id),
                        )
                        _enqueue_commit(conn)
                        should_return_conn = False
                        return True, "Campo actualizado"
                    conflict_nombre = (conflict[1] or "").strip()
                    conflict_categoria = (conflict[3] or "").strip()
                    conflict_medida = (conflict[4] or "").strip()
                    conflict_color = (conflict[6] or "").strip()
                    parts = [
                        p
                        for p in [
                            conflict_nombre,
                            conflict_categoria,
                            conflict_medida,
                            conflict_color,
                        ]
                        if p
                    ]
                    conflict_desc = " - ".join(parts) if parts else f"ID {conflict_id}"
                    conn.rollback()
                    return False, (
                        f"El codigo '{new_codigo}' ya existe en {target_local or 'este local'} "
                        f"para {conflict_desc}"
                    )

        if not local:
            cur.execute(
                f"""
                UPDATE productos
                   SET {field}={ph}, updated_at=CURRENT_TIMESTAMP
                 WHERE id={ph}
                   AND (local IS NULL OR TRIM(COALESCE(local,''))='')
                """,
                (value, pid),
            )
        else:
            cur.execute(
                f"""
                UPDATE productos
                   SET {field}={ph}, updated_at=CURRENT_TIMESTAMP
                 WHERE id={ph}
                   AND LOWER(TRIM(local))=LOWER(TRIM({ph}))
                """,
                (value, pid, local),
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

        # replicate updates to other records that share all identifying fields (except the one being changed)
        if field in ("nombre", "material", "categoria", "fabricante", "medida"):
            cur.execute(
                f"""
                UPDATE productos
                   SET {field}={ph}, updated_at=CURRENT_TIMESTAMP
                 WHERE nombre={ph} AND COALESCE(material,'')=COALESCE({ph},'') AND categoria={ph} AND COALESCE(medida,'')=COALESCE({ph},'')
                   AND estado={ph} AND COALESCE(color,'')=COALESCE({ph},'')
                   AND COALESCE(codigo,'')=COALESCE({ph},'') AND id<> {ph}
                """,
                (
                    value,
                    current_nombre,
                    current_material,
                    current_cat,
                    current_med,
                    current_estado,
                    current_color,
                    current_codigo,
                    pid,
                ),
            )

        if field in ("precio_venta", "precio_costo"):
            cur.execute(
                f"""
                UPDATE productos
                   SET {field}={ph}, updated_at=CURRENT_TIMESTAMP
                 WHERE nombre={ph} AND COALESCE(material,'')=COALESCE({ph},'') AND categoria={ph} AND COALESCE(medida,'')=COALESCE({ph},'')
                   AND estado={ph} AND COALESCE(color,'')=COALESCE({ph},'')
                   AND COALESCE(codigo,'')=COALESCE({ph},'') AND id<> {ph}
                """,
                (
                    value,
                    current_nombre,
                    current_material,
                    current_cat,
                    current_med,
                    current_estado,
                    current_color,
                    current_codigo,
                    pid,
                ),
            )

        # after replicating we may have created exact duplicates within the same local (or even the one we edited)
        # if the updated field is part of the identity attributes we merge any fully identical rows.
        if field in (
            "nombre",
            "material",
            "categoria",
            "fabricante",
            "medida",
            "estado",
            "color",
            "codigo",
        ):
            _merge_duplicates_for_product(conn, pid)

        _enqueue_commit(conn)
        should_return_conn = False
        return True, "Campo actualizado"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        if payload.get("field") == "codigo":
            err_txt = str(e or "")
            if (
                "productos_local_codigo_key" in err_txt
                or "duplicate key value" in err_txt.lower()
            ):
                ok_merge, msg_merge = _try_merge_codigo_conflict(payload)
                if ok_merge:
                    return True, msg_merge
                if msg_merge:
                    return False, msg_merge
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
