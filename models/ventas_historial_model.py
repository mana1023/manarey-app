import time
from datetime import datetime, timedelta

from models.db import get_connection as get_conn
from models.db import is_postgres as db_is_pg
from models.db import put_connection as put_conn

_VENTAS_CACHE = {}
_VENTAS_CACHE_TTL = 8.0


def get_ventas_por_local(
    local: str,
    filtro_fecha: str = "todo",
    search: str = "",
    fecha_dia: str = None,
    fecha_inicio: str = None,
    fecha_fin: str = None,
    include_canceladas: bool = False,
) -> list:
    """
    Obtiene todas las ventas de un local específico con filtros de fecha

    Args:
        local: Local específico ('Cane', 'Vidriera', etc.) o 'Todos' para admin
        filtro_fecha: Filtro de fecha ('hoy', 'semana', 'mes', 'todo', 'dia')
        search: Texto de búsqueda para filtrar por cliente o número de venta

    Returns:
        list: Lista de ventas con toda la información
    """
    conn = get_conn()
    cur = conn.cursor()
    ph = "%s" if db_is_pg() else "?"

    # Construir consulta base (sin GROUP_CONCAT para compatibilidad entre motores)
    query = """
        SELECT v.*
        FROM ventas v
    """

    params = []

    # Filtrar por local solo si no es "Todos"
    if local and local != "Todos":
        query += f" WHERE v.local = {ph}"
        params = [local]
    else:
        query += " WHERE 1=1"

    # Solo ventas completadas (o incluir canceladas si se pide)
    if include_canceladas:
        query += " AND v.estado IN ('completada','cancelada')"
    else:
        query += " AND v.estado = 'completada'"

    # Aplicar filtro de fecha (rango calculado en Python, formato 'YYYY-MM-DD HH:MM:SS')
    start_ts = end_ts = None
    now = datetime.now()
    if fecha_inicio and fecha_fin:
        try:
            si = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            sf = datetime.strptime(fecha_fin, "%Y-%m-%d")
            start = si.replace(hour=0, minute=0, second=0, microsecond=0)
            end = sf.replace(hour=23, minute=59, second=59, microsecond=0)
            start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except Exception:
            start_ts = end_ts = None
    if fecha_dia:
        d = None
        try:
            d = datetime.strptime(fecha_dia, "%Y-%m-%d")
        except Exception:
            try:
                d = datetime.strptime(fecha_dia, "%d-%m-%Y")
            except Exception:
                d = None
        if d:
            start = d.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
    if not start_ts:
        if filtro_fecha in ["hoy", "dia"]:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        elif filtro_fecha == "semana":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
                days=7
            )
            end = now.replace(hour=23, minute=59, second=59, microsecond=0)
            start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        elif filtro_fecha == "mes":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
                days=30
            )
            end = now.replace(hour=23, minute=59, second=59, microsecond=0)
            start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

    if start_ts and end_ts:
        query += f" AND v.fecha >= {ph} AND v.fecha <= {ph}"
        params.extend([start_ts, end_ts])

    # Aplicar búsqueda
    if search:
        query += f" AND (v.cliente_nombre LIKE {ph} OR v.numero_venta LIKE {ph})"
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern])

    # Completar consulta
    query += " ORDER BY v.fecha DESC"

    cur.execute(query, tuple(params))
    columns = [desc[0] for desc in cur.description]
    ventas = [dict(zip(columns, row)) for row in cur.fetchall()]

    # Detectar existencia de tabla venta_pagos para evitar errores en Postgres
    has_venta_pagos = False
    try:
        if db_is_pg():
            try:
                cur.execute("SELECT to_regclass('venta_pagos')")
                r = cur.fetchone()
                # r puede ser tupla (('venta_pagos',)) o (None,)
                has_venta_pagos = bool(r and r[0])
            except Exception:
                try:
                    if db_is_pg():
                        conn.rollback()
                except Exception:
                    pass
                has_venta_pagos = False
        else:
            try:
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='venta_pagos'"
                )
                has_venta_pagos = cur.fetchone() is not None
            except Exception:
                has_venta_pagos = False
    except Exception:
        has_venta_pagos = False

    # Completar productos_count y productos_lista por cada venta (compatible con Postgres)
    for v in ventas:
        cur.execute(
            f"""
            SELECT producto_nombre, cantidad, producto_color
            FROM detalle_ventas
            WHERE venta_id = {ph}
            ORDER BY id
            """,
            (v["id"],),
        )
        det = cur.fetchall()
        # sqlite3.Row y RealDictRow se comportan como mappings
        productos_count = len(det)
        partes = []
        for r in det:
            try:
                nombre = r["producto_nombre"]
            except Exception:
                nombre = r[0]
            try:
                cantidad = r["cantidad"]
            except Exception:
                cantidad = r[1]
            # Incluir color si existe
            color = None
            try:
                color = r.get("producto_color")
            except Exception:
                try:
                    color = r[2]
                except Exception:
                    color = None
            if color:
                partes.append(f"{nombre} [{color}] ({cantidad})")
            else:
                partes.append(f"{nombre} ({cantidad})")
        v["productos_count"] = productos_count
        v["productos_lista"] = ", ".join(partes)

        # Adjuntar pagos por forma (si existen) para soportar pago dividido
        if has_venta_pagos:
            try:
                cur.execute(
                    f"""
                    SELECT forma, monto
                    FROM venta_pagos
                    WHERE venta_id = {ph}
                    ORDER BY id
                    """,
                    (v["id"],),
                )
                pagos_rows = cur.fetchall()
                pagos = []
                for pr in pagos_rows:
                    try:
                        pagos.append(
                            {"forma": pr["forma"], "monto": float(pr["monto"])}
                        )
                    except Exception:
                        pagos.append({"forma": pr[0], "monto": float(pr[1])})
                v["pagos"] = pagos
            except Exception:
                # En Postgres, tras un error, limpiar estado de transacción
                try:
                    if db_is_pg():
                        conn.rollback()
                except Exception:
                    pass
                v["pagos"] = []
        else:
            v["pagos"] = []

    put_conn(conn)
    return ventas


