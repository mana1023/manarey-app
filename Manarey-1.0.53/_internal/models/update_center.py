import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.db import get_connection, is_postgres, put_connection

logger = logging.getLogger(__name__)


def _ensure_table(cur) -> None:
    """Crea la tabla de actualizaciones si no existe."""
    if is_postgres():
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_updates (
                id SERIAL PRIMARY KEY,
                version TEXT NOT NULL,
                download_url TEXT NOT NULL,
                changelog TEXT,
                checksum TEXT,
                mandatory BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                download_url TEXT NOT NULL,
                changelog TEXT,
                checksum TEXT,
                mandatory INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )


def publish_update(
    version: str,
    download_url: str,
    changelog: str = "",
    checksum: str = "",
    mandatory: bool = False,
) -> bool:
    """Guarda una nueva actualización en la tabla app_updates."""
    if not version or not download_url:
        return False
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        _ensure_table(cur)
        now_ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """
            INSERT INTO app_updates (version, download_url, changelog, checksum, mandatory, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            if is_postgres()
            else """
            INSERT INTO app_updates (version, download_url, changelog, checksum, mandatory, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                version,
                download_url,
                changelog or "",
                checksum or "",
                bool(mandatory),
                now_ts,
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("No se pudo publicar la actualización: %s", e)
        return False
    finally:
        if conn:
            try:
                put_connection(conn)
            except Exception:
                pass


def latest_update() -> Optional[Dict[str, Any]]:
    """Devuelve la última actualización publicada o None."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        _ensure_table(cur)
        cur.execute(
            """
            SELECT id, version, download_url, changelog, checksum, mandatory, created_at
            FROM app_updates
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "version": row[1],
            "download_url": row[2],
            "changelog": row[3],
            "checksum": row[4],
            "mandatory": bool(row[5]),
            "created_at": row[6],
        }
    except Exception as e:
        logger.error("No se pudo leer la última actualización: %s", e)
        return None
    finally:
        if conn:
            try:
                put_connection(conn)
            except Exception:
                pass


def list_updates(limit: int = 20) -> List[Dict[str, Any]]:
    """Lista las últimas N actualizaciones."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        _ensure_table(cur)
        cur.execute(
            """
            SELECT id, version, download_url, changelog, checksum, mandatory, created_at
            FROM app_updates
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """
            if is_postgres()
            else """
            SELECT id, version, download_url, changelog, checksum, mandatory, created_at
            FROM app_updates
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "id": r[0],
                    "version": r[1],
                    "download_url": r[2],
                    "changelog": r[3],
                    "checksum": r[4],
                    "mandatory": bool(r[5]),
                    "created_at": r[6],
                }
            )
        return out
    except Exception as e:
        logger.error("No se pudo listar actualizaciones: %s", e)
        return []
    finally:
        if conn:
            try:
                put_connection(conn)
            except Exception:
                pass
