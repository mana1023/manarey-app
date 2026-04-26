#!/usr/bin/env python3
"""
Analiza la base de datos para encontrar productos similares/duplicados
que podrían ser los mismos productos con nombres diferentes.
"""

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher

# Agregar el path
sys.path.insert(0, os.path.dirname(__file__))

from models import stock_model as sm
from models.db import is_postgres

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def similarity_ratio(a, b):
    """Calcula la similitud entre dos strings (0-1)."""
    a = str(a).lower().strip()
    b = str(b).lower().strip()
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def normalize_name(name):
    """Normaliza el nombre para comparación: minúsculas, espacios normalizados."""
    name = str(name).lower().strip()
    # Remover caracteres especiales comunes
    name = (
        name.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )
    name = name.replace("ñ", "n")
    # Normalizar espacios múltiples
    name = " ".join(name.split())
    return name


def get_all_products():
    """Obtiene todos los productos de la BD."""
    try:
        with sm._get_conn_cm() as conn:
            cur = conn.cursor()
            ph = "?" if isinstance(conn, sqlite3.Connection) else "%s"

            # Obtener primero todos los locales
            locales_query = "SELECT DISTINCT local FROM productos WHERE local IS NOT NULL AND local != '' ORDER BY local"
            cur.execute(locales_query)
            locales = [row[0] for row in cur.fetchall()]

            logger.info(f"Encontrados {len(locales)} locales: {locales}")

            # Obtener todos los productos
            query = """
                SELECT id, nombre, categoria, medida, estado, color, cantidad, 
                       precio_venta, local, COALESCE(fabricante, ''), COALESCE(codigo, '')
                FROM productos
                ORDER BY local, nombre
            """
            cur.execute(query)
            rows = cur.fetchall()

            products = []
            for row in rows:
                products.append(
                    {
                        "id": row[0],
                        "nombre": row[1],
                        "categoria": row[2],
                        "medida": row[3],
                        "estado": row[4],
                        "color": row[5],
                        "cantidad": row[6],
                        "precio_venta": row[7],
                        "local": row[8],
                        "fabricante": row[9],
                        "codigo": row[10],
                    }
                )

            return products
    except Exception as e:
        logger.error(f"Error obteniendo productos: {e}")
        import traceback

        traceback.print_exc()
        return []


def find_similar_products(products, threshold=0.75):
    """
    Encuentra grupos de productos similares basado en nombre.

    threshold: 0-1, umbral mínimo de similitud (0.75 = 75% similar)
    """
    grouped = defaultdict(list)
    processed = set()
    groups = []

    logger.info(f"Analizando {len(products)} productos...")

    for i, prod1 in enumerate(products):
        if i in processed:
            continue

        group = [prod1]
        processed.add(i)

        # Buscar similares
        for j in range(i + 1, len(products)):
            if j in processed:
                continue

            prod2 = products[j]

            # Calcula similitud de nombre
            similarity = similarity_ratio(prod1["nombre"], prod2["nombre"])

            # También considera si tienen la misma categoría (más confianza en duplicado)
            same_category = (
                prod1.get("categoria", "").lower().strip()
                == prod2.get("categoria", "").lower().strip()
            )

            # Si son muy similares en nombre, o si son similares y de la misma categoría
            should_group = (similarity >= threshold) or (
                similarity >= 0.70 and same_category and similarity >= 0.65
            )

            if should_group:
                group.append(prod2)
                processed.add(j)

        # Solo agregar grupos con más de 1 producto
        if len(group) > 1:
            groups.append(group)

    return groups


def analyze_group(group):
    """Analiza un grupo de productos similares y retorna estadísticas."""
    stats = {
        "team_size": len(group),
        "nombres": list(set([p["nombre"] for p in group])),
        "categorias": list(set([p.get("categoria", "N/A") for p in group])),
        "locales": list(set([p.get("local", "N/A") for p in group])),
        "cantidad_total": sum([p.get("cantidad", 0) for p in group]),
        "precios": list(set([p.get("precio_venta", 0) for p in group])),
        "fabricantes": list(
            set([p.get("fabricante", "") for p in group if p.get("fabricante", "")])
        ),
        "productos": group,
    }
    return stats


