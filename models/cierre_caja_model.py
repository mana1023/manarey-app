"""Cierre de turno / caja diaria."""
import logging
from typing import Any, Dict, List, Optional

from models.db import get_connection as get_conn
from models.db import is_postgres
from models.db import put_connection as put_conn

logger = logging.getLogger(__name__)


def _ph():
    return "%s" if is_postgres() else "?"


# â”€â”€ Gastos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def add_gasto(local: str, usuario: str, concepto: str, monto: float) -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"INSERT INTO gastos_caja (local,usuario,concepto,monto) "
            f"VALUES ({ph},{ph},{ph},{ph})",
            (local, usuario, concepto.strip(), float(monto)),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception("Error agregando gasto")
        return False
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def get_gastos_del_dia(local: str) -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"SELECT id,concepto,monto,usuario,fecha FROM gastos_caja "
            f"WHERE local={ph} AND cierre_id IS NULL AND DATE(fecha)=CURRENT_DATE "
            f"ORDER BY fecha",
            (local,),
        )
        cols = ["id", "concepto", "monto", "usuario", "fecha"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        logger.exception("Error obteniendo gastos del dÃ­a")
        return []
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def delete_gasto(gasto_id: int) -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(f"DELETE FROM gastos_caja WHERE id={ph}", (gasto_id,))
        conn.commit()
        return True
    except Exception:
        logger.exception("Error eliminando gasto")
        return False
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


# â”€â”€ Cierre â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def hacer_cierre(
    local: str,
    usuario: str,
    monto_inicial: float,
    ventas_efectivo: float,
    monto_real: float,
    notas: str = "",
) -> Optional[int]:
    """Registra el cierre de turno y asocia los gastos del dÃ­a al cierre."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()

        gastos = get_gastos_del_dia(local)
        gastos_total = sum(float(g["monto"]) for g in gastos)
        monto_esperado = monto_inicial + ventas_efectivo - gastos_total
        diferencia = monto_real - monto_esperado

        if is_postgres():
            cur.execute(
                f"INSERT INTO cierre_caja "
                f"(local,usuario,monto_inicial,ventas_efectivo,gastos_total,"
                f"monto_esperado,monto_real,diferencia,notas) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph}) RETURNING id",
                (
                    local,
                    usuario,
                    float(monto_inicial),
                    float(ventas_efectivo),
                    float(gastos_total),
                    float(monto_esperado),
                    float(monto_real),
                    float(diferencia),
                    notas.strip(),
                ),
            )
            cierre_id = (cur.fetchone() or [None])[0]
        else:
            cur.execute(
                f"INSERT INTO cierre_caja "
                f"(local,usuario,monto_inicial,ventas_efectivo,gastos_total,"
                f"monto_esperado,monto_real,diferencia,notas) "
                f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
                (
                    local,
                    usuario,
                    float(monto_inicial),
                    float(ventas_efectivo),
                    float(gastos_total),
                    float(monto_esperado),
                    float(monto_real),
                    float(diferencia),
                    notas.strip(),
                ),
            )
            cierre_id = cur.lastrowid

        if cierre_id:
            ids = [g["id"] for g in gastos]
            for gid in ids:
                cur.execute(
                    f"UPDATE gastos_caja SET cierre_id={ph} WHERE id={ph}",
                    (cierre_id, gid),
                )

        conn.commit()
        return cierre_id
    except Exception:
        logger.exception("Error haciendo cierre de caja")
        return None
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def get_cierres(local: str, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        wheres = []
        params: list = []
        if local and local not in ("Todos", "Todos los locales"):
            wheres.append(f"local={ph}")
            params.append(local)
        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        cur.execute(
            f"SELECT id,local,usuario,fecha_cierre,monto_inicial,ventas_efectivo,"
            f"gastos_total,monto_esperado,monto_real,diferencia,notas "
            f"FROM cierre_caja {where_sql} ORDER BY fecha_cierre DESC LIMIT {limit}",
            tuple(params),
        )
        cols = [
            "id",
            "local",
            "usuario",
            "fecha_cierre",
            "monto_inicial",
            "ventas_efectivo",
            "gastos_total",
            "monto_esperado",
            "monto_real",
            "diferencia",
            "notas",
        ]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        logger.exception("Error obteniendo cierres")
        return []
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def get_ultimo_cierre(local: str) -> Optional[Dict[str, Any]]:
    cierres = get_cierres(local, limit=1)
    return cierres[0] if cierres else None
