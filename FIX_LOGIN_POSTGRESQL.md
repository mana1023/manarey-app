# 🔧 Fix: Login con PostgreSQL

## ⚠️ Problema

Al intentar hacer login con PostgreSQL/Supabase, aparecía:

```
Error de conexión a la base de datos (revisá logs/auth.log)
```

---

## 🐛 Causa Raíz

El código de login usaba **placeholders de SQLite** (`?`) pero PostgreSQL usa **`%s`**.

### Código Anterior (Incorrecto):
```python
cur.execute(
    "SELECT username, password, role, local FROM usuarios WHERE LOWER(username)=LOWER(?)",
    (self._username,)
)
```

**Problema:** PostgreSQL no entiende `?`, solo entiende `%s`.

---

## ✅ Solución Implementada

Detectar qué tipo de base de datos estás usando y adaptar el placeholder:

### Código Nuevo (Correcto):
```python
from models.db import is_postgres

# PostgreSQL usa %s, SQLite usa ?
if is_postgres():
    query = "SELECT username, password, role, local FROM usuarios WHERE LOWER(username)=LOWER(%s)"
else:
    query = "SELECT username, password, role, local FROM usuarios WHERE LOWER(username)=LOWER(?)"

cur.execute(query, (self._username,))
```

---

## 📝 Archivo Modificado

- **`views/login_view.py`** (líneas 54-73)
  - Agregado detección de tipo de BD
  - Adaptado placeholder según BD
  - Agregado traceback para debug

---

## 🧪 Cómo Probar

1. **Ejecutá la app:**
   ```bash
   python app.py
   ```

2. **Intentá hacer login:**
   - Usuario: `Cane`
   - Contraseña: `Manarey10`

3. **Resultado esperado:**
   - ✅ Login exitoso
   - ✅ Se abre la ventana del local
   - ❌ NO debe mostrar "Error de conexión"

---

## 🔍 Si Sigue Fallando

Si aún muestra error, ejecutá el diagnóstico:

```bash
python diagnostico_performance.py
```

Esto te dirá si:
- ✅ La conexión a Supabase funciona
- ✅ Los usuarios existen en la BD
- ❌ Hay algún otro problema

---

## 📊 Otros Lugares que Pueden Necesitar Fix

Si encontrás errores similares en otras partes de la app, revisá que **todas las consultas SQL** usen el placeholder correcto:

### Patrón a Buscar:
```python
# MAL (solo funciona con SQLite)
cur.execute("SELECT * FROM tabla WHERE campo = ?", (valor,))

# BIEN (funciona con ambos)
from models.db import is_postgres
placeholder = "%s" if is_postgres() else "?"
cur.execute(f"SELECT * FROM tabla WHERE campo = {placeholder}", (valor,))
```

---

## ✨ Diferencias SQLite vs PostgreSQL

| Característica | SQLite | PostgreSQL |
|----------------|--------|------------|
| **Placeholder** | `?` | `%s` |
| **Autoincrement** | `AUTOINCREMENT` | `SERIAL` |
| **Bool** | `0`/`1` | `TRUE`/`FALSE` |
| **LIKE** | Case-insensitive por defecto | Case-sensitive |
| **Timestamps** | Strings | `TIMESTAMP` |

---

## 🎯 Estado Actual

- ✅ Login compatible con PostgreSQL
- ✅ Login compatible con SQLite
- ✅ Detección automática de tipo de BD
- ✅ Mensajes de error claros

---

**Probá ahora el login y debería funcionar perfecto con PostgreSQL! 🚀**