def generar_reporte(groups, output_file="analisis_duplicados.json"):
    """Genera un reporte detallado de productos potencialmente duplicados."""
    logger.info(f"\nEncontrados {len(groups)} grupos de productos similares")

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_grupos": len(groups),
        "grupos": [],
    }

    for idx, group in enumerate(groups, 1):
        stats = analyze_group(group)

        # Crear datos para reporte
        grupo_data = {
            "grupo_id": idx,
            "cantidad_productos": stats["team_size"],
            "nombres_diferentes": stats["nombres"],
            "categorias": stats["categorias"],
            "locales": stats["locales"],
            "cantidad_total": stats["cantidad_total"],
            "precios_distintos": len(stats["precios"]),
            "fabricantes": stats["fabricantes"],
            "productos_detalle": [],
        }

        # Agregar detalles de cada producto
        for prod in stats["productos"]:
            grupo_data["productos_detalle"].append(
                {
                    "id": prod["id"],
                    "nombre": prod["nombre"],
                    "categoria": prod.get("categoria", ""),
                    "local": prod.get("local", ""),
                    "medida": prod.get("medida", ""),
                    "estado": prod.get("estado", ""),
                    "color": prod.get("color", ""),
                    "cantidad": prod.get("cantidad", 0),
                    "precio": prod.get("precio_venta", 0),
                    "fabricante": prod.get("fabricante", ""),
                    "codigo": prod.get("codigo", ""),
                }
            )

        report["grupos"].append(grupo_data)

    # Guardar reporte
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Reporte guardado en: {output_file}")
    except Exception as e:
        logger.error(f"Error guardando reporte: {e}")

    return report


def imprimir_grupos(groups):
    """Imprime los grupos encontrados de forma legible."""
    print("\n" + "=" * 100)
    print("ANALISIS DE PRODUCTOS DUPLICADOS/SIMILARES")
    print("=" * 100 + "\n")

    for idx, group in enumerate(groups, 1):
        stats = analyze_group(group)

        print(f"\n[GRUPO {idx}] - {len(group)} productos similares")
        print("-" * 100)

        print(f"  Nombres encontrados:")
        for nombre in stats["nombres"]:
            print(f"    * {nombre}")

        print(f"\n  Categorias: {', '.join([str(c) for c in stats['categorias']])}")
        print(f"  Locales: {', '.join([str(l) for l in stats['locales']])}")
        print(f"  Cantidad total en stock: {stats['cantidad_total']} unidades")
        print(f"  Precios diferentes: {len(stats['precios'])}")
        if stats["precios"]:
            print(f"    * ${min(stats['precios'])}-${max(stats['precios'])}")

        if stats["fabricantes"]:
            print(f"  Fabricantes: {', '.join(stats['fabricantes'])}")

        print(f"\n  Detalle de productos:")
        for prod in stats["productos"]:
            print(
                f"    ID:{prod['id']:5} | {prod['nombre']:<40} | Local: {prod['local']:<15} | Stock: {prod['cantidad']:>4} | ${prod['precio_venta']}"
            )


def main():
    logger.info("Iniciando análisis de duplicados...")

    # Obtener todos los productos
    products = get_all_products()

    if not products:
        logger.error("No se pudieron obtener los productos")
        return

    logger.info(f"Total de productos cargados: {len(products)}")

    # Buscar similares (umbral 75%)
    groups = find_similar_products(products, threshold=0.72)

    # Imprimir grupos
    imprimir_grupos(groups)

    # Generar reporte JSON
    report = generar_reporte(groups, "ANALISIS_DUPLICADOS.json")

    print("\n" + "=" * 100)
    print(f"✅ Análisis completado: {len(groups)} grupos encontrados")
    print("=" * 100)


if __name__ == "__main__":
    import sqlite3

    main()
