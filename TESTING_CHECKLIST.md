# ✅ Checklist de Verificación del Sistema de Actualizaciones

## 1️⃣ Verificar Configuración

### GitHub Credentials
```powershell
# Abrir PowerShell en el directorio del proyecto
cd c:\Users\USUARIO\Desktop\Manarey

# Configurar credenciales
$env:GITHUB_REPO = "mana1023/manarey-updates"    # Reemplaza con tu repo
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxx"           # Reemplaza con tu token

# Verificar que se configuraron
Write-Host "Repo: $env:GITHUB_REPO"
Write-Host "Token: $($env:GITHUB_TOKEN.Substring(0,10))..."
```

### Verificar JSON (opcional - alternativa a env vars)
```powershell
# Si prefieres usar config.json en lugar de variables de entorno:
$json = @{
    GITHUB_REPO = "mana1023/manarey-updates"
    GITHUB_TOKEN = "ghp_xxxxxxxxxxxxx"
} | ConvertTo-Json

$json | Out-File -FilePath "config.json" -Encoding UTF8
```

---

## 2️⃣ Probar Publicación en GitHub

### Prerequisitos
- PowerShell en el directorio del proyecto
- `requests` instalado: `pip install requests`
- Credenciales GitHub configuradas (paso 1)
- Un archivo ZIP de prueba

### Crear archivo ZIP de prueba
```powershell
# Desde PowerShell:
$testDir = "test_release"
New-Item -ItemType Directory -Path $testDir -Force | Out-Null
Set-Content -Path "$testDir\README.txt" -Value "Test release v1.0.0"
Compress-Archive -Path $testDir -DestinationPath "Manarey-1.0.0.zip"
```

### Publicar en GitHub
```powershell
# Opción A: Usar script PowerShell
.\publish_release.ps1 -Version "1.0.0" -ZipFile "Manarey-1.0.0.zip"

# Opción B: Usar Python directo
python publish_github_release.py --version 1.0.0 --file Manarey-1.0.0.zip

# Resultado esperado:
# ✓ Release publicada exitosamente!
# Versión: 1.0.0
# URL: https://github.com/tu_usuario/tu_repo/releases/tag/v1.0.0
```

### Verificar en GitHub
1. Ir a: `https://github.com/mana1023/manarey-updates/releases`
2. Debe aparecer el release `v1.0.0` con el archivo adjunto
3. Descargar el ZIP para verificar integridad

---

## 3️⃣ Probar Detección en la Aplicación

### Opción A: Verificación Automática (recomendado)

```powershell
# Configurar versión actual de la app
# 1. Editar version.py y cambiar VERSION a menor que 1.0.0
#    Por ejemplo: VERSION = "0.9.9"

# 2. Ejecutar la aplicación
python app.py

# 3. La aplicación debería:
#    - Iniciar normalmente
#    - Mostrar diálogo dorado "Nueva versión disponible" dentro de 2-3 segundos
#    - Mostrar changelog de GitHub
#    - Botones: "Instalar Ahora" y "Más Tarde"
```

### Opción B: Verificación Manual

```powershell
# En la aplicación, hacer clic en:
# Menú → "🔄 Comprobar Actualizaciones"

# Resultado esperado:
# - Mismo diálogo que en Opción A
# - Si no hay actualización: mensaje "Ya estás en la última versión"
```

---

## 4️⃣ Probar Instalación

⚠️ **IMPORTANTE**: Hacer backup antes de este paso

```powershell
# 1. En el diálogo "Nueva versión disponible"
# 2. Clic en "Instalar Ahora"

# 3. La aplicación debe:
#    ✓ Mostrar diálogo "Descargando y instalando..."
#    ✓ Barra de progreso dorada
#    ✓ Crear respaldo de archivos actuales
#    ✓ Descargar ZIP desde GitHub
#    ✓ Extraer archivos en el lugar correcto
#    ✓ Cerrar la aplicación
#    ✓ Reiniciar automáticamente

# 4. Verificar que la app reinició con nueva versión:
# Menú → About → Verificar versión es 1.0.0
```

---

## 5️⃣ Probar Restauración en Caso de Error

### Simular error de instalación

```powershell
# 1. Crear un ZIP corrupto de prueba:
$corruptZip = "Manarey-CORRUPT-1.0.1.zip"
"CORRUPTED DATA" | Out-File -FilePath $corruptZip -Encoding ASCII

# 2. Publicarlo:
python publish_github_release.py --version 1.0.1 --file $corruptZip

# 3. En la app: "Comprobar Actualizaciones"

# 4. Intentar instalar:
# - Debe fallar al extraer (JSON parse error o ZIP error)
# - La app debe restaurar automáticamente
# - Versión debe volver a la anterior
# - Ver logs: type logs\update_*.log
```

