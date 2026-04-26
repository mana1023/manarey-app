# ✅ Checklist: Sistema de Actualizaciones

## Verificación Pre-Implementación

- [ ] Versión de Python >= 3.7
- [ ] PyQt5 instalado
- [ ] Supabase configurado (SUPABASE_URL, SUPABASE_KEY)
- [ ] Tabla `updates` creada en BD
- [ ] `version.py` tiene `__version__` con versión actual

---

## Implementación en updater.py

- [x] Importado `zipfile`
- [x] Función `_get_app_dir()`
- [x] Función `_create_backup()`
- [x] Función `_restore_from_backup()`
- [x] Función `_install_update_from_zip()`
- [x] Función `_download_and_install_with_progress()`
- [x] Actualizada `_start_update_from_manifest()` para ZIP
- [x] Barra de progreso para descarga + extracción

---

## Scripts de Utilidad

- [ ] `build_release.py` - ✅ Creado
- [ ] `package_update.py` - ✅ Creado
- [ ] `deploy_update.py` - ✅ Creado
- [ ] `test_update_system.py` - ✅ Creado

## Documentación

- [ ] `GUIA_ACTUALIZACIONES_ZIP.md` - ✅ Creado
- [ ] `WORKFLOW_ACTUALIZACIONES.md` - ✅ Creado
- [ ] `GUIA_USUARIO_ACTUALIZACIONES.md` - ✅ Creado
- [ ] `QUICK_START_ACTUALIZACIONES.md` - ✅ Creado
- [ ] `RESUMEN_NUEVO_SISTEMA_ACTUALIZACIONES.md` - ✅ Creado
- [ ] `CHECKLIST_IMPLEMENTACION.md` - ✅ Este archivo

---

## Testing Inicial

### Test 1: Validar sintaxis
```bash
python -m py_compile updater.py
python -m py_compile build_release.py
python -m py_compile package_update.py
python -m py_compile deploy_update.py
```
- [ ] Sin errores

### Test 2: Validar importes
```bash
python -c "import updater; print(dir(updater))"
```
- [ ] Se ve: `_install_update_from_zip`, `_download_and_install_with_progress`, etc.

### Test 3: Test del sistema
```bash
python test_update_system.py
```
- [ ] ✓ TEST EXITOSO

### Test 4: Crear actualización real
```bash
python build_release.py --spec Manarey.spec
python package_update.py --source "C:\Temp\Manarey-1.0.5"
```
- [ ] ZIP se crea exitosamente
- [ ] ZIP contiene estructura correcta
- [ ] version.py tiene versión correcta

---

## Integración en App

### En `app.py`:
1. [ ] Importar `check_for_updates` de `updater`
2. [ ] Llamar en thread separado en `__init__`
3. [ ] Thread es daemon y no bloquea UI

### En `ui/main_window.py`:
1. [ ] Menú tiene opción "Comprobar actualizaciones"
2. [ ] Botón conecta a `check_for_updates(self)`

### En `models/update_center.py` (o equivalente):
1. [ ] Función `latest_update()` existe
2. [ ] Retorna: version, download_url, changelog, created_at, mandatory

---

## Base de Datos

```sql
-- Verificar que tabla existe
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name = 'updates';
```
- [ ] Tabla existe con columnas: version, download_url, changelog, published_at, mandatory, force_after_days

```sql
-- Verificar acceso
SELECT * FROM updates LIMIT 1;
```
- [ ] Sin errores de permisos

---

## Supabase Storage

- [ ] Bucket "releases" existe (o cuya sea el nombre)
- [ ] Configurado para acceso público (GET)
- [ ] CORS configurado si es necesario

---

## Primera Actualización (Production)

### Pre-deployment:
- [ ] `version.py` tiene versión nueva
- [ ] Changelog preparado
- [ ] ZIP se compila/empaqueta correctamente
- [ ] ZIP testeado localmente

### Deployment:
```bash
python deploy_update.py --zip Manarey-1.0.5.zip --changelog "Cambios..." --force-days 2
```
- [ ] Sin errores
- [ ] ZIP subido a Supabase
- [ ] Registro insertado en BD

### Post-deployment:
```sql
SELECT * FROM updates WHERE version = '1.0.5';
```
- [ ] Registro visible
- [ ] download_url accesible (copia en browser)
- [ ] Versión es mayor que la anterior

### User Testing:
- [ ] Usuario abre app
- [ ] Ve notificación de actualización
- [ ] Hace clic en "Instalar ahora"
- [ ] Ve barra de progreso descargando
- [ ] Ve barra de progreso instalando
- [ ] App se reinicia automáticamente
- [ ] App abre con nueva versión
- [ ] Usuario verifica: Menú → Acerca de (muestra nueva versión)

