import json
import logging
import os
import socket
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from models import db

logger = logging.getLogger(__name__)


def _appdata_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    p = Path(base) / "Manarey"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _db_path() -> Path:
    return _appdata_dir() / "offline.db"


def _now_local() -> str:
    try:
        return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_cache (
                producto_id INTEGER,
                nombre TEXT,
                material TEXT,
                categoria TEXT,
                medida TEXT,
                estado TEXT,
                color TEXT,
                cantidad INTEGER,
                precio_venta REAL,
                local TEXT,
                fabricante TEXT,
                codigo TEXT,
                updated_at TEXT,
                PRIMARY KEY (producto_id, local)
            )
            """
        )
        # Migración suave: agregar columna material si falta
        try:
            cur.execute("PRAGMA table_info(stock_cache)")
            cols = {r[1] for r in cur.fetchall()}
            if "material" not in cols:
                cur.execute("ALTER TABLE stock_cache ADD COLUMN material TEXT")
                # Limpiar cache antiguo sin material para evitar mostrar "-"
                cur.execute("DELETE FROM stock_cache")
        except Exception:
            pass
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS offline_ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0,
                synced_at TEXT,
                last_error TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _parse_db_host() -> Tuple[str, int]:
    try:
        url = db.DB_URL or os.environ.get("DATABASE_URL") or ""
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or 5432
        return host, int(port)
    except Exception:
        return "", 5432


def is_online(timeout: float = 2.0) -> bool:
    host, port = _parse_db_host()
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def is_offline_exception(exc: Exception) -> bool:
    msg = str(exc).lower()
    patterns = (
        "could not connect",
        "connection refused",
        "connection timed out",
        "timeout",
        "network is unreachable",
        "server closed the connection",
        "terminating connection",
        "connection not open",
        "connection already closed",
        "database_url no configurado",
    )
    return any(p in msg for p in patterns)


def cache_stock(local: str, data: List[dict]) -> None:
    if not local or not data:
        return
    init_db()
    conn = _conn()
    try:
        cur = conn.cursor()
        if local in ("Todos", "Todos los locales", ""):
            cur.execute("DELETE FROM stock_cache")
        else:
            cur.execute("DELETE FROM stock_cache WHERE local = ?", (local,))
        rows = []
        now = _now_local()
        for p in data:
            loc = (p.get("local") or local or "").strip()
            if not loc:
                continue
            rows.append(
                (
                    int(p.get("id") or 0),
                    p.get("nombre") or "",
                    p.get("material") or "",
                    p.get("categoria") or "",
                    p.get("medida") or "",
                    p.get("estado") or "",
                    p.get("color") or "",
                    int(p.get("cantidad") or 0),
                    float(p.get("precio_venta") or 0),
                    loc,
                    p.get("fabricante") or "",
                    p.get("codigo") or "",
                    now,
                )
            )
        cur.executemany(
            """
            INSERT OR REPLACE INTO stock_cache (
                producto_id, nombre, material, categoria, medida, estado, color,
                cantidad, precio_venta, local, fabricante, codigo, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    except Exception as e:
        logger.error("cache_stock failed: %s", e)
    finally:
        conn.close()


def _row_to_dict(r: sqlite3.Row) -> dict:
    return {
        "id": r["producto_id"],
        "nombre": r["nombre"],
        "material": r["material"] if "material" in r.keys() else "",
        "categoria": r["categoria"],
        "medida": r["medida"],
        "estado": r["estado"],
        "color": r["color"],
        "cantidad": r["cantidad"],
        "precio_venta": r["precio_venta"],
        "local": r["local"],
        "fabricante": r["fabricante"],
        "codigo": r["codigo"],
    }


def get_cached_stock(
    local: str,
    search: str = "",
    categoria: str = "",
    estado: str = "",
    medida: Any = "",
    fabricante: str = "",
    color: str = "",
) -> List[dict]:
    init_db()
    conn = _conn()
    try:
        cur = conn.cursor()
        if local in ("Todos", "Todos los locales", "", None):
            cur.execute("SELECT * FROM stock_cache")
        else:
            cur.execute("SELECT * FROM stock_cache WHERE local = ?", (local,))
        rows = [dict(_row_to_dict(r)) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_cached_stock failed: %s", e)
        rows = []
    finally:
        conn.close()

    s = (search or "").strip().lower()
    cat = (categoria or "").strip().lower()
    est = (estado or "").strip().lower()
    fab = (fabricante or "").strip().lower()
    col = (color or "").strip().lower()
    med = medida
    if isinstance(med, (list, tuple)):
        med_list = [str(m).strip().lower() for m in med if m]
    else:
        med_list = [str(med).strip().lower()] if med else []

    out = []
    for p in rows:
        if s and s not in (p.get("nombre") or "").lower():
            continue
        if cat and cat != (p.get("categoria") or "").lower():
            continue
        if est and est != (p.get("estado") or "").lower():
            continue
        if fab and fab != (p.get("fabricante") or "").lower():
            continue
        if col and col != (p.get("color") or "").lower():
            continue
        if med_list:
            if (p.get("medida") or "").lower() not in med_list:
                continue
        out.append(p)
    return out


def enqueue_venta(payload: Dict[str, Any]) -> int:
    init_db()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO offline_ventas (payload, created_at, synced) VALUES (?, ?, 0)",
            (json.dumps(payload, ensure_ascii=False), _now_local()),
        )
        offline_id = int(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    return offline_id


def get_offline_venta(offline_id: int) -> Optional[Dict[str, Any]]:
    init_db()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT payload FROM offline_ventas WHERE id = ?", (int(offline_id),)
        )
        row = cur.fetchone()
        if not row:
            return None
        return json.loads(row[0])
    except Exception:
        return None
    finally:
        conn.close()


def apply_offline_sale_to_cache(items: List[Dict[str, Any]]) -> None:
    if not items:
        return
    init_db()
    conn = _conn()
    try:
        cur = conn.cursor()
        for it in items:
            try:
                is_combo = int(it.get("is_combo") or 0) == 1
            except Exception:
                is_combo = False
            loc = (it.get("stock_local") or "").strip()
            if not loc:
                continue
            if is_combo:
                try:
                    from models import stock_model as sm

                    combo_id = int(it.get("combo_id") or it.get("producto_id") or 0)
                except Exception:
                    combo_id = 0
                if combo_id <= 0:
                    continue
                combo_items = it.get("combo_items")
                if not isinstance(combo_items, list) or not combo_items:
                    try:
                        combo_items = sm.get_combo_items(combo_id)
                    except Exception:
                        combo_items = []
                base_qty = int(it.get("cantidad") or 0)
                for ci in combo_items:
                    try:
                        pid = int(ci.get("producto_id") or 0)
                        qty = int(ci.get("cantidad") or 0) * base_qty
                    except Exception:
                        pid = 0
                        qty = 0
                    if pid <= 0 or qty <= 0:
                        continue
                    cur.execute(
                        "UPDATE stock_cache SET cantidad = MAX(0, cantidad - ?) WHERE producto_id = ? AND local = ?",
                        (int(qty), pid, loc),
                    )
            else:
                pid = int(it.get("producto_id") or 0)
                if not pid:
                    continue
                cur.execute(
                    "UPDATE stock_cache SET cantidad = MAX(0, cantidad - ?) WHERE producto_id = ? AND local = ?",
                    (int(it.get("cantidad") or 0), pid, loc),
                )
        conn.commit()
    except Exception as e:
        logger.error("apply_offline_sale_to_cache failed: %s", e)
    finally:
        conn.close()


def _pending_rows() -> List[Tuple[int, Dict[str, Any]]]:
    init_db()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, payload FROM offline_ventas WHERE synced = 0 ORDER BY id ASC"
        )
        rows = []
        for r in cur.fetchall():
            try:
                rows.append((int(r[0]), json.loads(r[1])))
            except Exception:
                continue
        return rows
    finally:
        conn.close()


def _mark_synced(offline_id: int) -> None:
    init_db()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE offline_ventas SET synced = 1, synced_at = ?, last_error = NULL WHERE id = ?",
            (_now_local(), int(offline_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _set_error(offline_id: int, msg: str) -> None:
    init_db()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE offline_ventas SET last_error = ? WHERE id = ?",
            (msg[:1000], int(offline_id)),
        )
        conn.commit()
    finally:
        conn.close()


def sync_pending() -> int:
    if not is_online():
        return 0
    rows = _pending_rows()
    if not rows:
        return 0
    synced = 0
    for offline_id, payload in rows:
        try:
            from models import ventas_model as vm

            ok, msg, _ = vm._registrar_venta_online(**payload)
            if ok:
                _mark_synced(offline_id)
                synced += 1
            else:
                _set_error(offline_id, msg)
        except Exception as e:
            _set_error(offline_id, str(e))
    return synced
