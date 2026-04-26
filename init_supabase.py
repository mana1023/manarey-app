"""
init_supabase.py - Inicializa un proyecto nuevo de Supabase con todas las tablas y usuarios
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

print("=" * 70)
print("INICIALIZACIÓN DE NUEVO PROYECTO SUPABASE")
print("=" * 70)

# Cargar configuración
import json

config_path = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(config_path, "r") as f:
        config = json.load(f)
    if config.get("database_type") == "postgresql" and config.get("database_url"):
        os.environ["DATABASE_URL"] = config["database_url"]
        print(f"✓ Configuración PostgreSQL cargada")
        print(f"  URL: {config['database_url'][:60]}...")
    else:
        print("✗ Configuración no está en modo PostgreSQL")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error cargando configuración: {e}")
    sys.exit(1)

# Verificar conexión
print("\n🔌 Verificando conexión a Supabase...")
try:
    import psycopg2

    conn = psycopg2.connect(config["database_url"])
    cur = conn.cursor()
    cur.execute("SELECT version()")
    version = cur.fetchone()[0]
    print(f"✓ Conexión exitosa!")
    print(f"  Versión: {version.split(',')[0]}")
except Exception as e:
    print(f"✗ Error de conexión: {e}")
    print("\n💡 Verifica:")
    print("   1. Que tengas conexión a internet")
    print("   2. Que la contraseña sea correcta")
    print("   3. Que el proyecto esté activo en Supabase")
    sys.exit(1)

# Crear tablas
print("\n📋 Creando tablas...")

try:
    # Tabla usuarios
    print("  → Creando tabla 'usuarios'...")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            local TEXT,
            last_seen TIMESTAMP
        )
    """
    )
    print("    ✓ usuarios")

    # Tabla productos
    print("  → Creando tabla 'productos'...")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS productos (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            categoria TEXT,
            medida TEXT,
            estado TEXT DEFAULT 'activo',
            color TEXT,
            cantidad INTEGER DEFAULT 0,
            precio_costo NUMERIC(10,2) DEFAULT 0,
            precio_venta NUMERIC(10,2) DEFAULT 0,
            local TEXT NOT NULL,
            codigo TEXT UNIQUE,
            descripcion TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """
    )
    print("    ✓ productos")

    # Tabla ventas
    print("  → Creando tabla 'ventas'...")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ventas (
            id SERIAL PRIMARY KEY,
            numero_venta TEXT UNIQUE NOT NULL,
            local TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT NOW(),
            vendedor TEXT NOT NULL,
            cliente_nombre TEXT NOT NULL,
            cliente_telefono TEXT NOT NULL,
            cliente_calle TEXT,
            cliente_numero TEXT,
            cliente_localidad TEXT,
            subtotal_productos NUMERIC(10,2) NOT NULL DEFAULT 0,
            precio_envio NUMERIC(10,2) DEFAULT 0,
            descuento_tipo TEXT CHECK(descuento_tipo IN ('porcentaje', 'monto')),
            descuento_valor NUMERIC(10,2) DEFAULT 0,
            descuento_aplicado NUMERIC(10,2) DEFAULT 0,
            total NUMERIC(10,2) NOT NULL,
            incluye_envio INTEGER DEFAULT 0,
            entre_calles TEXT,
            forma_pago_envio TEXT,
            remito_impreso INTEGER DEFAULT 0,
            entrega_entregado INTEGER DEFAULT 0,
            entrega_motivo TEXT,
            entrega_fecha TIMESTAMP,
            tarjeta_cuotas INTEGER DEFAULT 0,
            tarjeta_interes_pct NUMERIC(10,2) DEFAULT 0,
            tarjeta_interes_monto NUMERIC(10,2) DEFAULT 0,
            forma_pago TEXT NOT NULL,
            tipo_pago TEXT CHECK(tipo_pago IN ('completo', 'sena', 'domicilio', 'credito_personal')) DEFAULT 'completo',
            monto_pagado NUMERIC(10,2) DEFAULT 0,
            monto_pendiente NUMERIC(10,2) DEFAULT 0,
            notas TEXT,
            estado TEXT DEFAULT 'completada' CHECK(estado IN ('completada', 'pendiente', 'cancelada')),
            pdf_generado INTEGER DEFAULT 0
        )
    """
    )
    print("    ✓ ventas")

    # Tabla detalle_ventas
    print("  → Creando tabla 'detalle_ventas'...")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS detalle_ventas (
            id SERIAL PRIMARY KEY,
            venta_id INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
            producto_id INTEGER NOT NULL,
            producto_nombre TEXT NOT NULL,
            producto_categoria TEXT,
            producto_fabricante TEXT,
            producto_medida TEXT,
            producto_estado TEXT,
            producto_color TEXT,
            cantidad INTEGER NOT NULL,
            precio_unitario NUMERIC(10,2) NOT NULL,
            subtotal NUMERIC(10,2) NOT NULL
        )
    """
    )
    print("    ✓ detalle_ventas")

    # Tabla venta_pagos (para pagos divididos)
    print("  → Creando tabla 'venta_pagos'...")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS venta_pagos (
            id SERIAL PRIMARY KEY,
            venta_id INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
            forma TEXT NOT NULL,
            monto NUMERIC(10,2) NOT NULL
        )
    """
    )
    print("    ✓ venta_pagos")

    # Tabla historial_stock
    print("  → Creando tabla 'historial_stock'...")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS historial_stock (
            id SERIAL PRIMARY KEY,
            producto_id INTEGER,
            accion TEXT NOT NULL,
            detalle TEXT,
            cantidad INTEGER,
            usuario TEXT,
            local TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            motivo TEXT,
            meta TEXT,
            undone INTEGER DEFAULT 0,
            undone_by TEXT,
            undone_at TIMESTAMP,
            grupo_id TEXT
        )
    """
    )
    print("    ✓ historial_stock")

    conn.commit()
    print("\n✅ Todas las tablas creadas exitosamente")

except Exception as e:
    conn.rollback()
    print(f"\n✗ Error creando tablas: {e}")
    import traceback

    traceback.print_exc()
    conn.close()
    sys.exit(1)

# Crear índices
print("\n🔍 Creando índices para optimizar consultas...")
try:
    indices = [
        (
            "idx_ventas_fecha",
            "CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha)",
        ),
        (
            "idx_ventas_local",
            "CREATE INDEX IF NOT EXISTS idx_ventas_local ON ventas(local)",
        ),
        (
            "idx_ventas_estado",
            "CREATE INDEX IF NOT EXISTS idx_ventas_estado ON ventas(estado)",
        ),
        (
            "idx_detalle_venta",
            "CREATE INDEX IF NOT EXISTS idx_detalle_venta ON detalle_ventas(venta_id)",
        ),
        (
            "idx_hist_local_created",
            "CREATE INDEX IF NOT EXISTS idx_hist_local_created ON historial_stock(local, created_at)",
        ),
        (
            "idx_hist_producto",
            "CREATE INDEX IF NOT EXISTS idx_hist_producto ON historial_stock(producto_id)",
        ),
        (
            "idx_prod_local",
            "CREATE INDEX IF NOT EXISTS idx_prod_local ON productos(local)",
        ),
        (
            "idx_prod_local_nombre",
            "CREATE INDEX IF NOT EXISTS idx_prod_local_nombre ON productos(local, nombre)",
        ),
    ]

    for nombre, sql in indices:
        cur.execute(sql)
        print(f"  ✓ {nombre}")

    conn.commit()
    print("✅ Índices creados")

except Exception as e:
    print(f"⚠️  Advertencia creando índices: {e}")

# Crear usuarios por defecto
print("\n👥 Creando usuarios por defecto...")
try:
    from models import auth as auth_mod

    usuarios = [
        ("Administrador", "lautaro10", "admin", None),
        ("Cane", "Manarey10", "local", "Cane"),
        ("Vidriera", "Manarey10", "local", "Vidriera"),
        ("Longchamps", "Manarey10", "local", "Longchamps"),
        ("Glew", "Manarey10", "local", "Glew"),
    ]

    for username, password, role, local in usuarios:
        try:
            # Hash password
            hashed_pw = auth_mod.hash_password(password)

            # Insert or update
            cur.execute(
                """
                INSERT INTO usuarios (username, password, role, local)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    password = EXCLUDED.password,
                    role = EXCLUDED.role,
                    local = EXCLUDED.local
            """,
                (username, hashed_pw, role, local),
            )

            local_str = f"({local})" if local else ""
            print(f"  ✓ {username:<15} | {role:<8} {local_str}")

        except Exception as e:
            print(f"  ✗ Error con {username}: {e}")

    conn.commit()
    print("\n✅ Usuarios creados exitosamente")

except Exception as e:
    print(f"\n✗ Error creando usuarios: {e}")
    import traceback

    traceback.print_exc()

# Verificar todo
print("\n📊 Verificación final...")
try:
    cur.execute("SELECT COUNT(*) FROM usuarios")
    user_count = cur.fetchone()[0]
    print(f"  Usuarios: {user_count}")

    cur.execute("SELECT COUNT(*) FROM productos")
    prod_count = cur.fetchone()[0]
    print(f"  Productos: {prod_count}")

    cur.execute("SELECT COUNT(*) FROM ventas")
    sales_count = cur.fetchone()[0]
    print(f"  Ventas: {sales_count}")

except Exception as e:
    print(f"  Error en verificación: {e}")

conn.close()

print("\n" + "=" * 70)
print("🎉 INICIALIZACIÓN COMPLETADA EXITOSAMENTE")
print("=" * 70)

print("\n✅ Tu nuevo proyecto Supabase está listo para usar!")
print("\n🔐 Credenciales para iniciar sesión:")
print("   Administrador / lautaro10   (acceso a todos los locales)")
print("   Cane          / Manarey10   (solo local Cane)")
print("   Vidriera      / Manarey10   (solo local Vidriera)")
print("   Longchamps    / Manarey10   (solo local Longchamps)")
print("   Glew          / Manarey10   (solo local Glew)")

print("\n🚀 Próximo paso:")
print("   python app.py")

print("\n💡 Notas:")
print("   • La base de datos está vacía (sin productos ni ventas)")
print("   • Cada local debe empezar a cargar su inventario")
print("   • Todas las 4 mueblerías comparten la misma base de datos")
print("   • Los cambios se sincronizan en tiempo real")
