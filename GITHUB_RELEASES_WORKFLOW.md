# 📦 Sistema de Actualizaciones con GitHub Releases

## Resumen

La aplicación Manarey se actualiza **automáticamente** descargando releases desde GitHub. El sistema es completamente integrado en la aplicación sin necesidad de instaladores externos.

---

## ⚙️ Configuración

### 1. Variables de Entorno

Establece estas variables en tu máquina de compilación:

```powershell
# PowerShell
$env:GITHUB_REPO = "usuario/repo"           # Tu repositorio GitHub
$env:GITHUB_TOKEN = "your_github_token"     # Token de acceso personal
```

O en `config.json`:

```json
{
  "GITHUB_REPO": "usuario/repo",
  "GITHUB_TOKEN": "your_github_token"
}
```

### 2. Crear Token de Acceso

1. GitHub → Settings → Developer settings → Personal access tokens
2. "Generate new token (classic)"
3. Permisos necesarios: `repo` (acceso completo a repositorios)
4. Copiar token y guardar como variable de entorno

---

## 📤 Flujo de Publicación

### Opción A: Usando PowerShell (Recomendado)

Tu script `actualizacion.ps1` probablemente ya hace esto:

```powershell
# 1. Compilar aplicación
& ".\build.ps1"

# 2. Crear ZIP
$version = "1.0.5"
$zip_file = "Manarey-$version.zip"
Compress-Archive -Path "./dist/*" -DestinationPath $zip_file

# 3. Publicar en GitHub
python publish_github_release.py --version $version --file $zip_file --changelog "Nuevas características y correcciones"
```

### Opción B: Usando Python directamente

```bash
python publish_github_release.py --version 1.0.5 --file Manarey-1.0.5.zip
```

### Opción C: Con actualización obligatoria

```bash
python publish_github_release.py --version 1.0.5 --file Manarey-1.0.5.zip --mandatory
```

---

## 🔍 Detectar Actualizaciones (En la Aplicación)

La aplicación automáticamente:

1. **Al iniciar**: Verifica en background si hay nueva versión
2. **Manualmente**: Usuario puede hacer clic en "🔄 Comprobar Actualizaciones"

### Flujo Automático

```
App inicia
  ↓
Thread daemon verifica GitHub
  ↓
Si hay versión nueva: Muestra DialogoActualizacion (styled)
  ↓
Usuario elige: "Instalar Ahora" o "Más Tarde"
  ↓
Si instala: DialogoProgreso con barra dorada
  ↓
Descarga ZIP → Crea backup → Extrae archivos → Reinicia app
```

### Comparación de Versiones

El sistema utiliza comparación semántica:
- `1.0.5` < `1.0.10` < `1.1.0` < `2.0.0`

---

## 📋 Formato de Release en GitHub

Cada release debe tener:

```
Tag:     v1.0.5
Nombre:  Manarey 1.0.5
Descripción:
  Nuevas características:
  - Feature 1
  - Feature 2
  
  Correcciones:
  - Bug 1
  - Bug 2
  
Asset:   Manarey-1.0.5.zip (requerido)
```

El archivo ZIP debe contener la estructura compilada de la aplicación.

---

## 🔄 Sistema de Respaldo

Antes de instalar una actualización:

1. Crea backup de archivos actuales
2. Extrae versión nueva
3. Si hay error: Restaura automáticamente
4. Si todo OK: Elimina backup

---

## 🛡️ Fallback a Supabase (Legacy)

Si GitHub Releases no está disponible, el sistema automáticamente intenta Supabase (si está configurado). Esto permite transición gradual de infraestructura.

---

## 📊 Monitoreo

Para ver logs de actualizaciones:

```bash
# Ver último log
Get-Content "logs/update_*.log" | Select-Object -Last 20

# O desde Python
tail -f logs/update_*.log
```

---

## ✅ Checklist de Publicación

- [ ] Incrementar versión en `version.py`
- [ ] Actualizar `app.py` o similar con nuevas características
- [ ] Compilar aplicación: `build.ps1` o similar
- [ ] Crear ZIP: `Manarey-X.Y.Z.zip`
- [ ] Publicar: `python publish_github_release.py --version X.Y.Z --file Manarey-X.Y.Z.zip`
- [ ] Verificar en GitHub Releases que está visible
- [ ] Probar descarga manual: Link en https://github.com/usuario/repo/releases
- [ ] Probar actualización: Esperar a que se lance el checker, o clic en botón "Comprobar Actualizaciones"

---

## 🐛 Troubleshooting

### "GITHUB_REPO y GITHUB_TOKEN requeridos"

Solución:
```powershell
$env:GITHUB_REPO = "tu_usuario/tu_repo"
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxx"
# Verifica que se establecieron
Write-Output $env:GITHUB_REPO
```

### "Error 404: No se encuentra el archivo"

Solución: Asegúrate que:
- El ZIP existe: `Test-Path ./Manarey-1.0.5.zip`
- El nombre es correcto
- El token tiene permisos de `repo`

### App no detecta actualización

Solución:
1. Clic en "🔄 Comprobar Actualizaciones" (botón manual)
2. Ver logs: `logs/update_*.log`
3. Verificar URL en GitHub es accesible: `https://api.github.com/repos/usuario/repo/releases/latest`

---

## 📝 Notas

- **GitHub API**: Límite: 60 req/hora sin auth, 5000 req/hora con token
- **ZIP recomendado**: Solo archivos compilados necesarios (~50-100 MB)
- **Múltiples ubicaciones**: Ventaja clave de GitHub vs Supabase centralizado
- **Privado/Publico**: Funciona igual, pero privado requiere token válido

