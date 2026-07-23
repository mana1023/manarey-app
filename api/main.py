"""API de Manarey para la app del jefe.

Guarda la conexion a la base del lado del servidor (nunca en el celular) y
reutiliza los modulos `models/` de la app de escritorio, de forma que el
celular use EXACTAMENTE las mismas reglas de negocio (historial de stock,
reservas, combos) y las boletas/remitos salgan identicas.
"""
import os
import sys
from datetime import datetime

# La API vive dentro del repo de Manarey: models/ esta un nivel arriba.
# Asi comparte el codigo real y nunca se despega de la app de escritorio.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from fastapi import (  # noqa: E402
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse  # noqa: E402

from models.db import get_connection, put_connection  # noqa: E402

app = FastAPI(title="Manarey API", version="1.0.0")

API_TOKEN = os.environ.get("MANAREY_API_TOKEN", "")
# En un servidor real el token es OBLIGATORIO: sin el, cualquiera que
# adivine la direccion podria leer y modificar todo el negocio.
EXIGIR_TOKEN = os.environ.get("MANAREY_ENTORNO", "").lower() == "produccion"

if EXIGIR_TOKEN and not API_TOKEN:
    raise RuntimeError(
        "Falta MANAREY_API_TOKEN. En produccion el token es obligatorio."
    )


def auth(authorization: str = Header(default="")) -> None:
    """El celular guarda este token; la huella/PIN protege el acceso local."""
    if not API_TOKEN:
        if EXIGIR_TOKEN:
            raise HTTPException(status_code=503, detail="API sin configurar")
        return  # solo desarrollo local
    if authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="No autorizado")


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _hoy() -> str:
    return datetime.now().strftime("%Y-%m-%d")


@app.get("/health")
def health():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        return {"ok": True}
    finally:
        put_connection(conn)


@app.get("/inicio/resumen", dependencies=[Depends(auth)])
def inicio_resumen():
    """Todo lo que el jefe quiere ver de un vistazo al abrir la app:
    ventas de hoy por local, efectivo para retirar, plata por cobrar y
    entregas pendientes. En una sola llamada para que cargue rapido."""
    from models import ventas_model as vm

    conn = get_connection()
    try:
        cur = conn.cursor()
        hoy = _hoy()

        # Ventas de hoy: total, efectivo y por local
        cur.execute(
            """
            SELECT COALESCE(SUM(total), 0), COUNT(*)
            FROM ventas
            WHERE estado = 'completada' AND fecha >= %s
            """,
            (f"{hoy} 00:00:00",),
        )
        total_hoy, cant_hoy = cur.fetchone()

        cur.execute(
            """
            SELECT local, COALESCE(SUM(total), 0) AS total
            FROM ventas
            WHERE estado = 'completada' AND fecha >= %s AND local <> ''
            GROUP BY local ORDER BY total DESC
            """,
            (f"{hoy} 00:00:00",),
        )
        por_local = [{"local": r[0], "total": float(r[1] or 0)} for r in cur.fetchall()]

        # Plata por cobrar (todas las ventas con saldo)
        cur.execute(
            "SELECT COALESCE(SUM(monto_pendiente), 0) FROM ventas "
            "WHERE estado = 'completada' AND monto_pendiente > 0"
        )
        por_cobrar = float(cur.fetchone()[0] or 0)

        # Entregas pendientes (envios no entregados)
        cur.execute(
            "SELECT COUNT(*) FROM ventas WHERE estado = 'completada' "
            "AND COALESCE(incluye_envio, 0) = 1 "
            "AND COALESCE(entrega_entregado, 0) = 0"
        )
        entregas_pendientes = int(cur.fetchone()[0] or 0)

        # Locales para el efectivo disponible
        cur.execute(
            "SELECT DISTINCT local FROM productos WHERE local <> '' ORDER BY local"
        )
        locales = [r[0] for r in cur.fetchall()]
    finally:
        put_connection(conn)

    # Efectivo para retirar por local (misma cuenta que la PC)
    efectivo_locales = []
    efectivo_total = 0.0
    for local in locales:
        try:
            ultimo = vm.get_last_withdrawal_datetime(local)
            monto = float(vm.get_cash_earned_since(local, ultimo) or 0)
            if local.strip().lower() == LOCAL_DOMICILIO.lower():
                monto += float(vm.get_domicilio_retirados_since(ultimo) or 0)
            dias = None
            if ultimo:
                try:
                    d = datetime.fromisoformat(str(ultimo))
                    dias = (datetime.now() - d).days
                except Exception:
                    dias = None
        except Exception:
            monto, dias = 0.0, None
        efectivo_total += monto
        efectivo_locales.append(
            {"local": local, "efectivo": round(monto, 2), "dias_sin_retirar": dias}
        )

    return {
        "ventas_hoy": {
            "total": float(total_hoy or 0),
            "cantidad": int(cant_hoy or 0),
            "por_local": por_local,
        },
        "efectivo": {
            "total": round(efectivo_total, 2),
            "locales": efectivo_locales,
        },
        "por_cobrar": por_cobrar,
        "entregas_pendientes": entregas_pendientes,
    }


@app.get("/app/version", dependencies=[Depends(auth)])
def app_version():
    """Ultima version de la app movil, para que se actualice sola.

    El celular compara version_codigo con la que tiene instalada; si el
    servidor tiene una mas nueva, ofrece bajarla e instalarla con un toque.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT version_codigo, version_nombre, url, notas, obligatoria
               FROM movil_version ORDER BY version_codigo DESC LIMIT 1"""
        )
        fila = cur.fetchone()
        if not fila:
            return {"hay_version": False}
        return {
            "hay_version": True,
            "version_codigo": fila[0],
            "version_nombre": fila[1],
            "url": fila[2],
            "notas": fila[3] or "",
            "obligatoria": bool(fila[4]),
        }
    finally:
        put_connection(conn)


