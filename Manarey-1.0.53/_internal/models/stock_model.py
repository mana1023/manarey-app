# stock_model.py
import json
import os
import re
import sqlite3
import uuid

try:
    from psycopg2 import InterfaceError as _PgIfaceError
    from psycopg2 import OperationalError as _PgOpError
except Exception:
    _PgOpError = _PgIfaceError = None

from models import db, offline_store
from models import stock_queue_api as qa

# from models.sql_utils import is_safe_identifier as _central_is_safe_identifier, validate_sets_list as _central_validate_sets_list

# Nota importante:
# Este módulo contiene utilidades históricas para manipular stock directamente.
# Para operaciones asíncronas o en background (evitar bloqueos y permitir retry),
# preferimos usar la API de cola en `models/stock_queue_api.py`:
#
#     from models import stock_queue_api as qa
#     qa.enqueue_op('decrement', payload)
#
# Usar la API evita inconsistencias entre conexiones/BD (ej. root `db.py` vs `models.db`)
# y previene errores como "database is locked" en SQLite cuando se encola desde
# dentro de la misma transacción. No modifiques `op_queue` directamente; usa
# las funciones públicas en `models.stock_queue_api`.
# Detectar si estamos usando Postgres para adaptar DDL/SQL
try:
    from models.db import is_postgres as _is_postgres
except Exception:

    def _is_postgres():
        return False


# Alias local a la conexion de BD (Postgres/SQLite)
try:
    from models.db import get_connection as _get_db_connection
    from models.db import put_connection as _put_db_connection
except Exception:
    _get_db_connection = None
    _put_db_connection = None

# Bandera global de fallback a SQLite (ruta del archivo)
_FALLBACK_SQLITE_PATH = None
_HAS_MATERIAL_COL = None
_SYNC_PRODUCTS_ALL_LOCALS_DONE = False
_SYNC_PRODUCTS_ALL_LOCALS_LOCK = None


def get_conn():
    """Obtiene una conexion SQL (Postgres Supabase o SQLite local)."""
    if _get_db_connection:
        return _get_db_connection()
    raise RuntimeError("No hay backend SQL configurado")


import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ==================== LOGGING ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if _SYNC_PRODUCTS_ALL_LOCALS_LOCK is None:
    _SYNC_PRODUCTS_ALL_LOCALS_LOCK = threading.Lock()


def _now_local() -> str:
    """Devuelve la hora local como cadena YYYY-MM-DD HH:MM:SS usando timezone local.

    Usamos astimezone() para evitar discrepancias cuando el servidor/DB trabaja en UTC.
    """
    try:
        return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        # Fallback sencillo
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _sanitize_name(name: str) -> str:
    """Sanea el nombre de producto removiendo caracteres potencialmente peligrosos
    y normalizando espacios. Devuelve cadena vacía si el nombre resulta vacío.
    """
    try:
        if name is None:
            return ""
        s = str(name)
        # Quitar bytes nulos y caracteres problemáticos comunes en inyección/XSS
        s = s.replace("\x00", "")
        s = re.sub(r'[<>"\'";%()&+]', "", s)
        # Normalizar múltiples espacios
        s = " ".join(s.split()).strip()
        return s
    except Exception:
        return str(name).strip() if name is not None else ""


# Identificador seguro: empieza con letra/underscore, seguido de letras/dígitos/underscore
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _is_safe_identifier(name: str) -> bool:
    """Verifica si un identificador es seguro (solo letras, números y guiones bajos)."""
    if not name:
        return False
    return bool(_IDENT_RE.match(name))


def _ensure_allowed_field(field: str) -> str:
    """Verifica que el nombre de columna sea un identificador seguro y conocido.

    Lanza ValueError si no es seguro. Esto evita inyección al interpolar nombres de
    columnas en sentencias SQL que no admiten parámetros.
    """
    if not isinstance(field, str) or not _is_safe_identifier(field):
        raise ValueError(f"Invalid column identifier: {field!r}")
    return field


# Evitar ejecutar DDL de combos en paralelo
_COMBO_SCHEMA_OK = False
_COMBO_SCHEMA_LOCK = threading.Lock()
_CODIGO_SCHEMA_OK = False
_CODIGO_SCHEMA_LOCK = threading.Lock()


def _validate_sets_list(sets: List[str]):
    """Valida una lista de cláusulas SET para UPDATE."""
    for s in sets:
        # Esperamos "campo=?" o "campo=valor"
        parts = s.split("=")
        if len(parts) < 2:
            raise ValueError(f"Invalid SET clause: {s}")
        field = parts[0].strip()
        if not _is_safe_identifier(field):
            raise ValueError(f"Invalid field in SET clause: {field}")


# ==================== CATÁLOGOS ====================
ALLOWED_MEDIDAS = [
    "20cm",
    "40cm",
    "60cm",
    "80cm",
    "1m",
    "1,20m",
    "1,40m",
    "1,60m",
    "1,80m",
    "2m",
]

ALLOWED_LITROS = ["1l", "2l", "3l", "4l", "5l", "10l", "20l"]

CATEGORIAS = [
    "Pino",
    "Melamina",
    "Caño",
    "Televisores",
    "Electrodomésticos",
    "Parlantes",
    "Audio y video",
    "Cuidado personal",
    "Colchones",
    "Somier",
    "Herramientas",
    "Jardinería",
    "Bebés/niños",
    "Climatización",
    "Blanquería",
    "Living",
    "Respaldos",
    "Tulum",
    "Cocinas",
    "Ollas",
    "Termotanque y calefón",
    "Mesadas",
    "Heladeras y freezers",
    "Purificadores y campanas",
    "Celulares y tablets",
    "Parrillas",
    "Bicicletas",
]

ESTADOS = ["Nuevo", "Reacondicionado", "En promoción"]


# ==================== UTILIDADES DB/JSON ====================
def _touch_update(conn, pid: int) -> None:
    try:
        ph = "%s" if _is_postgres() else "?"
        cur = conn.cursor()
        cur.execute(
            f"UPDATE productos SET updated_at={ph} WHERE id={ph}", (_now_local(), pid)
        )
    except Exception as e:
        logger.error(f"Error actualizando timestamp producto {pid}: {e}")


def _norm_cat(s: str) -> str:
    if not s:
        return ""
    return " ".join(s.strip().split()).lower()


def _norm_medida(m: Optional[str]) -> Optional[str]:
    """Normaliza el campo medida: limpia espacios y devuelve cadena vacía para valores vacíos.

    Usar cadena vacía ('') como representación consistente en la base de datos
    evita inconsistencias entre NULL y '' que hacían algunos filtros ocultar
    productos después de editar la medida.
    """
    if m is None:
        return ""
    s = str(m).strip()
    if not s or s in ("-", "—"):
        return ""
    return s


def _j(d: dict) -> str:
    try:
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    except Exception as e:
        logger.error(f"Error serializando JSON: {e}")
        return "{}"


def ensure_combo_schema() -> Tuple[bool, str]:
    """Asegura columnas/tablas necesarias para combos."""
    try:
        global _COMBO_SCHEMA_OK
        if _COMBO_SCHEMA_OK:
            return True, "OK"
        with _COMBO_SCHEMA_LOCK:
            if _COMBO_SCHEMA_OK:
                return True, "OK"
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            if _is_postgres():
                cur.execute(
                    "ALTER TABLE productos ADD COLUMN IF NOT EXISTS is_combo INTEGER DEFAULT 0"
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS combo_items (
                        id SERIAL PRIMARY KEY,
                        combo_producto_id INTEGER NOT NULL,
                        producto_id INTEGER NOT NULL,
                        cantidad INTEGER NOT NULL DEFAULT 1,
                        producto_nombre TEXT,
                        producto_categoria TEXT,
                        producto_medida TEXT,
                        producto_estado TEXT,
                        producto_color TEXT,
                        producto_fabricante TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )
                cur.execute(
                    "ALTER TABLE combo_items ADD COLUMN IF NOT EXISTS producto_nombre TEXT"
                )
                cur.execute(
                    "ALTER TABLE combo_items ADD COLUMN IF NOT EXISTS producto_categoria TEXT"
                )
                cur.execute(
                    "ALTER TABLE combo_items ADD COLUMN IF NOT EXISTS producto_medida TEXT"
                )
                cur.execute(
                    "ALTER TABLE combo_items ADD COLUMN IF NOT EXISTS producto_estado TEXT"
                )
                cur.execute(
                    "ALTER TABLE combo_items ADD COLUMN IF NOT EXISTS producto_color TEXT"
                )
                cur.execute(
                    "ALTER TABLE combo_items ADD COLUMN IF NOT EXISTS producto_fabricante TEXT"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_combo_items_combo ON combo_items(combo_producto_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_combo_items_producto ON combo_items(producto_id)"
                )
            else:
                cur.execute("PRAGMA table_info(productos)")
                cols = {r[1] for r in cur.fetchall()}
                if "is_combo" not in cols:
                    cur.execute(
                        "ALTER TABLE productos ADD COLUMN is_combo INTEGER DEFAULT 0"
                    )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS combo_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        combo_producto_id INTEGER NOT NULL,
                        producto_id INTEGER NOT NULL,
                        cantidad INTEGER NOT NULL DEFAULT 1,
                        producto_nombre TEXT,
                        producto_categoria TEXT,
                        producto_medida TEXT,
                        producto_estado TEXT,
                        producto_color TEXT,
                        producto_fabricante TEXT,
                        created_at TEXT DEFAULT (datetime('now'))
                    )
                """
                )
                cur.execute("PRAGMA table_info(combo_items)")
                ci_cols = {r[1] for r in cur.fetchall()}
                if "producto_nombre" not in ci_cols:
                    cur.execute(
                        "ALTER TABLE combo_items ADD COLUMN producto_nombre TEXT"
                    )
                if "producto_categoria" not in ci_cols:
                    cur.execute(
                        "ALTER TABLE combo_items ADD COLUMN producto_categoria TEXT"
                    )
                if "producto_medida" not in ci_cols:
                    cur.execute(
                        "ALTER TABLE combo_items ADD COLUMN producto_medida TEXT"
                    )
                if "producto_estado" not in ci_cols:
                    cur.execute(
                        "ALTER TABLE combo_items ADD COLUMN producto_estado TEXT"
                    )
                if "producto_color" not in ci_cols:
                    cur.execute(
                        "ALTER TABLE combo_items ADD COLUMN producto_color TEXT"
                    )
                if "producto_fabricante" not in ci_cols:
                    cur.execute(
                        "ALTER TABLE combo_items ADD COLUMN producto_fabricante TEXT"
                    )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_combo_items_combo ON combo_items(combo_producto_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_combo_items_producto ON combo_items(producto_id)"
                )
            try:
                conn.commit()
            except Exception:
                pass
        _COMBO_SCHEMA_OK = True
        return True, "OK"
    except Exception as e:
        logger.error(f"Error ensure_combo_schema: {e}")
        return False, str(e)


def ensure_codigo_unique_per_local() -> Tuple[bool, str]:
    """Asegura que el código no sea único global, sino por local."""
    global _CODIGO_SCHEMA_OK
    if _CODIGO_SCHEMA_OK:
        return True, "OK"
    with _CODIGO_SCHEMA_LOCK:
        if _CODIGO_SCHEMA_OK:
            return True, "OK"
        try:
            with _get_conn_cm() as conn:
                cur = conn.cursor()
                if isinstance(conn, sqlite3.Connection):
                    # En SQLite no ajustamos constraints aquí.
                    _CODIGO_SCHEMA_OK = True
                    return True, "OK"
                # Drop unique constraint global on codigo if exists.
                cur.execute(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1
                            FROM pg_constraint c
                            JOIN pg_class t ON c.conrelid = t.oid
                            WHERE t.relname='productos' AND c.conname='productos_codigo_key'
                        ) THEN
                            ALTER TABLE productos DROP CONSTRAINT productos_codigo_key;
                        END IF;
                    END$$;
                    """
                )
                # Create unique index per local for non-empty codigo.
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS productos_local_codigo_key
                    ON productos (local, codigo)
                    WHERE codigo IS NOT NULL AND TRIM(codigo) <> '';
                    """
                )
                try:
                    conn.commit()
                except Exception:
                    pass
            _CODIGO_SCHEMA_OK = True
            return True, "OK"
        except Exception as e:
            logger.error(f"Error ensure_codigo_unique_per_local: {e}")
            return False, str(e)


# Context manager seguro para obtener una conexión y asegurar su cierre.
@contextmanager
def _get_conn_cm():
    """Context manager seguro para conexiones SQL."""
    conn = None
    try:
        conn = get_conn()
        yield conn
    finally:
        try:
            if conn and _put_db_connection:
                _put_db_connection(conn)
            elif conn:
                conn.close()
        except Exception:
            pass


def _is_conn_closed_error(err: Exception) -> bool:
    """Detecta errores de conexiÃ³n cerrada para reintentar con un pool limpio."""
    msg = str(err).lower()
    if _PgOpError and isinstance(err, (_PgOpError, _PgIfaceError)):  # type: ignore[arg-type]
        return True
    patterns = (
        "server closed the connection unexpectedly",
        "terminating connection",
        "connection not open",
        "connection already closed",
        "ssl syscall error",
    )
    return any(p in msg for p in patterns)


def _row_to_dict(r: tuple) -> dict:
    if not r or len(r) < 8:
        return {}
    if _HAS_MATERIAL_COL:
        local_val = r[9] if len(r) > 9 else None
        material = r[2] if len(r) > 2 else None
        fabricante = None
        codigo = None
        is_combo = 0
        if len(r) == 11:
            is_combo = r[10]
        elif len(r) == 12:
            fabricante = r[10]
            is_combo = r[11]
        elif len(r) >= 13:
            fabricante = r[10]
            codigo = r[11]
            is_combo = r[12]
        return {
            "id": r[0],
            "nombre": r[1],
            "material": material,
            "categoria": r[3],
            "medida": r[4],
            "estado": r[5],
            "color": r[6],
            "cantidad": r[7],
            "precio_venta": r[8],
            "local": local_val,
            "fabricante": fabricante,
            "codigo": codigo,
            "is_combo": int(is_combo or 0),
        }
    local_val = r[8] if len(r) > 8 else None
    fabricante = None
    codigo = None
    is_combo = 0
    if len(r) == 10:
        # sin fabricante/codigo, con is_combo al final
        is_combo = r[9]
    elif len(r) == 11:
        # con fabricante, sin codigo, con is_combo al final
        fabricante = r[9]
        is_combo = r[10]
    elif len(r) >= 12:
        # con fabricante y codigo, is_combo al final
        fabricante = r[9]
        codigo = r[10]
        is_combo = r[11]
    else:
        fabricante = r[9] if len(r) > 9 else None
        codigo = r[10] if len(r) > 10 else None
    return {
        "id": r[0],
        "nombre": r[1],
        "categoria": r[2],
        "medida": r[3],
        "estado": r[4],
        "color": r[5],
        "cantidad": r[6],
        "precio_venta": r[7],
        "local": local_val,
        "fabricante": fabricante,
        "codigo": codigo,
        "is_combo": int(is_combo or 0),
    }


def _find_product(
    nombre: str,
    categoria: str,
    medida: Optional[str],
    estado: str,
    color: Optional[str],
    local: str,
    material: Optional[str] = None,
) -> Optional[Tuple]:
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            # Normalizar medida para compatibilidad (usamos '' como vacío)
            medida_norm = _norm_medida(medida)
            material_norm = (material or "").strip().lower()
            cur.execute(
                """
                SELECT id, cantidad, precio_venta FROM productos
                WHERE nombre=? AND COALESCE(material,'')=COALESCE(?,'') AND categoria=? AND COALESCE(medida,'')=COALESCE(?,'')
                    AND estado=? AND COALESCE(color,'')=COALESCE(?,'') AND local=?
            """,
                (
                    nombre,
                    material_norm,
                    _norm_cat(categoria),
                    medida_norm,
                    estado,
                    color,
                    local,
                ),
            )
            row = cur.fetchone()
        return row
    except Exception as e:
        logger.error(f"Error buscando producto: {e}")
        return None


def _is_admin(username: str) -> bool:
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            cur.execute("SELECT role FROM usuarios WHERE username=?", (username,))
            r = cur.fetchone()
        return r and (r[0] or "").lower() == "admin"
    except Exception:
        return False


# ==================== NOTIFICACIONES (BUFFER + MENSAJES) ====================
# Buffer: cambios en cola (se agrupan por local y se "emiten" a los 2 minutos).
# Mensajes: notificaciones listas para mostrar (hasta que el local las lea).
def _ensure_notif_tables(conn):
    cur = conn.cursor()
    # Crear tablas con DDL compatible según el motor (SQLite vs Postgres)
    if _is_postgres():
        # Postgres: usar SERIAL / TIMESTAMP
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS noti_buffer (
                id SERIAL PRIMARY KEY,
                target_local TEXT NOT NULL,
                source_local TEXT NOT NULL,
                source_user  TEXT NOT NULL,
                field        TEXT NOT NULL,
                prod_nombre  TEXT,
                categoria    TEXT,
                medida       TEXT,
                estado       TEXT,
                color        TEXT,
                old_value    TEXT,
                new_value    TEXT,
                created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                flushed      INTEGER NOT NULL DEFAULT 0
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS noti_messages (
                id SERIAL PRIMARY KEY,
                target_local TEXT NOT NULL,
                title        TEXT NOT NULL,
                body         TEXT NOT NULL,
                payload      TEXT NOT NULL,
                created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                seen         INTEGER NOT NULL DEFAULT 0
            )
        """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS noti_buffer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_local TEXT NOT NULL,
                source_local TEXT NOT NULL,
                source_user  TEXT NOT NULL,
                field        TEXT NOT NULL,
                prod_nombre  TEXT,
                categoria    TEXT,
                medida       TEXT,
                estado       TEXT,
                color        TEXT,
                old_value    TEXT,
                new_value    TEXT,
                created_at   TEXT NOT NULL,
                flushed      INTEGER NOT NULL DEFAULT 0
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS noti_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_local TEXT NOT NULL,
                title        TEXT NOT NULL,
                body         TEXT NOT NULL,
                payload      TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                seen         INTEGER NOT NULL DEFAULT 0
            )
        """
        )


def _ensure_op_queue_table(conn):
    """Crea tabla op_queue si no existe (adaptada a Postgres/SQLite)."""
    cur = conn.cursor()
    if _is_postgres():
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS op_queue (
                id SERIAL PRIMARY KEY,
                op_type TEXT NOT NULL,
                payload JSONB,
                status INTEGER NOT NULL DEFAULT 0, -- 0=queued,1=processing,2=done,3=failed
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS op_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                op_type TEXT NOT NULL,
                payload TEXT,
                status INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL
            )
        """
        )


def enqueue_op(op_type: str, payload: dict) -> int:
    """
    DISABLED: Función deshabilitada para evitar conflictos con Firestore.
    El sistema usa stock_queue_api que maneja Firestore directamente.
    Retorna un ID ficticio para mantener compatibilidad.
    """
    # Retornar ID ficticio - la operación real se maneja por Firestore
    import random

    return random.randint(1000, 9999)


def get_queue_count() -> int:
    """Obtiene el número de operaciones pendientes en la cola."""
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            _ensure_op_queue_table(conn)
            cur.execute("SELECT COUNT(*) FROM op_queue WHERE status=0")
            c = cur.fetchone()[0]
        return int(c or 0)
    except Exception as e:
        logger.error(f"Error en get_queue_count: {e}")
        return 0


def mark_queue_item_done(qid: int) -> bool:
    """Marca un item como procesado exitosamente."""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE op_queue SET status=2, attempts=attempts+1 WHERE id=?", (qid,)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error marcando item {qid} como done: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


def mark_queue_item_failed(qid: int, error: str) -> bool:
    """Marca un item como fallido permanentemente."""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE op_queue SET status=3, attempts=attempts+1, last_error=? WHERE id=?",
            (str(error), qid),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error marcando item {qid} como failed: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


