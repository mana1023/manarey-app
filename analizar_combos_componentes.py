#!/usr/bin/env python3
"""
Analiza combos/conjuntos para encontrar los que tienen los mismos componentes
y propone estandarización de nombres.
"""

import logging
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))

from models import stock_model as sm

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def get_all_combos():
    """Obtiene todos los productos que son combos/conjuntos"""
    try:
        with sm._get_conn_cm() as conn:
            cur = conn.cursor()

            query = """
                SELECT id, nombre, local, precio_venta, categoria, medida
                FROM productos
                WHERE nombre ILIKE '%combo%' OR nombre ILIKE '%conjunto%' OR nombre ILIKE '%set%'
                ORDER BY local, nombre
            """
            cur.execute(query)
            rows = cur.fetchall()

            combos = []
            for row in rows:
                combos.append(
                    {
                        "id": row[0],
                        "nombre": row[1],
                        "local": row[2],
                        "precio": row[3],
                        "categoria": row[4],
                        "medida": row[5],
                    }
                )

            return combos
    except Exception as e:
        logger.error(f"Error obteniendo combos: {e}")
        import traceback

        traceback.print_exc()
        return []


def get_combo_items(combo_id):
    """Obtiene los productos que forman un combo"""
    try:
        with sm._get_conn_cm() as conn:
            cur = conn.cursor()

            query = """
                SELECT producto_id, cantidad, producto_nombre, producto_categoria, 
                       producto_medida, producto_fabricante
                FROM combo_items
                WHERE combo_producto_id = %s
                ORDER BY producto_id
            """

            try:
                cur.execute(query, (combo_id,))
            except:
                # Si falla con %s, intentar con ?
                cur.execute(query.replace("%s", "?"), (combo_id,))

            rows = cur.fetchall()

            items = []
            for row in rows:
                items.append(
                    {
                        "producto_id": row[0],
                        "cantidad": row[1],
                        "nombre": row[2],
                        "categoria": row[3],
                        "medida": row[4],
                        "fabricante": row[5],
                    }
                )

            return items
    except Exception as e:
        logger.error(f"Error obteniendo items del combo {combo_id}: {e}")
        return []


def normalize_componentes(items):
    """Crea una firma única de los componentes"""
    if not items:
        return ""

    # Crear firma basada en productos (sin IDs que pueden variar)
    componentes = []
    for item in items:
        componentes.append(f"{item['nombre']}|{item['cantidad']}|{item['medida']}")

    componentes.sort()
    return ";".join(componentes)


def comparar_componentes(items1, items2):
    """Compara si dos conjuntos de componentes son iguales"""
    if len(items1) != len(items2):
        return (
            False,
            f"Diferente cantidad de componentes: {len(items1)} vs {len(items2)}",
        )

    for i1, i2 in zip(items1, items2):
        if (
            i1["nombre"].lower().strip() != i2["nombre"].lower().strip()
            or i1["cantidad"] != i2["cantidad"]
        ):
            return (
                False,
                f"Diferente componente: '{i1['nombre']}' ({i1['cantidad']}) vs '{i2['nombre']}' ({i2['cantidad']})",
            )

    return True, "Componentes idénticos"


