# 🚀 Quick Start: Actualizar Manarey con GitHub Releases

## TL;DR - 3 Pasos

```powershell
# 1. Configurar credenciales (una sola vez)
$env:GITHUB_REPO = "mana1023/manarey-updates"
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxx"

# 2. Compilar y crear ZIP
# (Tu script habitual de build)

# 3. Publicar
python publish_github_release.py --version 1.0.5 --file Manarey-1.0.5.zip
```

---

## ✅ ¿Qué está listo?

- ✅ La aplicación **detecta automáticamente** nuevas versiones en GitHub
- ✅ Muestra **diálogo profesional** (dorado) con cambios
- ✅ Usuario elige: **"Instalar Ahora"** o **"Más Tarde"**
- ✅ Descarga, extrae, reinicia automáticamente
- ✅ **Sistema de respaldo**: Si falla, restaura automáticamente

---

## 📦 Cómo Publicar Actualizaciones

### Opción 1: Script PowerShell (Recomendado)

```powershell
.\publish_release.ps1 -Version "1.0.5" -ZipFile "Manarey-1.0.5.zip"
```

### Opción 2: Python directo

```bash
python publish_github_release.py --version 1.0.5 --file Manarey-1.0.5.zip
```

### Opción 3: Integrar en tu script de compilación

```powershell
# En actualizacion.ps1:
$version = "1.0.5"
# ...compilar...
$zip = "Manarey-$version.zip"
Compress-Archive -Path "./dist/*" -DestinationPath $zip
python publish_github_release.py --version $version --file $zip
```

---

## 🔍 Verificar que Funciona

### En la Aplicación

1. Abre Manarey
2. Espera ~2 segundos (ve a verificar en background)
3. O haz clic en **"🔄 Comprobar Actualizaciones"** en el menú

### Manualmente

```bash
# Ver última release publicada
curl https://api.github.com/repos/mana1023/manarey-updates/releases/latest | jq .
```

---

## 🛠️ Configuración Única

Establece ANTES de usar los scripts:

```powershell
# PowerShell (temporal - sesión actual)
$env:GITHUB_REPO = "mana1023/manarey-updates"
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxx"

# O permanente - agregar a tu perfil PowerShell:
# C:\Users\USUARIO\Documents\PowerShell\profile.ps1
# Agregar:
#   $env:GITHUB_REPO = "mana1023/manarey-updates"
#   $env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxx"
```

O usar `config.json`:

```json
{
  "GITHUB_REPO": "mana1023/manarey-updates",
  "GITHUB_TOKEN": "ghp_xxxxxxxxxxxxx"
}
```

---

## 📋 Archivos Nuevos

- `publish_github_release.py` - Script Python para publicar
- `publish_release.ps1` - Script PowerShell wrapper
- `GITHUB_RELEASES_WORKFLOW.md` - Documentación completa

---

## 🎯 Características Incluidas

| Característica | Estado |
|---|---|
| Detectar nuevas versiones | ✅ Automático |
| Diálogo profesional (dorado) | ✅ Integrado |
| Descargar & instalar | ✅ Con barra de progreso |
| Respaldo automático | ✅ Restaura si falla |
| GitHub API | ✅ Con fallback a Supabase |
| Token autenticación | ✅ Apoya privado/público |
| Múltiples ubicaciones | ✅ Ideal para distribución |

---

## 📞 Soporte

Ver `GITHUB_RELEASES_WORKFLOW.md` para troubleshooting completo.

