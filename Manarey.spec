# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('PyQt5')
hiddenimports += collect_submodules('models')
hiddenimports += collect_submodules('views')
hiddenimports += collect_submodules('utils')


a = Analysis(
    ['C:\\Users\\USUARIO\\Desktop\\Manarey\\app.py'],
    pathex=['C:\\Users\\USUARIO\\Desktop\\Manarey'],
    binaries=[('C:\\Users\\USUARIO\\Desktop\\Manarey\\Oficial\\.venv_inst\\Lib\\site-packages\\psycopg2_binary.libs\\libpq-2d95d8c8be26654a630220107eb268e7.dll', '.'), ('C:\\Users\\USUARIO\\Desktop\\Manarey\\Oficial\\.venv_inst\\Lib\\site-packages\\psycopg2_binary.libs\\libpq.dll', '.')],
    datas=[('C:\\Users\\USUARIO\\Desktop\\Manarey\\assets', 'assets'), ('C:\\Users\\USUARIO\\Desktop\\Manarey\\views', 'views'), ('C:\\Users\\USUARIO\\Desktop\\Manarey\\models', 'models'), ('C:\\Users\\USUARIO\\Desktop\\Manarey\\utils', 'utils'), ('C:\\Users\\USUARIO\\Desktop\\Manarey\\workers', 'workers'), ('C:\\Users\\USUARIO\\Desktop\\Manarey\\ui', 'ui'), ('C:\\Users\\USUARIO\\Desktop\\Manarey\\config.py', '.'), ('C:\\Users\\USUARIO\\Desktop\\Manarey\\config.json', '.'), ('C:\\Users\\USUARIO\\Desktop\\Manarey\\updater.py', '.')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Manarey',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\USUARIO\\Desktop\\Manarey\\assets\\images\\logo_manarey.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Manarey',
)
