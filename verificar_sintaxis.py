"""
Script para verificar que no haya errores de sintaxis en todos los archivos principales
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("  VERIFICACION DE SINTAXIS - ARCHIVOS PRINCIPALES")
print("=" * 70)

archivos_criticos = [
    "app.py",
    "models/queue_processor.py",
    "models/stock_model.py",
    "models/firestore_db.py",
    "views/stock_view.py",
    "views/login_view.py",
]

errores = []

for archivo in archivos_criticos:
    try:
        print(f"\nVerificando: {archivo}...", end=" ")
        with open(archivo, "r", encoding="utf-8") as f:
            codigo = f.read()
        compile(codigo, archivo, "exec")
        print("[OK]")
    except SyntaxError as e:
        print(f"[ERROR]")
        errores.append(f"{archivo}: {e}")
        print(f"  Linea {e.lineno}: {e.msg}")
    except Exception as e:
        print(f"[ERROR]")
        errores.append(f"{archivo}: {e}")

print("\n" + "=" * 70)
if errores:
    print(f"  ERRORES ENCONTRADOS: {len(errores)}")
    print("=" * 70)
    for err in errores:
        print(f"  - {err}")
else:
    print("  TODOS LOS ARCHIVOS OK - Sin errores de sintaxis")
    print("=" * 70)
    print("\nProbando importaciones...")

    try:
        print("  - Importando models.queue_processor...", end=" ")
        from models import queue_processor

        print("[OK]")
    except Exception as e:
        print(f"[ERROR]: {e}")
        errores.append(f"Import queue_processor: {e}")

    try:
        print("  - Importando models.firestore_db...", end=" ")
        from models import firestore_db

        print("[OK]")
    except Exception as e:
        print(f"[ERROR]: {e}")
        errores.append(f"Import firestore_db: {e}")

    if not errores:
        print("\n" + "=" * 70)
        print("  APLICACION LISTA PARA EJECUTAR")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print(f"  ERRORES EN IMPORTACION: {len(errores)}")
        print("=" * 70)
        sys.exit(1)

sys.exit(1 if errores else 0)
