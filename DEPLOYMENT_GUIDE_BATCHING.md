# 📋 GUÍA DE DEPLOYMENT - BATCHING PARA SUPABASE FREE TIER

## 1. Pre-Deployment Checklist

### A. Verificar que Todos los Tests Pasen
```bash
cd c:\Users\USUARIO\Desktop\Manarey
python -m unittest discover tests -v
# Esperado: 36/36 tests (35 ✓, 1 bajo priority)
```

### B. Ejecutar Demo End-to-End
```bash
python demo_batching.py
# Esperado: ✅ DEMOSTRACIÓN COMPLETADA EXITOSAMENTE
```

### C. Verificar Migración
```bash
# Para SQLite (automático en init_db):
python -c "from models.db import init_db; init_db()" && echo "✓ SQLite OK"

# Para Postgres (si aplica):
python migrations/m0002_pending_increments.py
# Esperado: [Migration] pending_increments created successfully
```

---

## 2. Configuración de Variables de Entorno

### Para Cada Local (Windows):

#### Opción A: Archivo `.env` (Recomendado)
```ini
# .env en raíz del proyecto
DATABASE_URL=postgresql://user:pass@supabase.host/dbname
MANAREY_PG_POOL_MAX=4
MANAREY_LOGLEVEL=INFO
```

#### Opción B: Batch Script (Windows)
```batch
@echo off
REM config.bat - ejecutar antes de iniciar la aplicación

set DATABASE_URL=postgresql://user:pass@supabase.host/dbname
set MANAREY_PG_POOL_MAX=4
set MANAREY_LOGLEVEL=INFO

echo Iniciando Manarey...
python app.py
```

#### Opción C: PowerShell
```powershell
$env:DATABASE_URL = "postgresql://user:pass@supabase.host/dbname"
$env:MANAREY_PG_POOL_MAX = "4"
$env:MANAREY_LOGLEVEL = "INFO"

python app.py
```

---

## 3. Estrategia de Migración (Por Ubicación)

### Paso 1: Setup en Servidor de Desarrollo
```bash
# En tu PC de desarrollo:
cd c:\Users\USUARIO\Desktop\Manarey

# Actualizar código
git pull  # si usas git
# o copiar archivos manualmente

# Crear tabla pending_increments
python migrations/m0002_pending_increments.py

# Ejecutar tests
python -m unittest discover tests -v
```

### Paso 2: Deploy a Mueblería 1 (Piloto)
```bash
# 1. Copiar archivos actualizados:
#    - utils/stock_async.py
#    - utils/rate_limiter.py
#    - utils/pending_increments_processor.py
#    - models/db.py
#    - migrations/m0002_pending_increments.py
#    - Todos los cambios

# 2. Crear/actualizar config en Mueblería 1
#    - Configurar DATABASE_URL en .env o batch script
#    - Establecer MANAREY_PG_POOL_MAX=4

# 3. Probar en la mueblería
#    - Ejecutar demo_batching.py para validar
#    - Hacer 10-20 transacciones de prueba
#    - Monitorear logs por "pending_increments"

# 4. Monitorear durante 1 semana:
#    - Ver si hay errores en logs
#    - Verificar cantidad de conexiones simultáneas
#    - Checar que batches se procesan cada 2 segundos

# 5. Si OK → proceder con Mueblería 2-5
# 6. Si NO → rollback a versión anterior, investigar
```

### Paso 3: Rollout Gradual (Semanas 1-3)
```
Semana 1: Mueblería 1 (Cane) → Piloto
Semana 2: Mueblería 2-3 (Vidriera, Longchamps) → Validación
Semana 3: Mueblería 4-5 (Glew, etc) → Producción
```

---

## 4. Monitoreo Post-Deployment

### A. Logs del Worker (En Vivo)
```bash
# Ver logs de batching:
tail -f logs/manarey.log | grep "pending_increments"

# Esperado: cada 2 segundos debería ver:
# INFO:utils.pending_increments_processor:Processed pending_increments: X productos, Y items
```

