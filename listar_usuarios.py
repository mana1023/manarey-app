import psycopg2

url = "postgresql://postgres.bcdgkbptzogowbexcybn:Manarey10@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"

try:
    conn = psycopg2.connect(url)
    cur = conn.cursor()

    cur.execute("SELECT username, password, role, local FROM usuarios ORDER BY id")
    usuarios = cur.fetchall()

    print("\n" + "=" * 60)
    print("USUARIOS EN SUPABASE")
    print("=" * 60)
    print()
    print("┌─────────────────┬──────────────┬─────────┬──────────────┐")
    print("│ Usuario         │ Contraseña   │ Rol     │ Local        │")
    print("├─────────────────┼──────────────┼─────────┼──────────────┤")

    for username, password, role, local in usuarios:
        local_str = local if local else "N/A"
        print(f"│ {username:<15} │ {password:<12} │ {role:<7} │ {local_str:<12} │")

    print("└─────────────────┴──────────────┴─────────┴──────────────┘")
    print()
    print("=" * 60)
    print("✅ Base de datos inicializada correctamente")
    print("=" * 60)

    conn.close()
except Exception as e:
    print(f"Error: {e}")
