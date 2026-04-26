import psycopg2

url = "postgresql://postgres.bcdgkbptzogowbexcybn:Manarey10@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"

try:
    conn = psycopg2.connect(url)
    cur = conn.cursor()

    # Verificar tablas
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
    )
    tablas = cur.fetchone()[0]
    print(f"Tablas en la base de datos: {tablas}")

    # Verificar usuarios
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'usuarios'"
    )
    existe_usuarios = cur.fetchone()[0]

    if existe_usuarios > 0:
        cur.execute("SELECT COUNT(*) FROM usuarios")
        usuarios = cur.fetchone()[0]
        print(f"Usuarios en la tabla: {usuarios}")
    else:
        print("Tabla 'usuarios' NO existe aún")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
