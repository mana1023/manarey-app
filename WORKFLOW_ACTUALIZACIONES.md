# 🚀 Workflow Completo: Crear y Desplegar Actualizaciones

## Visión General

El nuevo sistema de actualizaciones funciona así:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Código fuente  │────▶│   Compilación   │────▶│  Archivo ZIP    │
│   actualizado   │     │   PyInstaller   │     │ automáticamente │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
                                    ┌──────────────────────────────┐
                                    │  Subir a Supabase Storage    │
                                    │  + Registrar en tabla updates│
                                    └──────────────────────────────┘
                                                         │
                                                         ▼
                                    ┌──────────────────────────────┐
                                    │  Usuario ve actualización    │
                                    │  Descarga + Instala (1 click)│
                                    └──────────────────────────────┘
```

## 🎯 Workflow Paso a Paso

### Opción A: Desde Código Compilado (Recomendado)

#### Paso 1: Actualizar versión

```bash
# Editar version.py
$version = "1.0.5"
```

Archivo: `version.py`
```python
__version__ = "1.0.5"
```

#### Paso 2: Compilar con PyInstaller

```bash
# Opción 1: Ejecutar script automático
python build_release.py --spec Manarey.spec

# Opción 2: Manual con PyInstaller
pyinstaller Manarey.spec
```

**Resultado:**
- Se crea carpeta `Manarey-1.0.5/` en la misma ubicación
- Se crea archivo `Manarey-1.0.5.zip` listo

#### Paso 3: Desplegar a Supabase

```bash
# Desplegar con ayuda:
python deploy_update.py --zip Manarey-1.0.5.zip --changelog "Bug fixes y optimizaciones" --force-days 2

# Desplegar como obligatoria (ahora mismo):
python deploy_update.py --zip Manarey-1.0.5.zip --changelog "Actualización de seguridad" --mandatory
```

**Resultado:**
- ZIP se sube a Supabase Storage
- Se registra en tabla `updates`
- Todos los usuarios verán la actualización

---

### Opción B: Desde Código Fuente (Sin compilación)

#### Paso 1: Actualizar archivos Python

```bash
# Editar archivos Python necesarios
# Por ejemplo: app.py, db.py, views/*, etc.
# IMPORTANTE: Actualizar version.py con nueva versión
```

#### Paso 2: Empaquetar archivos

```bash
# 1. Copiar archivos a carpeta temporal
mkdir C:\Temp\Manarey-1.0.5
copy *.py C:\Temp\Manarey-1.0.5
xcopy views C:\Temp\Manarey-1.0.5\views /E
xcopy models C:\Temp\Manarey-1.0.5\models /E
xcopy assets C:\Temp\Manarey-1.0.5\assets /E

# 2. Crear ZIP
python package_update.py --source C:\Temp\Manarey-1.0.5 --version 1.0.5

