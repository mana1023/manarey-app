#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Configurar esta PC para usar Supabase"""

import json
import os

print("=" * 60)
print("CONFIGURANDO TU PC PARA USAR SUPABASE")
print("=" * 60)
print()

# Crear carpeta de config
local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
config_dir = os.path.join(local_appdata, "Manarey")
config_path = os.path.join(config_dir, "config.json")

print(f"Carpeta de configuración: {config_dir}")

# Crear directorio si no existe
if not os.path.exists(config_dir):
    os.makedirs(config_dir)
    print("✓ Carpeta creada")
else:
    print("✓ Carpeta ya existe")

# Crear config.json
config = {
    "database_type": "postgresql",
    "database_url": "postgresql://postgres.bcdgkbptzogowbexcybn:Manarey10@aws-1-sa-east-1.pooler.supabase.com:5432/postgres",
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"✓ Archivo creado: {config_path}")
print()
print("=" * 60)
print("✅ CONFIGURACIÓN COMPLETADA")
print("=" * 60)
print()
print("Ahora:")
print("1. Cerrá Manarey si está abierto")
print("2. Volvé a abrir Manarey")
print("3. Iniciá sesión con:")
print("   Usuario: Vidriera")
print("   Contraseña: Manarey10")
print()
print("También podés usar:")
print("   • Administrador / lautaro10")
print("   • Cane / Manarey10")
print("   • Longchamps / Manarey10")
print("   • Glew / Manarey10")
print()
