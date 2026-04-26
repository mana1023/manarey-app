import os
import re
import sqlite3
import sys
import traceback
from typing import List

try:
    import psycopg2
    from psycopg2.extras import DictCursor
except Exception:
    print("Falta psycopg2-binary. Instálalo con: pip install psycopg2-binary")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SQLITE_DB = os.path.join(BASE_DIR, "manarey.db")
PG_URL = os.environ.get("DATABASE_URL", "").strip()
# Fallback: primer argumento CLI
if (not PG_URL) and len(sys.argv) > 1:
    PG_URL = (sys.argv[1] or "").strip()
# Fallback: archivo .dburl en BASE_DIR
if not PG_URL:
    dburl_path = os.path.join(BASE_DIR, ".dburl")
    if os.path.exists(dburl_path):
        try:
            with open(dburl_path, "r", encoding="utf-8") as f:
                PG_URL = (f.readline() or "").strip()
        except Exception:
            PG_URL = ""

TABLES_SCHEMA: List[str] = [
    # ventas
    """
    CREATE TABLE IF NOT EXISTS ventas (
        id SERIAL PRIMARY KEY,
        numero_venta TEXT UNIQUE NOT NULL,
        local TEXT NOT NULL,
        fecha TEXT,
        vendedor TEXT NOT NULL,
        cliente_nombre TEXT NOT NULL,
        cliente_telefono TEXT NOT NULL,
        cliente_calle TEXT,
        cliente_numero TEXT,
        cliente_localidad TEXT,
        subtotal_productos DOUBLE PRECISION NOT NULL DEFAULT 0,
        precio_envio DOUBLE PRECISION DEFAULT 0,
        descuento_tipo TEXT,
        descuento_valor DOUBLE PRECISION,
        descuento_aplicado DOUBLE PRECISION,
        total DOUBLE PRECISION NOT NULL,
        incluye_envio INTEGER DEFAULT 0,
        entre_calles TEXT,
        forma_pago TEXT NOT NULL,
        tipo_pago TEXT,
        monto_pagado DOUBLE PRECISION DEFAULT 0,
        monto_pendiente DOUBLE PRECISION DEFAULT 0,
        notas TEXT,
        estado TEXT,
        pdf_generado INTEGER DEFAULT 0
    );
    """,
    # productos
    """
    CREATE TABLE IF NOT EXISTS productos (
        id SERIAL PRIMARY KEY,
        nombre TEXT NOT NULL,
        categoria TEXT NOT NULL,
        medida TEXT,
        estado TEXT DEFAULT 'Nuevo',
        color TEXT,
        cantidad INTEGER NOT NULL DEFAULT 0,
        precio_costo DOUBLE PRECISION DEFAULT 0,
        precio_venta DOUBLE PRECISION NOT NULL DEFAULT 0,
        local TEXT NOT NULL,
        created_at TEXT,
        updated_at TEXT
    );
    """,
    # detalle_ventas
    """
    CREATE TABLE IF NOT EXISTS detalle_ventas (
        id SERIAL PRIMARY KEY,
        venta_id INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
        producto_id INTEGER NOT NULL,
        producto_nombre TEXT NOT NULL,
        producto_categoria TEXT,
        producto_medida TEXT,
        producto_estado TEXT,
        producto_color TEXT,
        cantidad INTEGER NOT NULL,
        precio_unitario DOUBLE PRECISION NOT NULL,
        subtotal DOUBLE PRECISION NOT NULL
    );
    """,
    # tipos
    """
    CREATE TABLE IF NOT EXISTS tipos (
        id SERIAL PRIMARY KEY,
        nombre TEXT UNIQUE NOT NULL
    );
    """,
    # usuarios
    """
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        local TEXT
    );
    """,
    # historial_stock
    """
    CREATE TABLE IF NOT EXISTS historial_stock (
        id SERIAL PRIMARY KEY,
        producto_id INTEGER,
        accion TEXT NOT NULL,
        detalle TEXT,
        cantidad INTEGER,
        usuario TEXT,
        local TEXT,
        created_at TEXT,
        motivo TEXT,
        meta TEXT,
        undone INTEGER DEFAULT 0,
        undone_by TEXT,
        undone_at TEXT,
        grupo_id TEXT
    );
    """,
    # notificaciones buffer
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
        created_at   TEXT NOT NULL,
        flushed      INTEGER NOT NULL DEFAULT 0
    );
    """,
    # notificaciones mensajes
    """
    CREATE TABLE IF NOT EXISTS noti_messages (
        id SERIAL PRIMARY KEY,
        target_local TEXT NOT NULL,
        title        TEXT NOT NULL,
        body         TEXT NOT NULL,
        payload      TEXT NOT NULL,
        created_at   TEXT NOT NULL,
        seen         INTEGER NOT NULL DEFAULT 0
    );
    """,
    # cierres diarios
    """
    CREATE TABLE IF NOT EXISTS cierres_diarios (
        id SERIAL PRIMARY KEY,
        fecha TEXT NOT NULL,
        local TEXT NOT NULL,
        total_items INTEGER NOT NULL,
        total_valorizado DOUBLE PRECISION NOT NULL,
        generado_por TEXT NOT NULL,
        creado_en TEXT
    );
    """,
    # updates
    """
    CREATE TABLE IF NOT EXISTS updates (
        id SERIAL PRIMARY KEY,
        version TEXT NOT NULL,
        notes   TEXT,
        zip_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1
    );
    """,
    # updates_ack
    """
    CREATE TABLE IF NOT EXISTS updates_ack (
        id SERIAL PRIMARY KEY,
        update_id INTEGER NOT NULL,
        local TEXT NOT NULL,
        ack_at TEXT NOT NULL
    );
    """,
    # índices
    "CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha);",
    "CREATE INDEX IF NOT EXISTS idx_ventas_local ON ventas(local);",
    "CREATE INDEX IF NOT EXISTS idx_ventas_estado ON ventas(estado);",
    "CREATE INDEX IF NOT EXISTS idx_detalle_venta ON detalle_ventas(venta_id);",
]

COPY_TABLES_ORDER = [
    "ventas",
    "detalle_ventas",
    "usuarios",
    "productos",
    "tipos",
    "historial_stock",
    "noti_buffer",
    "noti_messages",
    "cierres_diarios",
    "updates",
    "updates_ack",
]

ADJUST_SEQUENCES_FOR = COPY_TABLES_ORDER


def main():
    if not PG_URL:
        print("DATABASE_URL no seteado en entorno ni en .dburl ni como argumento")
        return 1
    if not os.path.exists(SQLITE_DB):
        print(f"No se encontró la base SQLite: {SQLITE_DB}")
        return 1

    # Conexiones
    src = sqlite3.connect(SQLITE_DB)
    src.row_factory = sqlite3.Row
    s_cur = src.cursor()

    dst = psycopg2.connect(PG_URL)
    d_cur = dst.cursor(cursor_factory=DictCursor)

    # Crear esquema
    for sql in TABLES_SCHEMA:
        d_cur.execute(sql)
    dst.commit()

    # Usar validador central para consistencia
    from models.sql_utils import is_safe_identifier

    # Helper: columnas destino por tabla (schema public)
    def _dst_columns(tbl: str):
        d_cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
            """,
            (tbl,),
        )
        return [row[0] for row in d_cur.fetchall()]

    # Copiar tablas en orden (intersección de columnas)
    for table in COPY_TABLES_ORDER:
        try:
            if not is_safe_identifier(table):
                print(f"Skipping invalid table name: {table!r}")
                continue
            s_cur.execute(f"SELECT * FROM {table} ORDER BY id")
            rows = s_cur.fetchall()
        except Exception:
            # Tabla puede no existir en SQLite; continuar
            continue
        if not rows:
            continue

        src_cols = [d[0] for d in s_cur.description]
        dst_cols = _dst_columns(table)
        # Intersección manteniendo orden de origen
        common = [c for c in src_cols if c in dst_cols]
        if not common:
            # nada que copiar con columnas compatibles
            continue
        # Preferimos mantener el id si existe en ambos (para referencial)
        if ("id" in dst_cols) and ("id" not in common) and ("id" in src_cols):
            # forzamos id al inicio si está en origen y destino
            common = ["id"] + [c for c in common if c != "id"]

        placeholders = ",".join(["%s"] * len(common))
        col_list = ",".join(common)
        ins = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"
        for r in rows:
            vals = [r[c] for c in common]
            d_cur.execute(ins, vals)
        dst.commit()

    # Ajustar secuencias
    for table in ADJUST_SEQUENCES_FOR:
        try:
            if not is_safe_identifier(table):
                print(f"Skipping invalid table name for sequence adjust: {table!r}")
                continue
            d_cur.execute(f"SELECT COALESCE(MAX(id),0) FROM {table}")
            max_id = d_cur.fetchone()[0] or 0
            try:
                d_cur.execute("SELECT pg_get_serial_sequence(%s,'id')", (table,))
                seq = d_cur.fetchone()[0]
                if seq:
                    d_cur.execute("SELECT setval(%s, %s, %s)", (seq, max_id, True))
            except Exception:
                pass
        except Exception:
            pass
    dst.commit()

    # Resumen de conteos de tablas principales
    for table in ("ventas", "detalle_ventas", "usuarios", "productos"):
        try:
            if not is_safe_identifier(table):
                print(f"Skipping invalid table name for count: {table!r}")
                continue
            d_cur.execute(f"SELECT COUNT(*) FROM {table}")
            c = d_cur.fetchone()[0]
            print(f"{table}: {c}")
        except Exception:
            pass

    s_cur.close()
    src.close()
    d_cur.close()
    dst.close()
    print("OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