---

## 6️⃣ Probar Actualización Obligatoria

### Publicar release obligatoria

```powershell
# Publicar como major release (fuerza obligatoria después de N días)
python publish_github_release.py --version 2.0.0 --file Manarey-2.0.0.zip --mandatory

# O editar tag en GitHub: Marcar "Pre-release" en GitHub para hacer opcional temporalmente
```

### Verificar comportamiento

```powershell
# Si es obligatoria:
# - Usuario VE: "⚠️ ACTUALIZACIÓN OBLIGATORIA"
# - Si elige "Más Tarde": la app se cierra (fuerza actualización)
# - Sin opción de esperar

# Si es opcional con fecha límite:
# - Usuario VE: "⏰ Tienes X días antes de ser obligatoria"
# - Puede elegir "Más Tarde"
# - Después de X días: pasa a obligatoria
```

---

## 7️⃣ Verificar Logs

```powershell
# Ver logs de actualización:
Get-Content "logs\update_*.log" | Select-Object -Last 50

# O en PowerShell:
tail -f logs\update_*.log
```

**Expected log entries:**
```
[DEBUG] Buscando actualizaciones...
[DEBUG] Conectando a GitHub...
[INFO] Nueva versión disponible: 1.0.0
[DEBUG] Descargando desde: https://github.com/.../Manarey-1.0.0.zip
[DEBUG] Creando backup en: C:\Users\...\update_backup_20240115_103020.zip
[DEBUG] Extrayendo archivos...
[INFO] Actualización completada. Reiniciando...
```

---

## 8️⃣ Probar Fallback a Supabase (si existe)

Si tienes Supabase configurado:

```powershell
# 1. Deshabilitar GitHub (simular que no está disponible):
$env:GITHUB_REPO = ""
$env:GITHUB_TOKEN = ""

# 2. Ejecutar la app
python app.py

# 3. Hacer clic en "Comprobar Actualizaciones"

# 4. Resultado esperado:
#    - Si no hay GitHub, intenta Supabase
#    - Si tiene registro en Supabase: lo muestra
#    - Si no: "Ya estás en la última versión"

# 5. Restaurar variables:
$env:GITHUB_REPO = "mana1023/manarey-updates"
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxx"
```

---

## ✅ Checklist Final

| Ítem | ✓ | Notas |
|---|---|---|
| Credenciales GitHub configuradas | ⬜ | |
| Archivo ZIP creado | ⬜ | |
| Release publicado en GitHub | ⬜ | |
| Descarga manual desde GitHub OK | ⬜ | |
| App detecta automáticamente | ⬜ | |
| Diálogo aparece con estilos | ⬜ | |
| Usuario puede elegir "Instalar Ahora" | ⬜ | |
| Instalación completa | ⬜ | |
| App reinicia automáticamente | ⬜ | |
| Nueva versión se muestra correctamente | ⬜ | |
| Respaldo se crea correctamente | ⬜ | |
| Restauración funciona en caso de error | ⬜ | |
| Logs muestran progreso | ⬜ | |
| Fallback a Supabase funciona | ⬜ | |

---

## 🐛 Troubleshooting Rápido

| Problema | Solución |
|---|---|
| "GITHUB_REPO no configurado" | Ejecutar: `$env:GITHUB_REPO = "tu_usuario/tu_repo"` |
| "Error 404 al descargar" | Verificar que el ZIP está en GitHub Releases y es público (o token válido) |
| "Python: No module named 'requests'" | Ejecutar: `pip install requests` |
| "App no detecta actualización" | Ver `logs/update_*.log` para detalles del error |
| "Dialogo no aparece" | Ver que PyQt5 esté instalado y sin errores |
| "Restauración no funciona" | Verificar que hay espacio disponible, logs en carpeta `update_backup_*` |
| "Versión no se actualiza" | Editar `version.py` y cambiar VERSION manualmente después de instalar |

---

## 📞 Información Relevante

- **Docs completa**: Ver `GITHUB_RELEASES_WORKFLOW.md`
- **Quick start**: Ver `QUICK_START_GITHUB_RELEASES.md`
- **Scripts creados**:
  - `publish_github_release.py` - Python puro
  - `publish_release.ps1` - PowerShell wrapper
- **Archivos modificados**:
  - `updater.py` - Ahora soporta GitHub
  - `app.py` - Auto-check en background
  - `ui/menu_window.py` - Botón "Comprobar Actualizaciones"
  - `ui/ui_update_dialog.py` - Diálogos profesionales

