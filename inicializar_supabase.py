#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para inicializar Supabase con usuarios y estructura"""

import json
import os

import psycopg2

# URL de Supabase
SUPABASE_URL = "postgresql://postgres.bcdgkbptzogowbexcybn:Manarey10@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"


def inicializar_supabase():
    """Inicializa la base de datos de Supabase con tablas y usuarios"""
    print("=" * 60)
    print("INICIALIZACIÓN DE SUPABASE PARA MANAREY")
    print("=" * 60)
    print()

    try:
        print("📡 Conectando a Supabase...")
        conn = psycopg2.connect(SUPABASE_URL)
        conn.autocommit = False
        cur = conn.cursor()
        print("✅ Conexión establecida\n")

        # 1. CREAR TABLAS
        print("📋 Creando estructura de tablas...")

        # Tabla usuarios
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                local TEXT
            );
        """
        )
        print("   ✓ Tabla 'usuarios' creada")

        # Tabla productos
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS productos (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                categoria TEXT,
                medida TEXT,
                estado TEXT DEFAULT 'Nuevo',
                color TEXT,
                cantidad INTEGER DEFAULT 0,
                precio_costo REAL DEFAULT 0,
                precio_venta REAL DEFAULT 0,
                local TEXT NOT NULL,
                codigo TEXT UNIQUE,
                descripcion TEXT,
                created_at TEXT,
                updated_at TEXT
            );
        """
        )
        print("   ✓ Tabla 'productos' creada")

        # Tabla ventas
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ventas (
                id SERIAL PRIMARY KEY,
                numero_venta TEXT UNIQUE NOT NULL,
                local TEXT NOT NULL,
                fecha TEXT DEFAULT (NOW() AT TIME ZONE 'America/Argentina/Buenos_Aires')::TEXT,
                vendedor TEXT NOT NULL,
                cliente_nombre TEXT NOT NULL,
                cliente_telefono TEXT NOT NULL,
                cliente_calle TEXT,
                cliente_numero TEXT,
                cliente_localidad TEXT,
                subtotal_productos REAL NOT NULL DEFAULT 0,
                precio_envio REAL DEFAULT 0,
                descuento_tipo TEXT,
                descuento_valor REAL DEFAULT 0,
                descuento_aplicado REAL DEFAULT 0,
                total REAL NOT NULL,
                incluye_envio INTEGER DEFAULT 0,
                entre_calles TEXT,
                forma_pago_envio TEXT,
                remito_impreso INTEGER DEFAULT 0,
                entrega_entregado INTEGER DEFAULT 0,
                entrega_motivo TEXT,
                entrega_fecha TIMESTAMP,
                tarjeta_cuotas INTEGER DEFAULT 0,
                tarjeta_interes_pct REAL DEFAULT 0,
                tarjeta_interes_monto REAL DEFAULT 0,
                forma_pago TEXT NOT NULL,
                tipo_pago TEXT DEFAULT 'completo',
                monto_pagado REAL DEFAULT 0,
                monto_pendiente REAL DEFAULT 0,
                notas TEXT,
                estado TEXT DEFAULT 'completada',
                pdf_generado INTEGER DEFAULT 0
            );
        """
        )
        print("   ✓ Tabla 'ventas' creada")

        # Tabla detalle_ventas
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS detalle_ventas (
                id SERIAL PRIMARY KEY,
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
                FOREIGN KEY(venta_id) REFERENCES ventas(id) ON DELETE CASCADE
            );
        """
        )
        print("   ✓ Tabla 'detalle_ventas' creada")

        # Tabla historial_stock
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
                created_at TEXT DEFAULT (NOW() AT TIME ZONE 'America/Argentina/Buenos_Aires')::TEXT,
                motivo TEXT,
                meta TEXT,
                undone INTEGER DEFAULT 0,
                undone_by TEXT,
                undone_at TEXT,
                grupo_id TEXT
            );
        """
        )
        print("   ✓ Tabla 'historial_stock' creada")

        # Tabla venta_pagos
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS venta_pagos (
                id SERIAL PRIMARY KEY,
                venta_id INTEGER NOT NULL,
                metodo TEXT NOT NULL,
                monto REAL NOT NULL,
                FOREIGN KEY(venta_id) REFERENCES ventas(id) ON DELETE CASCADE
            );
        """
        )
        print("   ✓ Tabla 'venta_pagos' creada")

        print("\n👥 Creando usuarios...")

        # 2. CREAR USUARIOS
        usuarios = [
            ("Administrador", "lautaro10", "admin", None),
            ("cane", "Manarey10", "local", "Cane"),
            ("vidriera", "Manarey10", "local", "Vidriera"),
            ("longchamps", "Manarey10", "local", "Longchamps"),
        ]

        for username, password, role, local in usuarios:
            try:
                cur.execute(
                    """
                    INSERT INTO usuarios (username, password, role, local)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (username) DO NOTHING
                """,
                    (username, password, role, local),
                )
                print(f"   ✓ Usuario '{username}' creado")
            except Exception as e:
                print(f"   ⚠ Usuario '{username}' ya existe o error: {e}")

        # Confirmar cambios
        conn.commit()

        print("\n" + "=" * 60)
        print("✅ INICIALIZACIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 60)
        print("\n📊 Usuarios creados:\n")

        # Mostrar usuarios
        cur.execute("SELECT username, role, local FROM usuarios ORDER BY id")
        usuarios_creados = cur.fetchall()

        print("┌─────────────────┬─────────┬──────────────┐")
        print("│ Usuario         │ Rol     │ Local        │")
        print("├─────────────────┼─────────┼──────────────┤")
        for username, role, local in usuarios_creados:
            local_str = local if local else "N/A"
            print(f"│ {username:<15} │ {role:<7} │ {local_str:<12} │")
        print("└─────────────────┴─────────┴──────────────┘")

        print("\n🔑 Credenciales de acceso:\n")
        print("  ADMINISTRADOR:")
        print("    Usuario: Administrador")
        print("    Contraseña: lautaro10")
        print()
        print("  LOCAL CANE:")
        print("    Usuario: cane")
        print("    Contraseña: Manarey10")
        print()
        print("  LOCAL VIDRIERA:")
        print("    Usuario: vidriera")
        print("    Contraseña: Manarey10")
        print()
        print("  LOCAL LONGCHAMPS:")
        print("    Usuario: longchamps")
        print("    Contraseña: Manarey10")
        print()
        print("=" * 60)
        print("🎉 Ahora podés iniciar sesión desde cualquier PC!")
        print("=" * 60)

        cur.close()
        conn.close()
        return True

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        try:
            conn.rollback()
        except:
            pass
        return False


if __name__ == "__main__":
    try:
        print()
        inicializar_supabase()
        print()
        input("Presioná ENTER para salir...")
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {str(e)}")
        input("Presioná ENTER para salir...")
