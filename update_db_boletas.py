def update_database_for_boletas():
    """Actualiza la base de datos agregando las tablas de boletas"""
    conn = get_conn()
    cursor = conn.cursor()
    try:
        logger.info("Iniciando actualización de base de datos para boletas...")

        # Habilitar FK en SQLite
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Tabla principal
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS boletas_emitidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_boleta TEXT UNIQUE NOT NULL,
                local TEXT NOT NULL,
                fecha_emision DATETIME DEFAULT CURRENT_TIMESTAMP,

                -- Datos del cliente
                cliente_dni TEXT,
                cliente_nombre TEXT,
                cliente_apellido TEXT,
                cliente_telefono TEXT,
                cliente_direccion TEXT,
                cliente_email TEXT,

                -- Totales
                subtotal REAL DEFAULT 0,
                descuento REAL DEFAULT 0,
                total REAL DEFAULT 0,

                -- Metadatos
                usuario_emisor TEXT NOT NULL,
                observaciones TEXT,

                -- Control de impresión
                impresa INTEGER DEFAULT 0,
                fecha_impresion DATETIME
            )
        """
        )
        logger.info("✓ Tabla boletas_emitidas creada/ok")

        # Detalle
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS boletas_detalle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                boleta_id INTEGER NOT NULL,
                producto_id INTEGER NOT NULL,
                producto_nombre TEXT NOT NULL,
                producto_categoria TEXT,
                producto_medida TEXT,
                cantidad INTEGER NOT NULL,
                precio_unitario REAL NOT NULL,
                subtotal REAL NOT NULL,

                FOREIGN KEY (boleta_id) REFERENCES boletas_emitidas(id) ON DELETE CASCADE,
                FOREIGN KEY (producto_id) REFERENCES productos(id) -- ⚠️ cambia 'productos' si tu tabla se llama distinto
            )
        """
        )
        logger.info("✓ Tabla boletas_detalle creada/ok")

        # Numeración
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS boletas_numeracion (
                local TEXT PRIMARY KEY,
                ultimo_numero INTEGER DEFAULT 0
            )
        """
        )
        logger.info("✓ Tabla boletas_numeracion creada/ok")

        # Semillas numeración
        for local in ["Cane", "Vidriera", "Longchamps", "Glew"]:
            cursor.execute(
                """
                INSERT OR IGNORE INTO boletas_numeracion (local, ultimo_numero)
                VALUES (?, 0)
            """,
                (local,),
            )
        logger.info("✓ Numeración inicializada")

        # Índices
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_boletas_local   ON boletas_emitidas(local)",
            "CREATE INDEX IF NOT EXISTS idx_boletas_fecha   ON boletas_emitidas(fecha_emision)",
            "CREATE INDEX IF NOT EXISTS idx_boletas_numero  ON boletas_emitidas(numero_boleta)",
            "CREATE INDEX IF NOT EXISTS idx_boletas_impresa ON boletas_emitidas(impresa)",
            "CREATE INDEX IF NOT EXISTS idx_detalle_boleta  ON boletas_detalle(boleta_id)",
            "CREATE INDEX IF NOT EXISTS idx_detalle_producto ON boletas_detalle(producto_id)",
        ]:
            cursor.execute(stmt)
        logger.info("✓ Índices creados/ok")

        conn.commit()
        logger.info("✅ Base de datos actualizada exitosamente para boletas")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'boletas%'"
        )
        logger.info(f"Tablas de boletas: {[t[0] for t in cursor.fetchall()]}")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error actualizando base de datos: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("🔄 Actualizando base de datos para sistema de boletas...")
    # Corre SIEMPRE; es idempotente por IF NOT EXISTS
    update_database_for_boletas()
    print("✨ Actualización completada")
