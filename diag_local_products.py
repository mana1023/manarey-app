"""
Script para diagnosticar qué locales tienen productos en la base de datos.
Ejecutar: python diag_local_products.py
"""
import os
import sys

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.firestore_db import _get_conn, list_products_by_local


def main():
    print("=" * 60)
    print("DIAGNÓSTICO DE LOCALES Y PRODUCTOS")
    print("=" * 60)

    # Obtener todos los locales únicos de la base de datos
    try:
        with _get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT local FROM productos ORDER BY local ASC")
            locales = [str(r[0]).strip() for r in cur.fetchall() if r and r[0]]
            print(f"\n1. Locales encontrados en la BD ({len(locales)}):")
            for i, loc in enumerate(locales, 1):
                # Contar productos por local
                cur.execute("SELECT COUNT(*) FROM productos WHERE local = %s", (loc,))
                count = cur.fetchone()[0]
                print(f"   {i}. '{loc}' -> {count} productos")
    except Exception as e:
        print(f"Error consultando locales: {e}")
        locales = []

    # Probar list_products_by_local con cada local
    print("\n2. Probando list_products_by_local:")
    for loc in locales[:5]:  # Probar solo los primeros 5
        try:
            products = list_products_by_local(loc)
            print(f"   '{loc}' -> {len(products)} productos encontrados")
        except Exception as e:
            print(f"   '{loc}' -> ERROR: {e}")

    # Probar con None (todos)
    print("\n3. Probando list_products_by_local(None) - todos:")
    try:
        products = list_products_by_local(None)
        print(f"   Todos -> {len(products)} productos encontrados")

        # Contar por local
        from collections import Counter

        por_local = Counter([p.get("local", "sin_local") for p in products])
        print("   Distribución por local:")
        for loc, count in sorted(por_local.items()):
            print(f"      '{loc}': {count}")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Probar con variaciones de "Estacion"
    print("\n4. Probando variaciones de 'Estacion':")
    variaciones = ["Estacion", "estacion", "ESTACION", "Estación", "estación"]
    for var in variaciones:
        try:
            products = list_products_by_local(var)
            print(f"   '{var}' -> {len(products)} productos")
        except Exception as e:
            print(f"   '{var}' -> ERROR: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
