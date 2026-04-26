# 🎯 Quick Start: Sistema de Actualizaciones ZIP

## Instalación Rápida (5 minutos)

### 1️⃣ Preparar base de datos

Ejecuta este SQL en tu Supabase:

```sql
CREATE TABLE public.updates (
  id BIGSERIAL PRIMARY KEY,
  version VARCHAR(20) NOT NULL UNIQUE,
  download_url TEXT NOT NULL,
  changelog TEXT,
  published_at TIMESTAMP DEFAULT NOW(),
  mandatory BOOLEAN DEFAULT FALSE,
  force_after_days INT DEFAULT 2,
  created_at TIMESTAMP DEFAULT NOW()
) WITH (oids = false);

CREATE INDEX idx_updates_version ON updates(version DESC);
CREATE INDEX idx_updates_published ON updates(published_at DESC);

-- (Opcional) Dar permisos
ALTER TABLE updates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anyone can read updates" ON updates FOR SELECT USING (true);
```

### 2️⃣ Verificar que el código está actualizado

```bash
# Verificar que updater.py tiene las funciones nuevas:
# - _get_app_dir()
# - _create_backup()
# - _install_update_from_zip()
# - _download_and_install_with_progress()

grep "_install_update_from_zip" updater.py
# Debe mostrar: def _install_update_from_zip
```

### 3️⃣ Crear primera actualización

```bash
# Opción A: Si tienes compilación PyInstaller
python build_release.py --spec Manarey.spec

# Opción B: Si es solo código Python
python package_update.py --source "C:\Ruta\Manarey-1.0.5" --version "1.0.5"
```

### 4️⃣ Desplegar

```bash
python deploy_update.py --zip Manarey-1.0.5.zip --changelog "Primera actualización"
```

¡**Listo!** 🎉

---

## Archivos Nuevos

| Archivo | Propósito |
|---------|-----------|
| `updater.py` | ✅ Actualizado - Sistema ZIP integrado |
| `build_release.py` | 🆕 Compilar y empaquetar automáticamente |
| `package_update.py` | 🆕 Empaquetar archivos Python |
| `deploy_update.py` | 🆕 Subir a Supabase + registrar BD |
| `GUIA_ACTUALIZACIONES_ZIP.md` | 📖 Guía técnica completa |
| `WORKFLOW_ACTUALIZACIONES.md` | 📖 Workflow paso a paso |
| `GUIA_USUARIO_ACTUALIZACIONES.md` | 📖 Instrucciones para usuarios |
| `QUICK_START_ACTUALIZACIONES.md` | 📖 Este archivo |

---

## Verificación

Para verificar que todo está funcionando:

1. **En app.py**, importar en `check_for_updates()`:
```python
from updater import check_for_updates
```

2. **En menú**, agregar botón:
```python
menu.addAction("Comprobar actualizaciones", lambda: check_for_updates(self))
```

3. **Testear localmente:**
```python
# En una terminal
python
>>> from updater import _install_update_from_zip
>>> _install_update_from_zip("C:\Temp\Manarey-1.0.5.zip")
True  # Éxito
```

---

## Comandos Útiles

```bash
# Ver versión actual
python -c "from version import __version__; print(__version__)"

# Validar ZIP
python -m zipfile -l Manarey-1.0.5.zip

# Extraer ZIP para verificar
python -m zipfile -e Manarey-1.0.5.zip extracted/

# Listar backups
dir "%LOCALAPPDATA%\Manarey\backups"

# Ver logs
type "%LOCALAPPDATA%\Manarey\logs\app.log"
```

---

## Próximos Pasos

1. ✅ Base de datos configurada
2. ✅ Archivos descargados
3. ⬜ **Cambiar servidor para usar ZIP en lugar de EXE** (si aplica)
4. ⬜ Crear primera actualización
5. ⬜ Probar con usuario beta
6. ⬜ Desplegar versión final

---

## Soporte

**Documentación completa:**
- [GUIA_ACTUALIZACIONES_ZIP.md](GUIA_ACTUALIZACIONES_ZIP.md)
- [WORKFLOW_ACTUALIZACIONES.md](WORKFLOW_ACTUALIZACIONES.md)
- [GUIA_USUARIO_ACTUALIZACIONES.md](GUIA_USUARIO_ACTUALIZACIONES.md)

**¿Te atascas?** Revisa la sección "Troubleshooting" en WORKFLOW_ACTUALIZACIONES.md

---

**Sistema de actualizaciones moderno, automático y seguro. ✨**