### B. Stats de Pending Increments (En Terminal)
```python
# Ejecutar en una ventana de terminal:
python -c "
from utils.pending_increments_processor import get_pending_increments_stats
import time
while True:
    stats = get_pending_increments_stats()
    print(f'{time.strftime(\"%H:%M:%S\")} - Items: {stats[\"total_items\"]}, \
Delta: {stats[\"total_delta\"]}, Productos: {stats[\"num_productos\"]}')
    time.sleep(5)
"
```

### C. Conexiones Supabase (Dashboard)
1. Ir a Supabase Dashboard → Project → Database → Connections
2. Monitorear "Active Connections" (debe estar < 30 para 5 locales)
3. Si sube > 40: revisar logs, puede haber problema de rate-limit

### D. Queries SQL para Verificar
```sql
-- Ver tabla pending_increments
SELECT COUNT(*) as items, SUM(delta) as total_delta 
FROM pending_increments;
-- Esperado: bajo (< 100) después de cada batch (cada 2s)

-- Ver historial batch
SELECT accion, COUNT(*) as count 
FROM historial_stock 
WHERE meta LIKE '%pending_increments%' 
GROUP BY accion;
-- Esperado: acción='suma' apareciendo regularmente

-- Ver productos con cambios batch
SELECT producto_id, detalle, cantidad, created_at 
FROM historial_stock 
WHERE meta LIKE '%pending_increments%' 
ORDER BY created_at DESC 
LIMIT 20;
```

---

## 5. Troubleshooting

### Problema: "table pending_increments does not exist"
```bash
# Solución: Crear tabla manualmente
python migrations/m0002_pending_increments.py

# O en SQLite (si no tienes Python):
sqlite3 manarey.db < migrations/m0002_pending_increments.sql
```

### Problema: Rate-limit muy agresivo (operaciones lentas)
```bash
# Causa: Token-bucket rate puede ser muy bajo
# Solución: Aumentar rate

# Editar: utils/stock_async.py, línea ~35
# Cambiar: TokenBucket(rate=10.0, capacity=20)
# A:       TokenBucket(rate=20.0, capacity=40)
```

### Problema: Pool de Postgres agotado
```bash
# Síntoma: "could not connect to the database"
# Causa: MANAREY_PG_POOL_MAX muy bajo
# Solución:

# Opción A: Aumentar pool size
export MANAREY_PG_POOL_MAX=6  # En lugar de 4

# Opción B: Reducir concurrencia en el sistema
# - Menos workers corriendo
# - Menos clientes simultáneos
# - Aumentar batch processing interval de 2s a 5s
```

### Problema: Batches no se procesan cada 2 segundos
```bash
# Síntoma: logs muestran "Processed pending_increments: 0 productos"
# Causa: Podría ser que no hay increments (normal)
# Solución: Hacer algunos increments y verificar

# Test:
from utils.stock_async import StockAsyncWorker
worker = StockAsyncWorker('test', 'Cane')
worker.enqueue_operation('increment', {'producto_id': 1, 'delta': 5})
# Esperar 2 segundos
# Verificar logs
```

### Problema: Stats devuelve error
```python
# Síntoma: get_pending_increments_stats() retorna {"error": "..."}
# Causa: Tabla no existe o permiso denegado
# Solución:

# A. Verificar tabla existe
SELECT * FROM pending_increments LIMIT 1;

# B. Si no existe:
python migrations/m0002_pending_increments.py

# C. Si permiso denegado:
# - Verificar que usuario Postgres tiene permisos
# - Re-crear tabla con permisos correctos
```

---

## 6. Rollback Plan (Si Falla)

### Opción 1: Revert de Código (Rápido)
```bash
# 1. Restaurar archivos anteriores:
git checkout HEAD~1 -- utils/stock_async.py utils/rate_limiter.py ...
# o copiar versión .bak manualmente

# 2. Reiniciar app
python app.py

# 3. Nota: pending_increments tabla queda pero no se usa
```