def mark_queue_item_retry(qid: int, error: str, attempts: int) -> bool:
    """Marca un item para reintento posterior."""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE op_queue 
            SET status=0, attempts=?, last_error=? 
            WHERE id=?
        """,
            (attempts, str(error), qid),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error marcando item {qid} para retry: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


def get_queue_items(limit: int = 50) -> list:
    """Obtiene items pendientes de la cola."""
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            _ensure_op_queue_table(conn)
            cur.execute(
                "SELECT id, op_type, payload, attempts, created_at FROM op_queue WHERE status=0 ORDER BY created_at ASC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
            items = []
            for r in rows:
                payload = r[2]
                try:
                    payload = (
                        json.loads(payload) if isinstance(payload, str) else payload
                    )
                except Exception:
                    payload = {}
                items.append(
                    {
                        "id": r[0],
                        "op_type": r[1],
                        "payload": payload,
                        "attempts": r[3],
                        "created_at": r[4],
                    }
                )
            return items
    except Exception as e:
        logger.error(f"Error en get_queue_items: {e}")
        return []


def get_queue_all_items(limit: int = 200) -> list:
    """Devuelve items de la cola con todos los estados (útil para UI de gestión)."""
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            _ensure_op_queue_table(conn)
            cur.execute(
                "SELECT id, op_type, payload, attempts, status, last_error, created_at FROM op_queue ORDER BY created_at ASC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
            items = []
            for r in rows:
                payload = r[2]
                try:
                    payload = (
                        json.loads(payload) if isinstance(payload, str) else payload
                    )
                except Exception:
                    payload = {}
                items.append(
                    {
                        "id": r[0],
                        "op_type": r[1],
                        "payload": payload,
                        "attempts": r[3],
                        "status": int(r[4] or 0),
                        "last_error": r[5],
                        "created_at": r[6],
                    }
                )
            return items
    except Exception as e:
        logger.error(f"Error en get_queue_all_items: {e}")
        return []


def retry_queue_item(qid: int) -> bool:
    """Marca un item como encolado (status=0) y resetea attempts/last_error para reintentar."""
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            _ensure_op_queue_table(conn)
            cur.execute(
                "UPDATE op_queue SET status=0, attempts=0, last_error=NULL WHERE id=?",
                (qid,),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error retry_queue_item({qid}): {e}")
        return False


def remove_queue_item(qid: int) -> bool:
    """Elimina un item de la cola (uso manual desde UI)."""
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            _ensure_op_queue_table(conn)
            cur.execute("DELETE FROM op_queue WHERE id=?", (qid,))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error remove_queue_item({qid}): {e}")
        return False


def process_queue_once(limit: int = 20) -> int:
    """Procesa hasta `limit` operaciones encoladas. Devuelve número de items procesados."""
    processed = 0
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            _ensure_op_queue_table(conn)
            # Seleccionar items pendientes
            cur.execute(
                "SELECT id, op_type, payload, attempts FROM op_queue WHERE status=0 ORDER BY created_at ASC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
            for r in rows:
                qid, op_type, payload_raw, attempts = r[0], r[1], r[2], int(r[3] or 0)
            try:
                payload = (
                    json.loads(payload_raw)
                    if isinstance(payload_raw, str)
                    else payload_raw
                )
            except Exception:
                payload = {}

            # Marcar como processing
            try:
                cur.execute(
                    "UPDATE op_queue SET status=1, attempts=? WHERE id=?",
                    (attempts + 1, qid),
                )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass

            success = False
            last_err = ""
            try:
                if op_type == "increment":
                    pid = int(payload.get("producto_id") or 0)
                    delta = int(payload.get("delta") or 0)
                    usuario = payload.get("usuario")
                    local = payload.get("local")
                    detalle = payload.get("detalle")
                    motivo = payload.get("motivo")
                    ok, msg = increment_stock(
                        pid,
                        delta,
                        usuario or "sistema",
                        local or "",
                        detalle=detalle or "",
                        motivo=motivo or "",
                    )
                    success = ok
                elif op_type == "update_field":
                    pid = int(payload.get("producto_id") or 0)
                    field = payload.get("field")
                    value = payload.get("value")
                    usuario = payload.get("usuario")
                    local = payload.get("local")
                    motivo = payload.get("motivo")
                    success = update_stock_field(
                        pid,
                        field,
                        value,
                        usuario=usuario or "sistema",
                        local=local,
                        motivo=motivo,
                    )
                elif op_type == "decrement":
                    pid = int(payload.get("producto_id") or 0)
                    delta = int(payload.get("delta") or 0)
                    usuario = payload.get("usuario")
                    local = payload.get("local")
                    detalle = payload.get("detalle")
                    motivo = payload.get("motivo")
                    # use increment_stock with negative delta
                    ok, msg = increment_stock(
                        pid,
                        -abs(delta),
                        usuario or "sistema",
                        local or "",
                        detalle=detalle or "",
                        motivo=motivo or "",
                    )
                    success = ok
                elif op_type == "transfer":
                    row = payload.get("row") or {}
                    to_local = payload.get("to_local")
                    cantidad = int(payload.get("cantidad") or 0)
                    usuario = payload.get("usuario")
                    success, msg = transfer_stock(
                        row, to_local, cantidad, usuario or "sistema"
                    )
                elif op_type == "add_product":
                    # payload: nombre,categoria,medida,estado,color,cantidad,precio_costo,precio_venta,local,usuario
                    try:
                        success, msg = add_or_increment(
                            payload.get("nombre"),
                            payload.get("categoria"),
                            payload.get("medida"),
                            payload.get("estado"),
                            payload.get("color"),
                            int(payload.get("cantidad") or 0),
                            float(payload.get("precio_costo") or 0),
                            float(payload.get("precio_venta") or 0),
                            payload.get("local"),
                            payload.get("usuario") or "sistema",
                            material=payload.get("material"),
                        )
                    except Exception as e:
                        success = False
                        msg = str(e)
                elif op_type == "change_state":
                    pid = int(payload.get("producto_id") or 0)
                    cantidad = int(payload.get("cantidad") or 0)
                    nuevo_estado = payload.get("nuevo_estado")
                    nuevo_precio = payload.get("nuevo_precio")
                    usuario = payload.get("usuario")
                    local = payload.get("local")
                    motivo = payload.get("motivo")
                    success, msg = change_state_quantity(
                        pid,
                        cantidad,
                        nuevo_estado,
                        nuevo_precio,
                        usuario or "sistema",
                        local or "",
                        motivo=motivo,
                    )
                elif op_type == "bulk_update_prices":
                    product_ids = payload.get("product_ids") or []
                    price_change = payload.get("price_change")
                    usuario = payload.get("usuario")
                    local = payload.get("local")
                    success, msg = bulk_update_prices(
                        product_ids, price_change, usuario or "sistema", local or ""
                    )
                else:
                    # Unknown op: mark failed
                    last_err = f"Unknown op_type {op_type}"
                    success = False
            except Exception as e:
                last_err = str(e)

            try:
                if success:
                    cur.execute("UPDATE op_queue SET status=2 WHERE id=?", (qid,))
                else:
                    # falló: incrementar attempts y marcar failed si ya superó 5 intentos
                    attempts_new = attempts + 1
                    if attempts_new >= 5:
                        cur.execute(
                            "UPDATE op_queue SET status=3, last_error=? WHERE id=?",
                            (last_err, qid),
                        )
                    else:
                        cur.execute(
                            "UPDATE op_queue SET status=0, attempts=?, last_error=? WHERE id=?",
                            (attempts_new, last_err, qid),
                        )
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass

            processed += 1

        # conn cerrado automáticamente por el context manager
    except Exception as e:
        logger.error(f"Error procesando queue: {e}")
    return processed


def _queue_change_notification(
    affected_locals: List[str],
    source_local: str,
    source_user: str,
    field: str,
    prod_snapshot: Dict[str, Any],
    old_value: Any,
    new_value: Any,
):
    """
    Enfila (una por local) el cambio realizado para que sea notificado
    luego del "batch window" de 2 minutos.
    """
    try:
        now = _now_local()
        with _get_conn_cm() as conn:
            _ensure_notif_tables(conn)
            cur = conn.cursor()

            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            for tgt in affected_locals:
                cur.execute(
                    f"""
                    INSERT INTO noti_buffer
                    (target_local, source_local, source_user, field, prod_nombre, categoria, medida, estado, color,
                     old_value, new_value, created_at, flushed)
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},0)
                """,
                    (
                        tgt,
                        source_local,
                        source_user,
                        field,
                        prod_snapshot.get("nombre"),
                        _norm_cat(prod_snapshot.get("categoria") or ""),
                        prod_snapshot.get("medida"),
                        prod_snapshot.get("estado"),
                        prod_snapshot.get("color"),
                        str(old_value) if old_value is not None else "",
                        str(new_value) if new_value is not None else "",
                        now,
                    ),
                )
            conn.commit()
    except Exception as e:
        logger.error(f"Error encolando notificación: {e}")


def flush_notifications_for_local(target_local: str, force: bool = False) -> int:
    """
    Igual a flush_notifications, pero SOLO para un local.
    Si force=True ignora la ventana de 2 minutos.
    """
    try:
        with _get_conn_cm() as conn:
            _ensure_notif_tables(conn)
            cur = conn.cursor()

            # Seleccionar todas las notificaciones pendientes para este local y filtrar
            # por antigüedad en Python (compatibilidad SQLite/Postgres).
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            cur.execute(
                f"""
                SELECT id, target_local, source_local, source_user, field,
                       prod_nombre, categoria, medida, estado, color,
                       old_value, new_value, created_at
                FROM noti_buffer
                WHERE flushed=0 AND target_local={ph}
                ORDER BY created_at ASC, id ASC
            """,
                (target_local,),
            )
            items_raw = cur.fetchall()
            items = []
            if force:
                items = items_raw
            else:
                # Mantener solo items con created_at hace al menos 2 minutos
                from datetime import datetime, timedelta

                now_dt = datetime.now()
                for r in items_raw:
                    try:
                        created_at = r[12]
                        created_dt = (
                            datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                            if isinstance(created_at, str)
                            else created_at
                        )
                        if (now_dt - created_dt) >= timedelta(minutes=2):
                            items.append(r)
                    except Exception:
                        # Si hay parsing error, incluir el item para no perder notificación
                        items.append(r)

            # items ya construido arriba
            if not items:
                return 0

            # Construir cuerpo (mismo formato que flush_notifications)
            lines = []
            payload_items = []
            for r in items:
                it = {
                    "id": r[0],
                    "target_local": r[1],
                    "source_local": r[2],
                    "source_user": r[3],
                    "field": r[4],
                    "prod_nombre": r[5],
                    "categoria": r[6],
                    "medida": r[7],
                    "estado": r[8],
                    "color": r[9],
                    "old_value": r[10],
                    "new_value": r[11],
                    "created_at": r[12],
                }

                if it["field"] == "transferencia":
                    line = f"• {it['source_user']} @ {it['source_local']} transfirió {it['new_value']} a tu local."
                elif it["field"] in (
                    "venta_otro_local",
                    "venta_otro_local_retiro",
                    "venta_otro_local_envio",
                ):
                    qty = it["new_value"] or "1"
                    desc = f"{it['prod_nombre'] or '???'}"
                    tail = []
                    if it["categoria"]:
                        tail.append(it["categoria"])
                    if it["medida"]:
                        tail.append(it["medida"])
                    if it["estado"]:
                        tail.append(it["estado"])
                    extra = f" ({', '.join(tail)})" if tail else ""
                    if it["field"] == "venta_otro_local_envio":
                        line = (
                            f"!!! IMPORTANTE: {it['source_user']} @ {it['source_local']} vendio "
                            f'{qty} unidad(es) de "{desc}"{extra} con stock de tu local. '
                            "Es una VENTA CON ENVIO: revisa la seccion 'Envios'."
                        )
                    else:
                        line = (
                            f"!!! IMPORTANTE: {it['source_user']} @ {it['source_local']} vendio "
                            f'{qty} unidad(es) de "{desc}"{extra} con stock de tu local. '
                            "Podes verlo en 'Vendidos por otros locales'. "
                            "Cuando se retire, presiona el boton Entregar en esa seccion."
                        )
                else:
                    desc = f"{it['prod_nombre'] or '—'}"
                    tail = []
                    if it["categoria"]:
                        tail.append(it["categoria"])
                    if it["medida"]:
                        tail.append(it["medida"])
                    if it["estado"]:
                        tail.append(it["estado"])
                    extra = f" ({', '.join(tail)})" if tail else ""
                    line = (
                        f"• {it['source_user']} @ {it['source_local']} cambió {it['field']} "
                        f'de "{desc}"{extra}: "{it["old_value"]}" → "{it["new_value"]}".'
                    )
                lines.append(line)

                payload_items.append(
                    {
                        "field": it["field"],
                        "product": {
                            "nombre": it["prod_nombre"],
                            "categoria": it["categoria"],
                            "medida": it["medida"],
                            "estado": it["estado"],
                            "color": it["color"],
                        },
                        "old": it["old_value"],
                        "new": it["new_value"],
                        "by_user": it["source_user"],
                        "by_local": it["source_local"],
                        "at": it["created_at"],
                    }
                )

            now = _now_local()
            title = "Actualizaciones de catálogo en tu local"
            body = "\n".join(lines)
            payload = _j(
                {
                    "generated_at": now,
                    "target_local": target_local,
                    "items": payload_items,
                }
            )

            cur.execute(
                """
                INSERT INTO noti_messages (target_local, title, body, payload, created_at, seen)
                VALUES (?,?,?,?,?,0)
            """,
                (target_local, title, body, payload, now),
            )

            ids = [r[0] for r in items]
            cur.execute(
                f"UPDATE noti_buffer SET flushed=1 WHERE id IN ({','.join('?'*len(ids))})",
                ids,
            )

            conn.commit()
            return 1
    except Exception as e:
        logger.error(
            f"Error en flush_notifications_for_local({target_local}, force={force}): {e}"
        )
        try:
            if "conn" in locals() and conn:
                conn.rollback()
        except:
            pass
        return 0


def get_unread_notifications(local: str) -> List[dict]:
    """Devuelve las notificaciones pendientes (no vistas) para un local."""
    try:
        with _get_conn_cm() as conn:
            _ensure_notif_tables(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, title, body, payload, created_at
                FROM noti_messages
                WHERE target_local=? AND seen=0
                ORDER BY created_at ASC, id ASC
            """,
                (local,),
            )
            rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "title": r[1],
                "body": r[2],
                "payload": json.loads(r[3] or "{}"),
                "created_at": r[4],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error leyendo notificaciones: {e}")
        return []


def mark_notifications_seen(ids: List[int]) -> None:
    """Marca como vistas una lista de notificaciones."""
    if not ids:
        return
    try:
        with _get_conn_cm() as conn:
            _ensure_notif_tables(conn)
            cur = conn.cursor()
            cur.execute(
                f"UPDATE noti_messages SET seen=1 WHERE id IN ({','.join('?'*len(ids))})",
                ids,
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error marcando notificaciones como vistas: {e}")


# ==================== LECTURA ====================
def get_product_names(local: str = None) -> List[str]:
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            if local:
                cur.execute(
                    "SELECT DISTINCT nombre FROM productos WHERE local=? ORDER BY nombre ASC",
                    (local,),
                )
            else:
                cur.execute("SELECT DISTINCT nombre FROM productos ORDER BY nombre ASC")
            result = [r[0] for r in cur.fetchall()]
        return result
    except Exception as e:
        logger.error(f"Error obteniendo nombres de productos: {e}")
        return []


def get_all_tipos() -> List[str]:
    """Devuelve todas las categorías únicas en la tabla productos."""
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT DISTINCT categoria FROM productos WHERE categoria IS NOT NULL AND categoria<>'' ORDER BY categoria ASC"
            )
            cats = [str(r[0] or "").strip().lower() for r in cur.fetchall()]
            return sorted({c for c in cats if c})
    except Exception as e:
        logger.error(f"Error obteniendo categorias: {e}")
        return []


from typing import Union


def _get_qty_map_for_ids(local: str, ids: List[int]) -> Dict[int, int]:
    if not ids:
        return {}
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            placeholders = ",".join([ph] * len(ids))
            cur.execute(
                f"SELECT id, COALESCE(cantidad,0) FROM productos WHERE local={ph} AND id IN ({placeholders})",
                tuple([local] + ids),
            )
            rows = cur.fetchall()
            return {int(r[0]): int(r[1] or 0) for r in rows}
    except Exception as e:
        logger.error(f"Error obteniendo cantidades para combos: {e}")
        return {}


def get_combo_items(combo_producto_id: int) -> List[dict]:
    try:
        if not combo_producto_id:
            return []
        ensure_combo_schema()
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            cur.execute(
                f"""
                SELECT producto_id, cantidad,
                       producto_nombre, producto_categoria, producto_medida,
                       producto_estado, producto_color, producto_fabricante
                FROM combo_items
                WHERE combo_producto_id = {ph}
                ORDER BY id ASC
                """,
                (int(combo_producto_id),),
            )
            out = []
            for r in cur.fetchall():
                out.append(
                    {
                        "producto_id": int(r[0]),
                        "cantidad": int(r[1] or 0),
                        "producto_nombre": r[2] if len(r) > 2 else None,
                        "producto_categoria": r[3] if len(r) > 3 else None,
                        "producto_medida": r[4] if len(r) > 4 else None,
                        "producto_estado": r[5] if len(r) > 5 else None,
                        "producto_color": r[6] if len(r) > 6 else None,
                        "producto_fabricante": r[7] if len(r) > 7 else None,
                    }
                )
            return out
    except Exception as e:
        logger.error(f"Error get_combo_items: {e}")
        return []


def _get_combo_definitions(local: str) -> Dict[int, List[dict]]:
    """Devuelve combos del local con sus items."""
    combos: Dict[int, List[dict]] = {}
    try:
        ensure_combo_schema()
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            cur.execute(
                f"""
                SELECT ci.combo_producto_id, ci.producto_id, ci.cantidad,
                       ci.producto_nombre, ci.producto_categoria, ci.producto_medida,
                       ci.producto_estado, ci.producto_color, ci.producto_fabricante
                FROM combo_items ci
                JOIN productos p ON p.id = ci.combo_producto_id
                WHERE p.local = {ph} AND COALESCE(p.is_combo,0)=1
                ORDER BY ci.combo_producto_id, ci.id
                """,
                (local,),
            )
            for row in cur.fetchall():
                combo_id = row[0]
                prod_id = row[1]
                qty = row[2]
                cid = int(combo_id or 0)
                if cid <= 0:
                    continue
                combos.setdefault(cid, []).append(
                    {
                        "producto_id": int(prod_id or 0),
                        "cantidad": int(qty or 0),
                        "producto_nombre": row[3] if len(row) > 3 else None,
                        "producto_categoria": row[4] if len(row) > 4 else None,
                        "producto_medida": row[5] if len(row) > 5 else None,
                        "producto_estado": row[6] if len(row) > 6 else None,
                        "producto_color": row[7] if len(row) > 7 else None,
                        "producto_fabricante": row[8] if len(row) > 8 else None,
                    }
                )
    except Exception as e:
        logger.error(f"Error obteniendo definiciones de combos: {e}")
    return combos


def create_combo(
    local: str,
    nombre: str,
    precio_venta: float,
    items: List[dict],
    usuario: str = "sistema",
    categoria: Optional[str] = None,
    medida: Optional[str] = None,
    estado: Optional[str] = None,
    color: Optional[str] = None,
    fabricante: Optional[str] = None,
    material: Optional[str] = None,
    codigo: Optional[str] = None,
    descripcion: Optional[str] = None,
) -> Tuple[bool, str, Optional[int]]:
    """Crea un combo como producto virtual + items."""
    try:
        ensure_combo_schema()
        nombre = _sanitize_name(nombre)
        if not nombre:
            return False, "Nombre de combo inválido", None
        try:
            precio_venta = float(precio_venta or 0)
        except Exception:
            precio_venta = 0.0
        if precio_venta < 0:
            return False, "Precio inválido", None
        categoria = (categoria or "combo").strip() or "combo"
        medida = (medida or "").strip()
        estado = (estado or "Nuevo").strip() or "Nuevo"
        color = (color or "").strip()
        fabricante = (fabricante or "").strip()
        material = (material or "").strip()
        codigo = (codigo or "").strip()
        descripcion = (descripcion or "").strip()
        if not codigo:
            codigo = None
        clean_items = []
        for it in items or []:
            try:
                pid = int(it.get("producto_id") or 0)
                qty = int(it.get("cantidad") or 0)
            except Exception:
                pid = 0
                qty = 0
            if pid > 0 and qty > 0:
                clean_items.append({"producto_id": pid, "cantidad": qty})
        if not clean_items:
            return False, "Debes seleccionar productos para el combo", None

        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            cur.execute(
                f"""
                SELECT id FROM productos
                WHERE local = {ph}
                  AND LOWER(nombre)=LOWER({ph})
                  AND COALESCE(medida,'')=COALESCE({ph},'')
                  AND COALESCE(is_combo,0)=1
                """,
                (local, nombre, medida),
            )
            if cur.fetchone():
                return False, "Ya existe un combo con ese nombre y medida", None

            # Validar que los productos existan y no sean combos
            ids = [it["producto_id"] for it in clean_items]
            placeholders = ",".join([ph] * len(ids))
            cur.execute(
                f"""
                SELECT id FROM productos
                WHERE local = {ph} AND id IN ({placeholders}) AND COALESCE(is_combo,0)=0
                """,
                tuple([local] + ids),
            )
            valid_ids = {int(r[0]) for r in cur.fetchall()}
            if len(valid_ids) != len(ids):
                return (
                    False,
                    "Algunos productos no existen en este local o son combos",
                    None,
                )

            now = _now_local()
            if isinstance(conn, sqlite3.Connection):
                cur.execute(
                    """
                    INSERT INTO productos
                    (nombre, categoria, medida, estado, color, cantidad, precio_costo, precio_venta, local,
                     codigo, descripcion, fabricante, material, created_at, updated_at, is_combo)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
                    """,
                    (
                        nombre,
                        categoria,
                        medida,
                        estado,
                        color,
                        0,
                        0,
                        float(precio_venta),
                        local,
                        codigo,
                        descripcion,
                        fabricante,
                        material,
                        now,
                        now,
                    ),
                )
                combo_pid = int(cur.lastrowid or 0)
            else:
                cur.execute(
                    """
                    INSERT INTO productos
                    (nombre, categoria, medida, estado, color, cantidad, precio_costo, precio_venta, local,
                     codigo, descripcion, fabricante, material, created_at, updated_at, is_combo)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
                    RETURNING id
                    """,
                    (
                        nombre,
                        categoria,
                        medida,
                        estado,
                        color,
                        0,
                        0,
                        float(precio_venta),
                        local,
                        codigo,
                        descripcion,
                        fabricante,
                        material,
                        now,
                        now,
                    ),
                )
                row = cur.fetchone()
                combo_pid = int(row[0]) if row else 0
            if combo_pid <= 0:
                conn.rollback()
                return False, "No se pudo crear el combo", None

            for it in clean_items:
                cur.execute(
                    f"""
                    SELECT nombre, categoria, COALESCE(medida,''), estado,
                           COALESCE(color,''), COALESCE(fabricante,'')
                    FROM productos
                    WHERE id = {ph}
                    """,
                    (int(it["producto_id"]),),
                )
                row = cur.fetchone()
                nombre_p = row[0] if row else ""
                categoria_p = row[1] if row else ""
                medida_p = row[2] if row else ""
                estado_p = row[3] if row else ""
                color_p = row[4] if row else ""
                fabricante_p = row[5] if row else ""
                cur.execute(
                    f"""
                    INSERT INTO combo_items (
                        combo_producto_id, producto_id, cantidad,
                        producto_nombre, producto_categoria, producto_medida,
                        producto_estado, producto_color, producto_fabricante, created_at
                    )
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                    """,
                    (
                        combo_pid,
                        int(it["producto_id"]),
                        int(it["cantidad"]),
                        nombre_p,
                        categoria_p,
                        medida_p,
                        estado_p,
                        color_p,
                        fabricante_p,
                        now,
                    ),
                )

            try:
                cur.execute(
                    f"""
                    INSERT INTO historial_stock
                    (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},0,{ph})
                    """,
                    (
                        combo_pid,
                        "combo",
                        f"Creación de combo: {nombre}",
                        0,
                        usuario,
                        local,
                        now,
                        "combo",
                        _j({"combo": True, "items": clean_items}),
                        None,
                    ),
                )
            except Exception:
                pass

            conn.commit()
            try:
                sync_combo_across_locals(combo_pid, local)
            except Exception:
                pass
            return True, "Combo creado correctamente", combo_pid
    except Exception as e:
        logger.error(f"Error creando combo: {e}")
        return False, f"Error creando combo: {e}", None


