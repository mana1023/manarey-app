"""
verificar_postgres.py - Verifica y prepara la base de datos PostgreSQL/Supabase
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

print("=" * 70)
print("VERIFICACIÓN Y CONFIGURACIÓN DE POSTGRESQL/SUPABASE")
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
        print(f"  URL: {config['database_url'][:50]}...")
    else:
        print("✗ Configuración no está en modo PostgreSQL")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error cargando configuración: {e}")
    sys.exit(1)

# Importar DB
try:
    from models.db import get_connection, is_postgres

    if not is_postgres():
        print("✗ La conexión no está usando PostgreSQL")
        sys.exit(1)
    print("✓ Módulo de base de datos importado correctamente")
except Exception as e:
    print(f"✗ Error importando módulo de DB: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Verificar conexión
print("\n🔌 Verificando conexión a Supabase...")
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT version()")
    version = cur.fetchone()[0]
    print(f"✓ Conexión exitosa!")
    print(f"  Versión PostgreSQL: {version.split(',')[0]}")
    conn.close()
except Exception as e:
    print(f"✗ Error de conexión: {e}")
    print("\n💡 Posibles causas:")
    print("   1. No hay conexión a internet")
    print("   2. Las credenciales de Supabase son incorrectas")
    print("   3. El proyecto de Supabase está pausado")
    print("\n   Revisa tu panel de Supabase: https://supabase.com/dashboard")
    sys.exit(1)

# Verificar tablas
print("\n📋 Verificando tablas necesarias...")
tablas_requeridas = [
    "usuarios",
    "productos",
    "ventas",
    "detalle_ventas",
    "historial_stock",
    "venta_pagos",
]

try:
    conn = get_connection()
    cur = conn.cursor()

    tablas_existentes = []
    tablas_faltantes = []

    for tabla in tablas_requeridas:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            )
        """,
            (tabla,),
        )
        existe = cur.fetchone()[0]
        if existe:
            tablas_existentes.append(tabla)
            print(f"  ✓ {tabla}")
        else:
            tablas_faltantes.append(tabla)
            print(f"  ✗ {tabla} - FALTA")

    conn.close()

    print(f"\n📊 Resumen:")
    print(f"  Tablas encontradas: {len(tablas_existentes)}/{len(tablas_requeridas)}")

    if tablas_faltantes:
        print(f"\n⚠️  FALTAN {len(tablas_faltantes)} TABLAS:")
        for tabla in tablas_faltantes:
            print(f"     • {tabla}")
        print("\n🔧 Acción requerida:")
        print("   Ejecuta el script de migración para crear las tablas:")
        print("   python migrate_to_postgres.py")
        sys.exit(1)

except Exception as e:
    print(f"\n✗ Error verificando tablas: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Verificar usuarios
print("\n👥 Verificando usuarios...")
try:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM usuarios")
    count = cur.fetchone()[0]
    print(f"  Total de usuarios: {count}")

    if count == 0:
        print("\n⚠️  NO HAY USUARIOS")
        print("  El script de migración creará los usuarios por defecto.")
    else:
        cur.execute(
            "SELECT username, role, local FROM usuarios ORDER BY role DESC, username"
        )
        for row in cur.fetchall():
            username, role, local_name = row
            local_str = f"({local_name})" if local_name else ""
            print(f"    • {username:<15} | {role:<8} {local_str}")

    conn.close()

except Exception as e:
    print(f"✗ Error verificando usuarios: {e}")

print("\n" + "=" * 70)
print("✅ VERIFICACIÓN COMPLETADA")
print("=" * 70)

print("\n📝 Próximos pasos:")
if tablas_faltantes:
    print("  1. Ejecuta: python migrate_to_postgres.py")
    print("     (Esto creará las tablas y migrará los datos si tienes SQLite local)")
else:
    print("  ✓ La base de datos está lista para usar")
    print("  ✓ Puedes iniciar la aplicación: python app.py")

print("\n💡 Credenciales por defecto:")
print("   Administrador / lautaro10   (acceso a todos los locales)")
print("   Cane          / Manarey10   (solo local Cane)")
print("   Vidriera      / Manarey10   (solo local Vidriera)")
print("   Longchamps    / Manarey10   (solo local Longchamps)")
print("   Glew          / Manarey10   (solo local Glew)")
