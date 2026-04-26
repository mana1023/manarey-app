# 💻 Ejemplos de Ejecución

## Ejemplo 1: Publicar Release (Python)

### Comando
```powershell
python publish_github_release.py --version 1.0.5 --file Manarey-1.0.5.zip
```

### Output Esperado (Éxito)
```
📤 Publicando en GitHub Releases
   Repo: mana1023/manarey-updates
   Versión: 1.0.5
   Archivo: Manarey-1.0.5.zip
   Tamaño: 45.32 MB
   Buscando release v1.0.5...
   Creando release v1.0.5...
   Subiendo archivo Manarey-1.0.5.zip...
✓ Release publicada exitosamente!

📊 Detalles:
   Versión: 1.0.5
   Release: v1.0.5
   Archivo: Manarey-1.0.5.zip
   URL: https://github.com/mana1023/manarey-updates/releases/tag/v1.0.5
```

### Output Esperado (Error - Token inválido)
```
❌ Error: GITHUB_REPO y GITHUB_TOKEN requeridos
   Configura variables de entorno:
   $env:GITHUB_REPO = 'usuario/repo'
   $env:GITHUB_TOKEN = 'tu_token'
```

### Output Esperado (Error - Archivo no existe)
```
❌ Error: No se encontró Manarey-1.0.5.zip
```

---

## Ejemplo 2: Publicar Release (PowerShell)

### Comando
```powershell
.\publish_release.ps1 -Version "1.0.5" -ZipFile "Manarey-1.0.5.zip"
```

### Output Esperado
```
📤 Publicando en GitHub Releases
   Repo: mana1023/manarey-updates
   Versión: 1.0.5
   Archivo: Manarey-1.0.5.zip
✓ Release publicada exitosamente
```

---

## Ejemplo 3: Verificar Automáticamente en la App

### Escenario: Usuario abre app con versión antigua

**Línea de tiempo:**
```
[10:00:00] Usuario ejecuta: python app.py
[10:00:02] App muestra ventana principal
[10:00:03] Background thread inicia verificación
           GET https://api.github.com/repos/mana1023/manarey-updates/releases/latest
[10:00:04] Respuesta: versión 1.0.5 disponible
[10:00:05] 🎨 DIÁLOGO APARECE
           ┌─────────────────────────────────────────┐
           │ 📦 Nueva versión disponible             │
           │                                         │
           │ Versión actual: 1.0.2                  │
           │ Nueva versión:  1.0.5                  │
           │                                         │
           │ ✨ Cambios:                             │
           │ - Mejorado desempeño en stock         │
           │ - Corregido bug en reportes           │
           │ - Nueva interfaz de usuarios          │
           │                                         │
           │ ⏰ Tienes 2 días antes de ser obligatoria
           │                                         │
           │ [Instalar Ahora]  [Más Tarde]         │
           └─────────────────────────────────────────┘

[Si usuario clicks "Instalar Ahora"]
[10:00:06] Crea backup: update_backup_20240115_100006.zip
[10:00:07] Inicia descarga desde GitHub
           ┌─────────────────────────────────────────┐
           │ Descargando e instalando...             │
           │                                         │
           │ [████████████░░░░] 65% (29.5 MB / 45 MB)
           │                                         │
           │ Tiempo restante: ~10 segundos          │
           └─────────────────────────────────────────┘
[10:00:15] ✓ Descarga completada
[10:00:16] ✓ Archivos extraídos
[10:00:17] App se cierra automáticamente
[10:00:18] App se reinicia
[10:00:19] 🎯 Usuario tiene versión 1.0.5
           Menú → About → Version: 1.0.5

[Si usuario clicks "Más Tarde"]
[10:00:06] Diálogo desaparece
[10:00:07] App continúa normalmente
[10:00:08] * La próxima vez que abra, verificará de nuevo
```

---

## Ejemplo 4: Verificar Manualmente en la App

### Comando (desde la app)
Hacer clic en: Menú → "🔄 Comprobar Actualizaciones"