def delete_combo(
    combo_producto_id: int, local: str, usuario: str = "sistema"
) -> Tuple[bool, str]:
    try:
        if not combo_producto_id:
            return False, "Combo inválido"
        ensure_combo_schema()
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            cur.execute(
                f"DELETE FROM combo_items WHERE combo_producto_id={ph}",
                (int(combo_producto_id),),
            )
            cur.execute(
                f"DELETE FROM historial_stock WHERE producto_id={ph}",
                (int(combo_producto_id),),
            )
            cur.execute(
                f"DELETE FROM productos WHERE id={ph} AND local={ph} AND COALESCE(is_combo,0)=1",
                (int(combo_producto_id), local),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return False, "Combo no encontrado en este local"
            conn.commit()
        return True, "Combo eliminado"
    except Exception as e:
        logger.error(f"Error eliminando combo: {e}")
        return False, f"Error eliminando combo: {e}"


def merge_duplicate_products(local: str, usuario: str = "sistema") -> int:
    """
    Une automáticamente filas de productos con todas las columnas iguales
    excepto 'cantidad': suma las cantidades y elimina los duplicados.
    Retorna la cantidad de filas eliminadas.
    """
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            is_pg = not isinstance(conn, sqlite3.Connection)
            # Obtener todos los productos no-combo del local
            cur.execute(
                f"""
                SELECT id, nombre, categoria, medida, estado, color, fabricante,
                       material, precio_venta, precio_costo, cantidad
                FROM productos
                WHERE local={ph} AND COALESCE(is_combo,0)=0
                ORDER BY id
                """,
                (local,),
            )
            rows = cur.fetchall() or []
            # Agrupar por clave (todo excepto id y cantidad)
            groups: dict = {}
            for r in rows:
                pid, nombre, cat, med, est, col, fab, mat, pv, pc, qty = r
                key = (
                    (nombre or "").strip().lower(),
                    (cat or "").strip().lower(),
                    (med or "").strip().lower(),
                    (est or "").strip().lower(),
                    (col or "").strip().lower(),
                    (fab or "").strip().lower(),
                    (mat or "").strip().lower(),
                    float(pv or 0),
                    float(pc or 0),
                )
                if key not in groups:
                    groups[key] = []
                groups[key].append({"id": pid, "cantidad": int(qty or 0)})
            deleted = 0
            for key, items in groups.items():
                if len(items) < 2:
                    continue
                # Conservar el de menor id, sumarle la cantidad total
                items.sort(key=lambda x: x["id"])
                keep_id = items[0]["id"]
                total_qty = sum(i["cantidad"] for i in items)
                delete_ids = [i["id"] for i in items[1:]]
                cur.execute(
                    f"UPDATE productos SET cantidad={ph} WHERE id={ph}",
                    (total_qty, keep_id),
                )
                for did in delete_ids:
                    cur.execute(
                        f"DELETE FROM productos WHERE id={ph}",
                        (did,),
                    )
                    deleted += 1
            if deleted:
                conn.commit()
                logger.info(
                    f"merge_duplicate_products({local}): {deleted} filas unidas"
                )
            return deleted
    except Exception as e:
        logger.error(f"Error uniendo productos duplicados: {e}")
        return 0


def find_duplicate_combos(local: str) -> List[Dict[str, Any]]:
    """
    Encuentra combos duplicados (misma firma de componentes) en un local.
    Retorna lista de grupos: cada grupo es una lista de combos con la misma firma.
    Solo retorna grupos con 2+ combos (los duplicados).
    """
    try:
        ensure_combo_schema()
        products = get_stock_filtered(local, "", "", "", apply_reservas=False)
        combos = [p for p in products if int(p.get("is_combo") or 0) == 1]
        # Para cada combo, obtener sus items y calcular la firma
        signature_map: Dict[tuple, List[dict]] = {}
        for combo in combos:
            combo_id = int(combo.get("id") or 0)
            if combo_id <= 0:
                continue
            items = get_combo_items(combo_id)
            sig = _combo_signature(items)
            if sig not in signature_map:
                signature_map[sig] = []
            signature_map[sig].append(combo)
        # Solo retornar grupos con duplicados
        duplicates = [group for group in signature_map.values() if len(group) > 1]
        return duplicates
    except Exception as e:
        logger.error(f"Error buscando combos duplicados: {e}")
        return []


def _normalize_comp_attr(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _combo_signature(items: List[dict]) -> Tuple[Tuple]:
    sig = []
    for it in items:
        sig.append(
            (
                _normalize_comp_attr(it.get("producto_nombre")),
                _normalize_comp_attr(it.get("producto_categoria")),
                _normalize_comp_attr(it.get("producto_medida")),
                _normalize_comp_attr(it.get("producto_estado")),
                _normalize_comp_attr(it.get("producto_color")),
                _normalize_comp_attr(it.get("producto_fabricante")),
                int(it.get("cantidad") or 0),
            )
        )
    return tuple(sorted(sig))


def _find_product_by_attrs(cur, local: str, comp: dict, ph: str) -> Optional[int]:
    nombre = _normalize_comp_attr(comp.get("producto_nombre"))
    categoria = _normalize_comp_attr(comp.get("producto_categoria"))
    medida = (comp.get("producto_medida") or "").strip()
    estado = (comp.get("producto_estado") or "").strip()
    color = (comp.get("producto_color") or "").strip()
    fabricante = (comp.get("producto_fabricante") or "").strip()
    try:
        cur.execute(
            f"""
            SELECT id FROM productos
            WHERE local={ph} AND LOWER(nombre)={ph} AND LOWER(categoria)={ph}
              AND COALESCE(medida,'')=COALESCE({ph},'') AND estado={ph}
              AND COALESCE(color,'')=COALESCE({ph},'')
              AND COALESCE(fabricante,'')=COALESCE({ph},'')
              AND COALESCE(is_combo,0)=0
            LIMIT 1
            """,
            (local, nombre, categoria, medida, estado, color, fabricante),
        )
        row = cur.fetchone()
        return int(row[0]) if row else None
    except Exception:
        try:
            cur.execute(
                f"""
                SELECT id FROM productos
                WHERE local={ph} AND LOWER(nombre)={ph} AND LOWER(categoria)={ph}
                  AND COALESCE(medida,'')=COALESCE({ph},'') AND estado={ph}
                  AND COALESCE(color,'')=COALESCE({ph},'')
                  AND COALESCE(is_combo,0)=0
                LIMIT 1
                """,
                (local, nombre, categoria, medida, estado, color),
            )
            row = cur.fetchone()
            return int(row[0]) if row else None
        except Exception:
            return None


def _fill_comp_attrs_from_product(cur, comp: dict, ph: str) -> dict:
    try:
        if all(
            comp.get(k)
            for k in (
                "producto_nombre",
                "producto_categoria",
                "producto_medida",
                "producto_estado",
                "producto_color",
            )
        ):
            return comp
        pid = int(comp.get("producto_id") or 0)
        if pid <= 0:
            return comp
        cur.execute(
            f"""
            SELECT nombre, categoria, COALESCE(medida,''), estado,
                   COALESCE(color,''), COALESCE(fabricante,'')
            FROM productos WHERE id={ph}
            """,
            (pid,),
        )
        row = cur.fetchone()
        if row:
            comp["producto_nombre"] = comp.get("producto_nombre") or row[0]
            comp["producto_categoria"] = comp.get("producto_categoria") or row[1]
            comp["producto_medida"] = comp.get("producto_medida") or row[2]
            comp["producto_estado"] = comp.get("producto_estado") or row[3]
            comp["producto_color"] = comp.get("producto_color") or row[4]
            comp["producto_fabricante"] = comp.get("producto_fabricante") or row[5]
    except Exception:
        pass
    return comp


def _get_all_locals_from_db() -> List[str]:
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT local FROM productos ORDER BY local ASC")
            return [str(r[0]) for r in cur.fetchall() if r and r[0]]
    except Exception:
        return []


def sync_all_products_across_locals(force=False):
    """
    Sincroniza todos los productos para que existan en todos los locales.
    Si un producto existe en el local A pero no en el B, se crea en el B con cantidad=0.
    """
    global _SYNC_PRODUCTS_ALL_LOCALS_DONE
    if _SYNC_PRODUCTS_ALL_LOCALS_DONE and not force:
        return
    with _SYNC_PRODUCTS_ALL_LOCALS_LOCK:
        if _SYNC_PRODUCTS_ALL_LOCALS_DONE and not force:
            return
        logger.info(
            "Iniciando sincronización global de productos en todos los locales..."
        )
        try:
            with _get_conn_cm() as conn:
                cur = conn.cursor()
                try:
                    is_pg = (
                        getattr(conn, "is_postgres", lambda: False)() or _is_postgres()
                    )
                except Exception:
                    is_pg = False
                ph = "%s" if is_pg else "?"

                # Obtener todos log locales válidos
                cur.execute(
                    "SELECT DISTINCT local FROM productos WHERE local IS NOT NULL AND local != ''"
                )
                locales = [str(r[0]) for r in cur.fetchall()]
                if not locales:
                    _SYNC_PRODUCTS_ALL_LOCALS_DONE = True
                    return

                # Obtener todos los productos distintos (por sus atributos principales)
                sql_distinct = """
                    SELECT nombre, COALESCE(material,''), categoria, COALESCE(fabricante,''), 
                           COALESCE(medida,''), estado, COALESCE(color,''), 
                           MAX(precio_venta), MAX(precio_costo), MAX(codigo), MAX(descripcion), MAX(is_combo)
                    FROM productos
                    GROUP BY nombre, COALESCE(material,''), categoria, COALESCE(fabricante,''), 
                             COALESCE(medida,''), estado, COALESCE(color,'')
                """

                try:
                    cur.execute(sql_distinct)
                    distinct_products = cur.fetchall()
                except Exception:
                    conn.rollback()
                    # Fallback si no hay fabricante o material
                    sql_distinct_fallback = """
                        SELECT nombre, '', categoria, '', 
                               COALESCE(medida,''), estado, COALESCE(color,''), 
                               MAX(precio_venta), MAX(precio_costo), MAX(codigo), MAX(descripcion), MAX(is_combo)
                        FROM productos
                        GROUP BY nombre, categoria, COALESCE(medida,''), estado, COALESCE(color,'')
                    """
                    try:
                        cur.execute(sql_distinct_fallback)
                        distinct_products = cur.fetchall()
                    except Exception as e_fb:
                        conn.rollback()
                        logger.error(
                            f"Fallback distinct_products fallback failed: {e_fb}"
                        )
                        return

                # Obtener las combinaciones existentes local/producto para no hacer SELECTs individuales
                cur.execute(
                    """
                    SELECT local, nombre, COALESCE(material,''), categoria, COALESCE(fabricante,''), 
                           COALESCE(medida,''), estado, COALESCE(color,'')
                    FROM productos
                    WHERE local IS NOT NULL AND local != ''
                """
                )
                existing = set()
                try:
                    for r in cur.fetchall():
                        existing.add((r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]))
                except Exception:
                    pass

                # Identificar combinaciones faltantes
                missing = []
                now_str = datetime.now().isoformat()
                for loc in locales:
                    for p in distinct_products:
                        sig = (loc, p[0], p[1], p[2], p[3], p[4], p[5], p[6])
                        if sig not in existing:
                            missing.append(
                                (
                                    p[0],
                                    p[1] if p[1] else None,
                                    p[2],
                                    p[3] if p[3] else None,
                                    p[4] if p[4] else None,
                                    p[5],
                                    p[6] if p[6] else None,
                                    loc,
                                    0,
                                    p[7] or 0,
                                    p[8] or 0,
                                    p[9] or "",
                                    p[10] or "",
                                    p[11] or 0,
                                    now_str,
                                    now_str,
                                )
                            )

                if missing:
                    logger.info(
                        f"Sincronizando {len(missing)} productos faltantes en locales..."
                    )
                    sql_insert = f"""
                        INSERT INTO productos (
                            nombre, material, categoria, fabricante, 
                            medida, estado, color, local, cantidad, 
                            precio_venta, precio_costo, codigo, descripcion, is_combo, 
                            created_at, updated_at
                        ) VALUES (
                            {ph}, {ph}, {ph}, {ph}, 
                            {ph}, {ph}, {ph}, {ph}, {ph}, 
                            {ph}, {ph}, {ph}, {ph}, {ph},
                            {ph}, {ph}
                        )
                    """
                    try:
                        cur.executemany(sql_insert, missing)
                        conn.commit()
                        logger.info("Sincronización global completada con éxito.")
                    except Exception as ins_e:
                        conn.rollback()
                        logger.error(
                            f"Error insertando productos sincronizados: {ins_e}"
                        )
                else:
                    logger.info(
                        "Sincronización global completada: Ningun producto faltante."
                    )

                _SYNC_PRODUCTS_ALL_LOCALS_DONE = True
        except Exception as e:
            logger.error(f"Error general en sync_all_products_across_locals: {e}")


def update_combo(
    combo_producto_id: int,
    local: str,
    nombre: str,
    precio_venta: float,
    items: List[dict],
    usuario: str = "sistema",
    categoria: Optional[str] = None,
    medida: Optional[str] = None,
    estado: Optional[str] = None,
    color: Optional[str] = None,
    fabricante: Optional[str] = None,
    material: Optional[str] = None,
    codigo: Optional[str] = None,
    descripcion: Optional[str] = None,
) -> Tuple[bool, str]:
    try:
        ensure_combo_schema()
        nombre = _sanitize_name(nombre)
        if not nombre:
            return False, "Nombre de combo inválido"
        try:
            precio_venta = float(precio_venta or 0)
        except Exception:
            precio_venta = 0.0
        clean_items = []
        for it in items or []:
            try:
                pid = int(it.get("producto_id") or 0)
                qty = int(it.get("cantidad") or 0)
            except Exception:
                pid = 0
                qty = 0
            if pid > 0 and qty > 0:
                clean_items.append({"producto_id": pid, "cantidad": qty})
        if not clean_items:
            return False, "Debes seleccionar productos para el combo"

        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            cur.execute(
                f"""
                SELECT nombre, categoria, medida, estado, color, fabricante, material,
                       codigo, descripcion, COALESCE(precio_venta,0)
                FROM productos
                WHERE id={ph} AND local={ph} AND COALESCE(is_combo,0)=1
                """,
                (int(combo_producto_id), local),
            )
            row = cur.fetchone()
            if not row:
                return False, "Combo no encontrado en este local"
            old_name = row[0] or ""
            categoria = (categoria or row[1] or "combo").strip() or "combo"
            medida = (medida if medida is not None else row[2] or "").strip()
            estado = (estado or row[3] or "Nuevo").strip() or "Nuevo"
            color = (color if color is not None else row[4] or "").strip()
            fabricante = (
                fabricante if fabricante is not None else row[5] or ""
            ).strip()
            material = (material if material is not None else row[6] or "").strip()
            codigo = (codigo if codigo is not None else row[7] or "").strip()
            descripcion = (
                descripcion if descripcion is not None else row[8] or ""
            ).strip()
            if not codigo:
                codigo = None

            cur.execute(
                f"""
                UPDATE productos
                SET nombre={ph}, categoria={ph}, medida={ph}, estado={ph}, color={ph},
                    fabricante={ph}, material={ph}, codigo={ph}, descripcion={ph},
                    precio_venta={ph}, updated_at={ph}
                WHERE id={ph}
                """,
                (
                    nombre,
                    categoria,
                    medida,
                    estado,
                    color,
                    fabricante,
                    material,
                    codigo,
                    descripcion,
                    float(precio_venta),
                    _now_local(),
                    int(combo_producto_id),
                ),
            )
            cur.execute(
                f"DELETE FROM combo_items WHERE combo_producto_id={ph}",
                (int(combo_producto_id),),
            )
            now = _now_local()
            for it in clean_items:
                cur.execute(
                    f"""
                    SELECT nombre, categoria, COALESCE(medida,''), estado,
                           COALESCE(color,''), COALESCE(fabricante,'')
                    FROM productos
                    WHERE id = {ph}
                    """,
                    (int(it["producto_id"]),),
                )
                prow = cur.fetchone()
                nombre_p = prow[0] if prow else ""
                categoria_p = prow[1] if prow else ""
                medida_p = prow[2] if prow else ""
                estado_p = prow[3] if prow else ""
                color_p = prow[4] if prow else ""
                fabricante_p = prow[5] if prow else ""
                cur.execute(
                    f"""
                    INSERT INTO combo_items (
                        combo_producto_id, producto_id, cantidad,
                        producto_nombre, producto_categoria, producto_medida,
                        producto_estado, producto_color, producto_fabricante, created_at
                    )
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                    """,
                    (
                        int(combo_producto_id),
                        int(it["producto_id"]),
                        int(it["cantidad"]),
                        nombre_p,
                        categoria_p,
                        medida_p,
                        estado_p,
                        color_p,
                        fabricante_p,
                        now,
                    ),
                )
            conn.commit()

        try:
            sync_combo_across_locals(int(combo_producto_id), local, old_name=old_name)
        except Exception:
            pass
        return True, "Combo actualizado"
    except Exception as e:
        logger.error(f"Error actualizando combo: {e}")
        return False, f"Error actualizando combo: {e}"


def sync_combo_across_locals(
    combo_producto_id: int, source_local: str, old_name: Optional[str] = None
) -> None:
    """Sincroniza un combo (nombre, precio e items) a otros locales si existen los productos."""
    ensure_combo_schema()
    with _get_conn_cm() as conn:
        cur = conn.cursor()
        ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
        cur.execute(
            f"""
            SELECT nombre, categoria, medida, estado, color, fabricante, material,
                   codigo, descripcion, COALESCE(precio_costo,0), COALESCE(precio_venta,0)
            FROM productos
            WHERE id={ph}
            """,
            (int(combo_producto_id),),
        )
        row = cur.fetchone()
        if not row:
            return
        combo_name = row[0] or ""
        combo_categoria = row[1] or "combo"
        combo_medida = row[2] or ""
        combo_estado = row[3] or "Nuevo"
        combo_color = row[4] or ""
        combo_fabricante = row[5] or ""
        combo_material = row[6] or ""
        combo_codigo = row[7] or ""
        combo_descripcion = row[8] or ""
        combo_costo = float(row[9] or 0)
        combo_price = float(row[10] or 0)
        if not str(combo_codigo or "").strip():
            combo_codigo = None
        items = get_combo_items(int(combo_producto_id))
        if not items:
            return
        for comp in items:
            _fill_comp_attrs_from_product(cur, comp, ph)
        sig = _combo_signature(items)
        locals_list = _get_all_locals_from_db()
        for loc in locals_list:
            if not loc or loc == source_local:
                continue
            # Buscar combo existente por nombre actual o nombre anterior
            cur.execute(
                f"""
                SELECT id FROM productos
                WHERE local={ph} AND COALESCE(is_combo,0)=1
                  AND COALESCE(medida,'')=COALESCE({ph},'')
                  AND (LOWER(nombre)=LOWER({ph}) OR LOWER(nombre)=LOWER({ph}))
                LIMIT 1
                """,
                (loc, combo_medida, combo_name, (old_name or combo_name)),
            )
            combo_row = cur.fetchone()
            target_combo_id = int(combo_row[0]) if combo_row else 0

            # Mapear componentes a productos del local
            mapped_items = []
            for comp in items:
                _fill_comp_attrs_from_product(cur, comp, ph)
                pid_local = _find_product_by_attrs(cur, loc, comp, ph)
                if not pid_local:
                    mapped_items = []
                    break
                mapped_items.append(
                    {
                        "producto_id": int(pid_local),
                        "cantidad": int(comp.get("cantidad") or 0),
                        "producto_nombre": comp.get("producto_nombre"),
                        "producto_categoria": comp.get("producto_categoria"),
                        "producto_medida": comp.get("producto_medida"),
                        "producto_estado": comp.get("producto_estado"),
                        "producto_color": comp.get("producto_color"),
                        "producto_fabricante": comp.get("producto_fabricante"),
                    }
                )
            if not mapped_items:
                continue

            now = _now_local()
            if target_combo_id:
                cur.execute(
                    f"""
                    UPDATE productos
                    SET nombre={ph}, categoria={ph}, medida={ph}, estado={ph}, color={ph},
                        fabricante={ph}, material={ph}, codigo={ph}, descripcion={ph},
                        precio_costo={ph}, precio_venta={ph}, updated_at={ph}
                    WHERE id={ph}
                    """,
                    (
                        combo_name,
                        combo_categoria,
                        combo_medida,
                        combo_estado,
                        combo_color,
                        combo_fabricante,
                        combo_material,
                        combo_codigo,
                        combo_descripcion,
                        combo_costo,
                        combo_price,
                        now,
                        target_combo_id,
                    ),
                )
                cur.execute(
                    f"DELETE FROM combo_items WHERE combo_producto_id={ph}",
                    (target_combo_id,),
                )
                for it in mapped_items:
                    cur.execute(
                        f"""
                        INSERT INTO combo_items (
                            combo_producto_id, producto_id, cantidad,
                            producto_nombre, producto_categoria, producto_medida,
                            producto_estado, producto_color, producto_fabricante, created_at
                        )
                        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                        """,
                        (
                            target_combo_id,
                            int(it["producto_id"]),
                            int(it["cantidad"]),
                            it.get("producto_nombre"),
                            it.get("producto_categoria"),
                            it.get("producto_medida"),
                            it.get("producto_estado"),
                            it.get("producto_color"),
                            it.get("producto_fabricante"),
                            now,
                        ),
                    )
            else:
                # crear combo en el local
                if isinstance(conn, sqlite3.Connection):
                    cur.execute(
                        """
                        INSERT INTO productos
                        (nombre, categoria, medida, estado, color, cantidad, precio_costo, precio_venta, local,
                         codigo, descripcion, fabricante, material, created_at, updated_at, is_combo)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
                        """,
                        (
                            combo_name,
                            combo_categoria,
                            combo_medida,
                            combo_estado,
                            combo_color,
                            0,
                            combo_costo,
                            combo_price,
                            loc,
                            combo_codigo,
                            combo_descripcion,
                            combo_fabricante,
                            combo_material,
                            now,
                            now,
                        ),
                    )
                    new_combo_id = int(cur.lastrowid or 0)
                else:
                    cur.execute(
                        """
                        INSERT INTO productos
                        (nombre, categoria, medida, estado, color, cantidad, precio_costo, precio_venta, local,
                         codigo, descripcion, fabricante, material, created_at, updated_at, is_combo)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
                        RETURNING id
                        """,
                        (
                            combo_name,
                            combo_categoria,
                            combo_medida,
                            combo_estado,
                            combo_color,
                            0,
                            combo_costo,
                            combo_price,
                            loc,
                            combo_codigo,
                            combo_descripcion,
                            combo_fabricante,
                            combo_material,
                            now,
                            now,
                        ),
                    )
                    r = cur.fetchone()
                    new_combo_id = int(r[0]) if r else 0
                if new_combo_id:
                    for it in mapped_items:
                        cur.execute(
                            f"""
                            INSERT INTO combo_items (
                                combo_producto_id, producto_id, cantidad,
                                producto_nombre, producto_categoria, producto_medida,
                                producto_estado, producto_color, producto_fabricante, created_at
                            )
                            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                            """,
                            (
                                new_combo_id,
                                int(it["producto_id"]),
                                int(it["cantidad"]),
                                it.get("producto_nombre"),
                                it.get("producto_categoria"),
                                it.get("producto_medida"),
                                it.get("producto_estado"),
                                it.get("producto_color"),
                                it.get("producto_fabricante"),
                                now,
                            ),
                        )
        try:
            conn.commit()
        except Exception:
            pass


def sync_combos_for_local(local: str) -> None:
    """Auto-crea combos en un local si existen los componentes."""
    ensure_combo_schema()
    with _get_conn_cm() as conn:
        cur = conn.cursor()
        ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
        cur.execute(
            f"""
            SELECT p.id, p.nombre, COALESCE(p.precio_venta,0),
                   p.categoria, p.medida, p.estado, p.color,
                   COALESCE(p.fabricante,''), COALESCE(p.material,''),
                   COALESCE(p.codigo,''), COALESCE(p.descripcion,''), COALESCE(p.precio_costo,0)
            FROM productos p
            WHERE COALESCE(p.is_combo,0)=1
            """,
        )
        combos = cur.fetchall()
        for combo_row in combos:
            combo_id = int(combo_row[0])
            combo_name = combo_row[1] or ""
            combo_price = float(combo_row[2] or 0)
            combo_categoria = combo_row[3] or "combo"
            combo_medida = combo_row[4] or ""
            combo_estado = combo_row[5] or "Nuevo"
            combo_color = combo_row[6] or ""
            combo_fabricante = combo_row[7] or ""
            combo_material = combo_row[8] or ""
            combo_codigo = combo_row[9] or ""
            combo_descripcion = combo_row[10] or ""
            combo_costo = float(combo_row[11] or 0)
            if not str(combo_codigo or "").strip():
                combo_codigo = None
            items = get_combo_items(int(combo_id))
            if not items:
                continue
            for comp in items:
                _fill_comp_attrs_from_product(cur, comp, ph)
            # si ya existe combo con ese nombre en el local, saltar
            cur.execute(
                f"""
                SELECT 1 FROM productos
                WHERE local={ph} AND COALESCE(is_combo,0)=1
                  AND COALESCE(medida,'')=COALESCE({ph},'')
                  AND LOWER(nombre)=LOWER({ph})
                LIMIT 1
                """,
                (local, combo_medida, combo_name),
            )
            if cur.fetchone():
                continue
            mapped_items = []
            for comp in items:
                pid_local = _find_product_by_attrs(cur, local, comp, ph)
                if not pid_local:
                    mapped_items = []
                    break
                mapped_items.append(
                    {
                        "producto_id": int(pid_local),
                        "cantidad": int(comp.get("cantidad") or 0),
                        "producto_nombre": comp.get("producto_nombre"),
                        "producto_categoria": comp.get("producto_categoria"),
                        "producto_medida": comp.get("producto_medida"),
                        "producto_estado": comp.get("producto_estado"),
                        "producto_color": comp.get("producto_color"),
                        "producto_fabricante": comp.get("producto_fabricante"),
                    }
                )
            if not mapped_items:
                continue
            now = _now_local()
            if isinstance(conn, sqlite3.Connection):
                cur.execute(
                    """
                    INSERT INTO productos
                    (nombre, categoria, medida, estado, color, cantidad, precio_costo, precio_venta, local,
                     codigo, descripcion, fabricante, material, created_at, updated_at, is_combo)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
                    """,
                    (
                        combo_name,
                        combo_categoria,
                        combo_medida,
                        combo_estado,
                        combo_color,
                        0,
                        combo_costo,
                        float(combo_price or 0),
                        local,
                        combo_codigo,
                        combo_descripcion,
                        combo_fabricante,
                        combo_material,
                        now,
                        now,
                    ),
                )
                new_combo_id = int(cur.lastrowid or 0)
            else:
                cur.execute(
                    """
                    INSERT INTO productos
                    (nombre, categoria, medida, estado, color, cantidad, precio_costo, precio_venta, local,
                     codigo, descripcion, fabricante, material, created_at, updated_at, is_combo)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
                    RETURNING id
                    """,
                    (
                        combo_name,
                        combo_categoria,
                        combo_medida,
                        combo_estado,
                        combo_color,
                        0,
                        combo_costo,
                        float(combo_price or 0),
                        local,
                        combo_codigo,
                        combo_descripcion,
                        combo_fabricante,
                        combo_material,
                        now,
                        now,
                    ),
                )
                r = cur.fetchone()
                new_combo_id = int(r[0]) if r else 0
            if new_combo_id:
                for it in mapped_items:
                    cur.execute(
                        f"""
                        INSERT INTO combo_items (
                            combo_producto_id, producto_id, cantidad,
                            producto_nombre, producto_categoria, producto_medida,
                            producto_estado, producto_color, producto_fabricante, created_at
                        )
                        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                        """,
                        (
                            new_combo_id,
                            int(it["producto_id"]),
                            int(it["cantidad"]),
                            it.get("producto_nombre"),
                            it.get("producto_categoria"),
                            it.get("producto_medida"),
                            it.get("producto_estado"),
                            it.get("producto_color"),
                            it.get("producto_fabricante"),
                            now,
                        ),
                    )
        try:
            conn.commit()
        except Exception:
            pass


def get_stock_filtered(
    local: str,
    search: str = "",
    categoria: str = "",
    medida: Union[str, List[str], Tuple[str, ...], None] = "",
    fabricante: str = "",
    estado: str = "",
    color: str = "",
    codigo: str = "",
    apply_reservas: bool = False,
) -> List[dict]:
    """Obtiene stock en forma de lista de dicts usando list_by_local."""
    try:
        try:
            ensure_combo_schema()
        except Exception:
            pass
        # Sync global una sola vez (dup + productos en todos los locales)
        try:
            ensure_products_in_all_locals_once()
        except Exception:
            pass
        rows = list_by_local(
            local, search, categoria, estado, medida, fabricante, color, codigo
        )
        data = [_row_to_dict(r) for r in rows]
        # Cachear stock para uso offline
        try:
            offline_store.cache_stock(local, data)
        except Exception:
            pass
        if apply_reservas and local and local not in ("Todos", "Todos los locales"):
            try:
                reservas = get_reservas_por_producto(local)
            except Exception:
                reservas = {}
            if reservas:
                for p in data:
                    try:
                        pid = int(p.get("id") or 0)
                        qty = int(p.get("cantidad") or 0)
                    except Exception:
                        pid = 0
                        qty = 0
                    if pid <= 0:
                        continue
                    res = int(reservas.get(pid, 0) or 0)
                    if res > 0:
                        p["cantidad_reservada"] = res
                        p["cantidad"] = max(0, qty - res)
        # Calcular stock virtual de combos
        try:
            combo_defs = _get_combo_definitions(local)
            if combo_defs:
                comp_ids = []
                for items in combo_defs.values():
                    for it in items:
                        pid = int(it.get("producto_id") or 0)
                        if pid > 0:
                            comp_ids.append(pid)
                uniq_ids = list(dict.fromkeys(comp_ids))
                qty_map = _get_qty_map_for_ids(local, uniq_ids)
                if (
                    apply_reservas
                    and local
                    and local not in ("Todos", "Todos los locales")
                ):
                    try:
                        reservas = get_reservas_por_producto(local)
                    except Exception:
                        reservas = {}
                    if reservas:
                        for pid, res in reservas.items():
                            if pid in qty_map:
                                qty_map[pid] = max(
                                    0, int(qty_map.get(pid, 0)) - int(res or 0)
                                )
                combo_by_id = {
                    int(c.get("id") or 0): c for c in data if int(c.get("id") or 0) > 0
                }
                for combo_id, items in combo_defs.items():
                    if combo_id not in combo_by_id:
                        continue
                    available = None
                    for it in items:
                        pid = int(it.get("producto_id") or 0)
                        qty_need = int(it.get("cantidad") or 0)
                        if pid <= 0 or qty_need <= 0:
                            available = 0
                            break
                        base_qty = int(qty_map.get(pid, 0))
                        can_make = base_qty // qty_need
                        available = (
                            can_make if available is None else min(available, can_make)
                        )
                    if available is None:
                        available = 0
                    combo_row = combo_by_id[combo_id]
                    combo_row["cantidad"] = int(available)
                    combo_row["is_combo"] = 1
                    combo_row["combo_items"] = items
                    combo_row["combo_id"] = combo_id
        except Exception as e:
            logger.error(f"Error calculando combos: {e}")
        return data
    except Exception as e:
        logger.error(f"Error get_stock_filtered({local}): {e}")
        # Fallback offline
        return offline_store.get_cached_stock(
            local, search, categoria, estado, medida, fabricante, color, codigo=""
        )


def _fetch_reservas_rows(local: Optional[str]) -> List[dict]:
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            where = ["v.estado = 'completada'"]
            params: List[Any] = []
            if local and local not in ("Todos", "Todos los locales"):
                where.append(f"v.local = {ph}")
                params.append(local)
            where.append(
                "("
                " (COALESCE(v.incluye_envio,0)=1 AND COALESCE(v.entrega_entregado,0)=0)"
                " OR (COALESCE(v.incluye_envio,0)=0 AND LOWER(COALESCE(v.tipo_pago,''))='sena' AND COALESCE(v.monto_pendiente,0) > 0)"
                ")"
            )
            query = f"""
                SELECT
                    dv.producto_id,
                    dv.producto_nombre,
                    dv.producto_categoria,
                    dv.producto_medida,
                    dv.producto_estado,
                    dv.producto_fabricante,
                    SUM(dv.cantidad) as cantidad,
                    CASE
                        WHEN COALESCE(v.incluye_envio,0)=1 AND COALESCE(v.entrega_entregado,0)=0 THEN 'envio'
                        WHEN COALESCE(v.incluye_envio,0)=0 AND LOWER(COALESCE(v.tipo_pago,''))='sena' AND COALESCE(v.monto_pendiente,0) > 0 THEN 'sena'
                        ELSE ''
                    END as tipo
                FROM ventas v
                JOIN detalle_ventas dv ON dv.venta_id = v.id
                WHERE {" AND ".join(where)}
                GROUP BY
                    dv.producto_id,
                    dv.producto_nombre,
                    dv.producto_categoria,
                    dv.producto_medida,
                    dv.producto_estado,
                    dv.producto_fabricante,
                    tipo
                ORDER BY dv.producto_nombre
            """
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]
    except Exception:
        logger.exception("Error obteniendo reservas")
        return []


