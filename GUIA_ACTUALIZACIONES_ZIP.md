# Guía: Sistema de Actualizaciones en Formato ZIP

## ¿Qué cambió?

El sistema de actualizaciones ha sido modernizado. Ahora:

✅ **Las actualizaciones se descargan directamente en la app**  
✅ **Extrae e instala automáticamente SIN ejecutar instaladores externos**  
✅ **Muestra barra de progreso integrada en la interfaz**  
✅ **Crea backups automáticos antes de instalar**  
✅ **Reinicia automáticamente después de la instalación**  

## Formato del Archivo ZIP

### Estructura recomendada:

```
Manarey-1.0.5.zip
├── Manarey-1.0.5/
│   ├── app.py
│   ├── db.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── ...
│   ├── ui/
│   │   ├── main_window.py
│   │   └── ...
│   ├── utils/
│   │   └── ...
│   ├── assets/
│   │   └── images/
│   └── version.py (IMPORTANTE: con __version__ = "1.0.5")
```

### Lo que NO debe incluirse:

- ❌ `__pycache__/`
- ❌ `*.pyc`
- ❌ `logs/` (se preservan)
- ❌ `user_prefs.json` (se preserva)
- ❌ `config.json` (se preserva)
- ❌ `.git/`
- ❌ `.env`

## Cómo Preparar una Actualización

### Opción 1: Desde compilación PyInstaller

```bash
# 1. Compilar la actualización
pyinstaller Manarey.spec

# 2. Copiar carpeta dist/Manarey a una carpeta temporal
# Por ejemplo: C:\Temp\Manarey-1.0.5

# 3. Renombrar la carpeta a coincida con versión
# Manarey-1.0.5

# 4. Crear ZIP
# - Meter la carpeta Manarey-1.0.5 DENTRO del ZIP
# - NO el contenido directamente

# Usando PowerShell:
Compress-Archive -Path "C:\Temp\Manarey-1.0.5" -DestinationPath "Manarey-1.0.5.zip"
```

### Opción 2: Desde código fuente

```bash
# 1. Copiar archivos .py actualizados a una carpeta
# C:\Temp\Manarey-1.0.5

# 2. Asegurarse que version.py tenga la versión correcta
# __version__ = "1.0.5"

# 3. Crear ZIP preservando la estructura:
# Comprimir solo los archivos que cambiaron (Python, UI, etc.)
# Excluir: __pycache__, logs, user_prefs.json, config.json

# Usando PowerShell:
Compress-Archive -Path "C:\Temp\Manarey-1.0.5" -DestinationPath "Manarey-1.0.5.zip"
```

## Subir la Actualización a Supabase

1. **Subir el archivo ZIP** a tu storage Supabase
2. **Registrar en la BD** con:
   - `version`: "1.0.5"
   - `download_url`: URL pública del ZIP en Supabase
   - `changelog`: "Cambios y mejoras..."
   - `published_at`: fecha actual
   - `mandatory`: true/false (si es obligatoria)
   - `force_after_days`: 2 (días antes de forzar instalación)

### SQL para registrar:

```sql
INSERT INTO updates (version, download_url, changelog, published_at, mandatory, force_after_days)
VALUES (
  '1.0.5',
  'https://tu-proyecto.supabase.co/storage/v1/object/public/releases/Manarey-1.0.5.zip',
  'Bug fixes y optimizaciones',
  NOW(),
  false,
  2
);
```

## Qué Sucede Durante la Actualización

1. **Descarga**: El usuario verá barra de progreso "Descargando... X%"
2. **Extracción**: El usuario verá "Instalando... X% (Y de Z archivos)"
3. **Backup**: Se crea un backup automático en:
   - `C:\Users\[USERNAME]\AppData\Local\Manarey\backups\backup_YYYYMMDD_HHMMSS`
4. **Instalación**: Los archivos se extraen a la carpeta de la app
5. **Reinicio**: La app se reinicia automáticamente
6. **Rollback**: Si algo falla, se restaura automáticamente desde el backup

## Verificar Versión Instalada

En la app, puedes verificar la versión actual en:
- Menú → Acerca de
- O en código: `from version import __version__`

## Solución de Problemas

### La actualización no aparece

- Verificar que `mandatory=false` o que pasaron los días para hacerla obligatoria
- Revisar que `version` en el ZIP sea mayor a la versión actual
- Confirmar que la URL en Supabase es accesible

### Error durante instalación

- Revisar logs en: `C:\Users\[USERNAME]\AppData\Local\Manarey\`
- Que el ZIP tenga la estructura correcta con carpeta raíz
- Que `version.py` esté actualizado

### Restaurar desde backup

```python
from updater import _restore_from_backup
backup_path = r"C:\Users\[USERNAME]\AppData\Local\Manarey\backups\backup_20260213_140000"
app_dir = r"C:\Program Files\Manarey"
_restore_from_backup(backup_path, app_dir)
```

## Testing Local

Para probar sin actualizar a Supabase:

```python
from updater import _install_update_from_zip

zip_path = r"C:\Path\to\Manarey-1.0.5.zip"
success = _install_update_from_zip(zip_path)
print(f"Instalación: {'Exitosa' if success else 'Falló'}")
```

---

**¡Listo!** El sistema de actualizaciones ahora es moderno, seguro y amigable con el usuario. 🚀
