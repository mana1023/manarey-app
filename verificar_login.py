"""
verificar_login.py - Script de diagnóstico para verificar usuarios y login
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from models.db import get_connection, init_db

print("=" * 60)
print("DIAGNÓSTICO DEL SISTEMA DE LOGIN")
print("=" * 60)

# Inicializar DB
try:
    init_db()
    print("✓ Base de datos inicializada correctamente")
except Exception as e:
    print(f"✗ Error inicializando DB: {e}")
    sys.exit(1)

# Verificar usuarios
try:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM usuarios")
    count = cur.fetchone()[0]
    print(f"\n📊 Total de usuarios en la base de datos: {count}")

    if count == 0:
        print("\n⚠️  NO HAY USUARIOS EN LA BASE DE DATOS")
        print("\nPara crear usuarios por defecto, ejecuta:")
        print("  python scripts/reseed_users.py")
    else:
        print("\n👥 Usuarios encontrados:")
        print("-" * 60)
        cur.execute("SELECT username, role, local, last_seen FROM usuarios")
        for row in cur.fetchall():
            username, role, local, last_seen = row
            local_str = f"({local})" if local else "(sin local)"
            last_seen_str = last_seen if last_seen else "nunca"
            print(
                f"  • {username:<15} | Rol: {role:<8} | Local: {local_str:<15} | Último acceso: {last_seen_str}"
            )

    # Verificar usuarios por defecto
    print("\n🔐 Verificando usuarios por defecto:")
    print("-" * 60)
    default_users = ["Administrador", "Cane", "Vidriera", "Longchamps", "Glew"]
    for user in default_users:
        cur.execute("SELECT username, role FROM usuarios WHERE username = ?", (user,))
        row = cur.fetchone()
        if row:
            print(f"  ✓ {user:<15} - {row[1]}")
        else:
            print(f"  ✗ {user:<15} - NO ENCONTRADO")

    conn.close()

except Exception as e:
    print(f"\n✗ Error consultando usuarios: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("CREDENCIALES POR DEFECTO:")
print("=" * 60)
print("  Administrador / lautaro10   (rol: admin)")
print("  Cane          / Manarey10   (rol: local)")
print("  Vidriera      / Manarey10   (rol: local)")
print("  Longchamps    / Manarey10   (rol: local)")
print("  Glew          / Manarey10   (rol: local)")
print("=" * 60)

print("\n✅ Diagnóstico completado")
print("\nPara verificar el login en modo DEBUG:")
print("  set MANAREY_DEBUG=1")
print("  python app.py")
print("\nLos errores de login se registran en: logs/auth.log")