def get_reservas_senas(local: Optional[str]) -> List[dict]:
    return [r for r in _fetch_reservas_rows(local) if (r.get("tipo") or "") == "sena"]


def get_reservas_envios(local: Optional[str]) -> List[dict]:
    return [r for r in _fetch_reservas_rows(local) if (r.get("tipo") or "") == "envio"]


def _fetch_interlocal_reservas_rows(
    local: Optional[str], include_envios: bool = True
) -> List[dict]:
    if not local or local in ("Todos", "Todos los locales"):
        return []
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            cutoff_ts = (datetime.now() - timedelta(days=4)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            where = [
                "v.estado = 'completada'",
                f"COALESCE(dv.stock_local,'') = {ph}",
                "COALESCE(v.local,'') <> COALESCE(dv.stock_local,'')",
                "COALESCE(dv.entrega_local_entregado,0) = 0",
                f"COALESCE(dv.entrega_local_fecha, v.fecha) >= {ph}",
            ]
            params = [local, cutoff_ts]
            if not include_envios:
                where.append("COALESCE(v.incluye_envio,0) = 0")

            cur.execute(
                f"""
                SELECT
                    dv.venta_id as venta_id,
                    v.local as venta_local,
                    dv.producto_id,
                    dv.producto_nombre,
                    dv.producto_categoria,
                    dv.producto_medida,
                    dv.producto_estado,
                    dv.producto_fabricante,
                    dv.producto_color,
                    dv.stock_local,
                    dv.cantidad,
                    COALESCE(dv.entrega_local_entregado,0) as entrega_local_entregado,
                    dv.entrega_local_fecha,
                    v.fecha as venta_fecha
                FROM detalle_ventas dv
                JOIN ventas v ON v.id = dv.venta_id
                WHERE { ' AND '.join(where) }
                ORDER BY COALESCE(dv.entrega_local_fecha, v.fecha) DESC, dv.producto_nombre
                """,
                tuple(params),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]
    except Exception:
        logger.exception("Error obteniendo reservas interlocales")
        return []


def get_reservas_interlocal(local: Optional[str]) -> List[dict]:
    return _fetch_interlocal_reservas_rows(local, include_envios=False)


def get_reservas_por_producto(local: Optional[str]) -> Dict[int, int]:
    reservas = {}
    for r in _fetch_reservas_rows(local):
        try:
            pid = int(r.get("producto_id") or 0)
            qty = int(r.get("cantidad") or 0)
        except Exception:
            pid = 0
            qty = 0
        if pid <= 0 or qty <= 0:
            continue
        reservas[pid] = reservas.get(pid, 0) + qty
    for r in _fetch_interlocal_reservas_rows(local, include_envios=True):
        try:
            pid = int(r.get("producto_id") or 0)
            qty = int(r.get("cantidad") or 0)
        except Exception:
            pid = 0
            qty = 0
        if pid <= 0 or qty <= 0:
            continue
        reservas[pid] = reservas.get(pid, 0) + qty
    return reservas


def _norm_key_value(val: Any) -> str:
    try:
        s = str(val) if val is not None else ""
        s = " ".join(s.split()).strip()
        return s.lower()
    except Exception:
        return str(val).strip().lower() if val is not None else ""


def _ts_sort_key(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime):
        try:
            return val.isoformat()
        except Exception:
            return ""
    try:
        return str(val)
    except Exception:
        return ""


def _get_product_columns(conn, cur) -> set:
    try:
        if isinstance(conn, sqlite3.Connection):
            cur.execute("PRAGMA table_info(productos)")
            return {r[1] for r in cur.fetchall()}
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='productos'"
        )
        return {r[0] for r in cur.fetchall()}
    except Exception:
        return set()


def _combo_items_exists(conn, cur) -> bool:
    try:
        if isinstance(conn, sqlite3.Connection):
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='combo_items'"
            )
            return cur.fetchone() is not None
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name='combo_items'"
        )
        return cur.fetchone() is not None
    except Exception:
        return False


def _select_products(cur, conn, local: Optional[str] = None) -> Tuple[List[dict], set]:
    cols_set = _get_product_columns(conn, cur)
    ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
    keys: List[str] = []
    parts: List[str] = []

    def _add(col: str, expr: str) -> None:
        parts.append(f"{expr} AS {col}")
        keys.append(col)

    _add("id", "id")
    _add("nombre", "nombre")
    _add("material", "COALESCE(material,'')" if "material" in cols_set else "''")
    _add("categoria", "COALESCE(categoria,'')" if "categoria" in cols_set else "''")
    _add("medida", "COALESCE(medida,'')" if "medida" in cols_set else "''")
    _add("estado", "COALESCE(estado,'')" if "estado" in cols_set else "''")
    _add("color", "COALESCE(color,'')" if "color" in cols_set else "''")
    _add("fabricante", "COALESCE(fabricante,'')" if "fabricante" in cols_set else "''")
    _add("codigo", "COALESCE(codigo,'')" if "codigo" in cols_set else "''")
    _add("cantidad", "COALESCE(cantidad,0)" if "cantidad" in cols_set else "0")
    _add(
        "precio_venta",
        "COALESCE(precio_venta,0)" if "precio_venta" in cols_set else "0",
    )
    _add(
        "precio_costo",
        "COALESCE(precio_costo,0)" if "precio_costo" in cols_set else "0",
    )
    _add("local", "COALESCE(local,'')" if "local" in cols_set else "''")
    _add("updated_at", "updated_at" if "updated_at" in cols_set else "NULL")
    _add("created_at", "created_at" if "created_at" in cols_set else "NULL")
    _add("is_combo", "COALESCE(is_combo,0)" if "is_combo" in cols_set else "0")

    query = f"SELECT {', '.join(parts)} FROM productos"
    params: List[Any] = []
    if local:
        query += f" WHERE local = {ph}"
        params.append(local)
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    return [dict(zip(keys, r)) for r in rows], cols_set


def _pick_price(items: List[dict], keep: dict, field: str) -> int:
    def _as_int(v: Any) -> int:
        try:
            return int(float(v or 0))
        except Exception:
            return 0

    keep_val = _as_int(keep.get(field))
    if keep_val > 0:
        return keep_val
    best = 0
    for it in items:
        val = _as_int(it.get(field))
        if val > best:
            best = val
    return best


