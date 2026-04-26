"""
Script para probar la conexión al login con PostgreSQL
Muestra el error exacto en consola
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# Cargar config
import json

config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(config_path, "r") as f:
    config = json.load(f)
    if config.get("database_type") == "postgresql":
        os.environ["DATABASE_URL"] = config["database_url"]
        print(f"✓ Usando PostgreSQL")
        print(f"  URL: {config['database_url'][:60]}...")

print("\n" + "=" * 70)
print("TEST DE CONEXIÓN Y LOGIN")
print("=" * 70)

# Test 1: Importar módulos
print("\n1. Importando módulos...")
try:
    from models.db import get_connection, is_postgres

    print("   ✓ models.db importado")
except Exception as e:
    print(f"   ✗ Error importando: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Test 2: Crear conexión
print("\n2. Creando conexión a BD...")
try:
    conn = get_connection()
    print(f"   ✓ Conexión creada")
    print(f"   ✓ Tipo: {'PostgreSQL' if is_postgres() else 'SQLite'}")
except Exception as e:
    print(f"   ✗ Error de conexión: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Test 3: Query simple
print("\n3. Probando query simple...")
try:
    cur = conn.cursor()
    if is_postgres():
        cur.execute("SELECT version()")
    else:
        cur.execute("SELECT sqlite_version()")
    version = cur.fetchone()
    print(f"   ✓ Query exitosa")
    print(f"   ✓ Versión: {version[0][:60] if version else 'N/A'}...")
except Exception as e:
    print(f"   ✗ Error en query: {e}")
    import traceback

    traceback.print_exc()
    conn.close()
    sys.exit(1)

# Test 4: Query de usuarios
print("\n4. Probando query de usuarios...")
try:
    placeholder = "%s" if is_postgres() else "?"
    query = f"SELECT username, password, role, local FROM usuarios WHERE LOWER(username)=LOWER({placeholder})"
    print(f"   Query: {query}")

    cur.execute(query, ("Cane",))
    row = cur.fetchone()

    if row:
        print(f"   ✓ Usuario encontrado: {row[0]}")
        print(f"   ✓ Role: {row[2]}")
        print(f"   ✓ Local: {row[3]}")
        print(f"   ✓ Password hash: {row[1][:20]}...")
    else:
        print(f"   ✗ Usuario 'Cane' no encontrado en la BD")

        # Listar usuarios existentes
        cur.execute("SELECT username FROM usuarios")
        users = cur.fetchall()
        print(f"\n   Usuarios en BD: {[u[0] for u in users]}")

except Exception as e:
    print(f"   ✗ Error en query de usuarios: {e}")
    import traceback

    traceback.print_exc()
    conn.close()
    sys.exit(1)

# Test 5: Verificar password
print("\n5. Probando verificación de contraseña...")
try:
    from models import auth as auth_mod

    if row:
        stored_hash = row[1]
        test_password = "Manarey10"

        verified = auth_mod.verify_password(test_password, stored_hash)

        if verified:
            print(f"   ✓ Contraseña verificada correctamente")
        else:
            print(f"   ✗ Contraseña incorrecta")
            print(f"   Probá con la contraseña correcta del usuario")

except Exception as e:
    print(f"   ✗ Error verificando contraseña: {e}")
    import traceback

    traceback.print_exc()

# Cerrar conexión
conn.close()
print("\n" + "=" * 70)
print("✓ TODAS LAS PRUEBAS COMPLETADAS")
print("=" * 70)
print("\nSi todas las pruebas pasaron, el problema puede estar en:")
print("  • La interfaz gráfica (PyQt)")
print("  • Los hilos de ejecución (QThread)")
print("  • El manejo de señales entre threads")
print("\nIntentá ejecutar la app ahora: python app.py")
