# 🔧 Solución al Bloqueo "No Responde" en Gestión de Stock

## ⚠️ Problema Identificado

La app se quedaba bloqueada al cargar la tabla de stock, mostrando "Gestión de stock (no responde)".

### Causas Posibles:

1. **Conexión lenta a PostgreSQL/Supabase** - La latencia de red puede ser alta
2. **Muchos productos en la base de datos** - Miles de productos sin paginación
3. **Falta de índices** - Consultas sin optimizar
4. **Worker bloqueado** - El GenericFieldQueueWorker estaba recargando tabla al inicio

---

## ✅ Soluciones Implementadas

### 1. **Protección contra Recargas Innecesarias**

**Problema:** El `GenericFieldQueueWorker` emitía señal `finished_all` al inicio, causando recarga infinita.

**Solución:**
```python
@pyqtSlot()
def _on_generic_finished_all(self):
    # SOLO recargar si hubo operaciones reales (no al inicio)
    if self._generic_queue_total > 0:
        self.load_data()
```

**Ubicación:** `views/stock_view.py` líneas 3033-3052

---

### 2. **Handler de Errores en Carga**

**Problema:** Si la carga fallaba, el usuario no sabía qué pasaba.

**Solución:**
- Agregado `error_occurred` signal en `LoadingThread`
- Agregado handler `_on_loading_error()` que muestra mensaje amigable
- Toast con el error específico

**Ubicación:** `views/stock_view.py` líneas 2564-2574

---

### 3. **Mejor Manejo de Excepciones en LoadingThread**

**Problema:** Errores de BD no se capturaban correctamente.

**Solución:**
```python
try:
    rows = sm.get_stock_filtered(self.local, self.search, self.categoria, self.medida)
    self.data_loaded.emit(rows if rows else [])
except Exception as query_error:
    logger.error(f"Error en consulta de stock: {query_error}")
    self.error_occurred.emit(f"Error al cargar productos: {str(query_error)}")
    self.data_loaded.emit([])
```

**Ubicación:** `views/stock_view.py` líneas 41-63

---

## 🚀 Mejoras Recomendadas (Pendientes)

### A. **Paginación de Productos**

Si tenés miles de productos, implementar paginación:

```python
PRODUCTOS_POR_PAGINA = 100

def get_stock_filtered_paginated(local, search, categoria, medida, page=1, per_page=100):
    offset = (page - 1) * per_page
    # Agregar LIMIT y OFFSET a la query SQL
```

### B. **Índices en PostgreSQL**

Crear índices para acelerar consultas:

```sql
-- En Supabase SQL Editor:
CREATE INDEX IF NOT EXISTS idx_productos_local_nombre 
    ON productos(local, nombre);

CREATE INDEX IF NOT EXISTS idx_productos_categoria 
    ON productos(categoria);

CREATE INDEX IF NOT EXISTS idx_productos_medida 
    ON productos(medida);
```

### C. **Caché en Memoria**

Guardar productos en caché temporal:

```python
self._products_cache = {}
self._cache_timestamp = None
CACHE_DURATION = 60  # segundos

def load_data(self):
    # Si cache es reciente, usar cache
    if self._cache_timestamp and (time.time() - self._cache_timestamp < CACHE_DURATION):
        self.populate_table(self._products_cache)
        return
    
    # Sino, cargar desde BD
    ...
```

### D. **Virtual Scrolling**

Cargar solo productos visibles en pantalla usando `QAbstractItemModel` en lugar de `QTableWidget`.

---

## 🧪 Cómo Verificar que Está Arreglado

### Test 1: Carga Normal
```
1. Abrí Gestión de Stock
2. Verificá que la tabla carga en menos de 5 segundos
3. No debe aparecer "no responde"
```

### Test 2: Error de Conexión
```
1. Desconectá internet
2. Abrí Gestión de Stock
3. Debe mostrar mensaje de error claro (no colgarse)
```

### Test 3: Múltiples Ediciones
```
1. Editá 5 productos seguidos
2. Al finalizar, debe recargar UNA sola vez
3. No debe quedarse cargando
```

---

## 📊 Diagnóstico de Performance

Si sigue lento, ejecutá este script para diagnosticar:

```python
# diagnostico_performance.py
import time
from models import stock_model as sm

print("Iniciando diagnóstico de performance...")

# Test 1: Conexión a BD
start = time.time()
try:
    from models.db import get_conn
    conn = get_conn()
    conn.close()
    print(f"✅ Conexión a BD: {(time.time() - start)*1000:.0f}ms")
except Exception as e:
    print(f"❌ Error de conexión: {e}")

# Test 2: Consulta de productos
start = time.time()
try:
    productos = sm.get_stock_filtered("Cane")
    print(f"✅ Carga de productos: {(time.time() - start)*1000:.0f}ms ({len(productos)} productos)")
except Exception as e:
    print(f"❌ Error en consulta: {e}")

# Test 3: Conversión a dict
start = time.time()
try:
    productos = sm.get_stock_filtered("Cane")
    print(f"✅ Total tiempo: {(time.time() - start)*1000:.0f}ms")
    
    if (time.time() - start) > 3:
        print("⚠️  ADVERTENCIA: La carga tarda más de 3 segundos")
        print("   Considera implementar paginación o índices")
except Exception as e:
    print(f"❌ Error: {e}")
```

---

## 🔍 Logs de Depuración

Los errores se registran en:
- **Console/Terminal:** Errores críticos
- **`logger`:** Todos los errores con traceback completo

Para ver logs detallados:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 💡 Consejos para Evitar Bloqueos

### ✅ Hacer:
- Usar workers (QThread) para operaciones de BD
- Mostrar indicadores de progreso
- Manejar errores con mensajes claros
- Implementar timeouts

### ❌ NO Hacer:
- Consultas pesadas en el hilo principal (UI)
- Recargar tabla después de cada edición
- Ignorar excepciones silenciosamente
- Usar `time.sleep()` en el hilo de UI

---

## 📝 Resumen de Cambios

| Archivo | Líneas | Cambio |
|---------|--------|--------|
| `views/stock_view.py` | 32 | Agregado `error_occurred` signal |
| `views/stock_view.py` | 41-63 | Mejor manejo de excepciones en LoadingThread |
| `views/stock_view.py` | 2564-2574 | Agregado handler `_on_loading_error` |
| `views/stock_view.py` | 3033-3052 | Protección contra recargas innecesarias |

---

## 🎯 Estado Actual

- ✅ **Carga asíncrona** funcionando
- ✅ **Manejo de errores** robusto
- ✅ **Feedback visual** con toast
- ✅ **Sin recargas innecesarias**
- ⚠️ **Pendiente:** Paginación si hay muchos productos
- ⚠️ **Pendiente:** Índices en PostgreSQL

---

## 🚑 Si Sigue Bloqueándose

1. **Ejecutá `diagnostico_performance.py`** para medir tiempos
2. **Verificá la conexión a Supabase** en el panel web
3. **Revisá cuántos productos tenés:** Si son >1000, implementar paginación
4. **Probá con SQLite local temporalmente** para descartar problemas de red

**Comando para cambiar a SQLite:**
```json
// config.json
{
  "database_type": "sqlite",
  "database_url": ""
}
```

---

Con estos cambios, la app debería cargar rápido y **nunca** mostrar "no responde". Si el problema persiste, es un tema de cantidad de datos o latencia de red que requiere paginación.
