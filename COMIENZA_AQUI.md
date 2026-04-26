# 🚀 EMPIEZA AQUÍ: Tu Primer Actualización en 15 Minutos

## Paso 0: Verificación (1 minuto)

```bash
# Abre PowerShell en la carpeta del proyecto y ejecuta:
python --version          # Debe ser 3.7+
python -c "import PyQt5"  # Sin errores
python test_update_system.py  # Debe decir "✓ TEST EXITOSO"
```

✓ Si todo funciona, continúa.  
✗ Si hay error, revisa [QUICK_START_ACTUALIZACIONES.md](QUICK_START_ACTUALIZACIONES.md)

---

## Paso 1: Preparar Base de Datos (2 minutos)

Abre Supabase y ejecuta este SQL:

```sql
CREATE TABLE public.updates (
  id BIGSERIAL PRIMARY KEY,
  version VARCHAR(20) NOT NULL UNIQUE,
  download_url TEXT NOT NULL,
  changelog TEXT,
  published_at TIMESTAMP DEFAULT NOW(),
  mandatory BOOLEAN DEFAULT FALSE,
  force_after_days INT DEFAULT 2
);

-- Índices
CREATE INDEX idx_updates_version ON updates(version DESC);

-- Verificar que se creó
SELECT * FROM updates;  -- Debe estar vacía, pero existe
```

✓ Tabla lista.

---

## Paso 2: Crear Tu Primera Actualización (5 minutos)

### Opción A: Desde Código Compilado [RECOMENDADO]

```bash
# 1. Editar version.py - cambiar a nueva versión:
#    __version__ = "1.0.5"

# 2. Compilar y empaquetar automáticamente:
python build_release.py --spec Manarey.spec

# Espera... (toma 1-2 minutos)
# Resultado: Manarey-1.0.5.zip en tu carpeta
```

### Opción B: Desde Solo Código Python

```bash
# 1. Copiar archivos actualizados a carpeta temporal:
mkdir C:\Temp\Manarey-1.0.5
copy *.py C:\Temp\Manarey-1.0.5
xcopy models C:\Temp\Manarey-1.0.5\models /E
xcopy ui C:\Temp\Manarey-1.0.5\ui /E
xcopy assets C:\Temp\Manarey-1.0.5\assets /E

# 2. Crear ZIP:
python package_update.py --source C:\Temp\Manarey-1.0.5 --version 1.0.5

# Resultado: Manarey-1.0.5.zip
```

✓ ZIP creado.

---

## Paso 3: Desplegar a Supabase (3 minutos)

```bash
# Desplegar (requiere config de Supabase):
python deploy_update.py --zip Manarey-1.0.5.zip --changelog "Primera actualización - cambios importantes"

# Espera a ver: "✓ Actualización desplegada exitosamente!"
```

✓ Desplegado en Supabase.

---

## Paso 4: Verificar (2 minutos)

### En Supabase SQL:
```sql
-- Verificar que está registrado:
SELECT * FROM updates WHERE version = '1.0.5';

-- Debería mostrar tu registro con:
-- version: 1.0.5
-- download_url: https://...
-- changelog: Tu texto
-- mandatory: false
-- force_after_days: 2
```

### En tu app:
```bash
# Si tienes check_for_updates() integrado:
# - Abre la app
# - Deberías ver notificación de actualización
# - Haz clic en "Instalar ahora"
# - Verás barra de progreso
# - Se reinicia automáticamente
# - ✓ Nueva versión instalada
```

✓ ¡Listo!

---

## 🎉 ¿Lo Hiciste?

Feliz, acabas de:

1. ✅ Crear una actualización
2. ✅ Desplegarla a Supabase
3. ✅ Que los usuarios puedan instalarla

**Lo que sucede ahora:**

- Cualquier usuario que abra la app verá: "Actualización disponible"
- Al hacer clic, se descarga automáticamente (con barra de progreso)
- Se instala automáticamente (con barra de progreso)
- La app se reinicia
- ¡Nueva versión instalada!

---

## 🆘 Si Algo No Funciona

### "No me aparecce actualización en app"
1. Verifica que version.py en ZIP tiene versión NUEVA (1.0.5)
2. Verifica query SQL encuentra el registro
3. Revisa logs: `%LOCALAPPDATA%\Manarey\logs\app.log`

### "Error en Supabase"
1. Verifica SUPABASE_URL y SUPABASE_KEY en config.json
2. Verifica que tabla `updates` existe en SQL

### "ZIP corrupto"
1. Valida: `python -m zipfile -t Manarey-1.0.5.zip`
2. Lista contenido: `python -m zipfile -l Manarey-1.0.5.zip`

### "Ayuda!"
1. Lee `QUICK_START_ACTUALIZACIONES.md`
2. Lee `WORKFLOW_ACTUALIZACIONES.md`
3. Lee `GUIA_ACTUALIZACIONES_ZIP.md`

---

## 📊 Timeline

```
Minute 0:  Este archivo
Minute 1:  test_update_system.py
Minute 3:  Crear tabla Supabase
Minute 8:  build_release.py (compilar)
Minute 13: deploy_update.py (desplegar)
Minute 15: ✓ ¡Listo!
```

---

## 🎯 Próximas Veces (Más Rápido)

Una vez que lo haces la primera vez, crear nuevas actualizaciones es aún más rápido:

```bash
# Solo cambias:
# 1. version.py (nueva versión)
# 2. Tus archivos de código

# Luego:
python build_release.py
python deploy_update.py --zip Manarey-X.Y.Z.zip --changelog "Cambios..."

# ¡Listo en 5 minutos!
```

---

## ✨ Lo Que Acabas de Habilitar

Tu app ahora tiene:

- ✅ Actualizaciones automáticas
- ✅ Barra de progreso integrada
- ✅ Backups automáticos
- ✅ Restauración automática si falla
- ✅ Sin instaladores externos
- ✅ Profesional y moderno

---

## 💭 Reflexión

Hace 30 minutos, tus usuarios necesitaban:
1. Descargar un .exe
2. Ejecutar un instalador
3. Seguir pasos complicados
4. Esperar a que termine
5. Rezar para que no se corrompiera nada

Ahora:
1. Ven una notificación
2. Hacen un clic
3. ¡Listo! Se instala automáticamente

**¿Increíble, no?** 🎉

---

## 🎬 Siguiente

- ✅ Has completado tu primer actualización
- ⏭️ **Próximo:** Lee [`WORKFLOW_ACTUALIZACIONES.md`](WORKFLOW_ACTUALIZACIONES.md) para entender todas las opciones
- ⏭️ **O:** Crea tu segunda actualización con los cambios que hagas

---

## 📞 Notas

- Los scripts son reutilizables (úsalos cada vez)
- La documentación es tu referencia (léela cuando dudes)
- El sistema es robusto (está diseñado para producción)
- Tus datos siempre están seguros (backups automáticos)

---

**¡Felicidades!** 🚀

Acabas de modernizar tu sistema de actualizaciones.

Tus usuarios estarán muy felices. 😊
