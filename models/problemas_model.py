import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from models.db import get_connection as get_conn
from models.db import is_postgres
from models.db import put_connection as put_conn

logger = logging.getLogger(__name__)


def ensure_problemas_schema() -> Tuple[bool, str]:
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        if is_postgres():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS problemas_chat (
                    id SERIAL PRIMARY KEY,
                    local TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    rol TEXT NOT NULL,
                    mensaje TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_problemas_chat_local ON problemas_chat(local)"
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS problemas_chat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    local TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    rol TEXT NOT NULL,
                    mensaje TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_problemas_chat_local ON problemas_chat(local)"
            )
        conn.commit()
        return True, "OK"
    except Exception as e:
        logger.exception("Error asegurando schema problemas_chat")
        try:
            if conn and is_postgres():
                conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def ensure_admin_reads_schema() -> Tuple[bool, str]:
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        if is_postgres():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_message_reads (
                    username TEXT PRIMARY KEY,
                    last_seen TIMESTAMP NOT NULL
                )
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_message_reads (
                    username TEXT PRIMARY KEY,
                    last_seen TEXT NOT NULL
                )
                """
            )
        conn.commit()
        return True, "OK"
    except Exception as e:
        logger.exception("Error asegurando schema admin_message_reads")
        try:
            if conn and is_postgres():
                conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def ensure_local_reads_schema() -> Tuple[bool, str]:
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        if is_postgres():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS local_message_reads (
                    local TEXT PRIMARY KEY,
                    last_seen TIMESTAMP NOT NULL
                )
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS local_message_reads (
                    local TEXT PRIMARY KEY,
                    last_seen TEXT NOT NULL
                )
                """
            )
        conn.commit()
        return True, "OK"
    except Exception as e:
        logger.exception("Error asegurando schema local_message_reads")
        try:
            if conn and is_postgres():
                conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def add_mensaje(local: str, usuario: str, rol: str, mensaje: str) -> Tuple[bool, str]:
    conn = None
    try:
        ok, msg = ensure_problemas_schema()
        if not ok:
            return False, msg
        local_norm = (local or "").strip() or "Sin local"
        usuario_norm = (usuario or "").strip() or "Sin usuario"
        rol_norm = (rol or "").strip() or "local"
        mensaje_norm = (mensaje or "").strip()
        if not mensaje_norm:
            return False, "Mensaje vacio"

        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if is_postgres() else "?"
        if is_postgres():
            cur.execute(
                f"""
                INSERT INTO problemas_chat (local, usuario, rol, mensaje)
                VALUES ({ph}, {ph}, {ph}, {ph})
                """,
                (local_norm, usuario_norm, rol_norm, mensaje_norm),
            )
        else:
            cur.execute(
                f"""
                INSERT INTO problemas_chat (local, usuario, rol, mensaje, created_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
                """,
                (
                    local_norm,
                    usuario_norm,
                    rol_norm,
                    mensaje_norm,
                    datetime.utcnow().isoformat(),
                ),
            )
        conn.commit()
        return True, "OK"
    except Exception as e:
        logger.exception("Error agregando mensaje")
        try:
            if conn and is_postgres():
                conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def delete_mensajes(ids: List[int]) -> Tuple[bool, str]:
    conn = None
    try:
        ok, msg = ensure_problemas_schema()
        if not ok:
            return False, msg
        ids = [int(i) for i in (ids or []) if i is not None]
        if not ids:
            return False, "Sin mensajes seleccionados"
        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if is_postgres() else "?"
        in_list = ",".join([ph] * len(ids))
        cur.execute(f"DELETE FROM problemas_chat WHERE id IN ({in_list})", tuple(ids))
        conn.commit()
        return True, "OK"
    except Exception as e:
        logger.exception("Error eliminando mensajes")
        try:
            if conn and is_postgres():
                conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def delete_mensajes_scoped(
    ids: List[int],
    role: str,
    username: str,
    local: str,
) -> Tuple[bool, str]:
    if (role or "").lower() == "admin":
        return delete_mensajes(ids)

    conn = None
    try:
        ok, msg = ensure_problemas_schema()
        if not ok:
            return False, msg
        ids = [int(i) for i in (ids or []) if i is not None]
        if not ids:
            return False, "Sin mensajes seleccionados"
        usuario_norm = (username or "").strip()
        local_norm = (local or "").strip()
        if not usuario_norm or not local_norm:
            return False, "Usuario o local inválido"

        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if is_postgres() else "?"
        in_list = ",".join([ph] * len(ids))
        cur.execute(
            f"""
            DELETE FROM problemas_chat
            WHERE id IN ({in_list}) AND usuario = {ph} AND local = {ph}
            """,
            tuple(ids + [usuario_norm, local_norm]),
        )
        deleted = getattr(cur, "rowcount", 0)
        conn.commit()
        if deleted <= 0:
            return False, "Solo puedes borrar tus propios mensajes"
        return True, "OK"
    except Exception as e:
        logger.exception("Error eliminando mensajes con scope")
        try:
            if conn and is_postgres():
                conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def list_mensajes(local: Optional[str] = None, limit: int = 300) -> List[Dict]:
    conn = None
    try:
        ok, _ = ensure_problemas_schema()
        if not ok:
            return []
        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if is_postgres() else "?"

        params = []
        where = ""
        if local:
            where = f"WHERE local = {ph}"
            params.append(local)

        lim = int(limit or 300)
        query = f"""
            SELECT id, local, usuario, rol, mensaje, created_at
            FROM problemas_chat
            {where}
            ORDER BY created_at ASC
            LIMIT {lim}
        """
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        mensajes = []
        for r in rows:
            mensajes.append(
                {
                    "id": r[0],
                    "local": r[1],
                    "usuario": r[2],
                    "rol": r[3],
                    "mensaje": r[4],
                    "created_at": str(r[5]),
                }
            )
        return mensajes
    except Exception as e:
        logger.exception("Error listando mensajes")
        return []
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def count_admin_unread(username: str) -> int:
    conn = None
    try:
        ok, _ = ensure_problemas_schema()
        if not ok:
            return 0
        ok2, _ = ensure_admin_reads_schema()
        if not ok2:
            return 0
        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if is_postgres() else "?"

        # Obtener last_seen
        cur.execute(
            f"SELECT last_seen FROM admin_message_reads WHERE username = {ph}",
            (username or "",),
        )
        row = cur.fetchone()
        if row and row[0]:
            last_seen = row[0]
        else:
            last_seen = "1970-01-01T00:00:00"

        # Contar mensajes de locales (rol != admin) posteriores
        cur.execute(
            f"""
            SELECT COUNT(1)
            FROM problemas_chat
            WHERE rol <> {ph} AND created_at > {ph}
            """,
            ("admin", last_seen),
        )
        res = cur.fetchone()
        return int(res[0]) if res and res[0] is not None else 0
    except Exception as e:
        logger.exception("Error contando mensajes no leidos admin")
        return 0
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def get_local_last_seen(local: str) -> Optional[str]:
    conn = None
    try:
        ok, _ = ensure_local_reads_schema()
        if not ok:
            return None
        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if is_postgres() else "?"
        cur.execute(
            f"SELECT last_seen FROM local_message_reads WHERE local = {ph}",
            ((local or "").strip(),),
        )
        row = cur.fetchone()
        return str(row[0]) if row and row[0] else None
    except Exception:
        logger.exception("Error leyendo last_seen local")
        return None
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def count_local_unread(local: str) -> int:
    conn = None
    try:
        ok, _ = ensure_problemas_schema()
        if not ok:
            return 0
        ok2, _ = ensure_local_reads_schema()
        if not ok2:
            return 0
        local_norm = (local or "").strip()
        if not local_norm:
            return 0
        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if is_postgres() else "?"

        cur.execute(
            f"SELECT last_seen FROM local_message_reads WHERE local = {ph}",
            (local_norm,),
        )
        row = cur.fetchone()
        last_seen = row[0] if row and row[0] else "1970-01-01T00:00:00"

        cur.execute(
            f"""
            SELECT COUNT(1)
            FROM problemas_chat
            WHERE local = {ph} AND rol = {ph} AND created_at > {ph}
            """,
            (local_norm, "admin", last_seen),
        )
        res = cur.fetchone()
        return int(res[0]) if res and res[0] is not None else 0
    except Exception:
        logger.exception("Error contando mensajes no leidos local")
        return 0
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def mark_local_seen(local: str, seen_at: Optional[str] = None) -> None:
    conn = None
    try:
        ok, _ = ensure_local_reads_schema()
        if not ok:
            return
        local_norm = (local or "").strip()
        if not local_norm:
            return
        ts = seen_at or datetime.utcnow().isoformat()
        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if is_postgres() else "?"
        if is_postgres():
            cur.execute(
                f"""
                INSERT INTO local_message_reads (local, last_seen)
                VALUES ({ph}, {ph})
                ON CONFLICT(local) DO UPDATE SET last_seen = EXCLUDED.last_seen
                """,
                (local_norm, ts),
            )
        else:
            cur.execute(
                f"""
                INSERT OR REPLACE INTO local_message_reads (local, last_seen)
                VALUES ({ph}, {ph})
                """,
                (local_norm, ts),
            )
        conn.commit()
    except Exception:
        try:
            if conn and is_postgres():
                conn.rollback()
        except Exception:
            pass
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass


def mark_admin_seen(username: str, seen_at: Optional[str] = None) -> None:
    conn = None
    try:
        ok, _ = ensure_admin_reads_schema()
        if not ok:
            return
        ts = seen_at or datetime.utcnow().isoformat()
        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if is_postgres() else "?"
        cur.execute(
            f"""
            INSERT INTO admin_message_reads (username, last_seen)
            VALUES ({ph}, {ph})
            ON CONFLICT(username) DO UPDATE SET last_seen = EXCLUDED.last_seen
            """,
            (username or "", ts),
        )
        conn.commit()
    except Exception:
        try:
            if conn and is_postgres():
                conn.rollback()
        except Exception:
            pass
    finally:
        try:
            if conn:
                put_conn(conn)
        except Exception:
            pass
