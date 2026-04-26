import sqlite3

# app.py - Aplicación principal de Manarey
from pathlib import Path

from models.sql_utils import is_safe_identifier

# db.py (raíz)
# Este archivo existe por compatibilidad histórica. La aplicación actual debería usar
# el módulo `models/db.py` que contiene la lógica principal de conexión (SQLite/Postgres,
# pooling, configuraciones de PRAGMA, etc.).
#
# Mantener este archivo con fines de referencia. Evita usar `db.py` de la raíz para
# nuevas modificaciones: edita `models/db.py`.


DB_PATH = Path("manarey.sqlite3")


def get_conn():
    return sqlite3.connect(DB_PATH)


def _has_column(conn, table, column):
    # validar identificador de tabla antes de interpolar en PRAGMA
    if not isinstance(table, str) or not is_safe_identifier(table):
        raise ValueError(f"Invalid table name: {table!r}")
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == column for r in cur.fetchall())


def init_db():
    first_time = not DB_PATH.exists()
    conn = get_conn()
    cur = conn.cursor()

    # Productos
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            material TEXT,
            categoria TEXT NOT NULL,
            medida TEXT,
            estado TEXT DEFAULT 'Nuevo',
            color TEXT,
            cantidad INTEGER NOT NULL DEFAULT 0,
            precio_costo REAL DEFAULT 0,
            precio_venta REAL NOT NULL DEFAULT 0,
            local TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """
    )

    # Usuarios
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,         -- 'admin' o 'local'
            local TEXT
        );
    """
    )

    # Historial
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS historial_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER,
            accion TEXT NOT NULL,       -- ingreso, ajuste, baja, cambio_estado, transferencia
            detalle TEXT,
            cantidad INTEGER,           -- delta (+/-); NULL en cambios de campo
            usuario TEXT,
            local TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            undone INTEGER DEFAULT 0,
            undone_by TEXT,
            undone_at TEXT
        );
    """
    )

    # Migraciones suaves
    for col, ddl in [
        ("motivo", "TEXT"),
        ("meta", "TEXT"),  # JSON: before/after y extras
        ("grupo_id", "TEXT"),  # para transferencias (ida/entrada)
    ]:
        if not _has_column(conn, "historial_stock", col):
            # columna/DDL provienen de la lista fija arriba; validar la columna
            if not is_safe_identifier(col):
                raise ValueError(f"Invalid column name in migration list: {col!r}")
            cur.execute(f"ALTER TABLE historial_stock ADD COLUMN {col} {ddl}")

    # Ventas completa (actualizada)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local TEXT NOT NULL,
            total REAL NOT NULL,
            cliente_nombre TEXT,
            cliente_direccion TEXT,
            cliente_telefono TEXT,
            notas TEXT,
            fecha TEXT DEFAULT (datetime('now')),
            vendedor TEXT,
            descuento_tipo TEXT,
            descuento_valor REAL,
            estado TEXT DEFAULT 'completada' CHECK(estado IN ('completada', 'pendiente', 'cancelada')),
            pdf_generado INTEGER DEFAULT 0,
            numero_venta TEXT UNIQUE,
            cliente_calle TEXT,
            cliente_numero TEXT,
            cliente_localidad TEXT,
            subtotal_productos REAL DEFAULT 0,
            precio_envio REAL DEFAULT 0,
            descuento_aplicado REAL DEFAULT 0,
            incluye_envio INTEGER DEFAULT 0,
            entre_calles TEXT,
            forma_pago_envio TEXT,
            remito_impreso INTEGER DEFAULT 0,
            entrega_entregado INTEGER DEFAULT 0,
            entrega_motivo TEXT,
            entrega_fecha TEXT,
            entrega_programada TEXT,
            tarjeta_cuotas INTEGER DEFAULT 0,
            tarjeta_interes_pct REAL DEFAULT 0,
            tarjeta_interes_monto REAL DEFAULT 0,
            forma_pago TEXT,
            tipo_pago TEXT CHECK(tipo_pago IN ('completo', 'sena', 'domicilio', 'credito_personal')),
            monto_pagado REAL DEFAULT 0,
            monto_pendiente REAL DEFAULT 0
        );
    """
    )
    if not _has_column(conn, "productos", "material"):
        cur.execute("ALTER TABLE productos ADD COLUMN material TEXT")
    if not _has_column(conn, "ventas", "forma_pago_envio"):
        cur.execute("ALTER TABLE ventas ADD COLUMN forma_pago_envio TEXT")
    if not _has_column(conn, "ventas", "remito_impreso"):
        cur.execute("ALTER TABLE ventas ADD COLUMN remito_impreso INTEGER DEFAULT 0")
    if not _has_column(conn, "ventas", "entrega_entregado"):
        cur.execute("ALTER TABLE ventas ADD COLUMN entrega_entregado INTEGER DEFAULT 0")
    if not _has_column(conn, "ventas", "entrega_motivo"):
        cur.execute("ALTER TABLE ventas ADD COLUMN entrega_motivo TEXT")
    if not _has_column(conn, "ventas", "entrega_fecha"):
        cur.execute("ALTER TABLE ventas ADD COLUMN entrega_fecha TEXT")
    if not _has_column(conn, "ventas", "entrega_programada"):
        cur.execute("ALTER TABLE ventas ADD COLUMN entrega_programada TEXT")
    if not _has_column(conn, "ventas", "tarjeta_cuotas"):
        cur.execute("ALTER TABLE ventas ADD COLUMN tarjeta_cuotas INTEGER DEFAULT 0")
    if not _has_column(conn, "ventas", "tarjeta_interes_pct"):
        cur.execute("ALTER TABLE ventas ADD COLUMN tarjeta_interes_pct REAL DEFAULT 0")
    if not _has_column(conn, "ventas", "tarjeta_interes_monto"):
        cur.execute(
            "ALTER TABLE ventas ADD COLUMN tarjeta_interes_monto REAL DEFAULT 0"
        )

    # Detalle de ventas
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS detalle_ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            producto_nombre TEXT NOT NULL,
            producto_categoria TEXT,
            producto_fabricante TEXT,
            producto_medida TEXT,
            producto_estado TEXT,
            producto_color TEXT,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (venta_id) REFERENCES ventas (id),
            FOREIGN KEY (producto_id) REFERENCES productos (id)
        );
    """
    )
    if not _has_column(conn, "detalle_ventas", "producto_fabricante"):
        cur.execute("ALTER TABLE detalle_ventas ADD COLUMN producto_fabricante TEXT")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cierres_diarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,             -- YYYY-MM-DD
            local TEXT NOT NULL,
            total_items INTEGER NOT NULL,
            total_valorizado REAL NOT NULL,
            generado_por TEXT NOT NULL,
            creado_en TEXT DEFAULT (datetime('now')),
            UNIQUE(fecha, local)
        );
    """
    )

    conn.commit()
    if first_time:
        seed_users(cur)
        conn.commit()
    conn.close()


def seed_users(cur):
    users = [
        ("Administrador", "lautaro10", "admin", None),
        ("Cane", "Manarey10", "local", "Cane"),
        ("Vidriera", "Manarey10", "local", "Vidriera"),
        ("Longchamps", "Manarey10", "local", "Longchamps"),
        ("Glew", "Manarey10", "local", "Glew"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO usuarios (username, password, role, local) VALUES (?,?,?,?)",
        users,
    )