def get_ventas_por_local_fast(
    local: str,
    filtro_fecha: str = "todo",
    search: str = "",
    fecha_dia: str = None,
    fecha_inicio: str = None,
    fecha_fin: str = None,
    include_canceladas: bool = False,
) -> list:
    cache_key = (
        local or "",
        filtro_fecha or "",
        search or "",
        fecha_dia or "",
        fecha_inicio or "",
        fecha_fin or "",
        int(bool(include_canceladas)),
    )
    now_ts = time.time()
    cached = _VENTAS_CACHE.get(cache_key)
    if cached and (now_ts - cached[0]) <= _VENTAS_CACHE_TTL:
        return [dict(v) for v in cached[1]]

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        ph = "%s" if db_is_pg() else "?"

        query = """
            SELECT v.*
            FROM ventas v
        """
        params = []
        if local and local != "Todos":
            query += f" WHERE v.local = {ph}"
            params = [local]
        else:
            query += " WHERE 1=1"

        if include_canceladas:
            query += " AND v.estado IN ('completada','cancelada')"
        else:
            query += " AND v.estado = 'completada'"

        start_ts = end_ts = None
        now = datetime.now()
        if fecha_inicio and fecha_fin:
            try:
                si = datetime.strptime(fecha_inicio, "%Y-%m-%d")
                sf = datetime.strptime(fecha_fin, "%Y-%m-%d")
                start = si.replace(hour=0, minute=0, second=0, microsecond=0)
                end = sf.replace(hour=23, minute=59, second=59, microsecond=0)
                start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except Exception:
                start_ts = end_ts = None
        if fecha_dia:
            d = None
            try:
                d = datetime.strptime(fecha_dia, "%Y-%m-%d")
            except Exception:
                try:
                    d = datetime.strptime(fecha_dia, "%d-%m-%Y")
                except Exception:
                    d = None
            if d:
                start = d.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
                start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
        if not start_ts:
            if filtro_fecha in ["hoy", "dia"]:
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
                start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            elif filtro_fecha == "semana":
                start = now.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) - timedelta(days=7)
                end = now.replace(hour=23, minute=59, second=59, microsecond=0)
                start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            elif filtro_fecha == "mes":
                start = now.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) - timedelta(days=30)
                end = now.replace(hour=23, minute=59, second=59, microsecond=0)
                start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

        if start_ts and end_ts:
            query += f" AND v.fecha >= {ph} AND v.fecha <= {ph}"
            params.extend([start_ts, end_ts])

        if search:
            query += f" AND (v.cliente_nombre LIKE {ph} OR v.numero_venta LIKE {ph})"
            pattern = f"%{search}%"
            params.extend([pattern, pattern])

        query += " ORDER BY v.fecha DESC"
        cur.execute(query, tuple(params))
        columns = [desc[0] for desc in cur.description]
        ventas = [dict(zip(columns, row)) for row in cur.fetchall()]

        has_venta_pagos = False
        try:
            if db_is_pg():
                cur.execute("SELECT to_regclass('venta_pagos')")
                r = cur.fetchone()
                has_venta_pagos = bool(r and r[0])
            else:
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='venta_pagos'"
                )
                has_venta_pagos = cur.fetchone() is not None
        except Exception:
            try:
                if db_is_pg():
                    conn.rollback()
            except Exception:
                pass
            has_venta_pagos = False

        venta_ids = [v.get("id") for v in ventas if v.get("id") is not None]
        detalle_map = {}
        pagos_map = {}
        if venta_ids:
            in_clause = ", ".join([ph] * len(venta_ids))
            cur.execute(
                f"""
                SELECT venta_id, producto_nombre, cantidad, producto_color
                FROM detalle_ventas
                WHERE venta_id IN ({in_clause})
                ORDER BY venta_id, id
                """,
                tuple(venta_ids),
            )
            for r in cur.fetchall():
                try:
                    venta_id = r["venta_id"]
                    nombre = r["producto_nombre"]
                    cantidad = r["cantidad"]
                    color = r["producto_color"]
                except Exception:
                    venta_id, nombre, cantidad, color = r[0], r[1], r[2], r[3]
                detalle_map.setdefault(venta_id, []).append((nombre, cantidad, color))

            if has_venta_pagos:
                try:
                    cur.execute(
                        f"""
                        SELECT venta_id, forma, monto
                        FROM venta_pagos
                        WHERE venta_id IN ({in_clause})
                        ORDER BY venta_id, id
                        """,
                        tuple(venta_ids),
                    )
                    for r in cur.fetchall():
                        try:
                            venta_id = r["venta_id"]
                            forma = r["forma"]
                            monto = float(r["monto"])
                        except Exception:
                            venta_id, forma, monto = r[0], r[1], float(r[2])
                        pagos_map.setdefault(venta_id, []).append(
                            {"forma": forma, "monto": monto}
                        )
                except Exception:
                    try:
                        if db_is_pg():
                            conn.rollback()
                    except Exception:
                        pass
                    pagos_map = {}

        for v in ventas:
            det = detalle_map.get(v.get("id"), [])
            v["productos_count"] = len(det)
            v["productos_lista"] = ", ".join(
                [
                    f"{nombre} [{color}] ({cantidad})"
                    if color
                    else f"{nombre} ({cantidad})"
                    for nombre, cantidad, color in det
                ]
            )
            v["pagos"] = pagos_map.get(v.get("id"), []) if has_venta_pagos else []

        _VENTAS_CACHE[cache_key] = (now_ts, [dict(v) for v in ventas])
        return ventas
    finally:
        if conn is not None:
            try:
                put_conn(conn)
            except Exception:
                pass