@app.get("/locales", dependencies=[Depends(auth)])
def locales():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT local FROM productos WHERE local<>'' ORDER BY local"
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        put_connection(conn)


@app.get("/filtros", dependencies=[Depends(auth)])
def filtros():
    """Valores para los botones de filtro (ya limpios)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        out = {}
        for campo in ("categoria", "material", "fabricante"):
            cur.execute(
                f"SELECT {campo}, COUNT(*) FROM productos "
                f"WHERE {campo} IS NOT NULL AND {campo} <> '' "
                f"GROUP BY 1 ORDER BY 2 DESC"
            )
            out[campo] = [{"valor": v, "cantidad": c} for v, c in cur.fetchall()]
        return out
    finally:
        put_connection(conn)


@app.get("/productos", dependencies=[Depends(auth)])
def productos(
    q: str = Query("", description="Busqueda libre: palabras en cualquier orden"),
    local: str = "",
    categoria: str = "",
    material: str = "",
    fabricante: str = "",
    solo_stock: bool = False,
    orden: str = Query("nombre", pattern="^(nombre|precio|cantidad)$"),
    limite: int = 200,
    desde: int = 0,
):
    """Busqueda unica: una sola caja de texto que busca en todos los campos,
    sin tildes y con las palabras en cualquier orden (igual que la app de PC).
    Devuelve la foto si el producto tiene."""
    where = ["1=1"]
    params: list = []

    if local:
        where.append("p.local = %s")
        params.append(local)
    if categoria:
        where.append("p.categoria = %s")
        params.append(categoria)
    if material:
        where.append("p.material = %s")
        params.append(material)
    if fabricante:
        where.append("p.fabricante = %s")
        params.append(fabricante)
    if solo_stock:
        where.append("p.cantidad > 0")

    # Cada palabra debe aparecer en alguno de los campos de texto (sin tildes)
    for termino in [t for t in q.strip().split() if t]:
        where.append(
            "unaccent(lower(concat_ws(' ', p.nombre, p.medida, p.material, "
            "p.fabricante, p.color, p.categoria, p.codigo))) LIKE unaccent(lower(%s))"
        )
        params.append(f"%{termino}%")

    orden_sql = {
        "nombre": "p.nombre ASC, p.medida ASC",
        "precio": "p.precio_venta DESC",
        "cantidad": "p.cantidad DESC",
    }[orden]

    sql = f"""
        SELECT p.id, p.nombre, p.medida, p.color, p.categoria, p.material,
               p.fabricante, p.estado, p.cantidad, p.precio_venta, p.precio_costo,
               p.local, p.codigo, p.is_combo,
               m.image_data AS foto
        FROM productos p
        LEFT JOIN productos_web_metadata m
               ON m.product_key = md5(concat_ws('|',
                    lower(trim(p.nombre)),
                    lower(coalesce(trim(p.medida),'')),
                    lower(coalesce(trim(p.color),''))))
        WHERE {' AND '.join(where)}
        ORDER BY {orden_sql}
        LIMIT %s OFFSET %s
    """
    params.extend([limite, desde])

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return _rows(cur)
    finally:
        put_connection(conn)


# ---------------------------------------------------------------------------
# MARGENES Y COSTOS
# ---------------------------------------------------------------------------


@app.get("/productos/margenes", dependencies=[Depends(auth)])
def productos_margenes(
    q: str = Query("", description="Busqueda libre en todos los campos"),
    solo_faltantes: bool = False,
    orden: str = Query("margen", pattern="^(margen|nombre|ganancia)$"),
    limite: int = 300,
    desde: int = 0,
):
    """Productos con su margen de ganancia, agrupados (un precio por producto,
    igual que en los cambios de precio). Sirve para completar los costos que
    faltan y ver la rentabilidad. Incluye un resumen general del negocio."""
    where = ["COALESCE(p.is_combo, 0) = 0"]
    params: list = []
    for termino in [t for t in q.strip().split() if t]:
        where.append(
            "unaccent(lower(concat_ws(' ', p.nombre, p.medida, p.material, "
            "p.fabricante, p.color, p.categoria, p.codigo))) LIKE unaccent(lower(%s))"
        )
        params.append(f"%{termino}%")
    cond = " AND ".join(where)

    orden_sql = {
        # primero los que les falta el costo, despues por menor margen
        "margen": "falta_costo DESC, margen_pct ASC NULLS FIRST, nombre",
        "nombre": "nombre, medida",
        "ganancia": "ganancia DESC NULLS LAST, nombre",
    }[orden]
    having = ""
    if solo_faltantes:
        having = "HAVING COALESCE(MAX(p.precio_costo), 0) = 0"

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Resumen general: se calcula sobre TODOS los productos, no sobre el filtro
        cur.execute(
            """
            WITH prod AS (
                SELECT MAX(p.precio_venta) AS venta, MAX(p.precio_costo) AS costo
                FROM productos p
                WHERE COALESCE(p.is_combo, 0) = 0
                GROUP BY p.nombre, p.medida, p.color, p.material, p.fabricante
            )
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE COALESCE(costo, 0) = 0),
                   ROUND(AVG(CASE WHEN costo > 0 AND venta > 0
                                  THEN (venta - costo) / venta * 100 END)::numeric, 1)
            FROM prod
            """
        )
        r = cur.fetchone()
        resumen = {
            "total": int(r[0] or 0),
            "sin_costo": int(r[1] or 0),
            "margen_promedio": float(r[2]) if r[2] is not None else None,
        }

        sql = f"""
            SELECT MIN(p.id) AS id, p.nombre, p.medida, p.color, p.material,
                   p.fabricante,
                   MAX(p.precio_venta) AS precio_venta,
                   COALESCE(MAX(p.precio_costo), 0) AS precio_costo,
                   SUM(p.cantidad) AS cantidad,
                   (COALESCE(MAX(p.precio_costo), 0) = 0) AS falta_costo,
                   CASE WHEN MAX(p.precio_costo) > 0 AND MAX(p.precio_venta) > 0
                        THEN ROUND((MAX(p.precio_venta) - MAX(p.precio_costo))
                                   / MAX(p.precio_venta) * 100, 1)
                   END AS margen_pct,
                   CASE WHEN MAX(p.precio_costo) > 0
                        THEN MAX(p.precio_venta) - MAX(p.precio_costo)
                   END AS ganancia
            FROM productos p
            WHERE {cond}
            GROUP BY p.nombre, p.medida, p.color, p.material, p.fabricante
            {having}
            ORDER BY {orden_sql}
            LIMIT %s OFFSET %s
        """
        cur.execute(sql, params + [limite, desde])
        return {"resumen": resumen, "productos": _rows(cur)}
    finally:
        put_connection(conn)


@app.post("/productos/costo", dependencies=[Depends(auth)])
def fijar_costo(datos: dict):
    """Carga o corrige el costo de un producto.

    Se aplica a TODOS los locales que tengan el mismo producto (el costo es el
    mismo en los 5) y queda registrado en historial_stock para poder auditarlo.
    Devuelve el margen que queda, para mostrarlo al instante.
    """
    try:
        pid = int(datos["id"])
        costo = int(float(datos["costo"]))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Faltan 'id' o 'costo', o no son numeros")
    if costo < 0:
        raise HTTPException(400, "El costo no puede ser negativo")

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Identidad del producto: la misma clave con la que se agrupan los
        # precios, porque el producto esta repetido una vez por local.
        cur.execute(
            """SELECT nombre, medida, color, material, fabricante, precio_venta
               FROM productos WHERE id = %s""",
            (pid,),
        )
        fila = cur.fetchone()
        if not fila:
            raise HTTPException(404, "No se encontro el producto")
        nombre, medida, color, material, fabricante, venta = fila

        identidad = """
              nombre           IS NOT DISTINCT FROM %s
          AND medida           IS NOT DISTINCT FROM %s
          AND color            IS NOT DISTINCT FROM %s
          AND material         IS NOT DISTINCT FROM %s
          AND fabricante       IS NOT DISTINCT FROM %s
          AND COALESCE(is_combo, 0) = 0
        """
        claves = (nombre, medida, color, material, fabricante)

        # Historial ANTES de pisar el valor, para dejar el costo anterior.
        cur.execute(
            f"""INSERT INTO historial_stock
                    (producto_id, accion, detalle, cantidad, usuario, local,
                     created_at, motivo, undone)
                SELECT id, 'ajuste', 'cambio de precio_costo', 0, %s, local,
                       NOW(), %s, 0
                FROM productos WHERE {identidad}""",
            ("app-jefe", f"costo {'' if costo else 'borrado'} -> {costo}") + claves,
        )
        cur.execute(
            f"""UPDATE productos SET precio_costo = %s, updated_at = NOW()
                WHERE {identidad}""",
            (costo,) + claves,
        )
        afectados = cur.rowcount
        conn.commit()

        venta_f = float(venta or 0)
        margen = (
            round((venta_f - costo) / venta_f * 100, 1)
            if venta_f > 0 and costo > 0
            else None
        )
        return {
            "ok": True,
            "locales_actualizados": afectados,
            "precio_costo": costo,
            "margen_pct": margen,
            "ganancia": int(venta_f - costo) if venta_f > 0 and costo > 0 else None,
        }
    finally:
        put_connection(conn)


# ---------------------------------------------------------------------------
# CONTROL DE STOCK
# ---------------------------------------------------------------------------


@app.get("/stock/{local}/conteo", dependencies=[Depends(auth)])
def stock_para_contar(local: str):
    """Todo lo que deberia haber en el local, con las unidades RESERVADAS.

    Las reservadas estan fisicamente en el local pero ya son de un cliente
    (senas, envios, pedidos de otro local). Hay que contarlas igual: por eso
    se muestran, para que el jefe no las descuente por error.
    """
    from models import stock_model as sm

    try:
        reservas = sm.get_reservas_por_producto(local) or {}
    except Exception:
        reservas = {}

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, nombre, medida, color, material, fabricante,
                   categoria, estado, cantidad, precio_venta, codigo
            FROM productos
            WHERE local = %s AND COALESCE(is_combo, 0) = 0 AND cantidad > 0
            ORDER BY nombre, medida
            """,
            (local,),
        )
        items = _rows(cur)
        for it in items:
            it["reservadas"] = int(reservas.get(it["id"], 0) or 0)
        return {"local": local, "total": len(items), "productos": items}
    finally:
        put_connection(conn)