# Resultado: Manarey-1.0.5.zip en la carpeta actual
```

#### Paso 3: Desplegar

```bash
python deploy_update.py --zip Manarey-1.0.5.zip --changelog "Cambios importantes"
```

---

## 📋 Preparación de la Base de Datos

Antes de desplegar, asegúrate que existe la tabla:

```sql
CREATE TABLE public.updates (
  id BIGSERIAL PRIMARY KEY,
  version VARCHAR(20) NOT NULL UNIQUE,
  download_url TEXT NOT NULL,
  changelog TEXT,
  published_at TIMESTAMP DEFAULT NOW(),
  mandatory BOOLEAN DEFAULT FALSE,
  force_after_days INT DEFAULT 2,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_updates_version ON updates(version);
CREATE INDEX idx_updates_published ON updates(published_at DESC);
```

---

## 🔍 Verificar Actualización

### Desde la aplicación (usuario):
1. Abrir Manarey
2. Ir a Menú → Acerca de (verá la nueva versión disponible)
3. Hacer clic en "Comprobar actualizaciones"
4. Aceptar descargar e instalar
5. Verá barra de progreso integrada
6. App reinicia automáticamente

### Desde servidor:
```sql
-- Ver todas las actualizaciones disponibles
SELECT version, published_at, mandatory, download_url 
FROM updates 
ORDER BY published_at DESC;

-- Ver la última versión
SELECT * FROM updates 
ORDER BY published_at DESC 
LIMIT 1;

-- Activar una versión anterior
UPDATE updates SET mandatory = true WHERE version = '1.0.4';
```

---

## 🛡️ Sistema de Backups Automático

La app crea backups automáticos antes de instalar:

**Ubicación:**
```
C:\Users\[USERNAME]\AppData\Local\Manarey\backups\
```

**Estructura:**
```
backups/
├── backup_20260213_140000/
│   ├── app.py
│   ├── models/
│   └── ...
└── backup_20260213_150000/
    └── ...
```

**Restaurar desde backup (si algo falla):**
```python
from updater import _restore_from_backup

backup_path = r"C:\Users\USUARIO\AppData\Local\Manarey\backups\backup_20260213_140000"
app_dir = r"C:\Program Files\Manarey"

if _restore_from_backup(backup_path, app_dir):
    print("✓ App restaurada")
else:
    print("✗ Error restaurando")
```

---

## 🚨 Troubleshooting

### Los usuarios no ven la actualización

**Causas posibles:**
1. ❌ ZIP no está en la URL pública correcta
2. ❌ Tabla `updates` no existe
3. ❌ Versión ingresada es menor que la actual
4. ❌ `download_url` es NULL o inválida

**Solución:**
```sql
-- Verificar registro
SELECT * FROM updates WHERE version = '1.0.5';

-- Si está NULL, actualizar:
UPDATE updates SET download_url = 'https://...' WHERE version = '1.0.5';

-- Si no existe, insertar manualmente:
INSERT INTO updates (version, download_url, changelog, mandatory)
VALUES ('1.0.5', 'https://url/Manarey-1.0.5.zip', 'Cambios', false);
```

### Error "No se pudo instalar la actualización"

**Causas:**
1. ❌ ZIP corrupto
2. ❌ Falta espacio en disco
3. ❌ Permisos de escritura limitados
4. ❌ Antivirus bloqueando

**Solución:**
```bash
# 1. Verificar ZIP
python -m zipfile -e Manarey-1.0.5.zip test_extract/

# 2. Revisar logs
type "%LOCALAPPDATA%\Manarey\logs\app.log"

# 3. Restaurar desde backup
python -c "from updater import _restore_from_backup; _restore_from_backup(r'C:\...\backup_xxx', r'C:\...\app_dir')"
```

### La app se reinicia constantemente

**Causa:** ZIP tiene `version.py` con versión errada

**Solución:**
```bash
# Extraer ZIP
7z x Manarey-1.0.5.zip

# Verficar version.py en la carpeta
type Manarey-1.0.5\version.py

# Debe tener: __version__ = "1.0.5"
# Si está mal, corregrlo en la fuente y recompilar
```

---

## 📊 Monitoreo

```sql
-- Ver historial de actualizaciones
SELECT 
  version, 
  published_at, 
  mandatory,
  CASE 
    WHEN published_at > NOW() - INTERVAL '1 day' THEN 'Reciente'
    WHEN mandatory THEN 'Obligatoria'
    ELSE 'Disponible'
  END as estado
FROM updates
ORDER BY published_at DESC;

-- Ver cuántos días pasan antes de hacer obligatoria
SELECT 
  version,
  published_at,
  published_at + (force_after_days || ' days')::interval as forced_at,
  CASE 
    WHEN NOW() > published_at + (force_after_days || ' days')::interval THEN 'FORZADA'
    ELSE 'Opcional'
  END as status
FROM updates
WHERE version = '1.0.5';
```

---

## 🎬 Ejemplo Completo (5 minutos)

```bash
# 1. Actualizar versión
echo "__version__ = \"1.0.5\"" > version.py

# 2. Compilar
python build_release.py

# 3. Desplegar
python deploy_update.py --zip Manarey-1.0.5.zip --changelog "Nuevas características"

# ✓ ¡Listo! Los usuarios verán la actualización automáticamente
```

---

**¡Ya está!** Las actualizaciones ahora son simples, rápidas y seguras. 🎉