def get_venta_detallada(venta_id: int) -> dict:
    """
    Obtiene todos los detalles de una venta específica

    Args:
        venta_id: ID de la venta

    Returns:
        dict: Información completa de la venta con detalles de productos
    """
    conn = get_conn()
    cur = conn.cursor()
    ph = "%s" if db_is_pg() else "?"

    try:
        # Obtener datos principales de la venta
        cur.execute(f"SELECT * FROM ventas WHERE id = {ph}", (venta_id,))
        venta_row = cur.fetchone()

        if not venta_row:
            return None

        venta_cols = [desc[0] for desc in cur.description]
        venta = dict(zip(venta_cols, venta_row))

        # Obtener detalles de productos
        cur.execute(
            f"""
            SELECT producto_id, producto_nombre AS nombre, producto_categoria AS categoria,
                   producto_medida AS medida, producto_estado AS estado, producto_color AS color,
                   cantidad, precio_unitario, subtotal
            FROM detalle_ventas
            WHERE venta_id = {ph}
            ORDER BY id
            """,
            (venta_id,),
        )
        det_rows = cur.fetchall()
        det_cols = [desc[0] for desc in cur.description]
        venta["items"] = [dict(zip(det_cols, r)) for r in det_rows]

        # Adjuntar pagos si existe tabla venta_pagos
        try:
            has_venta_pagos = False
            if db_is_pg():
                cur.execute("SELECT to_regclass('public.venta_pagos')")
                r = cur.fetchone()
                has_venta_pagos = bool(r and r[0])
            else:
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='venta_pagos'"
                )
                has_venta_pagos = cur.fetchone() is not None

            if has_venta_pagos:
                cur.execute(
                    f"SELECT forma, monto FROM venta_pagos WHERE venta_id = {ph} ORDER BY id",
                    (venta_id,),
                )
                pagos_rows = cur.fetchall()
                venta["pagos"] = [
                    {"forma": pr[0], "monto": float(pr[1])} for pr in pagos_rows
                ]
            else:
                venta["pagos"] = []
        except Exception:
            try:
                if db_is_pg():
                    conn.rollback()
            except Exception:
                pass
            venta["pagos"] = []

        return venta
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass


