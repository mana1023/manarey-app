"""
Script para verificar si Supabase está disponible (conexiones liberadas)
"""
import sys
import time

import psycopg2

# Tu URL de Supabase
url = "postgresql://postgres.bcdgkbptzogowbexcybn:Manarey10@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=disable"


def verificar_conexion():
    """Intenta conectar a Supabase"""
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT NOW();")
        resultado = cur.fetchone()
        cur.close()
        conn.close()
        return True, f"Conectado exitosamente - Hora del servidor: {resultado[0]}"
    except psycopg2.OperationalError as e:
        error = str(e)
        if "MaxClientsInSessionMode" in error or "max clients reached" in error:
            return False, "⏳ Supabase sigue con límite de conexiones alcanzado"
        elif "SSL" in error:
            return False, f"❌ Error SSL: {error[:100]}"
        else:
            return False, f"❌ Error: {error[:100]}"
    except Exception as e:
        return False, f"❌ Error inesperado: {str(e)[:100]}"


print("=" * 70)
print("VERIFICADOR DE DISPONIBILIDAD DE SUPABASE")
print("=" * 70)
print("\nPresioná Ctrl+C para detener\n")

intentos = 0
while True:
    intentos += 1
    print(f"[{time.strftime('%H:%M:%S')}] Intento #{intentos}...", end=" ")

    disponible, mensaje = verificar_conexion()

    if disponible:
        print(f"\n\n{'='*70}")
        print("✅ ¡SUPABASE DISPONIBLE!")
        print(f"{'='*70}")
        print(f"\n{mensaje}")
        print("\n🔄 Pasos para volver a usar PostgreSQL:")
        print("1. Abrí config.json")
        print('2. Cambiá "database_type": "sqlite" a "postgresql"')
        print('3. Copiá la URL desde "_postgres_url_cuando_funcione"')
        print("4. Ejecutá: python app.py")
        print(f"\n{'='*70}\n")
        break
    else:
        print(mensaje)

    # Esperar 30 segundos antes del próximo intento
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        print("\n\n⏹️  Verificación detenida por el usuario")
        print("Podés ejecutar este script de nuevo cuando quieras.")
        sys.exit(0)

print("Verificación completada. ¡Supabase está listo!")
