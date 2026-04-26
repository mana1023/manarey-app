"""
Script de migración para agregar columna fabricante a la tabla stock
Soporta tanto PostgreSQL como SQLite
"""
import json
import os
import sys

# Agregar el directorio raíz al path para importar models
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Cargar configuración de base de datos (igual que app.py)
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
try:
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            if config.get("database_type") == "postgresql" and config.get(
                "database_url"
            ):
                os.environ["DATABASE_URL"] = config["database_url"]
                print(f"✓ Configurado para usar PostgreSQL/Supabase")
            else:
                print(f"✓ Configurado para usar SQLite local")
except Exception as e:
    print(f"⚠ Error cargando configuración: {e}")


def migrate():
    """Agrega la columna fabricante a la tabla stock"""
    try:
        from models.db import _WANT_POSTGRES, get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()

        # Verificar si la columna ya existe
        if _WANT_POSTGRES:
            # PostgreSQL: consultar information_schema
            cursor.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='stock' AND column_name='fabricante'
            """
            )
            exists = cursor.fetchone() is not None
        else:
            # SQLite: PRAGMA table_info
            cursor.execute("PRAGMA table_info(stock)")
            columns = [column[1] for column in cursor.fetchall()]
            exists = "fabricante" in columns

        if exists:
            print("✅ La columna 'fabricante' ya existe")
            conn.close()
            return True

        # Agregar la columna fabricante
        print("📝 Agregando columna 'fabricante' a tabla stock...")
        cursor.execute("ALTER TABLE stock ADD COLUMN fabricante TEXT")

        # Establecer valor por defecto para registros existentes
        cursor.execute("UPDATE stock SET fabricante = '' WHERE fabricante IS NULL")

        conn.commit()
        print("✅ Migración completada exitosamente")
        print("   - Columna 'fabricante' agregada")

        db_type = "PostgreSQL" if _WANT_POSTGRES else "SQLite"
        print(f"   - Base de datos: {db_type}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error en migración: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=== Migración: Agregar columna fabricante ===\n")
    success = migrate()

    if success:
        print("\n✅ Migración completada. Puedes ejecutar la aplicación.")
    else:
        print("\n❌ Migración falló. Revisa los errores arriba.")