### Output Esperado (Con actualización disponible)
```
[Mismo diálogo que Ejemplo 3]
```

### Output Esperado (Sin actualización disponible)
```powershell
┌──────────────────────────────┐
│ 📋 Información               │
│                              │
│ Ya estás en la última        │
│ versión (1.0.5)              │
│                              │
│        [OK]                  │
└──────────────────────────────┘
```

### Output Esperado (Error de conectividad)
```powershell
┌──────────────────────────────┐
│ ⚠️ Error                     │
│                              │
│ No se pudo verificar         │
│ actualizaciones.             │
│ Intenta más tarde.           │
│                              │
│        [OK]                  │
└──────────────────────────────┘
```

---

## Ejemplo 5: Logs durante Instalación

### Ver archivo de log
```powershell
Get-Content "logs\update_20240115.log"
```

### Output esperado
```
2024-01-15 10:00:03,456 - updater - DEBUG - Buscando actualizaciones...
2024-01-15 10:00:03,478 - updater - DEBUG - Conectando a GitHub...
2024-01-15 10:00:04,123 - updater - INFO - Nueva versión disponible: 1.0.5
2024-01-15 10:00:04,125 - updater - DEBUG - Versión actual: 1.0.2
2024-01-15 10:00:04,126 - updater - DEBUG - Comparación: 1.0.2 < 1.0.5 ✓
2024-01-15 10:00:05,832 - updater - DEBUG - Usuario clickeó "Instalar Ahora"
2024-01-15 10:00:06,123 - updater - DEBUG - Creando backup en: C:\Users\USUARIO\AppData\Local\Manarey\update_backup_20240115_100006.zip
2024-01-15 10:00:06,456 - updater - DEBUG - Descargando desde: https://github.com/mana1023/manarey-updates/releases/download/v1.0.5/Manarey-1.0.5.zip
2024-01-15 10:00:07,123 - updater - DEBUG - Descargados 5.2 MB de 45.3 MB
2024-01-15 10:00:08,234 - updater - DEBUG - Descargados 10.4 MB de 45.3 MB
2024-01-15 10:00:10,123 - updater - DEBUG - Descargados 20.8 MB de 45.3 MB
2024-01-15 10:00:13,456 - updater - DEBUG - Descargados 31.2 MB de 45.3 MB
2024-01-15 10:00:15,678 - updater - DEBUG - Descargados 41.6 MB de 45.3 MB
2024-01-15 10:00:16,123 - updater - DEBUG - Descargados 45.3 MB de 45.3 MB ✓
2024-01-15 10:00:16,234 - updater - DEBUG - Descarga completada
2024-01-15 10:00:16,456 - updater - DEBUG - Quitando versión anterior...
2024-01-15 10:00:16,678 - updater - DEBUG - Extrayendo archivo ZIP...
2024-01-15 10:00:17,234 - updater - DEBUG - Extracción completada
2024-01-15 10:00:17,456 - updater - INFO - Actualización completada. Reiniciando...
2024-01-15 10:00:17,678 - updater - DEBUG - Cerrando aplicación...
2024-01-15 10:00:18,000 - updater - DEBUG - Reiniciando aplicación...
```

---

## Ejemplo 6: Restauración en Caso de Error

### Escenario: ZIP corrupto durante instalación

```
[10:00:16] Descarga completada (archivo corrupto)
[10:00:17] Intentando extraer ZIP...
[10:00:17] ⚠️ ERROR: ZIP corrupido o inválido
[10:00:17] 🔄 Restaurando backup...
[10:00:18] ✓ Restauración completada
[10:00:18] Volviendo a versión anterior: 1.0.2

┌────────────────────────────────────────┐
│ ⚠️ Error de Instalación               │
│                                        │
│ Hubo un problema instalando la       │
│ actualización. Se ha restaurado       │
│ la versión anterior.                  │
│                                        │
│ Información guardada en:              │
│ logs/update_20240115.log              │
│                                        │
│              [OK]                      │
└────────────────────────────────────────┘
```