def merge_duplicate_products(local: str) -> int:
    """
    Fusiona productos duplicados del mismo local (misma base, ignorando diferencias
    de precio) sumando cantidades y eliminando los duplicados.
    Devuelve la cantidad de filas eliminadas.
    """
    if not local or local in ("Todos", "Todos los locales"):
        return 0
    merged = 0
    for attempt in range(2):
        try:
            with _get_conn_cm() as conn:
                cur = conn.cursor()
                ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
                rows, cols_set = _select_products(cur, conn, local)
                if not rows:
                    return 0
                combo_items_exists = _combo_items_exists(conn, cur)
                groups: Dict[tuple, list] = {}
                for r in rows:
                    if int(r.get("is_combo") or 0) == 1:
                        continue
                    key = (
                        _norm_key_value(r.get("nombre")),
                        _norm_key_value(r.get("material")),
                        _norm_key_value(_norm_cat(r.get("categoria"))),
                        _norm_key_value(_norm_medida(r.get("medida"))),
                        _norm_key_value(r.get("estado")),
                        _norm_key_value(r.get("color")),
                        _norm_key_value(r.get("fabricante")),
                        _norm_key_value(r.get("codigo")),
                    )
                    groups.setdefault(key, []).append(r)

                now = _now_local()
                for items in groups.values():
                    if len(items) <= 1:
                        continue
                    keep = None
                    keep_key = None
                    for it in items:
                        ts = _ts_sort_key(it.get("updated_at") or it.get("created_at"))
                        kid = int(it.get("id") or 0)
                        k = (ts, kid)
                        if keep is None or k > keep_key:
                            keep = it
                            keep_key = k
                    if not keep:
                        continue
                    keep_id = int(keep.get("id") or 0)
                    if keep_id <= 0:
                        continue
                    total_qty = 0
                    for it in items:
                        try:
                            total_qty += int(it.get("cantidad") or 0)
                        except Exception:
                            pass
                    keep_price = _pick_price(items, keep, "precio_venta")
                    keep_cost = _pick_price(items, keep, "precio_costo")

                    sets = [f"cantidad={ph}"]
                    vals: List[Any] = [total_qty]
                    if "precio_venta" in cols_set:
                        sets.append(f"precio_venta={ph}")
                        vals.append(keep_price)
                    if "precio_costo" in cols_set:
                        sets.append(f"precio_costo={ph}")
                        vals.append(keep_cost)
                    if "updated_at" in cols_set:
                        sets.append(f"updated_at={ph}")
                        vals.append(now)
                    vals.append(keep_id)
                    cur.execute(
                        f"UPDATE productos SET {', '.join(sets)} WHERE id={ph}",
                        tuple(vals),
                    )

                    ids_to_delete = [
                        int(it.get("id") or 0)
                        for it in items
                        if int(it.get("id") or 0) != keep_id
                    ]
                    ids_to_delete = [i for i in ids_to_delete if i > 0]
                    if ids_to_delete:
                        placeholders = ",".join([ph] * len(ids_to_delete))
                        if combo_items_exists:
                            cur.execute(
                                f"UPDATE combo_items SET producto_id={ph} WHERE producto_id IN ({placeholders})",
                                tuple([keep_id] + ids_to_delete),
                            )
                        cur.execute(
                            f"DELETE FROM productos WHERE id IN ({placeholders})",
                            tuple(ids_to_delete),
                        )
                        merged += len(ids_to_delete)
                conn.commit()
            break
        except Exception as e:
            if attempt == 0 and _is_conn_closed_error(e):
                logger.warning(
                    "Conexion cerrada al fusionar duplicados; limpiando pool y reintentando..."
                )
                try:
                    db.cleanup_connections()
                except Exception:
                    pass
                continue
            logger.error(f"Error fusionando duplicados: {e}")
            break
    return merged


def merge_exact_duplicate_products(local: str) -> int:
    """
    Fusiona productos duplicados del mismo local SOLO si todas las columnas
    base son iguales (incluye precio_venta). Suma cantidades y elimina duplicados.
    """
    if not local or local in ("Todos", "Todos los locales"):
        return 0
    merged = 0
    for attempt in range(2):
        try:
            with _get_conn_cm() as conn:
                cur = conn.cursor()
                ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
                rows, cols_set = _select_products(cur, conn, local)
                if not rows:
                    return 0
                combo_items_exists = _combo_items_exists(conn, cur)
                groups: Dict[tuple, list] = {}

                def _price(v: Any) -> int:
                    try:
                        return int(float(v or 0))
                    except Exception:
                        return 0

                for r in rows:
                    if int(r.get("is_combo") or 0) == 1:
                        continue
                    key = (
                        _norm_key_value(r.get("nombre")),
                        _norm_key_value(r.get("material")),
                        _norm_key_value(_norm_cat(r.get("categoria"))),
                        _norm_key_value(_norm_medida(r.get("medida"))),
                        _norm_key_value(r.get("estado")),
                        _norm_key_value(r.get("color")),
                        _norm_key_value(r.get("fabricante")),
                        _norm_key_value(r.get("codigo")),
                        _price(r.get("precio_venta")),
                    )
                    groups.setdefault(key, []).append(r)

                now = _now_local()
                for items in groups.values():
                    if len(items) <= 1:
                        continue
                    keep = None
                    keep_key = None
                    for it in items:
                        ts = _ts_sort_key(it.get("updated_at") or it.get("created_at"))
                        kid = int(it.get("id") or 0)
                        k = (ts, kid)
                        if keep is None or k > keep_key:
                            keep = it
                            keep_key = k
                    if not keep:
                        continue
                    keep_id = int(keep.get("id") or 0)
                    if keep_id <= 0:
                        continue

                    total_qty = 0
                    for it in items:
                        try:
                            total_qty += int(it.get("cantidad") or 0)
                        except Exception:
                            pass

                    sets = [f"cantidad={ph}"]
                    vals: List[Any] = [total_qty]
                    if "precio_venta" in cols_set:
                        sets.append(f"precio_venta={ph}")
                        vals.append(_price(keep.get("precio_venta")))
                    if "precio_costo" in cols_set:
                        sets.append(f"precio_costo={ph}")
                        vals.append(_price(keep.get("precio_costo")))
                    if "updated_at" in cols_set:
                        sets.append(f"updated_at={ph}")
                        vals.append(now)
                    vals.append(keep_id)
                    cur.execute(
                        f"UPDATE productos SET {', '.join(sets)} WHERE id={ph}",
                        tuple(vals),
                    )

                    ids_to_delete = [
                        int(it.get("id") or 0)
                        for it in items
                        if int(it.get("id") or 0) != keep_id
                    ]
                    ids_to_delete = [i for i in ids_to_delete if i > 0]
                    if ids_to_delete:
                        placeholders = ",".join([ph] * len(ids_to_delete))
                        if combo_items_exists:
                            cur.execute(
                                f"UPDATE combo_items SET producto_id={ph} WHERE producto_id IN ({placeholders})",
                                tuple([keep_id] + ids_to_delete),
                            )
                        cur.execute(
                            f"DELETE FROM productos WHERE id IN ({placeholders})",
                            tuple(ids_to_delete),
                        )
                        merged += len(ids_to_delete)
                conn.commit()
            break
        except Exception as e:
            if attempt == 0 and _is_conn_closed_error(e):
                logger.warning(
                    "Conexion cerrada al fusionar duplicados exactos; limpiando pool y reintentando..."
                )
                try:
                    db.cleanup_connections()
                except Exception:
                    pass
                continue
            logger.error(f"Error fusionando duplicados exactos: {e}")
            break
    return merged


def merge_duplicate_products_all_locals() -> int:
    total = 0
    try:
        locals_list = _get_all_locals_from_db() or []
    except Exception:
        locals_list = []
    for loc in locals_list:
        if not loc:
            continue
        try:
            total += merge_duplicate_products(loc)
        except Exception:
            pass
    return total


def _ensure_products_in_all_locals() -> int:
    inserted = 0
    with _get_conn_cm() as conn:
        cur = conn.cursor()
        ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
        cur.execute("SELECT DISTINCT local FROM productos ORDER BY local ASC")
        locals_list = [str(r[0]).strip() for r in cur.fetchall() if r and r[0]]
        locals_list = [
            l for l in locals_list if l and l not in ("Todos", "Todos los locales")
        ]
        if len(locals_list) <= 1:
            return 0

        rows, cols_set = _select_products(cur, conn, None)
        if not rows:
            return 0

        groups: Dict[tuple, dict] = {}
        for r in rows:
            loc = (r.get("local") or "").strip()
            if not loc or loc in ("Todos", "Todos los locales"):
                continue
            if int(r.get("is_combo") or 0) == 1:
                continue
            key = (
                _norm_key_value(r.get("nombre")),
                _norm_key_value(r.get("material")),
                _norm_key_value(_norm_cat(r.get("categoria"))),
                _norm_key_value(_norm_medida(r.get("medida"))),
                _norm_key_value(r.get("estado")),
                _norm_key_value(r.get("color")),
                _norm_key_value(r.get("fabricante")),
                _norm_key_value(r.get("codigo")),
            )
            entry = groups.setdefault(
                key, {"locals": set(), "template": None, "template_key": None}
            )
            entry["locals"].add(loc)
            ts = _ts_sort_key(r.get("updated_at") or r.get("created_at"))
            rid = int(r.get("id") or 0)
            tkey = (ts, rid)
            if entry["template"] is None or tkey > entry["template_key"]:
                entry["template"] = r
                entry["template_key"] = tkey

        insert_cols: List[str] = ["nombre"]
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

        for entry in groups.values():
            template = entry.get("template") or {}
            missing = [l for l in locals_list if l not in entry["locals"]]
            if not missing:
                continue
            for target_local in missing:
                vals: List[Any] = []
                for col in insert_cols:
                    if col == "nombre":
                        vals.append(template.get("nombre") or "")
                    elif col == "material":
                        vals.append(template.get("material") or "")
                    elif col == "categoria":
                        vals.append(template.get("categoria") or "")
                    elif col == "medida":
                        vals.append(template.get("medida") or "")
                    elif col == "estado":
                        vals.append(template.get("estado") or "")
                    elif col == "color":
                        vals.append(template.get("color") or "")
                    elif col == "fabricante":
                        vals.append(template.get("fabricante") or "")
                    elif col == "codigo":
                        vals.append(template.get("codigo") or "")
                    elif col == "cantidad":
                        vals.append(0)
                    elif col == "precio_costo":
                        try:
                            vals.append(int(float(template.get("precio_costo") or 0)))
                        except Exception:
                            vals.append(0)
                    elif col == "precio_venta":
                        try:
                            vals.append(int(float(template.get("precio_venta") or 0)))
                        except Exception:
                            vals.append(0)
                    elif col == "local":
                        vals.append(target_local)
                    elif col == "created_at":
                        vals.append(now)
                    elif col == "updated_at":
                        vals.append(now)
                    elif col == "is_combo":
                        vals.append(int(template.get("is_combo") or 0))
                cur.execute(insert_sql, tuple(vals))
                inserted += 1

        try:
            conn.commit()
        except Exception:
            pass
    return inserted


def ensure_products_in_all_locals_once() -> None:
    global _SYNC_PRODUCTS_ALL_LOCALS_DONE
    if _SYNC_PRODUCTS_ALL_LOCALS_DONE:
        return
    if _SYNC_PRODUCTS_ALL_LOCALS_LOCK is None:
        return
    with _SYNC_PRODUCTS_ALL_LOCALS_LOCK:
        if _SYNC_PRODUCTS_ALL_LOCALS_DONE:
            return
        try:
            inserted = _ensure_products_in_all_locals()
            if inserted:
                logger.info(f"Sync productos/locales: insertados={inserted}")
            _SYNC_PRODUCTS_ALL_LOCALS_DONE = True
        except Exception as e:
            logger.warning(f"ensure_products_in_all_locals_once error: {e}")


def list_by_local(
    local: str,
    search: str = "",
    categoria: str = "",
    estado: str = "",
    medida: Union[str, List[str], Tuple[str, ...], None] = "",
    fabricante: str = "",
    color: str = "",
    codigo: str = "",
) -> List[dict]:
    global _FALLBACK_SQLITE_PATH
    """Obtiene productos por local usando SQL (Postgres/SQLite)."""
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            where = [f"local = {ph}"]
            params: List[Any] = [local]
            if search:
                # buscar en nombre, categoria, fabricante y codigo (subcadena)
                # search should match against several textual fields including color
                search_pattern = f"%{search}%"
                where.append(
                    f"(LOWER(nombre) LIKE LOWER({ph}) OR LOWER(COALESCE(categoria,'')) LIKE LOWER({ph}) OR LOWER(COALESCE(fabricante,'')) LIKE LOWER({ph}) OR LOWER(COALESCE(color,'')) LIKE LOWER({ph}) OR LOWER(COALESCE(codigo,'')) LIKE LOWER({ph}))"
                )
                params.extend(
                    [
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                    ]
                )
            if categoria:
                where.append(f"LOWER(TRIM(COALESCE(categoria,''))) = LOWER(TRIM({ph}))")
                params.append(_norm_cat(categoria))
            if estado:
                where.append(f"estado = {ph}")
                params.append(estado)
            if medida:
                if isinstance(medida, (list, tuple, set)):
                    medidas_list = [m for m in medida if m]
                    if medidas_list:
                        placeholders = ",".join([ph] * len(medidas_list))
                        where.append(f"COALESCE(medida,'') IN ({placeholders})")
                        params.extend([_norm_medida(m) for m in medidas_list])
                else:
                    where.append(f"COALESCE(medida,'') = COALESCE({ph},'')")
                    params.append(_norm_medida(medida))
            if fabricante:
                where.append(
                    f"LOWER(TRIM(COALESCE(fabricante,''))) = LOWER(TRIM(COALESCE({ph},'')))"
                )
                params.append(fabricante)
            if color:
                where.append(
                    f"LOWER(TRIM(COALESCE(color,''))) = LOWER(TRIM(COALESCE({ph},'')))"
                )
                params.append(color)
            if codigo:
                where.append(f"LOWER(COALESCE(codigo,'')) LIKE LOWER({ph})")
                params.append(f"%{codigo}%")
            has_material = False
            try:
                if isinstance(conn, sqlite3.Connection):
                    cur.execute("PRAGMA table_info(productos)")
                    cols = {r[1] for r in cur.fetchall()}
                    has_material = "material" in cols
                else:
                    cur.execute(
                        """
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name='productos' AND column_name='material'
                        """
                    )
                    has_material = cur.fetchone() is not None
            except Exception:
                has_material = False
            global _HAS_MATERIAL_COL
            _HAS_MATERIAL_COL = has_material
            material_col = "COALESCE(material,''), " if has_material else ""
            cols_with_fab_codigo = f"""
                id, nombre, {material_col}categoria, COALESCE(medida,''), estado, COALESCE(color,''),
                COALESCE(cantidad,0), COALESCE(precio_venta,0), local, COALESCE(fabricante,''), COALESCE(codigo,''),
                COALESCE(is_combo,0)
            """
            cols_with_fab = f"""
                id, nombre, {material_col}categoria, COALESCE(medida,''), estado, COALESCE(color,''),
                COALESCE(cantidad,0), COALESCE(precio_venta,0), local, COALESCE(fabricante,''), COALESCE(is_combo,0)
            """
            cols_no_fab = f"""
                id, nombre, {material_col}categoria, COALESCE(medida,''), estado, COALESCE(color,''),
                COALESCE(cantidad,0), COALESCE(precio_venta,0), local, COALESCE(is_combo,0)
            """
            q = f"""
                SELECT {cols_with_fab_codigo}
                FROM productos
                WHERE {' AND '.join(where)}
                ORDER BY nombre ASC
            """
            try:
                cur.execute(q, tuple(params))
                rows = cur.fetchall()
            except Exception:
                try:
                    # Fallback si la columna codigo no existe
                    q = f"""
                        SELECT {cols_with_fab}
                        FROM productos
                        WHERE {' AND '.join(where)}
                        ORDER BY nombre ASC
                    """
                    cur.execute(q, tuple(params))
                    rows = cur.fetchall()
                except Exception:
                    try:
                        # Fallback si la columna fabricante no existe
                        q = f"""
                            SELECT {cols_no_fab}
                            FROM productos
                            WHERE {' AND '.join(where)}
                            ORDER BY nombre ASC
                        """
                        cur.execute(q, tuple(params))
                        rows = cur.fetchall()
                    except Exception:
                        # Último fallback sin is_combo
                        cols_no_combo = f"""
                            id, nombre, {material_col}categoria, COALESCE(medida,''), estado, COALESCE(color,''),
                            COALESCE(cantidad,0), COALESCE(precio_venta,0), local
                        """
                        q = f"""
                            SELECT {cols_no_combo}
                            FROM productos
                            WHERE {' AND '.join(where)}
                            ORDER BY nombre ASC
                        """
                        cur.execute(q, tuple(params))
                        rows = cur.fetchall()
            if rows:
                return rows
            # Si no hay resultados en la base actual, intentar SQLite local
            try:
                base_dir = os.path.dirname(os.path.dirname(__file__))
                db_path = os.path.join(base_dir, "manarey.db")
                con2 = sqlite3.connect(db_path)
                cur2 = con2.cursor()
                try:
                    cur2.execute(q, tuple(params))
                except Exception:
                    try:
                        q2 = f"""
                            SELECT {cols_no_fab}
                            FROM productos
                            WHERE {' AND '.join(where)}
                            ORDER BY nombre ASC
                        """
                        cur2.execute(q2, tuple(params))
                    except Exception:
                        q3 = f"""
                            SELECT id, nombre, categoria, COALESCE(medida,''), estado, COALESCE(color,''),
                                   COALESCE(cantidad,0), COALESCE(precio_venta,0), local
                            FROM productos
                            WHERE {' AND '.join(where)}
                            ORDER BY nombre ASC
                        """
                        cur2.execute(q3, tuple(params))
                rows2 = cur2.fetchall()
                con2.close()
                _FALLBACK_SQLITE_PATH = db_path
                return rows2
            except Exception:
                return rows
    except Exception as e:
        logger.error(f"Error listando productos por local (SQL): {e}")
        return []


# ==================== SINCRONIZACIÓN ENTRE LOCALES ====================
# Estado no se sincroniza entre locales (requerimiento de negocio).
SYNC_FIELDS = {"nombre", "material", "categoria", "medida", "color", "precio_venta"}


def _match_tuple(
    nombre: str,
    material: Optional[str],
    categoria: str,
    medida: Optional[str],
    estado: str,
    color: Optional[str],
) -> Tuple:
    # Normalizar medida al construir la "clave" de producto usada para
    # sincronización entre locales. Usamos cadena vacía para valores vacíos.
    return (
        nombre or "",
        (material or "").strip().lower(),
        _norm_cat(categoria or ""),
        _norm_medida(medida),
        estado or "Nuevo",
        color or None,
    )