### Opción 2: Eliminar Tabla (Si Necesario)
```sql
-- En Postgres/SQLite:
DROP TABLE IF EXISTS pending_increments;

-- Recrear usando versión anterior (sin batching)
```

### Opción 3: Revert Completo
```bash
# Si tienes respaldo de git:
git revert <commit-hash-batching>

# Si tienes backup de BD:
# Restaurar DB desde backup anterior
```

---

## 7. Validación Post-Rollout

### Después de 24 Horas:
- [ ] Cero errores en logs relacionados con pending_increments
- [ ] Conexiones Supabase < 30 (para 5 locales)
- [ ] Ventas procesadas correctamente
- [ ] Historial accurado (batch entries aparecen)

### Después de 1 Semana:
- [ ] Performance estable
- [ ] Usuarios reportan que app es más rápida
- [ ] Zero crashes relacionados con batching
- [ ] Pool de Postgres nunca agotado

### Después de 1 Mes:
- [ ] Confianza de tener todo en producción
- [ ] Poder documentar lecciones aprendidas
- [ ] Preparar para optimizaciones futuras (RPC, etc)

---

## 8. Performance Expectations

### Metrics a Monitorear:

| Métrica | Target | Aceptable | Alerta |
|---------|--------|-----------|--------|
| Conexiones simultáneas | <15 | <25 | >30 |
| Items en pending_increments | <5 | <50 | >100 |
| Batch processing time | <10ms | <50ms | >100ms |
| Op queue size | <10 | <20 | >50 |
| DB response time | <100ms | <500ms | >1s |

### Velocidad Esperada:
- Increments: callback inmediato (< 50ms)
- Otros ops: procesados en < 5s (con rate-limit)
- Batch apply: < 10ms por batch

---

## 9. Escalación Futura

### Si Supabase Free Sigue siendo Cuello de Botella:

**Opción 1: Upgrade a Postgres Pro** (~$25/mes)
- Aumentar MANAREY_PG_POOL_MAX a 20
- Rate-limit a 50 ops/sec
- Sin cambios en código

**Opción 2: RPC Batch Endpoint** (más avanzado)
```sql
-- Crear RPC en Supabase:
CREATE FUNCTION manarey_batch_increments(
    updates JSONB
) RETURNS TABLE (updated INTEGER) AS $$
    -- Aplicar todos UPDATEs en 1 transacción
    -- Más eficiente que N UPDATEs individuales
$$ LANGUAGE plpgsql;
```

**Opción 3: Multi-Region** (si Supabase lo permite)
- Réplicas en diferentes regiones
- Cada local conecta a la réplica más cercana
- Reduce latencia

---

## 10. Checklist Final

Antes de hacer go-live:

- [ ] Todos los tests pasan (36/36)
- [ ] Demo batching ejecuta exitosamente
- [ ] Tabla pending_increments creada en todas las BDs
- [ ] MANAREY_PG_POOL_MAX=4 configurado en cada local
- [ ] Logs habilitados (MANAREY_LOGLEVEL=INFO)
- [ ] Monitoreo de Supabase dashboard habilitado
- [ ] Equipo entrenado en troubleshooting
- [ ] Rollback plan documentado y probado
- [ ] Backup de BD actual hecho
- [ ] Notificación a usuarios sobre potencial timing change

---

**DEPLOYMENT READY: ✅ GO/NO-GO DECISION**

Si todos los checkboxes están ✓ → **SAFE TO DEPLOY**

Si alguno está pendiente → **HOLD DEPLOYMENT**

---

**Contacto para Problemas:** Tu equipo DevOps / Sistema
**Documentación:** IMPLEMENTACION_BATCHING_SUPABASE.md, RESUMEN_BATCHING_COMPLETO.md
