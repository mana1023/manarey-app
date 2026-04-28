"""models/db.py

Conector SQL para Manarey (PostgreSQL/Supabase obligatorio).
Lee DATABASE_URL de env, config.json o .dburl (legado) y no tiene
fallback a SQLite.
"""
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

try:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool
except ImportError:
    psycopg2 = None
    ThreadedConnectionPool = None

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATHS = [
    BASE_DIR / "config.json",
    Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    / "Manarey"
    / "config.json",
]


def _load_config() -> dict:
    for cfg_path in CONFIG_PATHS:
        if cfg_path.exists():
            try:
                return json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("No se pudo leer config de %s: %s", cfg_path, exc)
    return {}


def _resolve_db_url(cfg: dict, cfg_path: Path) -> str:
    """Obtiene la DB URL del config. Si está en texto plano la ofusca y guarda."""
    try:
        from models.config_security import decode_url, migrate_config

        if cfg.get("database_url_enc"):
            return decode_url(cfg["database_url_enc"]).strip()

        plain = cfg.get("database_url", "").strip()
        if plain:
            migrate_config(cfg_path)
            return plain
    except Exception:
        return (cfg.get("database_url") or "").strip()
    return ""


_config = _load_config()
_config_path = next((p for p in CONFIG_PATHS if p.exists()), CONFIG_PATHS[0])
_config_url = _resolve_db_url(_config, _config_path)

DB_URL = os.environ.get("DATABASE_URL") or _config_url
if not DB_URL:
    dburl_path = BASE_DIR / ".dburl"
    if dburl_path.exists():
        DB_URL = dburl_path.read_text(encoding="utf-8").strip()

_pool = None
_last_pool_fail_ts = 0.0
_last_pool_fail_exc: Exception | None = None


def _pool_fail_cooldown_seconds() -> int:
    try:
        return int(os.environ.get("MANAREY_PG_POOL_RETRY_SECONDS", "15"))
    except Exception:
        return 15


def _should_skip_pool_init() -> bool:
    if not _last_pool_fail_ts or _last_pool_fail_exc is None:
        return False
    try:
        return (time.time() - _last_pool_fail_ts) < _pool_fail_cooldown_seconds()
    except Exception:
        return False


def _supabase_direct_fallback(pool_url: str) -> str | None:
    """Convierte una URL de pooler Supabase en el host directo db.<project>.supabase.co."""
    try:
        parsed = urlparse(pool_url)
    except Exception:
        return None

    host = (parsed.hostname or "").lower()
    if ".pooler.supabase.com" not in host:
        return None

    user = parsed.username or ""
    password = parsed.password or ""
    project_ref = None
    base_user = user

    if "." in user:
        base_user, project_ref = user.split(".", 1)

    qs = parse_qs(parsed.query)
    if not project_ref:
        for opt in qs.get("options", []):
            if opt.startswith("project="):
                project_ref = opt.split("project=", 1)[1]
                break

    if not project_ref:
        return None

    new_host = f"db.{project_ref}.supabase.co"
    port = parsed.port or 5432
    path = parsed.path or "/postgres"
    qs.pop("options", None)
    query = urlencode(qs, doseq=True)

    auth_user = base_user or "postgres"
    auth = f"{auth_user}:{password}" if password else auth_user
    netloc = f"{auth}@{new_host}:{port}"

    return urlunparse((parsed.scheme or "postgresql", netloc, path, "", query, ""))


def _with_connect_params(dsn: str) -> str:
    """Agrega timeouts/keepalives a la URL si no existen."""
    try:
        parsed = urlparse(dsn)
    except Exception:
        return dsn

    qs = parse_qs(parsed.query)
    # Timeouts y keepalives razonables para evitar esperas largas
    if "connect_timeout" not in qs:
        qs["connect_timeout"] = ["5"]
    if "keepalives" not in qs:
        qs["keepalives"] = ["1"]
    if "keepalives_idle" not in qs:
        qs["keepalives_idle"] = ["30"]
    if "keepalives_interval" not in qs:
        qs["keepalives_interval"] = ["10"]
    if "keepalives_count" not in qs:
        qs["keepalives_count"] = ["5"]
    query = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", query, ""))