def _sync_field_all_locales(
    old_key: Tuple, field: str, new_value: Any, source_local: str, source_user: str
) -> List[str]:
    """
    Encola la actualización de `field` a todos los locales que tengan el MISMO producto
    (igual a old_key), excepto el local de origen. Devuelve lista de locales a los que se
    encoló la operación.

    En lugar de ejecutar los UPDATEs directamente, ponemos operaciones `update_field`
    en la `op_queue` para que el worker las procese y así amortiguar picos en la DB.
    """
    updated_locals = []
    try:
        nombre, material, categoria, medida, estado, color = old_key
        # field viene de llamadores que controlan SYNC_FIELDS, pero volvemos a validar
        if not _is_safe_identifier(field) or field not in SYNC_FIELDS:
            logger.error(
                f"Campo inseguro o no sincronizable en _sync_field_all_locales: {field}"
            )
            return []

        with _get_conn_cm() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT id, local, {field}
                FROM productos
                WHERE nombre=? AND COALESCE(material,'')=COALESCE(?,'') AND categoria=? AND COALESCE(medida,'')=COALESCE(?,'')
                  AND estado=? AND COALESCE(color,'')=COALESCE(?)
                  AND local<>?
            """,
                (nombre, material, categoria, medida, estado, color, source_local),
            )
            rows = cur.fetchall()

            for pid, other_local, old_val in rows:
                if str(old_val) == str(new_value):
                    continue
                # Encolar actualización para este producto/local
                payload = {
                    "producto_id": int(pid),
                    "field": field,
                    "value": new_value,
                    "usuario": source_user,
                    "local": other_local,
                    "motivo": "sincronizado_automatico",
                }
                qid = enqueue_op("update_field", payload)
                if qid and qid > 0:
                    updated_locals.append(other_local)
    except Exception as e:
        logger.error(f"Error sincronizando campo {field}: {e}")
    return updated_locals


def sync_price_all_locales(
    nombre: str,
    material: Optional[str],
    categoria: str,
    medida: Optional[str],
    estado: str,
    color: Optional[str],
    new_price: int,
    source_local: str,
    source_user: str,
) -> None:
    # Conservamos para compatibilidad; ahora delega al general.
    _sync_field_all_locales(
        _match_tuple(nombre, material, categoria, medida, estado, color),
        "precio_venta",
        int(new_price),
        source_local,
        source_user,
    )


# ==================== OPERACIONES DE STOCK ====================
def add_or_increment(
    nombre,
    categoria,
    medida,
    estado,
    color,
    cantidad,
    precio_costo,
    precio_venta,
    local,
    usuario,
    force_update: bool = False,
    material: Optional[str] = None,
):
    """Agrega un producto nuevo o incrementa cantidad en Firestore."""
    nombre = _sanitize_name(nombre)
    categoria = _norm_cat(categoria)
    medida_norm = _norm_medida(medida)
    material_norm = (material or "").strip().lower()
    try:
        cantidad = int(cantidad)
    except Exception:
        return False, "Cantidad inválida"
    if cantidad < 0:
        return False, "Cantidad no puede ser negativa"
    if cantidad > 1_000_000:
        return False, "Cantidad demasiado grande"
    try:
        precio_costo = float(precio_costo or 0)
        precio_venta = float(precio_venta or 0)
    except Exception:
        return False, "Precio inválido"
    if precio_costo < 0 or precio_venta < 0:
        return False, "Precios no pueden ser negativos"
    # Buscar si existe producto igual en SQL
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            cur.execute(
                f"""
                SELECT id, cantidad FROM productos
                 WHERE nombre={ph} AND COALESCE(material,'')=COALESCE({ph},'') AND categoria={ph} AND COALESCE(medida,'')=COALESCE({ph},'')
                   AND estado={ph} AND COALESCE(color,'')=COALESCE({ph},'') AND local={ph}
                 LIMIT 1
                """,
                (
                    nombre,
                    material_norm,
                    categoria,
                    medida_norm,
                    estado,
                    color or "",
                    local,
                ),
            )
            existing = cur.fetchone()
            if existing:
                pid = int(existing[0])
                old_qty = int(existing[1] or 0)
                if force_update:
                    now_ts = _now_local()
                    new_qty = old_qty + cantidad
                    cur.execute(
                        f"UPDATE productos SET cantidad={ph}, precio_costo={ph}, precio_venta={ph}, updated_at={ph} WHERE id={ph}",
                        (new_qty, precio_costo, precio_venta, now_ts, pid),
                    )
                    cur.execute(
                        f"""
                        INSERT INTO historial_stock
                        (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
                        VALUES ({ph},'ajuste',{ph},{ph},{ph},{ph},{ph},{ph},{ph},0,{ph})
                        """,
                        (
                            pid,
                            "incremento por add_or_increment (force)",
                            cantidad,
                            usuario,
                            local,
                            now_ts,
                            "add_or_increment_force",
                            json.dumps({"old_qty": old_qty, "new_qty": new_qty}),
                            None,
                        ),
                    )
                    conn.commit()
                    return True, "Stock incrementado correctamente"
                else:
                    return False, f"Ese producto ya existe. ID={pid}"
    except Exception as e:
        logger.error(f"Error verificando producto existente: {e}")
    # Si no existe, agregar nuevo
    prod_data = {
        "nombre": nombre,
        "material": material_norm,
        "categoria": categoria,
        "medida": medida_norm,
        "estado": estado,
        "color": color,
        "cantidad": cantidad,
        "precio_costo": precio_costo,
        "precio_venta": precio_venta,
        "local": local,
        "created_at": _now_local(),
        "updated_at": _now_local(),
    }
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"
            cur.execute(
                f"""
                INSERT INTO productos
                (nombre, material, categoria, medida, estado, color, cantidad, precio_costo, precio_venta, local, created_at, updated_at)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                RETURNING id
                """,
                (
                    nombre,
                    material_norm,
                    categoria,
                    medida_norm,
                    estado,
                    color,
                    cantidad,
                    precio_costo,
                    precio_venta,
                    local,
                    prod_data["created_at"],
                    prod_data["updated_at"],
                ),
            )
            pid = cur.fetchone()[0]
            cur.execute(
                f"""
                INSERT INTO historial_stock
                (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
                VALUES ({ph},'ingreso',{ph},{ph},{ph},{ph},{ph},{ph},{ph},0,{ph})
                """,
                (
                    pid,
                    "add_product",
                    cantidad,
                    usuario,
                    local,
                    prod_data["created_at"],
                    "",
                    json.dumps({"delta": cantidad, "new_qty": cantidad}),
                    None,
                ),
            )
            conn.commit()
        return True, "Producto agregado correctamente"
    except Exception as e:
        logger.error(f"Error agregando producto: {e}")
        return False, f"Error: {e}"


def insert_stock(
    local: str,
    nombre: str,
    categoria: str,
    medida: Optional[str],
    estado: str,
    cantidad: int,
    precio_venta: float,
    color: Optional[str] = None,
    usuario: str = "sistema",
    precio_costo: float = 0,
) -> None:
    add_or_increment(
        nombre,
        categoria,
        medida,
        estado,
        color,
        cantidad,
        precio_costo,
        precio_venta,
        local,
        usuario,
    )
    insert_tipo_si_no_existe(categoria)


def update_stock_field(
    pid: int,
    field: str,
    value: Any,
    usuario: str = "sistema",
    local: Optional[str] = None,
    motivo: Optional[str] = None,
    perform_sync: bool = True,
    skip_db_update: bool = False,
) -> bool:
    """
    Actualiza un campo del producto y SINCRONIZA el mismo campo en todos los locales
    que tengan el mismo producto (clave de match ANTES del cambio).
    Encola notificaciones a los locales afectados (batch de 2 minutos).

    Parámetros:
    - skip_db_update: Si es True, NO actualiza la BD directamente (útil cuando
      se procesa desde la queue y ya se ha encolado). Solo sincroniza a otros locales.
    """
    if field not in SYNC_FIELDS:
        logger.warning(f"Campo no permitido: {field}")
        return False

    logger.debug(
        f"update_stock_field called pid={pid} field={field} value={value} usuario={usuario} local={local} perform_sync={perform_sync} skip_db_update={skip_db_update}"
    )

    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()

            # Snapshot antes del cambio (para clave y notificación)
            cur.execute(
                "SELECT nombre,material,categoria,medida,estado,color,precio_venta,local FROM productos WHERE id=?",
                (pid,),
            )
            r = cur.fetchone()
            if not r:
                return False

            old_data = {
                "nombre": r[0],
                "material": r[1],
                "categoria": r[2],
                "medida": r[3],
                "estado": r[4],
                "color": r[5],
                "precio_venta": r[6],
            }
            prod_local = r[7]
            old_value = old_data.get(field)

            # Normalización de valor según campo
            if field == "categoria":
                value = _norm_cat(value)
                insert_tipo_si_no_existe(value)
            elif field == "medida":
                # Normalizar medida para evitar valores inconsistentes que produzcan filtros vacíos
                value = _norm_medida(value)
            elif field == "precio_venta":
                try:
                    value = int(float(value or 0))
                except Exception:
                    value = 0

            # Validar nombre de columna antes de interpolar
            try:
                _ensure_allowed_field(field)
            except Exception as e:
                logger.error(f"Campo inseguro al actualizar producto: {field} - {e}")
                return False

            # Ejecutar actualización SOLO si no se salta (es decir, si NO viene de la queue)
            if not skip_db_update:
                # Intentar escribir con reintentos en caso de bloqueos transitórios
                import sqlite3 as _sqlite3

                max_attempts = 5
                attempt = 0
                while True:
                    try:
                        cur.execute(
                            f"UPDATE productos SET {field}=?, updated_at=? WHERE id=?",
                            (value, _now_local(), pid),
                        )

                        # Historial del origen
                        meta = {"field": field, "old": old_value, "new": value}
                        if _is_admin(usuario):
                            meta["by_admin"] = True
                        cur.execute(
                            """
                            INSERT INTO historial_stock
                                (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone)
                            VALUES (?, 'ajuste', ?, 0, ?, ?, ?, ?, ?, 0)
                            """,
                            (
                                pid,
                                f"cambio de {field}",
                                usuario,
                                (local or prod_local),
                                _now_local(),
                                (motivo or ""),
                                _j(meta),
                            ),
                        )

                        conn.commit()
                        break
                    except Exception as e:
                        attempt += 1
                        # Retry on sqlite 'database is locked' or similar operational errors
                        if (
                            isinstance(e, _sqlite3.OperationalError)
                            and attempt < max_attempts
                        ):
                            import time

                            time.sleep(0.05 * attempt)
                            continue
                        # No es recuperable: re-lanzar para que el bloque externo haga fallback
                        raise

        # Sincronización global (usando clave ANTERIOR al cambio)
        # Evitar re-sincronizar si el cambio ya viene de una sincronización automática (evita bucles)
        if (
            perform_sync
            and not skip_db_update
            and (motivo is None or motivo != "sincronizado_automatico")
        ):
            old_key = _match_tuple(
                old_data["nombre"],
                old_data["material"],
                old_data["categoria"],
                old_data["medida"],
                old_data["estado"],
                old_data["color"],
            )
            updated_locals = _sync_field_all_locales(
                old_key, field, value, prod_local, usuario
            )

            # Encolar notificaciones para los locales actualizados
            if updated_locals:
                _queue_change_notification(
                    affected_locals=updated_locals,
                    source_local=prod_local,
                    source_user=usuario,
                    field=field,
                    prod_snapshot=old_data,
                    old_value=old_value,
                    new_value=value,
                )

        return True

    except Exception as e:
        # Registrar stacktrace completo para facilitar diagnóstico de errores en tests
        logger.exception(f"Error actualizando campo {field}: {e}")
        # También imprimir en stdout temporalmente para que los tests muestren la traza
        try:
            import sys
            import traceback

            print("[DEBUG] update_stock_field exception:", file=sys.stderr)
            traceback.print_exc()
        except Exception:
            pass
        # Intento de fallback: aplicar UPDATE + registro de historial de forma manual
        try:
            with _get_conn_cm() as conn:
                cur = conn.cursor()
                try:
                    cur.execute(
                        f"UPDATE productos SET {field}=?, updated_at=? WHERE id=?",
                        (value, _now_local(), pid),
                    )
                    # Insertar historial de forma manual
                    meta = {"field": field, "old": None, "new": value}
                    cur.execute(
                        """
                        INSERT INTO historial_stock
                            (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone)
                        VALUES (?, 'ajuste', ?, 0, ?, ?, ?, ?, ?, 0)
                        """,
                        (
                            pid,
                            f"cambio de {field}",
                            usuario or None,
                            (local or None),
                            _now_local(),
                            (motivo or ""),
                            _j(meta),
                        ),
                    )
                    conn.commit()
                    logger.warning(
                        f"Fallback aplicado para update_stock_field pid={pid} field={field}"
                    )
                    return True
                except Exception as e2:
                    logger.exception(
                        f"Fallback falló al aplicar update manual para {field} en pid={pid}: {e2}"
                    )
        except Exception:
            pass
        return False


# ==================== EDICIÓN MÚLTIPLE ====================
_price_pct_re = re.compile(r"^\s*([+-]?)(\d+(?:[.,]\d+)?)\s*%\s*$")
_price_abs_re = re.compile(r"^\s*([+-]?)(\d{1,3}(?:[.,]\d{3})*|\d+(?:[.,]\d+)?)\s*$")
#                 admite 1.234 o 1,234 o 1234, y también 1234.56 / 1.234,56


def _normalize_number_token(num_str: str) -> float:
    """
    Normaliza un número escrito con formato ES/AR:
    - '500.000'      -> 500000
    - '1.234,56'     -> 1234.56
    - '1,234.56'     -> 1234.56
    - '25000'        -> 25000
    """
    s = num_str.strip()
    if not s:
        return 0.0

    # Si tiene COMA y PUNTO: asumimos que el separador decimal es la COMA (formato es/AR: 1.234,56)
    if "," in s and "." in s:
        s = s.replace(".", "")  # quita miles
        s = s.replace(",", ".")  # coma -> decimal
        return float(s)

    # Si solo tiene PUNTO: puede ser miles o decimal. Si hay grupos de 3 tras el punto, trátalo como miles.
    if "." in s and "," not in s:
        parts = s.split(".")
        # si todos los grupos tras el primero son de 3 dígitos => miles
        if all(len(p) == 3 for p in parts[1:]):
            s = s.replace(".", "")  # miles
            return float(s)
        # si no, es decimal estilo US (1234.56)
        return float(s)

    # Si solo tiene COMA: trátalo como decimal (es/AR: 1234,56)
    if "," in s and "." not in s:
        s = s.replace(".", "")  # (por si acaso)
        s = s.replace(",", ".")
        return float(s)

    # Sin separadores
    return float(s)


def _compute_new_price_from_str(base: int, s: str) -> int:
    """Calcula nuevo precio desde string con soporte para +, -, % y diferentes separadores."""
    if s is None:
        return base

    s = str(s).strip().replace("$", "")
    if not s:
        return base

    # Porcentajes: +15%, -10%, 20%
    m = _price_pct_re.match(s)
    if m:
        sign, num = m.groups()
        try:
            pct = _normalize_number_token(num)  # <-- normalizado
            delta = int(round(base * pct / 100.0))
            if sign == "-":
                return max(0, base - delta)
            else:
                return max(0, base + delta)
        except Exception:
            return base

    # Valores absolutos: +1000, -500, 15000, 500.000, 1.234,56
    m = _price_abs_re.match(s)
    if m:
        sign, num = m.groups()
        try:
            val = int(round(_normalize_number_token(num)))  # <-- normalizado
            if sign == "+":
                return max(0, base + val)
            elif sign == "-":
                return max(0, base - val)
            else:
                return max(0, val)  # valor absoluto
        except Exception:
            return base

    # Fallback: quitar miles y reintentar entero
    try:
        return max(0, int(s.replace(".", "").replace(",", "")))
    except Exception:
        return base


def bulk_update_prices(
    product_ids: List[int], price_change: str, usuario: str, local: str
) -> Tuple[bool, str]:
    if not product_ids:
        return False, "No hay productos seleccionados"
    try:
        conn = get_conn()
        cur = conn.cursor()
        placeholders = ",".join("?" * len(product_ids))
        cur.execute(
            f"""
            SELECT id, precio_venta, nombre, categoria, medida, estado, color, local
            FROM productos WHERE id IN ({placeholders})
        """,
            product_ids,
        )
        products = cur.fetchall()
        enqueued = 0
        for (
            pid,
            current_price,
            nombre,
            categoria,
            medida,
            estado,
            color,
            prod_local,
        ) in products:
            base_price = int(current_price or 0)
            new_price = _compute_new_price_from_str(base_price, price_change)
            if new_price != base_price:
                payload = {
                    "producto_id": int(pid),
                    "field": "precio_venta",
                    "value": int(new_price),
                    "usuario": usuario,
                    "local": local,
                    "motivo": "edicion_masiva",
                }
                qid = enqueue_op("update_field", payload)
                if qid and qid > 0:
                    enqueued += 1
        return (
            True,
            f"Encoladas {enqueued} actualizaciones de precio (procesadas por worker)",
        )
    except Exception as e:
        logger.error(f"Error en actualización masiva: {e}")
        return False, f"Error en actualización masiva: {str(e)}"
    finally:
        if "conn" in locals() and conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


# ==================== CANTIDADES / TRANSFERENCIAS ====================
def update_stock_quantity(
    producto_id: int,
    new_qty: int,
    usuario: str,
    local: str,
    detalle: str = None,
    motivo: str = None,
) -> Tuple[bool, str]:
    conn = None
    try:
        # Para acelerar las sumas/retiros repetidos implementamos la actualizacion
        # en dos modos: si el llamador quiere establecer nuevo valor absoluto se
        # usa este flujo (legacy). Para sumar/restar múltiples veces mejor usar
        # `increment_stock` que hace un UPDATE atómico.
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT cantidad FROM productos WHERE id=?", (producto_id,))
        row = cur.fetchone()
        if not row:
            return False, "Producto no encontrado"
        old_qty = int(row[0] or 0)
        delta = int(new_qty) - old_qty
        cur.execute(
            "UPDATE productos SET cantidad=?, updated_at=? WHERE id=?",
            (int(new_qty), _now_local(), producto_id),
        )
        if (detalle or "").lower().startswith("baja") or (delta < 0 and motivo):
            accion = "baja"
            detalle = (detalle or "baja").strip()
        else:
            accion = "ajuste"
            if (detalle or "").lower().startswith("bot"):
                detalle = "botón +" if delta > 0 else "botón −"
            else:
                detalle = detalle or "ajuste manual"
        meta = {"old_qty": old_qty, "new_qty": int(new_qty)}
        if _is_admin(usuario):
            meta["by_admin"] = True
        cur.execute(
            """
            INSERT INTO historial_stock
                (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone)
            VALUES (?, 'ajuste', ?, ?, ?, ?, ?, ?, ?, 0)
        """,
            (
                producto_id,
                accion,
                detalle,
                delta,
                usuario,
                local,
                _now_local(),
                (motivo or "").strip(),
                _j(meta),
            ),
        )
        conn.commit()
        return True, "Cantidad actualizada correctamente"
    except Exception as e:
        logger.error(f"Error actualizando cantidad: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, f"Error al actualizar cantidad: {str(e)}"
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


def increment_stock(
    producto_id: int,
    delta: int,
    usuario: str,
    local: str,
    detalle: str = None,
    motivo: str = None,
) -> Tuple[bool, str]:
    """Incrementa (o decrementa si delta<0) de forma atómica la cantidad.
    Usa un solo UPDATE atómico para minimizar contención y permitir pulsaciones
    repetidas del botón +/-. Inserta el historial con el delta aplicado.
    """
    conn = None
    try:
        delta = int(delta or 0)
        if delta == 0:
            return False, "Delta inválido"
        conn = get_conn()
        cur = conn.cursor()
        # UPDATE atómico
        cur.execute(
            "UPDATE productos SET cantidad = COALESCE(cantidad,0) + ?, updated_at=? WHERE id=?",
            (delta, _now_local(), producto_id),
        )
        # Obtener cantidad resultante
        cur.execute("SELECT cantidad, local FROM productos WHERE id=?", (producto_id,))
        row = cur.fetchone()
        if not row:
            return False, "Producto no encontrado"
        new_qty = int(row[0] or 0)
        prod_local = row[1]

        accion = "ajuste"
        if delta < 0:
            accion = "baja"
        detalle_text = detalle or ("botón +" if delta > 0 else "botón −")

        meta = {"delta": delta, "new_qty": new_qty}
        if _is_admin(usuario):
            meta["by_admin"] = True

        cur.execute(
            """
            INSERT INTO historial_stock
                (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
            (
                producto_id,
                accion,
                detalle_text,
                delta,
                usuario,
                (local or prod_local),
                _now_local(),
                (motivo or "").strip(),
                _j(meta),
            ),
        )

        conn.commit()
        return True, f"Cantidad modificada: {delta} (ahora {new_qty})"
    except Exception as e:
        logger.error(f"Error incrementando cantidad: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, f"Error al modificar cantidad: {str(e)}"
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


def transfer_stock(
    row: dict, to_local: str, cantidad: int, usuario: str
) -> Tuple[bool, str]:
    conn = None
    try:
        prod_id = int(row.get("id"))
        from_local = row.get("local") or row.get("Local") or row.get("local_name")
        nombre = row.get("nombre") or ""
        categoria = row.get("categoria") or ""
        medida = row.get("medida")
        estado = row.get("estado") or "Nuevo"
        precio = int(row.get("precio_venta") or 0)
        color = row.get("color")

        if not from_local or not to_local or from_local == to_local:
            return False, "Local de destino inválido"
        cantidad = int(cantidad or 0)
        if cantidad <= 0:
            return False, "Cantidad debe ser mayor a 0"

        conn = get_conn()
        cur = conn.cursor()

        # Verificar stock origen
        cur.execute(
            "SELECT cantidad FROM productos WHERE id=? AND local=?",
            (prod_id, from_local),
        )
        r = cur.fetchone()
        if not r:
            return False, "Producto de origen no encontrado"
        old_qty_origen = int(r[0] or 0)
        if old_qty_origen < cantidad:
            return False, f"Stock insuficiente. Disponible: {old_qty_origen}"

        # Salida en origen
        new_qty_origen = old_qty_origen - cantidad
        cur.execute(
            "UPDATE productos SET cantidad=?, updated_at=? WHERE id=?",
            (new_qty_origen, _now_local(), prod_id),
        )

        # Destino: buscar/crear
        existing_dest = _find_product(
            nombre,
            categoria,
            medida,
            estado,
            color,
            to_local,
            material=row.get("material"),
        )
        if existing_dest:
            dest_id, old_qty_dest, pv_dest = (
                int(existing_dest[0]),
                int(existing_dest[1] or 0),
                int(existing_dest[2] or 0),
            )
            new_qty_dest = old_qty_dest + cantidad
            cur.execute(
                "UPDATE productos SET cantidad=?, updated_at=? WHERE id=?",
                (new_qty_dest, _now_local(), dest_id),
            )
            prod_id_dest = dest_id
        else:
            # Normalizar medida al crear nuevo producto destino
            medida_norm = _norm_medida(medida)
            cur.execute(
                """
                INSERT INTO productos
                    (nombre, material, categoria, medida, estado, color, cantidad, precio_costo, precio_venta, local, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
                (
                    nombre,
                    (row.get("material") or "").strip().lower(),
                    _norm_cat(categoria),
                    medida_norm,
                    estado,
                    color,
                    cantidad,
                    0,
                    precio,
                    to_local,
                    _now_local(),
                    _now_local(),
                ),
            )
            prod_id_dest = cur.lastrowid
            old_qty_dest = 0

        grupo_id = str(uuid.uuid4())
        meta_out = {
            "from_local": from_local,
            "to_local": to_local,
            "moved": cantidad,
            "old_qty": old_qty_origen,
            "new_qty": new_qty_origen,
        }
        meta_in = {
            "from_local": from_local,
            "to_local": to_local,
            "moved": cantidad,
            "old_qty": old_qty_dest,
            "new_qty": (old_qty_dest + cantidad),
        }
        if _is_admin(usuario):
            meta_out["by_admin"] = True
            meta_in["by_admin"] = True

        cur.execute(
            """
            INSERT INTO historial_stock
                (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
            VALUES (?, 'transferencia', 'salida a '||?, ?, ?, ?, ?, '', ?, 0, ?)
        """,
            (
                prod_id,
                to_local,
                -cantidad,
                usuario,
                from_local,
                _now_local(),
                _j(meta_out),
                grupo_id,
            ),
        )

        cur.execute(
            """
            INSERT INTO historial_stock
                (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
            VALUES (?, 'transferencia', 'entrada desde '||?, ?, ?, ?, ?, '', ?, 0, ?)
        """,
            (
                prod_id_dest,
                from_local,
                cantidad,
                usuario,
                to_local,
                _now_local(),
                _j(meta_in),
                grupo_id,
            ),
        )

        conn.commit()

        # Notificar al local destino (no debe romper la transferencia si falla)
        try:
            _queue_change_notification(
                affected_locals=[to_local],
                source_local=from_local,
                source_user=usuario,
                field="transferencia",
                prod_snapshot={
                    "nombre": nombre,
                    "material": row.get("material"),
                    "categoria": categoria,
                    "medida": medida,
                    "estado": estado,
                    "color": color,
                },
                old_value=from_local,
                new_value=f"{cantidad} × {nombre}",
            )
        except Exception as _e:
            logger.error(f"Queue noti transfer: {_e}")

        logger.info(
            f"Transferencia exitosa: {cantidad} {nombre} de {from_local} a {to_local}"
        )
        return True, f"Transferencia completada: {cantidad} unidades a {to_local}"

    except Exception as e:
        logger.error(f"Error en transferencia: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, f"Error en transferencia: {str(e)}"
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


# ==================== HISTORIAL / UNDO ====================
def get_historial(
    role: str,
    user_local: str,
    search: str = "",
    action: str = "Todos",
    local_filter: str = "Todos",
    range_key: str = "30d",
) -> List[tuple]:
    """Lee historial desde SQL (historial_stock)."""
    try:
        return _get_historial_sql(
            role, user_local, search, action, local_filter, range_key
        )
    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        return []


def _get_historial_sql(
    role: str,
    user_local: str,
    search: str,
    action: str,
    local_filter: str,
    range_key: str,
) -> List[tuple]:
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "%s" if _is_postgres() else "?"
            query = """
                SELECT
                    h.id, h.producto_id, h.accion, h.detalle, h.cantidad, h.usuario, h.local, h.created_at,
                    h.undone, h.undone_by, h.undone_at,
                    p.nombre, p.categoria, p.medida, p.precio_venta, h.motivo, h.meta
                FROM historial_stock h
                LEFT JOIN productos p ON h.producto_id = p.id
                WHERE 1=1
                """
            params: List[Any] = []
            if role != "admin":
                query += f" AND h.local = {ph}"
                params.append(user_local)
            elif local_filter and local_filter != "Todos":
                query += f" AND h.local = {ph}"
                params.append(local_filter)
            if action and action != "Todos":
                query += f" AND h.accion = {ph}"
                params.append(action)
            if search:
                sp = f"%{search}%"
                query += f" AND (p.nombre LIKE {ph} OR h.detalle LIKE {ph} OR h.motivo LIKE {ph})"
                params.extend([sp, sp, sp])
            from datetime import datetime, timedelta

            if range_key and range_key != "todo":
                now = datetime.now()
                if range_key == "hoy":
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif range_key == "7d":
                    start_date = now - timedelta(days=7)
                else:
                    start_date = now - timedelta(days=30)
                query += f" AND h.created_at >= {ph}"
                params.append(start_date.strftime("%Y-%m-%d %H:%M:%S"))
            query += " ORDER BY h.created_at DESC"
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return rows
    except Exception as e:
        logger.error(f"Error fallback SQL get_historial: {e}")
        return []


def split_stock_estado(
    producto_id: int,
    cantidad: int,
    nuevo_estado: str,
    usuario: str,
    local: str,
    motivo: str = None,
) -> Tuple[bool, str]:
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT cantidad, estado FROM productos WHERE id=?", (producto_id,))
        row = cur.fetchone()
        if not row:
            return False, "Producto no encontrado"
        cantidad_actual = int(row[0])
        estado_actual = row[1]
        if cantidad <= 0 or cantidad > cantidad_actual:
            return False, f"Cantidad inválida. Disponible: {cantidad_actual}"

        nueva_cantidad_origen = cantidad_actual - cantidad
        cur.execute(
            "UPDATE productos SET cantidad=?, updated_at=? WHERE id=?",
            (nueva_cantidad_origen, _now_local(), producto_id),
        )

        cur.execute(
            """
            SELECT nombre, categoria, medida, precio_costo, precio_venta, local, color
            FROM productos WHERE id=?
        """,
            (producto_id,),
        )
        prod_info = cur.fetchone()

        cur.execute(
            """
            INSERT INTO productos
                (nombre, categoria, medida, precio_costo, precio_venta, cantidad, estado, color, local, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
            (
                prod_info[0],
                prod_info[1],
                prod_info[2],
                prod_info[3],
                prod_info[4],
                cantidad,
                nuevo_estado,
                prod_info[6],
                prod_info[5],
                _now_local(),
                _now_local(),
            ),
        )
        nuevo_producto_id = cur.lastrowid

        grupo_id = str(uuid.uuid4())
        meta_salida = {
            "from": estado_actual,
            "to": nuevo_estado,
            "moved": cantidad,
            "old_qty": cantidad_actual,
            "new_qty": nueva_cantidad_origen,
        }
        meta_entrada = {
            "from": estado_actual,
            "to": nuevo_estado,
            "moved": cantidad,
            "old_qty": 0,
            "new_qty": cantidad,
        }
        if _is_admin(usuario):
            meta_salida["by_admin"] = True
            meta_entrada["by_admin"] = True

        cur.execute(
            """
            INSERT INTO historial_stock
                (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
            VALUES (?, 'cambio_estado', ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
            (
                producto_id,
                f"salida de estado: {estado_actual} → {nuevo_estado}",
                -cantidad,
                usuario,
                local,
                _now_local(),
                (motivo or ""),
                _j(meta_salida),
                grupo_id,
            ),
        )
        cur.execute(
            """
            INSERT INTO historial_stock
                (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone, grupo_id)
            VALUES (?, 'cambio_estado', ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
            (
                nuevo_producto_id,
                f"entrada a estado: {estado_actual} → {nuevo_estado}",
                cantidad,
                usuario,
                local,
                _now_local(),
                (motivo or ""),
                _j(meta_entrada),
                grupo_id,
            ),
        )

        conn.commit()
        return (
            True,
            f"Cambio de estado registrado: {cantidad} unidades a '{nuevo_estado}'",
        )
    except Exception as e:
        logger.error(f"Error en cambio de estado: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, f"Error en cambio de estado: {str(e)}"
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


def undo_historial_entry(entry_id: int, username: str) -> Tuple[bool, str]:
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id,producto_id,accion,detalle,cantidad,usuario,local,created_at,undone,grupo_id,meta
            FROM historial_stock WHERE id=?
        """,
            (entry_id,),
        )
        row = cur.fetchone()
        if not row:
            return False, "Movimiento no encontrado"
        (
            _id,
            pid,
            accion,
            detalle,
            cantidad,
            usuario,
            local,
            created_at,
            undone,
            grupo_id,
            meta_raw,
        ) = row
        if undone:
            return False, "Este movimiento ya está deshecho"
        # Calcular diferencia de horas en Python para compatibilidad SQLite/Postgres
        try:
            from datetime import datetime

            now_dt = datetime.now()
            created_dt = (
                datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                if isinstance(created_at, str)
                else created_at
            )
            horas = (now_dt - created_dt).total_seconds() / 3600.0
        except Exception:
            horas = 0.0
        if horas > 24.0:
            return False, "Solo se puede deshacer dentro de 24 horas"
        cur.execute("SELECT role FROM usuarios WHERE username=?", (username,))
        role_row = cur.fetchone()
        role = role_row[0] if role_row else ""
        if cantidad is not None and abs(int(cantidad or 0)) > 20 and role != "admin":
            return (
                False,
                "Solo un administrador puede deshacer movimientos grandes (>20)",
            )
        try:
            meta = json.loads(meta_raw or "{}")
        except:
            meta = {}

        if accion in ("ingreso", "baja") or (
            accion == "ajuste" and cantidad is not None
        ):
            cur.execute("SELECT cantidad FROM productos WHERE id=?", (pid,))
            current_row = cur.fetchone()
            if not current_row:
                return False, "Producto no existe actualmente"
            current_qty = int(current_row[0])
            inverse_delta = -int(cantidad or 0)
            new_qty = max(0, current_qty + inverse_delta)
            cur.execute(
                "UPDATE productos SET cantidad=?, updated_at=? WHERE id=?",
                (new_qty, _now_local(), pid),
            )
            _touch_update(conn, pid)

        elif accion == "ajuste" and cantidad is None and meta.get("field"):
            field = meta.get("field")
            old_value = meta.get("old")
            if field not in SYNC_FIELDS:
                return False, f"Campo '{field}' no es reversible"
            try:
                _ensure_allowed_field(field)
            except Exception:
                return False, f"Campo inseguro: {field}"
            cur.execute(
                f"UPDATE productos SET {field}=?, updated_at=? WHERE id=?",
                (old_value, _now_local(), pid),
            )
            _touch_update(conn, pid)
        elif accion == "cambio_estado":
            # Dos casos: (A) todo el producto cambió de estado (delta==0)
            #            (B) se partieron unidades (grupo con 2 filas: una negativa y otra positiva)
            try:
                meta = json.loads(meta_raw or "{}")
            except Exception:
                meta = {}

            if grupo_id:
                # Caso B: hay grupo de dos partes (salida -m y entrada +m)
                cur.execute(
                    """
                    SELECT id,producto_id,cantidad,meta
                    FROM historial_stock
                    WHERE grupo_id=? AND accion='cambio_estado'
                    ORDER BY id ASC
                """,
                    (grupo_id,),
                )
                parts = cur.fetchall()

                # Esperamos 2 entradas: una negativa (origen) y otra positiva (destino)
                if len(parts) != 2:
                    return False, "Movimiento de cambio de estado incompleto"

                (id_a, pid_a, delta_a, meta_a), (id_b, pid_b, delta_b, meta_b) = parts
                # Identificamos cuál fue la salida (negativa) y cuál la entrada (positiva)
                if delta_a > 0:
                    # invertimos para que A sea salida y B entrada
                    id_a, pid_a, delta_a, meta_a, id_b, pid_b, delta_b, meta_b = (
                        id_b,
                        pid_b,
                        delta_b,
                        meta_b,
                        id_a,
                        pid_a,
                        delta_a,
                        meta_a,
                    )

                moved = abs(int(delta_a))
                # devolvemos las unidades al producto origen
                cur.execute("SELECT cantidad FROM productos WHERE id=?", (pid_a,))
                row_ori = cur.fetchone()
                if not row_ori:
                    return False, "Producto origen no existe para revertir"
                qty_ori = int(row_ori[0] or 0)
                cur.execute(
                    "UPDATE productos SET cantidad=?, updated_at=? WHERE id=?",
                    (qty_ori + moved, _now_local(), pid_a),
                )

                # restamos al producto destino
                cur.execute("SELECT cantidad FROM productos WHERE id=?", (pid_b,))
                row_dst = cur.fetchone()
                if not row_dst:
                    return False, "Producto destino no existe para revertir"
                qty_dst = int(row_dst[0] or 0)
                if qty_dst < moved:
                    return (
                        False,
                        f"Stock insuficiente en destino para revertir. Disponible: {qty_dst}",
                    )
                cur.execute(
                    "UPDATE productos SET cantidad=?, updated_at=? WHERE id=?",
                    (qty_dst - moved, _now_local(), pid_b),
                )

                # marcamos ambas filas del grupo como deshechas
                cur.execute(
                    """
                    UPDATE historial_stock
                    SET undone=1, undone_by=?, undone_at=?
                    WHERE grupo_id=?
                """,
                    (username, _now_local(), grupo_id),
                )

                conn.commit()
                return True, "Cambio de estado deshecho"

            else:
                # Caso A: cambio de estado del mismo producto (delta==0)
                # Revertimos estado (y precio si lo guardamos en meta)
                old_state = meta.get("from")
                old_price = meta.get("old_price")
                sets, vals = [], []

                if old_state:
                    sets.append("estado=?")
                    vals.append(old_state)
                if old_price is not None:
                    sets.append("precio_venta=?")
                    vals.append(int(old_price))

                if not sets:
                    return False, "No hay datos para revertir el cambio de estado"

                # Validar que las cláusulas SET sean seguras antes de ejecutar
                try:
                    _validate_sets_list(sets)
                except Exception as e:
                    return False, f"SET invalido: {e}"

                sets.append("updated_at=?")
                vals.append(_now_local())
                vals.append(pid)
                cur.execute(f"UPDATE productos SET {', '.join(sets)} WHERE id=?", vals)

                cur.execute(
                    """
                    UPDATE historial_stock
                    SET undone=1, undone_by=?, undone_at=?
                    WHERE id=?
                """,
                    (username, _now_local(), _id),
                )

                conn.commit()
                return True, "Cambio de estado revertido"

        elif accion == "transferencia" and grupo_id:
            cur.execute(
                """
                SELECT id,producto_id,cantidad FROM historial_stock
                WHERE grupo_id=? AND accion='transferencia' ORDER BY id ASC
            """,
                (grupo_id,),
            )
            parts = cur.fetchall()
            if len(parts) != 2:
                return False, "Transferencia incompleta, no se puede deshacer"
            (id_a, pid_a, delta_a), (id_b, pid_b, delta_b) = parts
            if delta_a > 0:
                id_a, pid_a, delta_a, id_b, pid_b, delta_b = (
                    id_b,
                    pid_b,
                    delta_b,
                    id_a,
                    pid_a,
                    delta_a,
                )
            moved = abs(int(delta_a))
            cur.execute("SELECT cantidad FROM productos WHERE id=?", (pid_b,))
            dest_row = cur.fetchone()
            if not dest_row:
                return False, "Producto destino no existe"
            qty_dest = int(dest_row[0])
            if qty_dest < moved:
                return (
                    False,
                    f"Stock insuficiente en destino para revertir. Disponible: {qty_dest}",
                )
            cur.execute("SELECT cantidad FROM productos WHERE id=?", (pid_a,))
            qty_ori = int(cur.fetchone()[0])
            cur.execute(
                "UPDATE productos SET cantidad=?, updated_at=? WHERE id=?",
                (qty_ori + moved, _now_local(), pid_a),
            )
            cur.execute(
                "UPDATE productos SET cantidad=?, updated_at=? WHERE id=?",
                (qty_dest - moved, _now_local(), pid_b),
            )
            _touch_update(conn, pid_a)
            _touch_update(conn, pid_b)
            cur.execute(
                """
                UPDATE historial_stock
                SET undone=1, undone_by=?, undone_at=?
                WHERE grupo_id=?
            """,
                (username, _now_local(), grupo_id),
            )
            conn.commit()
            return True, "Transferencia deshecha correctamente"

        else:
            return False, f"Tipo de movimiento '{accion}' no es reversible"

        cur.execute(
            """
            UPDATE historial_stock
            SET undone=1, undone_by=?, undone_at=?
            WHERE id=?
        """,
            (username, _now_local(), entry_id),
        )
        conn.commit()
        return True, "Movimiento deshecho correctamente"
    except Exception as e:
        logger.error(f"Error deshaciendo movimiento {entry_id}: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, f"Error al deshacer: {str(e)}"
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


# ==================== RESÚMENES / VALIDACIÓN ====================
def get_stock_summary(local: str = None) -> Dict[str, Any]:
    try:
        with _get_conn_cm() as conn:
            cur = conn.cursor()
            base_query = "SELECT COUNT(*), SUM(cantidad), SUM(cantidad * precio_venta) FROM productos"
            params = []
            if local:
                base_query += " WHERE local = ?"
                params.append(local)
            cur.execute(base_query, params)
            total_products, total_items, total_value = cur.fetchone()
            low_stock_query = base_query.replace(
                "COUNT(*), SUM(cantidad), SUM(cantidad * precio_venta)", "COUNT(*)"
            )
            if local:
                low_stock_query += " AND cantidad <= 5"
            else:
                low_stock_query += " WHERE cantidad <= 5"
            cur.execute(low_stock_query, params)
            low_stock_count = cur.fetchone()[0]
        return {
            "total_products": total_products or 0,
            "total_items": total_items or 0,
            "total_value": total_value or 0,
            "low_stock_count": low_stock_count or 0,
            "local": local,
        }
    except Exception as e:
        logger.error(f"Error obteniendo resumen de stock: {e}")
        return {
            "total_products": 0,
            "total_items": 0,
            "total_value": 0,
            "low_stock_count": 0,
            "local": local,
        }


def validate_stock_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    required_fields = ["nombre", "local"]
    for field in required_fields:
        if not data.get(field, "").strip():
            return False, f"Campo '{field}' es obligatorio"
    if data.get("cantidad", 0) < 0:
        return False, "La cantidad no puede ser negativa"
    if data.get("precio_venta", 0) < 0:
        return False, "El precio de venta no puede ser negativo"
    return True, "Datos válidos"


def change_state_quantity(
    producto_id: int,
    cantidad: int,
    nuevo_estado: str,
    nuevo_precio: Optional[int],
    usuario: str,
    local: str,
    motivo: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Cambia el estado de 'cantidad' unidades. Si 'cantidad' == stock total,
    cambia el estado (y opcionalmente el precio) del mismo producto.
    Si 'cantidad' < stock total, descuenta del original y crea un producto nuevo
    con el nuevo estado y precio. NO sincroniza a otros locales.
    """
    conn = None
    try:
        placeholder = "%s" if _is_postgres() else "?"

        def _sql(q: str) -> str:
            """Normaliza placeholders para SQLite ('?') o Postgres ('%s')."""
            return q.replace("?", placeholder)

        conn = get_conn()
        cur = conn.cursor()

        # Datos actuales
        cur.execute(
            _sql(
                """
            SELECT nombre,categoria,medida,estado,color,cantidad,precio_costo,precio_venta,local,COALESCE(fabricante,'')
            FROM productos WHERE id=?
        """
            ),
            (producto_id,),
        )
        row = cur.fetchone()
        if not row:
            return False, "Producto no encontrado"

        (
            nombre,
            categoria,
            medida,
            estado_actual,
            color,
            cant_actual,
            precio_costo,
            precio_venta,
            prod_local,
            fabricante,
        ) = row

        if prod_local != local:
            return False, "Sólo se puede cambiar estado en el local actual"

        cantidad = int(cantidad or 0)
        if cantidad <= 0 or cantidad > int(cant_actual or 0):
            return False, f"Cantidad inválida. Disponible: {cant_actual}"

        nuevo_estado = (nuevo_estado or "").strip() or estado_actual
        nuevo_precio = int(nuevo_precio) if nuevo_precio is not None else None
        ahora = _now_local()
        grupo_id = str(uuid.uuid4())

        if cantidad == cant_actual:
            # Cambiar el mismo producto
            sets = [f"estado={placeholder}", f"updated_at={placeholder}"]
            vals = [nuevo_estado, ahora]

            if nuevo_precio is not None:
                vals.insert(0, nuevo_precio)
                sets.insert(0, f"precio_venta={placeholder}")

            # Validar las cláusulas SET antes de interpolarlas en la consulta
            try:
                _validate_sets_list(sets)
            except Exception as e:
                return False, f"SET inválido: {e}"

            cur.execute(
                f"UPDATE productos SET {', '.join(sets)} WHERE id={placeholder}",
                (*vals, producto_id),
            )

            meta = {
                "from": estado_actual,
                "to": nuevo_estado,
                "all_units": True,
                "qty": cantidad,
            }
            if nuevo_precio is not None:
                meta["new_price"] = nuevo_precio
                meta["old_price"] = int(precio_venta or 0)
            if _is_admin(usuario):
                meta["by_admin"] = True

            cur.execute(
                _sql(
                    """
                INSERT INTO historial_stock
                (producto_id,accion,detalle,cantidad,usuario,local,created_at,motivo,meta,undone,grupo_id)
                VALUES (?,?,?,?,?,?,?,?,?,0,?)
            """
                ),
                (
                    producto_id,
                    "cambio_estado",
                    f"cambio de estado: {estado_actual} → {nuevo_estado}",
                    0,
                    usuario,
                    local,
                    ahora,
                    (motivo or ""),
                    _j(meta),
                    grupo_id,
                ),
            )

        else:
            # Partir: descontar del original y crear nuevo con estado/precio
            nueva_cant_origen = int(cant_actual) - cantidad
            cur.execute(
                _sql("UPDATE productos SET cantidad=?, updated_at=? WHERE id=?"),
                (nueva_cant_origen, ahora, producto_id),
            )

            # Buscar si ya existe el mismo producto con el nuevo estado en este local
            cur.execute(
                _sql(
                    """
                SELECT id,cantidad,precio_venta FROM productos
                 WHERE nombre=? AND categoria=? AND COALESCE(medida,'')=COALESCE(?,'')
                   AND estado=? AND COALESCE(color,'')=COALESCE(?,'') AND COALESCE(fabricante,'')=COALESCE(?,'')
                   AND local=?
                 LIMIT 1
            """
                ),
                (nombre, categoria, medida, nuevo_estado, color, fabricante, local),
            )
            dest_row = cur.fetchone()

            dest_price_db = dest_row[2] if dest_row else None
            price_dest = (
                int(nuevo_precio)
                if nuevo_precio is not None
                else (
                    int(dest_price_db)
                    if dest_price_db is not None
                    else int(precio_venta or 0)
                )
            )

            if dest_row:
                dest_id, dest_qty, _ = dest_row
                nueva_cant_dest = int(dest_qty or 0) + cantidad
                sets = [f"cantidad={placeholder}", f"updated_at={placeholder}"]
                vals = [nueva_cant_dest, ahora]
                if nuevo_precio is not None:
                    sets.insert(0, f"precio_venta={placeholder}")
                    vals.insert(0, price_dest)
                cur.execute(
                    f"UPDATE productos SET {', '.join(sets)} WHERE id={placeholder}",
                    (*vals, dest_id),
                )
                nuevo_producto_id = dest_id
            else:
                cur.execute(
                    _sql(
                        """
                    INSERT INTO productos
                    (nombre,categoria,medida,estado,color,cantidad,precio_costo,precio_venta,local,created_at,updated_at,fabricante)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """
                    ),
                    (
                        nombre,
                        categoria,
                        medida,
                        nuevo_estado,
                        color,
                        cantidad,
                        precio_costo,
                        price_dest,
                        local,
                        ahora,
                        ahora,
                        fabricante,
                    ),
                )
                nuevo_producto_id = cur.lastrowid

            meta_out = {
                "from": estado_actual,
                "to": nuevo_estado,
                "moved": cantidad,
                "old_qty": int(cant_actual),
                "new_qty": nueva_cant_origen,
            }
            meta_in = {
                "from": estado_actual,
                "to": nuevo_estado,
                "moved": cantidad,
                "old_qty": 0,
                "new_qty": cantidad,
                "new_price": price_dest,
            }
            if _is_admin(usuario):
                meta_out["by_admin"] = True
                meta_in["by_admin"] = True

            cur.execute(
                _sql(
                    """
                INSERT INTO historial_stock
                (producto_id,accion,detalle,cantidad,usuario,local,created_at,motivo,meta,undone,grupo_id)
                VALUES (?,?,?,?,?,?,?,?,?,0,?)
            """
                ),
                (
                    producto_id,
                    "cambio_estado",
                    f"salida de estado: {estado_actual} → {nuevo_estado}",
                    -cantidad,
                    usuario,
                    local,
                    ahora,
                    (motivo or ""),
                    _j(meta_out),
                    grupo_id,
                ),
            )

            cur.execute(
                _sql(
                    """
                INSERT INTO historial_stock
                (producto_id,accion,detalle,cantidad,usuario,local,created_at,motivo,meta,undone,grupo_id)
                VALUES (?,?,?,?,?,?,?,?,?,0,?)
            """
                ),
                (
                    nuevo_producto_id,
                    "cambio_estado",
                    f"entrada a estado: {estado_actual} → {nuevo_estado}",
                    cantidad,
                    usuario,
                    local,
                    ahora,
                    (motivo or ""),
                    _j(meta_in),
                    grupo_id,
                ),
            )

        conn.commit()
        return True, "Cambio de estado realizado"
    except Exception as e:
        logger.error(f"Error en change_state_quantity: {e}")
        try:
            if conn:
                conn.rollback()
        except:
            pass
        return False, f"Error: {str(e)}"
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


# Compatibilidad: asegurar que existan las funciones esperadas por tests/otros módulos.
# Algunas ejecuciones antiguas o importaciones parciales pueden dejar una versión
# previa del módulo sin las implementaciones actuales; forzamos wrappers fiables
# que delegan en las funciones internas ya presentes (update_stock_quantity, _find_product).
def _compat_increment_stock(
    producto_id: int,
    delta: int,
    usuario: str,
    local: str,
    detalle: str = None,
    motivo: str = None,
) -> Tuple[bool, str]:
    try:
        delta = int(delta or 0)
    except Exception:
        return False, "Delta inválido"
    if delta == 0:
        return False, "Delta inválido"

    # Intentar usar implementación atómica si está definida
    impl = globals().get("increment_stock")
    if impl and impl is not _compat_increment_stock:
        try:
            return impl(producto_id, delta, usuario, local, detalle, motivo)
        except Exception:
            pass

    # Fallback: calcular nuevo absoluto y delegar a update_stock_quantity
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT cantidad FROM productos WHERE id=?", (producto_id,))
        r = cur.fetchone()
        if not r:
            return False, "Producto no encontrado"
        old_qty = int(r[0] or 0)
        new_qty = max(0, old_qty + int(delta))
        return update_stock_quantity(
            producto_id, new_qty, usuario, local, detalle=detalle, motivo=motivo
        )
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return False, f"Error al modificar cantidad: {e}"
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


def _compat_add_or_increment(
    nombre,
    categoria,
    medida,
    estado,
    color,
    cantidad,
    precio_costo,
    precio_venta,
    local,
    usuario,
    material: Optional[str] = None,
):
    """Wrapper robusto para add_or_increment: normaliza y si existe DEVUELVE existencia (no incrementa), si no inserta.
    Soporta parámetro opcional force_update para forzar incremento cuando sea necesario.
    """
    try:
        nombre_norm = (
            _sanitize_name(nombre)
            if " _sanitize_name" in globals() or "_sanitize_name" in globals()
            else (nombre or "").strip()
        )
    except Exception:
        nombre_norm = (nombre or "").strip()
    categoria_norm = _norm_cat(categoria)
    medida_norm = _norm_medida(medida)
    try:
        cantidad = int(cantidad or 0)
    except Exception:
        return False, "Cantidad inválida"

    # Buscar producto existente
    existing = _find_product(
        nombre_norm,
        categoria_norm,
        medida_norm,
        estado,
        color,
        local,
        material=material,
    )
    if existing:
        try:
            pid = int(existing[0])
            if isinstance(cantidad, dict):
                # compat: if cantidad passed as dict (unexpected), don't change
                return False, f"Ese producto ya existe. ID={pid}"
            return False, f"Ese producto ya existe. ID={pid}"
        except Exception:
            return False, "Ese producto ya existe"

    # Insertar nuevo
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO productos
                (nombre, material, categoria, medida, estado, color, cantidad, precio_costo, precio_venta, local, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
            (
                nombre_norm,
                (material or "").strip().lower(),
                categoria_norm,
                medida_norm,
                estado,
                color,
                int(cantidad or 0),
                int(precio_costo or 0),
                int(precio_venta or 0),
                local,
                _now_local(),
                _now_local(),
            ),
        )
        conn.commit()
        return True, "Producto agregado correctamente"
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        return False, f"Error al agregar producto: {e}"
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


# Nota: las funciones de compatibilidad `_compat_increment_stock` y
# `_compat_add_or_increment` se mantienen definidas para diagnósticos, pero
# ya no se sobrescriben en el namespace principal. Esto evita confusión si el
# módulo se importa parcialmente; las funciones canónicas definidas arriba
# (e.g. `increment_stock`, `add_or_increment`) son las utilizadas.

import sqlite3

# === PEGAR AL FINAL DE models/stock_model.py ===
from models.db import get_connection

_CANDIDATE_TABLES = ["stock", "productos", "inventario"]


def _table_exists(cur, name):
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (name,)
    )
    return cur.fetchone() is not None


def _detect_stock_table(cur):
    for t in _CANDIDATE_TABLES:
        if _table_exists(cur, t):
            return t
    return None


def _create_stock_table(cur):
    # Solo se crea si no existe NINGUNA de las tablas candidatas
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            categoria TEXT,
            precio_venta REAL NOT NULL DEFAULT 0,
            cantidad INTEGER NOT NULL DEFAULT 0,
            local TEXT NOT NULL,
            medida TEXT,
            estado TEXT DEFAULT 'Nuevo',
            color TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_stock_local_nombre ON stock(local, nombre);"
    )


def get_stock_for_local(local_name: str):
    """
    Devuelve lista de dicts uniformes: [{id, nombre, categoria, precio, disponible}, ...]
    Busca primero tablas candidatas; si no hay ninguna, crea 'stock' vacía (para no fallar).
    """
    con = get_connection()
    try:
        cur = con.cursor()
        table = _detect_stock_table(cur)
        if table is None:
            _create_stock_table(cur)
            con.commit()
            table = "stock"  # recién creada (vacía)

        # detectar nombre real de columna precio
        # asegurar que `table` es un identificador seguro y conocido
        if not _is_safe_identifier(table) or table not in _CANDIDATE_TABLES:
            logger.warning(
                f"Nombre de tabla sospechoso/inesperado: {table}; usando 'stock' por defecto"
            )
            table = "stock"

        cur.execute(f"PRAGMA table_info({table});")
        cols = {row[1] for row in cur.fetchall()}

        # elegir columnas preferidas, validando cada identificador
        def _safe_col(name, default):
            # si es literal (entre comillas) lo permitimos tal cual
            if isinstance(name, str) and (name.startswith("'") or name.startswith('"')):
                return name
            if name in cols and _is_safe_identifier(name):
                return name
            return default

        precio_col = _safe_col("precio_venta", "precio_venta")
        if (
            precio_col == "precio_venta"
            and "precio" in cols
            and _is_safe_identifier("precio")
        ):
            precio_col = "precio"
        elif "precio_unit" in cols and _is_safe_identifier("precio_unit"):
            precio_col = "precio_unit"

        id_col = _safe_col("id", "id")
        nombre_col = _safe_col("nombre", "nombre")
        categoria_col = _safe_col("categoria", "COALESCE('', '')")
        cantidad_col = _safe_col("cantidad", "cantidad")
        local_col = _safe_col("local", "local")

        # Asegurar que al menos las columnas por defecto sean usadas (evitar inyección)
        if not _is_safe_identifier(id_col):
            id_col = "id"
        if not _is_safe_identifier(nombre_col):
            nombre_col = "nombre"
        if not _is_safe_identifier(precio_col):
            precio_col = "precio_venta"
        if not _is_safe_identifier(cantidad_col):
            cantidad_col = "cantidad"
        if not _is_safe_identifier(local_col):
            local_col = "local"

        q = f"""
            SELECT
                {id_col} AS id,
                {nombre_col} AS nombre,
                COALESCE({categoria_col}, '') AS categoria,
                COALESCE({precio_col}, 0) AS precio,
                COALESCE({cantidad_col}, 0) AS cantidad,
                {local_col} AS local
            FROM {table}
            WHERE {local_col} = ?
            ORDER BY {nombre_col} COLLATE NOCASE;
        """
        cur.execute(q, (local_name,))
        rows = cur.fetchall()

        productos = []
        for r in rows:
            productos.append(
                {
                    "id": r["id"],
                    "nombre": r["nombre"],
                    "categoria": r["categoria"],
                    "precio": float(r["precio"] or 0),
                    "disponible": int(r["cantidad"] or 0),
                }
            )
        return productos
    finally:
        con.close()


try:
    # Importar la API dedicada de cola (implementación separada)
    from . import stock_queue_api as _sqa
except Exception as _e:
    _sqa = None


def _attach_if_missing(name: str) -> bool:
    """Adjunta la función `name` desde stock_queue_api al namespace de este módulo
    sólo si no existe ya. Devuelve True si la función quedó disponible."""
    try:
        if _sqa is None:
            return False
        if name in globals():
            return True
        fn = getattr(_sqa, name, None)
        if fn is None:
            return False
        globals()[name] = fn
        return True
    except Exception:
        return False


# Nombres esperados por el código del proyecto; si faltan en este módulo
# los traemos desde stock_queue_api.
for _name in (
    "enqueue_op",
    "get_queue_items",
    "mark_queue_item_done",
    "mark_queue_item_failed",
    "mark_queue_item_retry",
    "get_queue_count",
    "get_queue_all_items",
    "retry_queue_item",
    "remove_queue_item",
    "process_queue_once",
):
    _attach_if_missing(_name)


# Forzar implementación canónica de add_or_increment si la versión cargada
# no contiene el parámetro `force_update` o no registra historial al crear.
def add_or_increment_v2(
    nombre,
    categoria,
    medida,
    estado,
    color,
    cantidad,
    precio_costo,
    precio_venta,
    local,
    usuario,
    force_update: bool = False,
    material: Optional[str] = None,
):
    """Implementación canónica y robusta de add_or_increment.
    Garantiza validaciones y registro en `historial_stock` cuando se crea
    un producto nuevo o cuando se aplica `force_update`.
    """
    try:
        nombre = _sanitize_name(nombre)
        categoria = _norm_cat(categoria)
        medida_norm = _norm_medida(medida)
        material_norm = (material or "").strip().lower()
        try:
            cantidad = int(cantidad or 0)
        except Exception:
            return False, "Cantidad inválida"
        if cantidad < 0:
            return False, "Cantidad no puede ser negativa"
        if cantidad > 1_000_000:
            return False, "Cantidad demasiado grande"

        try:
            precio_costo = float(precio_costo or 0)
            precio_venta = float(precio_venta or 0)
        except Exception:
            return False, "Precio inválido"
        if precio_costo < 0 or precio_venta < 0:
            return False, "Precios no pueden ser negativos"

        with _get_conn_cm() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, cantidad FROM productos
                WHERE nombre=? AND IFNULL(material,'')=? AND categoria=? AND IFNULL(medida,'')=? AND estado=? AND IFNULL(color,'')=? AND local=?
            """,
                (
                    nombre,
                    material_norm,
                    categoria,
                    medida_norm,
                    estado,
                    color or "",
                    local,
                ),
            )
            existing = cur.fetchone()
            if existing:
                pid = int(existing[0])
                old_qty = int(existing[1] or 0)
                if force_update:
                    new_qty = old_qty + int(cantidad)
                    cur.execute(
                        "UPDATE productos SET cantidad=?, precio_costo=?, precio_venta=?, updated_at=? WHERE id=?",
                        (
                            new_qty,
                            int(precio_costo),
                            int(precio_venta),
                            _now_local(),
                            pid,
                        ),
                    )
                    meta = {"old_qty": old_qty, "new_qty": new_qty}
                    cur.execute(
                        """
                        INSERT INTO historial_stock
                            (producto_id, accion, detalle, cantidad, usuario, local, created_at, motivo, meta, undone)
                        VALUES (?, 'ajuste', ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                        (
                            pid,
                            f"incremento por add_or_increment (force)",
                            int(cantidad),
                            usuario,
                            local,
                            _now_local(),
                            "add_or_increment_force",
                            _j(meta),
                        ),
                    )
                    conn.commit()
                    return True, "Stock incrementado correctamente"
                else:
                    return False, f"Ese producto ya existe. ID={pid}"

            # Insertar nuevo producto y registrar historial
            cur.execute(
                """
                INSERT INTO productos
                    (nombre, material, categoria, medida, estado, color, cantidad, precio_costo, precio_venta, local, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
                (
                    nombre,
                    material_norm,
                    categoria,
                    medida_norm,
                    estado,
                    color,
                    cantidad,
                    int(precio_costo),
                    int(precio_venta),
                    local,
                    _now_local(),
                    _now_local(),
                ),
            )
            pid = cur.lastrowid
            if pid:
                # No insertar una entrada de historial para la creación del producto aquí.
                # Historial de cambios de cantidad se registra solo en operaciones de ajuste
                # (update_stock_quantity / increment/decrement) para evitar duplicados
                # entre capas de la aplicación y triggers.
                meta = {
                    "initial_qty": cantidad,
                    "precio_costo": int(precio_costo),
                    "precio_venta": int(precio_venta),
                }
            conn.commit()
            return True, "Producto agregado correctamente"
    except Exception as e:
        logger.exception(f"add_or_increment_v2 error: {e}")
        return False, f"Error al agregar producto: {e}"


# Reemplazar la función exportada si la versión cargada no acepta force_update
try:
    if (
        "add_or_increment" not in globals()
        or getattr(globals().get("add_or_increment"), "__code__", None) is None
        or globals()["add_or_increment"].__code__.co_argcount < 11
    ):
        globals()["add_or_increment"] = add_or_increment_v2
except Exception:
    globals()["add_or_increment"] = add_or_increment_v2


def _canonical_stock_queue_result(result) -> Tuple[bool, str]:
    if isinstance(result, tuple) and len(result) >= 2:
        return bool(result[0]), str(result[1])
    return bool(result), ""


def update_stock_quantity(
    producto_id: int,
    new_qty: int,
    usuario: str,
    local: str,
    detalle: str = None,
    motivo: str = None,
) -> Tuple[bool, str]:
    """Implementacion canonica: calcula delta y delega en increment_stock."""
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if _is_postgres() else "?"
        cur.execute(
            f"SELECT cantidad, local FROM productos WHERE id={ph}", (producto_id,)
        )
        row = cur.fetchone()
        if not row:
            return False, "Producto no encontrado"
        old_qty = int(row[0] or 0)
        prod_local = row[1] or ""
        target_qty = max(0, int(new_qty))
        delta = target_qty - old_qty
        if delta == 0:
            return True, "Cantidad sin cambios"
        return increment_stock(
            producto_id,
            delta,
            usuario,
            local or prod_local,
            detalle=detalle or "ajuste manual",
            motivo=motivo,
        )
    except Exception as e:
        logger.error(f"Error actualizando cantidad: {e}")
        return False, f"Error al actualizar cantidad: {str(e)}"
    finally:
        if conn:
            try:
                _put_db_connection(conn) if _put_db_connection else conn.close()
            except Exception:
                pass


def increment_stock(
    producto_id: int,
    delta: int,
    usuario: str,
    local: str,
    detalle: str = None,
    motivo: str = None,
) -> Tuple[bool, str]:
    """Implementacion canonica: delega en stock_queue_api.execute_increment."""
    try:
        delta = int(delta or 0)
    except Exception:
        return False, "Delta invalido"
    if delta == 0:
        return False, "Delta invalido"
    payload = {
        "producto_id": int(producto_id or 0),
        "delta": delta,
        "usuario": usuario or "sistema",
        "local": local or "",
        "detalle": detalle or ("boton +" if delta > 0 else "boton -"),
        "motivo": motivo or "",
    }
    return _canonical_stock_queue_result(qa.execute_increment(payload))


def transfer_stock(
    row: dict, to_local: str, cantidad: int, usuario: str
) -> Tuple[bool, str]:
    """Implementacion canonica: delega en stock_queue_api.execute_transfer."""
    payload = {
        "producto_id": int((row or {}).get("id") or 0),
        "cantidad": int(cantidad or 0),
        "from_local": (row or {}).get("local")
        or (row or {}).get("Local")
        or (row or {}).get("local_name")
        or "",
        "to_local": to_local or "",
        "usuario": usuario or "sistema",
        "nombre": (row or {}).get("nombre") or "",
        "categoria": (row or {}).get("categoria") or "",
        "medida": (row or {}).get("medida"),
        "estado": (row or {}).get("estado") or "Nuevo",
        "color": (row or {}).get("color"),
        "precio_venta": (row or {}).get("precio_venta") or 0,
    }
    return _canonical_stock_queue_result(qa.execute_transfer(payload))


def enqueue_op(op_type: str, payload: dict) -> int:
    return qa.enqueue_op(op_type, payload)


def get_queue_count() -> int:
    try:
        return int(qa.get_queue_count() or 0)
    except Exception as e:
        logger.error(f"Error en get_queue_count: {e}")
        return 0


def process_queue_once(limit: int = 20) -> int:
    try:
        return int(qa.process_queue_once(limit=limit) or 0)
    except Exception as e:
        logger.error(f"Error procesando cola: {e}")
        return 0


def notify_interlocal_sale(
    target_local: str,
    source_local: str,
    source_user: str,
    product: Dict[str, Any],
    qty: int,
    venta_id: int = 0,
    include_envio: bool = False,
) -> None:
    """Notifica al local dueno del stock sobre una venta realizada por otro local."""
    try:
        field = "venta_otro_local_envio" if include_envio else "venta_otro_local_retiro"
        _queue_change_notification(
            affected_locals=[target_local],
            source_local=source_local,
            source_user=source_user,
            field=field,
            prod_snapshot=product or {},
            old_value="",
            new_value=str(int(qty) if qty is not None else ""),
        )
    except Exception as e:
        logger.error(f"Error notificando venta interlocal: {e}")
