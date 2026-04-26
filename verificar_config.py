#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verificar configuración actual"""

import json
import os
import sys

print("=" * 60)
print("VERIFICACIÓN DE CONFIGURACIÓN")
print("=" * 60)
print()

# 1. Verificar config.json en proyecto
config_proyecto = os.path.join(os.path.dirname(__file__), "config.json")
print(f"1. Config en proyecto: {config_proyecto}")
if os.path.exists(config_proyecto):
    with open(config_proyecto, "r") as f:
        config = json.load(f)
    print(f"   ✓ Existe")
    print(f"   Tipo: {config.get('database_type')}")
    print(f"   URL: {config.get('database_url')[:50]}...")
else:
    print(f"   ✗ No existe")

print()

# 2. Verificar config.json en LOCALAPPDATA
local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
config_appdata = os.path.join(local_appdata, "Manarey", "config.json")
print(f"2. Config en AppData: {config_appdata}")
if os.path.exists(config_appdata):
    with open(config_appdata, "r") as f:
        config = json.load(f)
    print(f"   ✓ Existe")
    print(f"   Tipo: {config.get('database_type')}")
    print(f"   URL: {config.get('database_url')[:50]}...")
else:
    print(f"   ✗ No existe")

print()

# 3. Verificar DATABASE_URL en environment
print(f"3. Variable de entorno DATABASE_URL:")
db_url = os.environ.get("DATABASE_URL", "")
if db_url:
    print(f"   ✓ Configurada: {db_url[:50]}...")
else:
    print(f"   ✗ No configurada")

print()

# 4. Simular carga de config como lo hace app.py
print("4. Simulando carga de configuración...")
if getattr(sys, "frozen", False):
    config_path = config_appdata
    print(f"   App empaquetada → usar: {config_path}")
else:
    config_path = config_proyecto
    print(f"   Desarrollo → usar: {config_path}")

if os.path.exists(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)
    if config.get("database_type") == "postgresql" and config.get("database_url"):
        print(f"   ✓ PostgreSQL configurado")
        print(f"   ✓ DATABASE_URL se establecería correctamente")
    else:
        print(f"   ✗ No está configurado para PostgreSQL")
else:
    print(f"   ✗ Config no encontrado")

print()

# 5. Verificar si models.db puede conectar a Supabase
print("5. Probando conexión a Supabase...")
try:
    # Establecer DATABASE_URL manualmente
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
        if config.get("database_type") == "postgresql":
            os.environ["DATABASE_URL"] = config.get("database_url")

    from models.db import IS_POSTGRES, is_postgres

    if IS_POSTGRES or is_postgres():
        print(f"   ✓ models.db detectó PostgreSQL")
        print(f"   ✓ App usará Supabase")
    else:
        print(f"   ✗ models.db NO detectó PostgreSQL")
        print(f"   ✗ App usará SQLite local")
except Exception as e:
    print(f"   ✗ Error: {e}")

print()
print("=" * 60)
print("CONCLUSIÓN")
print("=" * 60)
print()

if IS_POSTGRES if "IS_POSTGRES" in locals() else False:
    print("✅ TODO CORRECTO - Manarey usará Supabase")
    print()
    print("Si aún no podés iniciar sesión:")
    print("1. Cerrá completamente Manarey")
    print("2. Volvé a abrirlo")
    print("3. Intentá con: Vidriera / Manarey10")
else:
    print("❌ PROBLEMA DETECTADO - Manarey NO usará Supabase")
    print()
    print("Posibles causas:")
    print("• psycopg2 no está instalado")
    print("• config.json no se carga correctamente")
    print("• Manarey ya está abierto (cerralo y volvé a abrir)")

print()
