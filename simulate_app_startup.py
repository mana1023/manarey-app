#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIMULACIÓN: Tu app 1.0.23 abriendo la primera vez
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import updater

# Simular que tu app dice:
print("🚀 Manarey v1.0.23 iniciando...")
print(
    "Que tengas un gran día de ventas. Si veas una actualización, instala para mantener Manarey al día.\n"
)

time.sleep(2)

print("=" * 70)
print("🔄 VERIFICANDO ACTUALIZACIONES EN BACKGROUND (2 SEGUNDOS DESPUÉS)...")
print("=" * 70)

# Obtener versión actual
current_version = updater.get_current_version()
print(f"\nVersión actual: {current_version}")

# Obtener última de GitHub
manifest = updater._get_latest_release_from_github()

if manifest:
    new_version = manifest.get("version")
    current_tuple = updater._parse_version(current_version)
    new_tuple = updater._parse_version(new_version)

    print(f"Versión en GitHub: {new_version}")

    if new_tuple > current_tuple:
        print(f"\n✅ ¡ACTUALIZACIÓN DISPONIBLE: v{new_version}!")
        print(f"\nNOTAS DE VERSIÓN:")
        print(f"{manifest.get('notes', 'N/A')}")
        print(f"\n🎯 La app mostraría el DIÁLOGO DORADO aquí ahora")
        print(f"   Con botones: [Instalar Ahora] [Más Tarde]")
    else:
        print("\n✓ Estás al día")
else:
    print("\n❌ No se pudo conectar a GitHub")

print("\n" + "=" * 70)
