"""Seguimiento interno de operaciones Boston Creed."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from models.db import get_connection as get_conn
from models.db import is_postgres
from models.db import put_connection as put_conn

logger = logging.getLogger(__name__)
BUFFER_PCT = 0.15  # 15 % interno, nunca visible en boleta
DIAS_PAGO = 30


def _ph():
    return "%s" if is_postgres() else "?"


def registrar_operacion(
    venta_id: int,
    local: str,
    usuario: str,
    monto_venta: float,
) -> bool:
    """Crea un registro interno al registrar una venta Boston Creed."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        monto_interno = round(monto_venta * (1 + BUFFER_PCT), 2)
        fecha_esp = datetime.now() + timedelta(days=DIAS_PAGO)
        cur.execute(
            f"INSERT INTO boston_creed_ops "
            f"(venta_id,local,usuario,monto_venta,monto_interno,estado,fecha_esperada) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph},'pendiente',{ph})",
            (
                int(venta_id),
                local,
                usuario,
                float(monto_venta),
                float(monto_interno),
                fecha_esp.isoformat(),
            ),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception("Error registrando op Boston Creed")
        return False
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def list_operaciones(
    local: str = "",
    estado: str = "",
    limit: int = 200,
) -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        wheres = []
        params: list = []
        if local and local not in ("Todos", "Todos los locales"):
            wheres.append(f"bc.local={ph}")
            params.append(local)
        if estado:
            wheres.append(f"bc.estado={ph}")
            params.append(estado)
        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        cur.execute(
            f"SELECT bc.id, bc.venta_id, bc.local, bc.usuario, bc.monto_venta, "
            f"bc.monto_interno, bc.estado, bc.fecha, bc.fecha_esperada, "
            f"bc.fecha_liquidacion, bc.liquidado_por, bc.notas, "
            f"v.numero_venta, v.cliente_nombre, v.cliente_telefono "
            f"FROM boston_creed_ops bc "
            f"LEFT JOIN ventas v ON v.id=bc.venta_id "
            f"{where_sql} "
            f"ORDER BY bc.fecha DESC LIMIT {limit}",
            tuple(params),
        )
        cols = [
            "id",
            "venta_id",
            "local",
            "usuario",
            "monto_venta",
            "monto_interno",
            "estado",
            "fecha",
            "fecha_esperada",
            "fecha_liquidacion",
            "liquidado_por",
            "notas",
            "numero_venta",
            "cliente_nombre",
            "cliente_telefono",
        ]
        rows = []
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            d["vencida"] = False
            if d["fecha_esperada"] and d["estado"] == "pendiente":
                try:
                    fe = d["fecha_esperada"]
                    if hasattr(fe, "date"):
                        fe = fe.replace(tzinfo=None)
                    else:
                        fe = datetime.fromisoformat(str(fe))
                    d["vencida"] = datetime.now() > fe
                except Exception:
                    pass
            rows.append(d)
        return rows
    except Exception:
        logger.exception("Error listando operaciones Boston Creed")
        return []
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def liquidar_operacion(op_id: int, usuario: str, notas: str = "") -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"UPDATE boston_creed_ops SET estado='liquidado', "
            f"fecha_liquidacion=NOW(), liquidado_por={ph}, notas={ph} "
            f"WHERE id={ph}",
            (usuario, notas, int(op_id)),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception("Error liquidando op Boston Creed")
        return False
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def marcar_efectivo_en_local(op_id: int, notas: str = "") -> bool:
    """El cliente pagÃ³ en efectivo â†’ la plata estÃ¡ en el local."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        cur.execute(
            f"UPDATE boston_creed_ops SET estado='efectivo_en_local', notas={ph} WHERE id={ph}",
            (notas, int(op_id)),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception("Error marcando efectivo en local")
        return False
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def get_resumen(local: str = "") -> Dict[str, Any]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = _ph()
        loc_filter = f"AND local={ph}" if local and local not in ("Todos",) else ""
        params = [local] if loc_filter else []
        cur.execute(
            f"SELECT estado, COUNT(*), COALESCE(SUM(monto_venta),0) "
            f"FROM boston_creed_ops WHERE 1=1 {loc_filter} GROUP BY estado",
            tuple(params),
        )
        res = {
            "pendiente": 0,
            "efectivo_en_local": 0,
            "liquidado": 0,
            "monto_pendiente": 0.0,
            "monto_efectivo": 0.0,
        }
        for row in cur.fetchall():
            estado, cnt, monto = row
            if estado == "pendiente":
                res["pendiente"] = int(cnt)
                res["monto_pendiente"] = float(monto)
            elif estado == "efectivo_en_local":
                res["efectivo_en_local"] = int(cnt)
                res["monto_efectivo"] = float(monto)
            elif estado == "liquidado":
                res["liquidado"] = int(cnt)
        return res
    except Exception:
        logger.exception("Error obteniendo resumen Boston Creed")
        return {}
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass
