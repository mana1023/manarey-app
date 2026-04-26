# 📋 Estructura de Archivos - Sistema de Actualizaciones

## 🎯 Archivos Nuevos Creados

```
Manarey (raíz)
├── publish_github_release.py      ← Script Python para publicar
├── publish_release.ps1            ← Script PowerShell para publicar
│
├── GITHUB_RELEASES_WORKFLOW.md    ← Docs completa (65 líneas)
├── QUICK_START_GITHUB_RELEASES.md ← Quick start (80 líneas)  
├── TESTING_CHECKLIST.md           ← Pasos de testing (250+ líneas)
└── SISTEMA_COMPLETO_GITHUB_RELEASES.md  ← Este resumen
```

---

## 🔧 Archivos Modificados

### `updater.py` (Core - 713 líneas)
**Ubicación:** `c:\Users\USUARIO\Desktop\Manarey\updater.py`

**Funciones nuevas agregadas:**
```python
# Línea ~20-30: Helpers
- _parse_version()                    # Comparar versiones (1.0.5 vs 1.0.10)

# Línea ~30-50: GitHub Integration
- _get_github_repo_from_config()      # Lee GITHUB_REPO y GITHUB_TOKEN
- _get_latest_release_from_github()   # Conecta a API de GitHub

# Línea ~100-125: Manifest loading
- _load_manifest_from_db()            # Intenta GitHub, luego Supabase

# Línea ~612+: Main function
- check_for_updates()                 # Punto de entrada principal
```

**Cambios clave:**
- GitHub API integration (líneas 40-95)
- Fallback logic en `_load_manifest_from_db()` (líneas 103-125)
- Usa diálogos profesionales de `ui.ui_update_dialog`

---

### `app.py` (Entrypoint)
**Ubicación:** `c:\Users\USUARIO\Desktop\Manarey\app.py`

**Cambios:**
```python
# Al crear main window:
threading.Thread(
    target=lambda: (
        time.sleep(2),  # Esperar a que se renderice
        updater.check_for_updates(window, show_ui=True)
    ),
    daemon=True
).start()
```

**Propósito:** 
- Verifica actualizaciones en background
- No bloquea interfaz
- Usuario no ve delay

---

### `ui/menu_window.py` (Menú Principal)
**Ubicación:** `c:\Users\USUARIO\Desktop\Manarey\ui\menu_window.py`

**Cambios:**
```python
# En layout de botones:
self.btn_check_updates = QPushButton("🔄 Comprobar Actualizaciones")
self.btn_check_updates.clicked.connect(self._on_check_updates)

# Callback:
def _on_check_updates(self):
    updater.check_for_updates(self, show_ui=True)
```

**Propósito:**
- Botón manual para verificar
- Usuario controla cuándo verificar
- Estilos dorados coherentes

---

### `ui/ui_update_dialog.py` (NUEVO - 300+ líneas)
**Ubicación:** `c:\Users\USUARIO\Desktop\Manarey\ui\ui_update_dialog.py`

**Clases incluidas:**
```python
class UpdateDialog(QDialog):
    # Diálogo de notificación
    # - Muestra versión nueva
    # - Muestra changelog
    # - Botones: "Instalar Ahora" / "Más Tarde"
    # - Estilos dorados profesionales
    
class UpdateProgressDialog(QDialog):
    # Diálogo de progreso
    # - Barra de progreso dorada
    # - Muestra: "Descargando..." / "Instalando..."
    # - Progreso en porcentaje
```

**Propósito:**
- UI profesional integrada
- No depende de QMessageBox genérico
- Estilos uniformes con app

---

## 📦 Configuración Requerida

### Variables de Entorno
```powershell
# PowerShell
$env:GITHUB_REPO = "tu_usuario/tu_repo"        # e.g., "mana1023/manarey-updates"
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxx"        # Token autenticación

# O en config.json:
{
  "GITHUB_REPO": "tu_usuario/tu_repo",
  "GITHUB_TOKEN": "ghp_xxxxxxxxxxxxx"
}
```

### Dependencias de Python
```bash
# Necesario para publicar (ya incluido en std library):
# - urllib
# - json
# - subprocess

# Necesario para scripts de publicación:
pip install requests    # Para publish_github_release.py

# Ya presente en app:
# - PyQt5 (para UI)
```

---

## 🚀 Flujo de Uso

### Publicador (Desarrollador)

```
1. Compilar aplicación
   └─ app.exe, archivos compilados
   
2. Crear ZIP
   └─ Manarey-1.0.5.zip
   
3. Ejecutar script de publicación
   ├─ Option A: python publish_github_release.py --version 1.0.5 --file Manarey-1.0.5.zip
   └─ Option B: .\publish_release.ps1 -Version "1.0.5" -ZipFile "Manarey-1.0.5.zip"
   
4. Release aparece en GitHub
   └─ https://github.com/{GITHUB_REPO}/releases/tag/v1.0.5
```

### Usuario Final

```
1. Abre aplicación
   └─ app.py ejecutado
   
2. Background thread verifica GitHub
   ├─ Si hay versión nueva → Muestra diálogo
   └─ Si está actualizado → No hace nada
   
3. Usuario ve diálogo profesional
   ├─ "Nueva versión: 1.0.5"
   ├─ Changelog desde GitHub
   └─ Botones: "Instalar Ahora" / "Más Tarde"
   
4a. Si "Instalar Ahora":
    ├─ Crea backup
    ├─ Descarga Manarey-1.0.5.zip desde GitHub
    ├─ Muestra barra de progreso dorada
    ├─ Extrae archivos
    ├─ Cierra app
    ├─ Reinicia automáticamente
    └─ Usuario tiene nueva versión
    
4b. Si "Más Tarde":
    └─ Sigue con versión actual
```

---

## 🗂️ Estructura de Datos en Disco

### AppData Local (State)
```
C:\Users\USUARIO\AppData\Local\Manarey\
├── update_state.json          # Estado de última verificación
└── update_backup_*.zip        # Backups de instalaciones previas
```

### Logs
```
logs/
└── update_YYYYMMDD.log        # Logs de cada sesión de updates
```

---

## 🔍 Debugging

### Ver último que pasó
```powershell
# Logs
Get-Content "logs\update_*.log" | Select-Object -Last 50
Get-Content "logs\update_*.log" -Wait  # Modo real-time

# Estado
$state = Get-Content "C:\Users\$env:USERNAME\AppData\Local\Manarey\update_state.json" | ConvertFrom-Json
$state
```

### Resetear estado
```powershell
# Limpiar state (fuerza re-verificación)
Remove-Item "C:\Users\$env:USERNAME\AppData\Local\Manarey\update_state.json" -ErrorAction SilentlyContinue

# Ejecutar app
python app.py
# → Should verify immediately
```

---

## 📝 Resumen de Cambios por Archivo

| Archivo | Líneas | Cambio | Impacto |
|---------|--------|--------|---------|
| `updater.py` | 713 | +GitHub integration | Core feature |
| `app.py` | Pocas | +Thread checker | Background verification |
| `ui/menu_window.py` | Pocas | +Button | UI manual trigger |
| `ui/ui_update_dialog.py` | +300 | New file | Professional UI |
| `publish_github_release.py` | 200+ | New file | Publishing tool |
| `publish_release.ps1` | 40 | New file | PowerShell wrapper |

---

## ✅ Verificación Rápida de Integridad

```powershell
# 1. Verificar archivos existen
Test-Path "updater.py"
Test-Path "app.py"
Test-Path "ui/menu_window.py"
Test-Path "ui/ui_update_dialog.py"
Test-Path "publish_github_release.py"
Test-Path "publish_release.ps1"

# 2. Verificar sintaxis Python
python -m py_compile updater.py
python -m py_compile publish_github_release.py

# 3. Verificar imports en updater.py
python -c "import sys; exec(open('updater.py').read())"

# 4. Verificar config
Test-Path "config.json"
Get-Content "config.json" | ConvertFrom-Json | Select-Object GITHUB_REPO, GITHUB_TOKEN
```

---

## 🎯 Próximo Pasó

1. **Testear**: Seguir `TESTING_CHECKLIST.md` (punto por punto)
2. **Publicar**: Usar `publish_github_release.py` para primera versión
3. **Verificar**: Clic en "Comprobar Actualizaciones" en app
4. **Integrar**: Agregar líneas de publish al script de compilación
5. **Producción**: Release automático cada build