def get_estadisticas_ventas(
    local: str = None,
    filtro_fecha: str = "mes",
    fecha_dia: str = None,
    fecha_inicio: str = None,
    fecha_fin: str = None,
) -> dict:
    """
    Obtiene estadísticas de ventas para un local o todos

    Args:
        local: Local específico o None para todos
        filtro_fecha: Período para estadísticas ('dia', 'hoy', 'semana', 'mes', 'todo')

    Returns:
        dict: Estadísticas de ventas
    """
    conn = get_conn()
    cur = conn.cursor()
    ph = "%s" if db_is_pg() else "?"

    # Construir consulta para estadísticas
    query = """
        SELECT
            COUNT(DISTINCT v.id) as total_ventas,
            SUM(v.total) as total_monto,
            AVG(v.total) as promedio_venta,
            SUM(CASE WHEN v.tipo_pago = 'sena' THEN v.monto_pagado ELSE 0 END) as total_senas,
            COUNT(DISTINCT CASE WHEN v.tipo_pago = 'sena' THEN v.id END) as ventas_con_sena,
            COALESCE(SUM(dv.cantidad), 0) as total_productos,
            SUM(v.monto_pendiente) as total_pendiente
        FROM ventas v
        LEFT JOIN detalle_ventas dv ON v.id = dv.venta_id
    """

    params = []

    # Filtrar por local si se especifica
    if local:
        query += f" WHERE v.local = {ph}"
        params = [local]
    else:
        query += " WHERE 1=1"

    # Solo ventas completadas
    query += " AND v.estado = 'completada'"

    # Filtro de fecha independiente del motor
    start_ts = end_ts = None
    now = datetime.now()
    if fecha_inicio and fecha_fin:
        try:
            si = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            sf = datetime.strptime(fecha_fin, "%Y-%m-%d")
            start = si.replace(hour=0, minute=0, second=0, microsecond=0)
            end = sf.replace(hour=23, minute=59, second=59, microsecond=0)
            start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except Exception:
            start_ts = end_ts = None
    if fecha_dia:
        d = None
        try:
            d = datetime.strptime(fecha_dia, "%Y-%m-%d")
        except Exception:
            try:
                d = datetime.strptime(fecha_dia, "%d-%m-%Y")
            except Exception:
                d = None
        if d:
            start = d.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
    if not start_ts:
        if filtro_fecha in ["hoy", "dia"]:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        elif filtro_fecha == "semana":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
                days=7
            )
            end = now.replace(hour=23, minute=59, second=59, microsecond=0)
            start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        elif filtro_fecha == "mes":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
                days=30
            )
            end = now.replace(hour=23, minute=59, second=59, microsecond=0)
            start_ts, end_ts = start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

    if start_ts and end_ts:
        query += f" AND v.fecha >= {ph} AND v.fecha <= {ph}"
        params.extend([start_ts, end_ts])

    try:
        cur.execute(query, tuple(params))
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description] if cur.description else []
        row_dict = dict(zip(cols, row)) if row else {}
        estadisticas = {
            "total_ventas": (row_dict.get("total_ventas") or 0),
            "total_monto": (row_dict.get("total_monto") or 0),
            "promedio_venta": (row_dict.get("promedio_venta") or 0),
            "total_senas": (row_dict.get("total_senas") or 0),
            "ventas_con_sena": (row_dict.get("ventas_con_sena") or 0),
            "total_productos": (row_dict.get("total_productos") or 0),
            "total_pendiente": (row_dict.get("total_pendiente") or 0),
        }
        return estadisticas
    finally:
        try:
            put_conn(conn)
        except Exception:
            pass
