# Instalador oficial de Manarey

Este directorio contiene el script para generar un ejecutable de Manarey tal como se usa en este proyecto.

## Requisitos previos
- Windows con PowerShell.
- Python 3.11+ instalado y en PATH.
- Acceso a internet para descargar dependencias.
- Archivo `.dburl` y `config.json` configurados como en tu entorno actual (se copian al bundle).

## Pasos rápidos
1. Abrí PowerShell en la raíz del proyecto (`C:\Users\USUARIO\Desktop\Manarey`).
2. Ejecutá:
   ```powershell
   .\Oficial\build_installer.ps1
   ```
   Para limpiar y reconstruir todo:
   ```powershell
   .\Oficial\build_installer.ps1 -Clean
   ```
3. El ejecutable queda en `dist\Manarey.exe` (single file).

## Qué hace el script
- Crea un entorno virtual aislado en `Oficial/.venv_inst`.
- Instala dependencias desde `requirements.txt`.
- Empaqueta la app con PyInstaller, incluyendo carpetas `assets`, `views`, `models`, `utils`, `workers`, `ui`, y archivos de configuración (`config.py`, `config.json`, `.dburl`).
- Copia `config.json` y `.dburl` al bundle final.

## Notas sobre la base de datos
- `.dburl` define la conexión (SQLite o Postgres). Se copia tal cual al ejecutable.
- Si usás SQLite local, asegurate de que el archivo de base esté accesible según la ruta en `.dburl`.
- Si usás Postgres, las credenciales/host deben estar en `.dburl` o en `config.py`.

## Dependencias
- PyQt5 y demás paquetes declarados en `requirements.txt`.

## Problemas frecuentes
- **No encuentra PyInstaller**: el script lo instala dentro del venv al correr `pip install -r requirements.txt`. Si falta, agrega `pyinstaller` al archivo `requirements.txt`.
- **Faltan assets**: verificá que las carpetas indicadas existan y que los paths de `--add-data` sean correctos.