def main():
    logger.info("Iniciando análisis de combos/conjuntos...")

    combos = get_all_combos()
    logger.info(f"Total de combos/conjuntos encontrados: {len(combos)}")

    if not combos:
        logger.error("No hay combos para analizar")
        return

    # Agrupar por local
    combos_por_local = defaultdict(list)
    for combo in combos:
        combos_por_local[combo["local"]].append(combo)

    print("\n" + "=" * 140)
    print("ANALISIS DE COMBOS/CONJUNTOS - ESTANDARIZACION DE NOMBRES")
    print("=" * 140 + "\n")

    # Analizar cada combo
    combos_con_items = []
    for combo in combos:
        items = get_combo_items(combo["id"])
        combos_con_items.append(
            {**combo, "items": items, "firma": normalize_componentes(items)}
        )

    # Agrupar por componentes (firma)
    grupos_por_componentes = defaultdict(list)
    for combo in combos_con_items:
        if combo["firma"]:  # Solo si tiene componentes
            grupos_por_componentes[combo["firma"]].append(combo)

    # Encontrar combos duplicados (mismos componentes)
    print("[1] COMBOS CON MISMOS COMPONENTES (Potenciales Duplicados):\n")

    duplicados_encontrados = 0
    for firma, grupo_combos in grupos_por_componentes.items():
        if len(grupo_combos) > 1:
            duplicados_encontrados += 1

            # Obtener componentes para mostrar
            componentes = grupo_combos[0]["items"]

            print(f"ENCONTRADO: {len(grupo_combos)} combos con los MISMOS COMPONENTES")
            print("-" * 140)

            # Mostrar componentes
            if componentes:
                print("  COMPONENTES:")
                for item in componentes:
                    print(
                        f"    - {item['nombre']} (cantidad: {item['cantidad']}, medida: {item['medida']})"
                    )

            print("\n  COMBOS CON ESTOS COMPONENTES:")

            # Reunir información sobre los combos
            for combo in grupo_combos:
                tipo_combo = (
                    "COMBO" if "combo" in combo["nombre"].lower() else "CONJUNTO"
                )
                print(
                    f"    ID:{combo['id']:>4} | {tipo_combo:>7} | {combo['nombre']:<50} | Local: {combo['local']:<12} | ${combo['precio']:>10,.0f}"
                )

            # Recomendación
            nombres_unicos = list(set([c["nombre"] for c in grupo_combos]))
            print(f"\n  RECOMENDACION:")

            # Extraer la base del nombre (sin combo/conjunto)
            base_nombres = []
            for nombre in nombres_unicos:
                nombre_limpio = (
                    nombre.replace("combo", "")
                    .replace("conjunto", "")
                    .replace("set", "")
                    .strip()
                )
                base_nombres.append(nombre_limpio)

            base_unica = list(set(base_nombres))

            if len(base_unica) == 1:
                base = base_unica[0]
                print(
                    f"    -> Renombrar todos a: 'conjunto {base}' (usar nombre estándar 'conjunto')"
                )
                print(f"    -> Nombres actuales: {', '.join(nombres_unicos)}")
            else:
                print(
                    f"    -> Los nombres tienen bases diferentes. Revisar manualmente."
                )
                print(f"    -> Bases encontradas: {', '.join(base_unica)}")

            print()

    print("\n" + "=" * 140)
    print(f"[2] COMBOS SIN COMPONENTES REGISTRADOS:\n")

    sin_componentes = [c for c in combos_con_items if not c["items"]]
    if sin_componentes:
        print(f"Total: {len(sin_componentes)} combos sin componentes\n")
        for combo in sin_componentes[:20]:  # Mostrar primeros 20
            print(
                f"  ID:{combo['id']:>4} | {combo['nombre']:<50} | Local: {combo['local']:<12} | ${combo['precio']:>10,.0f}"
            )
    else:
        print("Todos los combos tienen componentes registrados.")

    print("\n" + "=" * 140)
    print(f"[3] COMPARACION DETALLADA - COMBO vs CONJUNTO (Grupo 78-79):\n")

    # Buscar combos y conjuntos que se parecen (grupo 78-79)
    sommier_combos = [
        c
        for c in combos_con_items
        if ("sommier" in c["nombre"].lower() or "conjunto" in c["nombre"].lower())
        and c["items"]
    ]

    if sommier_combos:
        # Agrupar por base de nombre
        grupos_sommier = defaultdict(list)
        for combo in sommier_combos:
            # Extraer la parte después de "combo"/"conjunto"
            nombre_base = combo["nombre"].lower()
            nombre_base = (
                nombre_base.replace("combo sommier", "")
                .replace("combo", "")
                .replace("conjunto", "")
                .strip()
            )
            grupos_sommier[nombre_base].append(combo)

        # Mostrar grupos
        for base_nombre, combos_base in grupos_sommier.items():
            if len(combos_base) > 1:
                print(
                    f"\nNOMBRE BASE: '{base_nombre}' - {len(combos_base)} variantes\n"
                )

                for combo in combos_base:
                    print(
                        f"  {'ID':>4} | {'Nombre':<40} | {'Local':<12} | {'Items'} | Precio"
                    )
                    print(
                        f"  {combo['id']:>4} | {combo['nombre']:<40} | {combo['local']:<12} | {len(combo['items'])} items | ${combo['precio']:>10,.0f}"
                    )

                    # Mostrar componentes
                    for item in combo["items"][:3]:  # Primeros 3 componentes
                        print(f"       - {item['nombre']}")
                    if len(combo["items"]) > 3:
                        print(f"       - ... y {len(combo['items']) - 3} más")

                print()

    print("=" * 140)
    print(
        f"RESUMEN: {duplicados_encontrados} grupos de combos con componentes idénticos encontrados"
    )
    print("=" * 140)


if __name__ == "__main__":
    import sqlite3

    main()
