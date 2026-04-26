"""
crear_usuarios_supabase.py - Crea usuarios en Supabase con bcrypt
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

print("=" * 70)
print("CREAR USUARIOS EN SUPABASE")
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
    else:
        print("✗ Configuración no está en modo PostgreSQL")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error cargando configuración: {e}")
    sys.exit(1)

# Instalar bcrypt si no está
print("\n📦 Verificando bcrypt...")
try:
    import bcrypt

    print("✓ bcrypt disponible")
except ImportError:
    print("⚠️  bcrypt no está instalado. Instalando...")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "bcrypt"])
    import bcrypt

    print("✓ bcrypt instalado")

# Conectar
print("\n🔌 Conectando a Supabase...")
try:
    import psycopg2

    conn = psycopg2.connect(config["database_url"])
    cur = conn.cursor()
    print("✓ Conectado")
except Exception as e:
    print(f"✗ Error de conexión: {e}")
    sys.exit(1)

# Crear usuarios
print("\n👥 Creando usuarios...")

usuarios = [
    ("Administrador", "lautaro10", "admin", None),
    ("Cane", "Manarey10", "local", "Cane"),
    ("Vidriera", "Manarey10", "local", "Vidriera"),
    ("Longchamps", "Manarey10", "local", "Longchamps"),
    ("Glew", "Manarey10", "local", "Glew"),
]

for username, password, role, local in usuarios:
    try:
        # Hash password con bcrypt
        salt = bcrypt.gensalt()
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

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

# Verificar
print("\n📊 Verificación...")
cur.execute("SELECT COUNT(*) FROM usuarios")
count = cur.fetchone()[0]
print(f"  Total usuarios creados: {count}")

conn.close()

print("\n" + "=" * 70)
print("✅ USUARIOS CREADOS EXITOSAMENTE")
print("=" * 70)

print("\n🔐 Credenciales:")
print("   Administrador / lautaro10")
print("   Cane          / Manarey10")
print("   Vidriera      / Manarey10")
print("   Longchamps    / Manarey10")
print("   Glew          / Manarey10")

print("\n🚀 Ahora ejecuta: python app.py")