---

## Rollback (Si algo falla)

### Opción 1: Restaurar desde backup
```python
from updater import _restore_from_backup

backup = r"C:\Users\USUARIO\AppData\Local\Manarey\backups\backup_20260213_140000"
app_dir = r"C:\Path\to\app"
_restore_from_backup(backup, app_dir)
```
- [ ] App restaurada exitosamente

### Opción 2: Revertir versión en BD
```sql
-- Hacer anterior versión obligatoria
UPDATE updates SET mandatory = true WHERE version = '1.0.4';
UPDATE updates SET mandatory = false WHERE version = '1.0.5';
```
- [ ] Usuarios verán actualización a versión anterior

---

## Monitoreo Continuo

- [ ] Revisar logs regularmente: `%LOCALAPPDATA%\Manarey\logs\`
- [ ] Monitorear tabla `updates`: ¿Se actualiza correctamente?
- [ ] Backup se crean: `%LOCALAPPDATA%\Manarey\backups\`
- [ ] No hay errores recurrentes en UI

---

## Mantenimiento

### Mensual:
- [ ] Revisar backups antiguos y limpiar si es necesario
- [ ] Verificar que versiones innecesarias se eliminen de `updates`

### Con cada release:
- [ ] Actualizar `version.py`
- [ ] Generar changelog
- [ ] Compilar/empaquetar
- [ ] Testear en máquina de prueba
- [ ] Desplegar a Supabase
- [ ] Verificar que usuarios lo ven

---

## Solucionador de Problemas

### ❌ "No aparece actualización en la app"
- [ ] Verificar tabla `updates` tiene registro
- [ ] Verificar `download_url` es válida (accesible)
- [ ] Verificar nueva versión > versión actual
- [ ] Revisar logs en `%LOCALAPPDATA%\Manarey\logs\`

### ❌ "Error durante instalación"
- [ ] ZIP está corrupto: `python -m zipfile -t Manarey-X.Y.Z.zip`
- [ ] ZIP tiene estructura correcta: `python -m zipfile -l ...`
- [ ] Espacio en disco insuficiente
- [ ] Permisos de escritura en carpeta de app
- [ ] Antivirus bloqueando: desactivar temporalmente

### ❌ "App se reinicia constantemente"
- [ ] version.py en ZIP tiene versión correcta
- [ ] ZIP no está corrupto
- [ ] No hay loop infinito de actualizaciones

### ❌ "Usuarios no pueden cancelar actualización obligatoria"
- [ ] Comportamiento normal - es OBLIGATORIA
- [ ] Para cancelarla, cambiar `mandatory = false` en BD

---

## Performance & Limitaciones

- [ ] ZIP no > 500 MB (limite recomendado)
- [ ] Descarga toma ~1-5 minutos en conexión normal
- [ ] Extracción toma ~30 segundos
- [ ] Backup toma ~1-2 minutos en primer release
- [ ] Usa ~200-300 MB en disco durante extracción temporal

---

## Notas de Seguridad

- [ ] No confiar en URL del usuario (solo Supabase)
- [ ] Validar checksum de ZIP si es crítico
- [ ] Encriptar ZIP si contiene datos sensibles
- [ ] Revisar permisos de archivos después de instalar
- [ ] Logs pueden contener rutas - proteger privacidad

---

## Final Checklist

- [ ] Todo testea localmente
- [ ] Primera actualización exitosa
- [ ] Usuarios pueden verla y instalarla
- [ ] Rollback funciona si es necesario
- [ ] Documentación completa y entendible
- [ ] Script de automatización funcionan
- [ ] Sistema es estable y confiable

---

## 🎉 ¡LISTO PARA PRODUCCIÓN!

Si todos los items están checkados, tu sistema de actualizaciones está 100% listo.

**Próximos pasos:**
1. Monitorear comportamiento en primeras actualizaciones
2. Recopilar feedback de usuarios
3. Optimizar según necesidades reales
4. Considerar mejoras futuras (auto-check, delta updates, etc.)

---

**¿Necesitas ayuda?** Revisa la documentación:
- [QUICK_START_ACTUALIZACIONES.md](QUICK_START_ACTUALIZACIONES.md)
- [WORKFLOW_ACTUALIZACIONES.md](WORKFLOW_ACTUALIZACIONES.md)
- [GUIA_ACTUALIZACIONES_ZIP.md](GUIA_ACTUALIZACIONES_ZIP.md)