def _ensure_psycopg():
    if psycopg2 is None or ThreadedConnectionPool is None:
        raise RuntimeError(
            "psycopg2-binary no está instalado y es requerido para PostgreSQL"
        )


def _init_pool_if_needed():
    global _pool, DB_URL, _last_pool_fail_ts, _last_pool_fail_exc
    if _pool or not is_postgres():
        return
    if _should_skip_pool_init():
        # Evitar reintentos agresivos cuando hay fallo de DNS/red
        raise _last_pool_fail_exc  # type: ignore[misc]
    _ensure_psycopg()
    max_pool = int(os.environ.get("MANAREY_PG_POOL_MAX", "10"))
    pool_urls = [DB_URL]
    fb = _supabase_direct_fallback(DB_URL)
    # Si es pooler, probar directo primero para reducir latencia
    prefer_pooler = os.environ.get("MANAREY_PG_PREFER_POOLER", "").strip() in (
        "1",
        "true",
        "yes",
    )
    if fb and fb not in pool_urls:
        if prefer_pooler:
            pool_urls.append(fb)
        else:
            pool_urls = [fb, DB_URL]

    last_exc = None
    for dsn in pool_urls:
        try:
            dsn = _with_connect_params(dsn)
            _pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=max_pool,
                dsn=dsn,
                sslmode="require",
            )
            DB_URL = dsn
            if dsn != pool_urls[0]:
                logger.warning(
                    "Conexion por pooler fallo; usando host directo de Supabase."
                )
            logger.info(f"Pool Postgres inicializado (max {max_pool})")
            return
        except Exception as exc:
            last_exc = exc
            _last_pool_fail_ts = time.time()
            _last_pool_fail_exc = exc
            logger.warning("No se pudo inicializar pool con %s: %s", dsn, exc)

    if last_exc:
        raise last_exc


def init_db():
    """Inicializa el pool (solo Postgres)."""
    if not is_postgres():
        raise RuntimeError(
            "DATABASE_URL no configurado; Manarey requiere PostgreSQL/Supabase"
        )
    _init_pool_if_needed()


def is_postgres():
    return isinstance(DB_URL, str) and DB_URL.lower().startswith("postgres")


def _is_conn_alive(conn) -> bool:
    if conn is None:
        return False
    try:
        if getattr(conn, "closed", 0):
            return False
    except Exception:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def _new_direct_connection():
    _ensure_psycopg()
    return psycopg2.connect(dsn=_with_connect_params(DB_URL), sslmode="require")


def get_connection():
    """Obtiene una conexión a PostgreSQL/Supabase."""
    if not is_postgres():
        raise RuntimeError(
            "DATABASE_URL no configurado; Manarey requiere PostgreSQL/Supabase"
        )
    _init_pool_if_needed()
    if _pool:
        conn = _pool.getconn()
        if _is_conn_alive(conn):
            return conn
        try:
            _pool.putconn(conn, close=True)
        except Exception:
            pass
        logger.warning("Conexion del pool invalida; solicitando una nueva.")
        conn = _pool.getconn()
        if _is_conn_alive(conn):
            return conn
        try:
            _pool.putconn(conn, close=True)
        except Exception:
            pass
        logger.warning("La conexion del pool sigue invalida; usando conexion directa.")
        return _new_direct_connection()
    return _new_direct_connection()


def put_connection(conn):
    """Devuelve la conexión al pool o la cierra."""
    if conn is None:
        return
    should_close = False
    try:
        should_close = bool(getattr(conn, "closed", 0))
    except Exception:
        should_close = True
    if _pool:
        try:
            _pool.putconn(conn, close=should_close)
            return
        except Exception:
            pass
    try:
        conn.close()
    except Exception:
        pass


def cleanup_connections():
    """Cierra el pool de Postgres si existe."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