---

## Ejemplo 7: Actualización Obligatoria

### Escenario después de 2 días sin actualizar

```
[10:00:05] DIÁLOGO APARECE
           ┌─────────────────────────────────────────┐
           │ ⚠️ ACTUALIZACIÓN OBLIGATORIA            │
           │                                         │
           │ Versión actual: 1.0.2                  │
           │ Nueva versión:  2.0.0 (CRÍTICA)        │
           │                                         │
           │ 🔴 Esta es una actualización crítica  │
           │ y debes instalarla para continuar.     │
           │                                         │
           │ Cambios importantes:                   │
           │ - Parche seguridad crítico            │
           │ - Compatibilidad base datos           │
           │ - Estabilidad completa                │
           │                                         │
           │ [Instalar Ahora]  [Salir]             │
           └─────────────────────────────────────────┘

[Si usuario clicks "Salir" o cierra diálogo]
[10:00:06] App se cierra (fuerza obligatoria)
[Usuario debe instalar next time]

[Si usuario clicks "Instalar Ahora"]
[10:00:06] Instala como en Ejemplo 3
```

---

## Ejemplo 8: Token de GitHub Inválido

### Setup incorrecto
```powershell
$env:GITHUB_REPO = "mana1023/manarey-updates"
$env:GITHUB_TOKEN = "invalid_token_123"
```

### Output
```
[10:00:03] Background thread verifica GitHub
[10:00:04] Error: Token inválido (HTTP 401)
[10:00:04] Intenta fallback a Supabase...
[10:00:05] Supabase: Sin conexión
[10:00:05] No se puede verificar actualizaciones
[10:00:05] → No muestra diálogo
[Logs]: ERROR - Authentication failed for GitHub API
```

---

## Ejemplo 9: Estadísticas de Uso

### Ver cuántas veces se verificó
```powershell
$logs = Get-Content "logs\update_*.log" | Select-String "Buscando actualizaciones"
$logs.Count
# Output: 23 (se verificó 23 veces)
```

### Ver última actualización exitosa
```powershell
$logs = Get-Content "logs\update_*.log" | Select-String "Actualización completada" | Select-Object -Last 1
# Output: 2024-01-14 15:23:45,123 - updater - INFO - Actualización completada. Reiniciando...
```

---

## Ejemplo 10: Publicación con Changelog Personalizado

### Comando
```powershell
python publish_github_release.py `
  --version 1.0.5 `
  --file Manarey-1.0.5.zip `
  --changelog "Versión 1.0.5 - Manteniendo
  
✨ Nuevas Características:
- Nuevo sistema de reportes
- Interfaz mejorada

🐛 Correcciones:
- Bug en cálculo de totales
- Error al procesar lotes

⚡ Performance:
- 30% más rápido en queries
- Menos uso de memoria"
```

### Output
```
📤 Publicando en GitHub Releases
   Repo: mana1023/manarey-updates
   Versión: 1.0.5
   Archivo: Manarey-1.0.5.zip
   Tamaño: 45.32 MB
✓ Release publicada exitosamente!

📊 En GitHub:
✨ Nuevas Características:
- Nuevo sistema de reportes
- Interfaz mejorada

🐛 Correcciones:
- Bug en cálculo de totales
- Error al procesar lotes

⚡ Performance:
- 30% más rápido en queries
- Menos uso de memoria
```

---

## ✅ Checklist de Outputs Esperados

| Escenario | ✓ Expected Output | Status |
|-----------|------------------|--------|
| Publicación exitosa | "Release publicada exitosamente!" | ⬜ |
| Update detectada | Diálogo dorado aparece | ⬜ |
| Instalación exitosa | App reinicia con nueva versión | ⬜ |
| Error de Red | Mensaje de error claro | ⬜ |
| Restauración | "Restauración completada" en logs | ⬜ |
| Obligatoria | Botón "Salir" en lugar de "Más Tarde" | ⬜ |