@app.post("/stock/ajustar", dependencies=[Depends(auth)])
def ajustar_stock(datos: dict):
    """Fija la cantidad contada de un producto.

    Usa la MISMA funcion que la app de escritorio, asi el ajuste queda
    registrado en el historial y se pueden deshacer los cambios.
    """
    from models import stock_model as sm

    try:
        producto_id = int(datos["producto_id"])
        cantidad = int(datos["cantidad"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Faltan producto_id o cantidad")

    if cantidad < 0:
        raise HTTPException(400, "La cantidad no puede ser negativa")

    ok, msg = sm.update_stock_quantity(
        producto_id=producto_id,
        new_qty=cantidad,
        usuario=datos.get("usuario", "jefe (celular)"),
        local=datos.get("local", ""),
        detalle="conteo desde el celular",
        motivo=datos.get("motivo", "Control de stock con la app"),
    )
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "mensaje": msg}


@app.post("/stock/agregar", dependencies=[Depends(auth)])
def agregar_mercaderia(datos: dict):
    """Suma unidades a un producto (llego mercaderia nueva).

    Usa la misma funcion que la PC: queda en el historial y se puede deshacer.
    """
    from models import stock_model as sm

    try:
        producto_id = int(datos["producto_id"])
        cantidad = int(datos["cantidad"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Faltan producto_id o cantidad")

    if cantidad <= 0:
        raise HTTPException(400, "La cantidad tiene que ser mayor a cero")

    ok, msg = sm.increment_stock(
        producto_id,
        cantidad,
        datos.get("usuario", "jefe (celular)"),
        datos.get("local", ""),
        detalle="mercaderia nueva",
        motivo=datos.get("motivo", "Ingreso de mercaderia desde el celular"),
    )
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "mensaje": msg}


@app.post("/stock/transferir", dependencies=[Depends(auth)])
def transferir_mercaderia(datos: dict):
    """Pasa unidades de un local a otro.

    Usa transfer_stock de la app de escritorio, que ademas de mover el stock
    avisa al local destino y registra el movimiento en ambos lados.
    """
    from models import stock_model as sm

    try:
        producto_id = int(datos["producto_id"])
        cantidad = int(datos["cantidad"])
        destino = str(datos["destino"]).strip()
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Faltan producto_id, cantidad o destino")

    if cantidad <= 0:
        raise HTTPException(400, "La cantidad tiene que ser mayor a cero")
    if not destino:
        raise HTTPException(400, "Falta el local de destino")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, nombre, categoria, medida, estado, color, material,
                      fabricante, precio_venta, precio_costo, cantidad, local,
                      codigo
               FROM productos WHERE id = %s""",
            (producto_id,),
        )
        filas = _rows(cur)
        if not filas:
            raise HTTPException(404, "Producto no encontrado")
        fila = filas[0]
    finally:
        put_connection(conn)

    if fila["local"].strip().lower() == destino.lower():
        raise HTTPException(400, "El destino es el mismo local de origen")
    if int(fila["cantidad"] or 0) < cantidad:
        raise HTTPException(
            400,
            f"Solo hay {fila['cantidad']} en {fila['local']}",
        )

    ok, msg = sm.transfer_stock(
        fila, destino, cantidad, datos.get("usuario", "jefe (celular)")
    )
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "mensaje": msg}


@app.get("/productos/{nombre}/en-locales", dependencies=[Depends(auth)])
def producto_en_locales(nombre: str, medida: str = "", color: str = ""):
    """Cuanto hay de un producto en CADA local (la pregunta tipica del jefe)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT local, cantidad, precio_venta, id
            FROM productos
            WHERE lower(trim(nombre)) = lower(trim(%s))
              AND coalesce(lower(trim(medida)),'') = coalesce(lower(trim(%s)),'')
              AND coalesce(lower(trim(color)),'')  = coalesce(lower(trim(%s)),'')
            ORDER BY local
            """,
            (nombre, medida, color),
        )
        return _rows(cur)
    finally:
        put_connection(conn)


# ---------------------------------------------------------------------------
# MENSAJES DE LOS LOCALES
# ---------------------------------------------------------------------------


@app.get("/mensajes", dependencies=[Depends(auth)])
def mensajes(local: str = "", limite: int = 100):
    """Lo que los locales le avisan al jefe."""
    from models import problemas_model as pm

    try:
        return pm.list_mensajes(local or None, limit=limite) or []
    except Exception as e:
        raise HTTPException(500, f"No se pudieron leer los mensajes: {e}")


@app.get("/mensajes/sin-leer", dependencies=[Depends(auth)])
def mensajes_sin_leer(usuario: str = "jefe"):
    """Cuantos mensajes nuevos hay (para el aviso en el menu)."""
    from models import problemas_model as pm

    try:
        return {"cantidad": int(pm.count_admin_unread(usuario) or 0)}
    except Exception:
        return {"cantidad": 0}


@app.post("/mensajes/marcar-leidos", dependencies=[Depends(auth)])
def marcar_leidos(datos: dict):
    from models import problemas_model as pm

    try:
        pm.mark_admin_seen(datos.get("usuario", "jefe"))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/mensajes/responder", dependencies=[Depends(auth)])
def responder_mensaje(datos: dict):
    """El jefe le contesta a un local."""
    from models import problemas_model as pm

    local = (datos.get("local") or "").strip()
    texto = (datos.get("mensaje") or "").strip()
    if not local or not texto:
        raise HTTPException(400, "Falta el local o el mensaje")

    ok, msg = pm.add_mensaje(local, datos.get("usuario", "jefe"), "admin", texto)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True}


# ---------------------------------------------------------------------------
# FOTOS DE PRODUCTOS
# ---------------------------------------------------------------------------

# Token de Vercel Blob, donde ya viven las 234 fotos que usa la web.
BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")


@app.post("/productos/{producto_id}/foto", dependencies=[Depends(auth)])
async def subir_foto(producto_id: int, archivo: UploadFile = File(...)):
    """Guarda la foto que saco el jefe con la camara.

    Va al mismo lugar que las fotos de la web (Vercel Blob), asi la foto
    aparece tanto en la app como en la pagina, sin duplicar nada.
    """
    if not BLOB_TOKEN:
        raise HTTPException(
            503,
            "Falta configurar el guardado de fotos (BLOB_READ_WRITE_TOKEN).",
        )

    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(400, "La foto llego vacia")
    if len(contenido) > 12 * 1024 * 1024:
        raise HTTPException(400, "La foto es demasiado grande (max 12 MB)")

    tipo = archivo.content_type or "image/jpeg"
    ext = tipo.split("/")[-1].split("+")[0] or "jpg"

    conn = get_connection()
    try:
        cur = conn.cursor()
        # La clave con la que la web enlaza foto y producto
        cur.execute(
            """
            SELECT md5(concat_ws('|',
                     lower(trim(nombre)),
                     lower(coalesce(trim(medida), '')),
                     lower(coalesce(trim(color), '')))) AS clave,
                   nombre
            FROM productos WHERE id = %s
            """,
            (producto_id,),
        )
        filas = _rows(cur)
        if not filas:
            raise HTTPException(404, "Producto no encontrado")
        clave = filas[0]["clave"]

        # Subir a Vercel Blob (misma convencion de nombre que la web)
        import requests

        ruta = f"productos/{clave}-main.{ext}"
        resp = requests.put(
            f"https://blob.vercel-storage.com/{ruta}",
            data=contenido,
            headers={
                "Authorization": f"Bearer {BLOB_TOKEN}",
                "x-content-type": tipo,
                "x-add-random-suffix": "0",
                "x-api-version": "7",
            },
            timeout=60,
        )
        if resp.status_code >= 300:
            raise HTTPException(502, f"No se pudo guardar la foto ({resp.status_code})")
        url = resp.json().get("url")
        if not url:
            raise HTTPException(502, "El guardado no devolvio la direccion")

        # Enlazar la foto con el producto (crea la fila si no existia)
        cur.execute(
            """
            INSERT INTO productos_web_metadata (product_key, image_data,
                                                images_data, updated_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (product_key) DO UPDATE
              SET image_data = EXCLUDED.image_data,
                  images_data = EXCLUDED.images_data,
                  updated_at = now()
            """,
            (clave, url, f'["{url}"]'),
        )
        conn.commit()
        return {"ok": True, "url": url}
    finally:
        put_connection(conn)


# ---------------------------------------------------------------------------
# PRECIOS
# ---------------------------------------------------------------------------


def _nuevo_precio(base: float, tipo: str, valor: float) -> int:
    """Calcula el precio nuevo. tipo: 'porcentaje' | 'monto' | 'fijo'."""
    if tipo == "porcentaje":
        return int(round(base * (1 + valor / 100.0)))
    if tipo == "monto":
        return int(round(base + valor))
    return int(round(valor))  # fijo


def _seleccion_sql(criterio: str, valor: str):
    """Devuelve (condicion_sql, params) segun el criterio de seleccion."""
    if criterio == "fabricante":
        return "p.fabricante = %s", [valor]
    if criterio == "material":
        return "p.material = %s", [valor]
    if criterio == "categoria":
        return "p.categoria = %s", [valor]
    if criterio == "todo":
        return "1=1", []
    raise HTTPException(400, "Criterio invalido")


@app.post("/precios/simular", dependencies=[Depends(auth)])
def simular_precios(datos: dict):
    """Muestra QUE va a pasar antes de tocar nada.

    Devuelve cuantos productos cambian, ejemplos, los que quedarian por
    debajo del costo (vender perdiendo) y los combos afectados.
    """
    criterio = datos.get("criterio", "")
    valor_sel = str(datos.get("valor", ""))
    tipo = datos.get("tipo", "porcentaje")
    try:
        valor = float(datos.get("cambio", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "El cambio debe ser un numero")

    cond, params = _seleccion_sql(criterio, valor_sel)

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Un precio por producto: se agrupa porque el precio se sincroniza
        # en los 5 locales.
        cur.execute(
            f"""
            SELECT MIN(p.id) AS id, p.nombre, p.medida, p.color, p.material,
                   p.fabricante, MAX(p.precio_venta) AS precio_venta,
                   MAX(p.precio_costo) AS precio_costo, SUM(p.cantidad) AS cantidad
            FROM productos p
            WHERE {cond} AND COALESCE(p.is_combo, 0) = 0
            GROUP BY p.nombre, p.medida, p.color, p.material, p.fabricante
            ORDER BY p.nombre
            """,
            params,
        )
        productos = _rows(cur)

        cambios, bajo_costo = [], []
        for p in productos:
            base = float(p["precio_venta"] or 0)
            if base <= 0:
                continue
            nuevo = _nuevo_precio(base, tipo, valor)
            if nuevo == int(base):
                continue
            costo = float(p["precio_costo"] or 0)
            item = {
                "id": p["id"],
                "nombre": p["nombre"],
                "medida": p["medida"],
                "detalle": " · ".join(
                    x for x in [p["color"], p["material"], p["fabricante"]] if x
                ),
                "precio_actual": int(base),
                "precio_nuevo": nuevo,
                "precio_costo": int(costo),
            }
            cambios.append(item)
            if costo > 0 and nuevo < costo:
                bajo_costo.append(item)

        # Combos que contienen alguno de los productos afectados
        combos = []
        if cambios:
            ids = [c["id"] for c in cambios]
            cur.execute(
                """
                SELECT DISTINCT c.id, c.nombre, c.medida, c.precio_venta
                FROM productos c
                JOIN combo_items ci ON ci.combo_producto_id = c.id
                WHERE ci.producto_id = ANY(%s) AND COALESCE(c.is_combo, 0) = 1
                ORDER BY c.nombre
                """,
                (ids,),
            )
            combos = [
                {
                    "id": r["id"],
                    "nombre": r["nombre"],
                    "medida": r["medida"] or "",
                    "precio_actual": int(float(r["precio_venta"] or 0)),
                    "precio_sugerido": _nuevo_precio(
                        float(r["precio_venta"] or 0), tipo, valor
                    ),
                }
                for r in _rows(cur)
            ]

        promedio_actual = (
            sum(c["precio_actual"] for c in cambios) / len(cambios) if cambios else 0
        )
        promedio_nuevo = (
            sum(c["precio_nuevo"] for c in cambios) / len(cambios) if cambios else 0
        )

        return {
            "cantidad": len(cambios),
            "promedio_actual": int(promedio_actual),
            "promedio_nuevo": int(promedio_nuevo),
            "bajo_costo": bajo_costo,
            "combos_afectados": combos,
            "ejemplos": cambios[:60],
        }
    finally:
        put_connection(conn)


def _aplicar_uno(cur, sm, ph, pid: int, nuevo: int, usuario: str, motivo: str) -> bool:
    """Cambia el precio de un producto y lo registra en el historial."""
    cur.execute(
        "SELECT precio_venta, precio_costo, local FROM productos WHERE id=%s",
        (pid,),
    )
    fila = cur.fetchone()
    if not fila:
        return False
    anterior = float(fila[0] or 0)
    costo = float(fila[1] or 0)
    local = fila[2] or ""
    if int(anterior) == nuevo:
        return False

    if not sm.update_stock_field(
        pid, "precio_venta", nuevo, usuario=usuario, local=local, motivo=motivo
    ):
        return False

    try:
        ph.registrar_cambio(
            producto_id=pid,
            local=local,
            usuario=usuario,
            precio_costo_ant=costo,
            precio_costo_nuevo=costo,
            precio_venta_ant=anterior,
            precio_venta_nuevo=nuevo,
            motivo=motivo,
        )
    except Exception:
        pass
    return True


@app.post("/precios/aplicar", dependencies=[Depends(auth)])
def aplicar_precios(datos: dict):
    """Aplica el cambio de precios. Queda registrado para poder deshacerlo.

    Recalcula el conjunto completo en el servidor con el MISMO criterio de la
    simulacion (no una lista recortada), asi se cambian todos los productos
    que se le mostraron al jefe. Los combos llevan el precio que el eligio.

    Espera: {"criterio","valor","tipo","cambio","combos":{"id":precio}}
    """
    from models import precio_historial_model as ph
    from models import stock_model as sm

    criterio = datos.get("criterio", "")
    valor_sel = str(datos.get("valor", ""))
    tipo = datos.get("tipo", "porcentaje")
    try:
        valor = float(datos.get("cambio", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "El cambio debe ser un numero")

    usuario = datos.get("usuario", "jefe (celular)")
    motivo = datos.get("motivo", "Cambio de precios desde el celular")
    combos = datos.get("combos") or {}

    cond, params = _seleccion_sql(criterio, valor_sel)

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Mismo agrupado que la simulacion: un precio por producto
        cur.execute(
            f"""
            SELECT MIN(p.id) AS id, MAX(p.precio_venta) AS precio_venta
            FROM productos p
            WHERE {cond} AND COALESCE(p.is_combo, 0) = 0
            GROUP BY p.nombre, p.medida, p.color, p.material, p.fabricante
            """,
            params,
        )
        objetivo = _rows(cur)

        aplicados = 0
        for o in objetivo:
            base = float(o["precio_venta"] or 0)
            if base <= 0:
                continue
            nuevo = _nuevo_precio(base, tipo, valor)
            if nuevo == int(base):
                continue
            if _aplicar_uno(cur, sm, ph, int(o["id"]), nuevo, usuario, motivo):
                aplicados += 1

        # Combos: el precio lo puso el jefe, uno por uno
        combos_aplicados = 0
        for cid, precio in combos.items():
            try:
                if _aplicar_uno(cur, sm, ph, int(cid), int(precio), usuario, motivo):
                    combos_aplicados += 1
            except (TypeError, ValueError):
                continue

        return {"aplicados": aplicados, "combos": combos_aplicados}
    finally:
        put_connection(conn)


@app.get("/precios/cambios", dependencies=[Depends(auth)])
def cambios_de_precio(limite: int = 40):
    """Cambios de precio AGRUPADOS por operacion.

    Un cambio masivo toca decenas de productos a la vez; agruparlos deja
    ver "Subir 10% a liliana - 77 productos" en vez de 77 lineas sueltas,
    y permite deshacer la operacion entera de una.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                to_char(date_trunc('minute', h.fecha), 'YYYY-MM-DD HH24:MI') AS momento,
                COALESCE(h.motivo, '')  AS motivo,
                COALESCE(h.usuario, '') AS usuario,
                MIN(h.fecha)            AS fecha,
                COUNT(*)                AS cantidad,
                array_agg(h.id)         AS ids,
                AVG(h.precio_venta_anterior) AS promedio_antes,
                AVG(h.precio_venta_nuevo)    AS promedio_despues
            FROM precio_historial h
            GROUP BY 1, 2, 3
            ORDER BY MIN(h.fecha) DESC
            LIMIT %s
            """,
            (limite,),
        )
        grupos = _rows(cur)

        # Ejemplos de cada grupo, para que sepa que toco
        for g in grupos:
            cur.execute(
                """
                SELECT p.nombre, p.medida,
                       h.precio_venta_anterior, h.precio_venta_nuevo
                FROM precio_historial h
                LEFT JOIN productos p ON p.id = h.producto_id
                WHERE h.id = ANY(%s)
                LIMIT 3
                """,
                (g["ids"],),
            )
            g["ejemplos"] = [
                {
                    "nombre": r["nombre"] or "Producto",
                    "medida": r["medida"] or "",
                    "antes": int(float(r["precio_venta_anterior"] or 0)),
                    "despues": int(float(r["precio_venta_nuevo"] or 0)),
                }
                for r in _rows(cur)
            ]
        return grupos
    finally:
        put_connection(conn)


@app.post("/precios/deshacer", dependencies=[Depends(auth)])
def deshacer_precios(datos: dict):
    """Vuelve los precios al valor anterior. Espera {"ids": [ids de historial]}."""
    from models import precio_historial_model as ph
    from models import stock_model as sm

    ids = datos.get("ids") or []
    if not ids:
        raise HTTPException(400, "No hay cambios para deshacer")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, producto_id, local, precio_venta_anterior,
                      precio_venta_nuevo
               FROM precio_historial WHERE id = ANY(%s)""",
            (ids,),
        )
        filas = _rows(cur)
        deshechos = 0
        for f in filas:
            anterior = int(float(f["precio_venta_anterior"] or 0))
            actual = int(float(f["precio_venta_nuevo"] or 0))
            ok = sm.update_stock_field(
                f["producto_id"],
                "precio_venta",
                anterior,
                usuario="jefe (celular)",
                local=f["local"] or "",
                motivo="Deshacer cambio de precio",
            )
            if ok:
                try:
                    ph.registrar_cambio(
                        producto_id=f["producto_id"],
                        local=f["local"] or "",
                        usuario="jefe (celular)",
                        precio_costo_ant=0,
                        precio_costo_nuevo=0,
                        precio_venta_ant=actual,
                        precio_venta_nuevo=anterior,
                        motivo="Deshacer cambio de precio",
                    )
                except Exception:
                    pass
                deshechos += 1
        return {"deshechos": deshechos}
    finally:
        put_connection(conn)


# ---------------------------------------------------------------------------
# DINERO
# ---------------------------------------------------------------------------

# Local donde se acumulan los cobros en domicilio de todos los locales
LOCAL_DOMICILIO = "Longchamps"


@app.get("/dinero/efectivo", dependencies=[Depends(auth)])
def efectivo_por_local():
    """Efectivo disponible para retirar en cada local.

    Usa la MISMA cuenta que la app de escritorio: lo cobrado en efectivo
    desde el ultimo retiro (despues de cada retiro la caja queda en cero).
    """
    from models import ventas_model as vm

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT local FROM productos WHERE local<>'' ORDER BY local"
        )
        locales = [r[0] for r in cur.fetchall()]
    finally:
        put_connection(conn)

    salida = []
    total = 0.0
    for local in locales:
        try:
            ultimo = vm.get_last_withdrawal_datetime(local)
            monto = float(vm.get_cash_earned_since(local, ultimo) or 0)
            # Longchamps suma los cobros en domicilio de todos los locales
            if local.strip().lower() == LOCAL_DOMICILIO.lower():
                try:
                    monto += float(vm.get_domicilio_retirados_since(ultimo) or 0)
                except Exception:
                    pass
        except Exception:
            ultimo, monto = None, 0.0

        total += monto
        salida.append(
            {
                "local": local,
                "efectivo": round(monto, 2),
                "ultimo_retiro": ultimo,
                "incluye_domicilio": local.strip().lower() == LOCAL_DOMICILIO.lower(),
            }
        )

    return {"total": round(total, 2), "locales": salida}


@app.post("/dinero/retirar", dependencies=[Depends(auth)])
def retirar_efectivo(datos: dict):
    """Registra un retiro de efectivo de un local.

    Usa la MISMA tabla y funcion que la app de escritorio (cash_withdrawals),
    asi el retiro se refleja al instante en la PC: el efectivo disponible del
    local pasa a contarse desde este retiro (baja a cero).

    Pide la contrasena de retiro (la misma que la PC) como control extra
    porque es plata que sale.
    """
    from models import ventas_model as vm

    local = (datos.get("local") or "").strip()
    password = (datos.get("password") or "").strip()
    try:
        monto = float(datos.get("monto", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "Monto invalido")

    if not local:
        raise HTTPException(400, "Falta el local")
    if monto <= 0:
        raise HTTPException(400, "El monto tiene que ser mayor a cero")

    # Validar la contrasena de retiro (la misma del sistema)
    try:
        correcta = vm.get_cash_withdraw_password()
    except Exception:
        correcta = None
    if not password or (correcta and password != correcta):
        raise HTTPException(403, "Contrasena de retiro incorrecta")

    # No dejar retirar mas de lo disponible
    try:
        ultimo = vm.get_last_withdrawal_datetime(local)
        disponible = float(vm.get_cash_earned_since(local, ultimo) or 0)
        if local.strip().lower() == LOCAL_DOMICILIO.lower():
            disponible += float(vm.get_domicilio_retirados_since(ultimo) or 0)
    except Exception:
        disponible = None
    if disponible is not None and monto > disponible + 0.5:
        raise HTTPException(
            400,
            f"No hay tanto: en {local} hay ${disponible:,.0f} disponibles",
        )

    ok, msg = vm.add_cash_withdrawal(
        local, monto, datos.get("usuario", "jefe (celular)")
    )
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "mensaje": f"Retiraste ${monto:,.0f} de {local}"}


@app.get("/dinero/boston-creed", dependencies=[Depends(auth)])
def boston_creed(local: str = ""):
    """Resumen de Boston Creed: plata que la financiera todavia debe."""
    from models import boston_creed_model as bc

    try:
        resumen = bc.get_resumen(local) or {}
    except Exception as e:
        raise HTTPException(500, f"No se pudo leer Boston Creed: {e}")

    try:
        operaciones = bc.list_operaciones(local=local) or []
    except Exception:
        operaciones = []

    return {"resumen": resumen, "operaciones": operaciones[:100]}


# ---------------------------------------------------------------------------
# VENTAS Y ENTREGAS
# ---------------------------------------------------------------------------


@app.get("/ventas", dependencies=[Depends(auth)])
def ventas(
    local: str = "",
    desde: str = Query("", description="AAAA-MM-DD"),
    hasta: str = Query("", description="AAAA-MM-DD"),
    solo_envios: bool = False,
    incluir_canceladas: bool = False,
    limite: int = 300,
):
    """Ventas del periodo, por local. Incluye el resumen del total vendido."""
    where = ["1=1"]
    params: list = []

    if local:
        where.append("v.local = %s")
        params.append(local)
    if desde:
        where.append("v.fecha >= %s")
        params.append(f"{desde} 00:00:00")
    if hasta:
        where.append("v.fecha <= %s")
        params.append(f"{hasta} 23:59:59")
    if solo_envios:
        where.append("COALESCE(v.incluye_envio, 0) = 1")
    if not incluir_canceladas:
        where.append("v.estado = 'completada'")

    filtro = " AND ".join(where)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT v.id, v.numero_venta, v.local, v.fecha, v.vendedor,
                   v.cliente_nombre, v.cliente_telefono,
                   v.cliente_calle, v.cliente_numero, v.cliente_localidad,
                   v.total, v.monto_pagado, v.monto_pendiente,
                   v.forma_pago, v.tipo_pago, v.estado,
                   COALESCE(v.incluye_envio, 0)      AS incluye_envio,
                   COALESCE(v.entrega_entregado, 0)  AS entregado,
                   v.entrega_programada,
                   (SELECT COUNT(*) FROM detalle_ventas d WHERE d.venta_id = v.id)
                       AS cantidad_items
            FROM ventas v
            WHERE {filtro}
            ORDER BY v.fecha DESC
            LIMIT %s
            """,
            params + [limite],
        )
        items = _rows(cur)

        cur.execute(
            f"""SELECT COUNT(*), COALESCE(SUM(v.total), 0),
                       COALESCE(SUM(v.monto_pendiente), 0)
                FROM ventas v WHERE {filtro}""",
            params,
        )
        cantidad, total, pendiente = cur.fetchone()

        # Efectivo: lo cobrado en efectivo en el periodo. Suma los pagos
        # en efectivo de pagos divididos (venta_pagos) mas las ventas
        # simples que se pagaron en efectivo (sin pago dividido).
        cur.execute(
            f"""
            SELECT
              COALESCE((
                SELECT SUM(p.monto) FROM venta_pagos p
                JOIN ventas v ON v.id = p.venta_id
                WHERE p.forma ILIKE '%%efectivo%%' AND {filtro}
              ), 0)
              +
              COALESCE((
                SELECT SUM(COALESCE(v.monto_pagado, v.total)) FROM ventas v
                WHERE v.forma_pago ILIKE '%%efectivo%%'
                  AND NOT EXISTS (SELECT 1 FROM venta_pagos p WHERE p.venta_id = v.id)
                  AND {filtro}
              ), 0)
            """,
            params + params,
        )
        efectivo = cur.fetchone()[0]

        return {
            "resumen": {
                "cantidad": int(cantidad or 0),
                "total": float(total or 0),
                "efectivo": float(efectivo or 0),
                "pendiente_de_cobro": float(pendiente or 0),
            },
            "ventas": items,
        }
    finally:
        put_connection(conn)


@app.get("/ventas/{venta_id}", dependencies=[Depends(auth)])
def venta_detalle(venta_id: int):
    """Detalle completo: que se vendio, a quien y como pago."""
    from models import ventas_model

    venta = ventas_model.get_venta_detalle(venta_id)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    return venta


def _entregar_pdf(ok: bool, resultado: str, prefijo: str) -> FileResponse:
    """Devuelve el PDF que genero la app de escritorio."""
    if not ok:
        raise HTTPException(500, f"No se pudo generar el PDF: {resultado}")
    if not os.path.exists(resultado):
        raise HTTPException(500, "El PDF no quedo generado")
    return FileResponse(
        resultado, media_type="application/pdf", filename=f"{prefijo}.pdf"
    )


@app.get("/ventas/{venta_id}/boleta.pdf", dependencies=[Depends(auth)])
def boleta(venta_id: int):
    """Boleta IDENTICA a la de la PC.

    Se llama a generar_pdf_boleta (la misma funcion que usa la app de
    escritorio) y NO al generador de bajo nivel: es esa funcion la que arma
    la estructura que la boleta espera (numero, fecha, forma de pago y el
    detalle de productos). Pasarle los datos crudos deja la boleta sin esos
    campos.
    """
    from models import ventas_model

    ok, resultado = ventas_model.generar_pdf_boleta(venta_id)
    return _entregar_pdf(ok, resultado, f"boleta-{venta_id}")


@app.get("/ventas/{venta_id}/remito.pdf", dependencies=[Depends(auth)])
def remito(venta_id: int):
    """Remito IDENTICO al de la PC (misma funcion que usa el escritorio)."""
    from models import ventas_model

    ok, resultado = ventas_model.generar_pdf_remito(venta_id)
    return _entregar_pdf(ok, resultado, f"remito-{venta_id}")
