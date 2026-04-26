# ⚡ Cheat Sheet - Sistema de Actualizaciones

## 🎯 Quick Commands

### Publicar Release
```powershell
# Setup (una sola vez)
$env:GITHUB_REPO = "mana1023/manarey-updates"
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxx"

# Publicar
python publish_github_release.py --version 1.0.5 --file Manarey-1.0.5.zip
```

### Crear ZIP
```powershell
cd c:\Users\USUARIO\Desktop\Manarey\DESCARGABLE
Compress-Archive -Path "*" -DestinationPath "..\Manarey-1.0.5.zip"
```

### Ver Logs
```powershell
Get-Content logs\update_*.log | Select-Object -Last 50
Get-Content logs\update_*.log -Wait  # Real-time
```

### Resetear Estado
```powershell
Remove-Item "$env:LOCALAPPDATA\Manarey\update_state.json"
```

---

## 📁 Archivos Importantes

| Archivo | Propósito | Dónde |
|---------|-----------|-------|
| `publish_github_release.py` | Publicar releases | Raíz |
| `publish_release.ps1` | Publicar (PowerShell) | Raíz |
| `updater.py` | Sistema de updates | Raíz |
| `ui_update_dialog.py` | Diálogos UI | `ui/` |
| `app.py` | Entrypoint | Raíz |
| `menu_window.py` | Botón de updates | `ui/` |

---

## 🔐 Configuración

### Variables de Entorno
```powershell
$env:GITHUB_REPO           # usuario/repo
$env:GITHUB_TOKEN          # ghp_xxxxxxxxxxxxx
```

### O en config.json
```json
{
  "GITHUB_REPO": "usuario/repo",
  "GITHUB_TOKEN": "ghp_xxxxxxxxxxxxx"
}
```

---

## ✨ Funciones Principales

### En updater.py
```python
check_for_updates(parent_widget, show_ui=True)  # Check now
refresh_update_state()                          # Get manifest
```

### En app.py
```python
threading.Thread(
    target=lambda: check_for_updates(window, show_ui=True),
    daemon=True
).start()
```

---

## 📊 Flujos

### Publicador
```
1. build APP
2. create ZIP
3. python publish_github_release.py --version X.Y.Z --file Manarey-X.Y.Z.zip
4. ✓ Release en GitHub
```

### Usuario
```
1. open app
2. automático: detecta versión
3. dialogo: "Instalar?" 
4. ✓ instalado + reinicia
```

---

## 🐛 Troubleshooting

| Error | Solución |
|-------|----------|
| Token inválido | Crear nuevo en GitHub → Settings → Tokens |
| Repo no encontrado | Verificar GITHUB_REPO formato: "usuario/repo" |
| App no detecta | Revisar `logs/update_*.log` para detalles |
| Falla instalación | Se restaura automático, ver logs |
| Sin conectividad | Fallback a Supabase automático |

---

## 📈 APIs Used

```
GitHub: GET /repos/{GITHUB_REPO}/releases/latest
Returns: version, url, notes, published_at, assets
```

---

## 🎨 UI Colors

```python
Gold:  #C9A040
Dark:  #0f0f14
Light: #E0E0E0
Gray:  #999999
```

---

## 🗂️ Paths

```
State:    AppData\Local\Manarey\update_state.json
Backup:   AppData\Local\Manarey\update_backup_*.zip
Logs:     logs\update_YYYYMMDD.log
Config:   ./config.json (opcional)
```

---

## 🔄 Versioning

```
Format: X.Y.Z (e.g., 1.0.5)
Compare: 1.0.2 < 1.0.10 < 1.1.0 < 2.0.0
GitHub Tag: v{VERSION} (e.g., v1.0.5)
```

---

## 🎯 Checklist Mínimo

- ⬜ GITHUB_REPO configurado
- ⬜ GITHUB_TOKEN válido
- ⬜ ZIP creado
- ⬜ publish_github_release.py ejecutado
- ⬜ Release visible en GitHub
- ⬜ App detecta actualización
- ⬜ Instalación funciona

---

## 📞 Documentación

1. [SISTEMA_COMPLETO_GITHUB_RELEASES.md](SISTEMA_COMPLETO_GITHUB_RELEASES.md) - Overview
2. [QUICK_START_GITHUB_RELEASES.md](QUICK_START_GITHUB_RELEASES.md) - 3 pasos
3. [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) - Testing
4. [GITHUB_RELEASES_WORKFLOW.md](GITHUB_RELEASES_WORKFLOW.md) - Docs completa
5. [EJEMPLOS_EJECUCION.md](EJEMPLOS_EJECUCION.md) - Ejemplos
6. [ARCHIVOS_Y_CAMBIOS.md](ARCHIVOS_Y_CAMBIOS.md) - Internals

---

## 💡 Pro Tips

✅ Usar `--mandatory` para fuerza obligatoria
✅ Ver GitHub web para verificar releases
✅ Los logs muestran TODO que sucede
✅ Backup se crea automático
✅ Soporta repos privados con token
✅ Fallback automático si GitHub falla

---

## ⏱️ Timing

- App startup → 2s delay → verificación
- Check button → Inmediato
- Download → 10-30s (depende tamaño/conexión)
- Install → 2-5s
- Restart → automático

---

**Imprimir o guardar para referencia rápida** 📌

