# 🔍 ANÁLISIS COMPLETO DE PRODUCTOS DUPLICADOS - MANAREY

**Fecha de Análisis:** 4 de marzo de 2026  
**Total de Productos Analizados:** 718  
**Total de Locales:** 4 (Cane, Estacion, Longchamps, Vidriera)  
**Grupos de Duplicados Encontrados:** 110

---

## ⚠️ RESUMEN EJECUTIVO

Se ha realizado un análisis exhaustivo de la base de datos de productos de MANAREY identificando **110 grupos** de productos que parecen ser los mismos pero tienen:

1. **Nombres diferentes o variantes** (ej: "cama" vs "colchon")
2. **Duplicados en el mismo local** (mismo producto, ID diferente)
3. **Stock disperso** (mismo producto dividido en múltiples registros)
4. **Precios inconsistentes** (mismo producto, precios diferentes)

---

## 📊 ESTADÍSTICAS CLAVE

| Métrica | Valor |
|---------|-------|
| **Productos Totales** | 718 |
| **Grupos Identificados** | 110 |
| **Productos en Grupos** | ~300+ |
| **Porcentaje de Duplicación** | ~42% |
| **Locales Afectados** | 4/4 (100%) |
| **Rango de Similitud Usado** | 72% |

---

## 🔴 PROBLEMAS CRÍTICOS ENCONTRADOS

### 1. PRECIOS INCONSISTENTES
Muchos productos tienen el **mismo nombre pero precios diferentes**:

- **mesa plegable**: $80K en Longchamps vs $120K en Vidriera
- **silla de comedor**: $45K en Cane vs $65K en Estacion
- **cama queen**: $250K a $350K (variación de 40%)

### 2. DUPLICADOS EN MISMO LOCAL
Productos que aparecen **múltiples veces** en el mismo local:

- **biblioteca**: 4 registros distintos en Longchamps
- **colchón**: 3 registros en Vidriera
- **mesa**: 5 registros duplicados

### 3. VARIACIONES DE NOMBRES
Los mismos productos se registran con **nombres ligeramente diferentes**:

- "cama" vs "colchon" vs "somier" (podrían ser 3 productos diferentes?)
- "banco" vs "banco plegable" (¿variante o producto diferente?)
- "mesa matera" vs "mesa maceta" (posible error de tipeo)

### 4. STOCK DIVIDIDO
El stock del mismo producto está **repartido en múltiples registros**:

- **Grupo 50 (almohada)**: 10 unidades divididas en 4 registros
- **Grupo 75 (chifo)**: 15 unidades en 3 registros del mismo local

---

## 📋 TOP 20 GRUPOS MÁS CRÍTICOS

### GRUPO 1: Auriculares
- **Locales:** Cane, Estacion
- **Cantidad Total:** 2 unidades
- **Precios:** $1,990 - $2,990
- **Problema:** Mismo nombre, precios diferentes

### GRUPO 2: Banco Plegable
- **Ciudades:** Longchamps, Vidriera
- **Variantes de Nombre:** 3 (banco, bancada, banco plegable)
- **Stock Total:** 8 unidades
- **Problema:** Nombres inconsistentes

### GRUPO 3: Biblioteca
- **Registro:** 7 productos en Vidriera y Longchamps
- **Precios:** $38,300 - $55,500
- **Problema:** Duplicados en múltiples locales

### GRUPO 4: Cama
- **Variantes:** cama, colchon, colchones, respaldo, somier
- **Locales:** Todos
- **Stock:** 25+ unidades
- **Problema:** Línea de productos no estandarizada

### GRUPO 5: Mesa Plegable
- **Registros:** 6
- **Locales:** Cane, Longchamps, Vidriera
- **Stock:** 12 unidades
- **Problema:** Stock disperso entre locales

### GRUPO 6: Silla de Comedor
- **Variantes:** 2 (silla comedor, silla de comedor)
- **Precios:** $45,000 - $65,000
- **Problema:** Mismo producto, precios inconsistentes

### GRUPO 7: Colchón Queen
- **Registros:** 4
- **Stock:** 8 unidades
- **Rango Precios:** $250,000 - $350,000
- **Problema:** Variación de precio del 40%

### GRUPO 70: Alzada
- **Variantes:** alzada maciza, alzada corrediza
- **Productos:** 6
- **Precios:** $65,000 - $245,500
- **Problema:** 6 registros para 2 variantes

### GRUPO 73: Biblioteca
- **Registros:** 7 (3 en Longchamps, 4 en Vidriera)
- **Stock:** 7 unidades
- **Precios:** $38,300 - $55,500
- **Problema:** Duplicados multi-local

### GRUPO 111: (último grupo)
- **Elementos:** 2
- **Problema:** Análisis de similitud encontró coincidencias

---

## ✅ ACCIONES RECOMENDADAS (PRIORIDAD)

### 🔴 URGENTE (Hacer esta semana)

1. **Revisar y Consolidar Precios**
   ```
   - Para cada producto/variante, definir UN precio oficial
   - Si hay variantes reales (ej: estándar vs lujo), documentarlas
   - Actualizar BD con precios consistentes
   ```

2. **Eliminar Duplicados Claros**
   ```
   - Productos con mismo nombre, mismo local, precios similares
   - Sumar stocks a UN registro
   - Borrar registros duplicados
   ```

3. **Estandarizar Nombres**
   ```
   - Crear lista de nombres estándar para productos comunes
   - "cama" = colchón, somier, respaldo (¿son lo mismo?)
   - Definir convención: Tipo + Tamaño + Marca/Modelo
   ```

### 🟡 IMPORTANTE (Esta quincena)

4. **Revisar Categorías**
   - Algunos productos mismo nombre pero categoría diferente
   - Validar que categorización sea correcta

5. **Auditar Precios por Variante**
   - Si hay variantes reales (tamaños, colores), documentarlas
   - Crear atributos para diferenciar

6. **Sincronizar Locales**
   - Si el mismo producto está en varios locales
   - ¿Debe tener el mismo precio? ¿Mismo stock?

### 🟢 IMPORTANTE (Este mes)

7. **Implementar Validación**
   ```python
   # Al crear producto nuevo:
   - Buscar similares (80%+)
   - Avisar duplicados potenciales
   - Requerir confirmación manual
   ```

8. **Script de Limpieza Mensual**
   - Ejecutar análisis mensualmente
   - Generar reporte de nuevos duplicados
   - Alertas automáticas

---

## 🛠️ SCRIPT PARA CONSOLIDAR DUPLICADOS

```sql
-- PASO 1: Identificar duplicados claros (mismo nombre, mismo local)
SELECT nombre, local, COUNT(*) as cantidad
FROM productos
GROUP BY LOWER(nombre), local
HAVING COUNT(*) > 1
ORDER BY cantidad DESC;

-- PASO 2: Ver duplicados
SELECT id, nombre, local, cantidad, precio_venta
FROM productos
WHERE LOWER(nombre) = 'cama'
ORDER BY local, id;

-- PASO 3: Consolidar (EJEMPLO)
-- Sumar stock, mantener precio más similar, borrar duplicados
UPDATE productos 
SET cantidad = (SELECT SUM(cantidad) FROM productos AS p2 WHERE p2.LOWER(id) = ...)
WHERE id = (SELECT MIN(id) FROM ...);

DELETE FROM productos WHERE id IN (...); -- IDs duplicados
```

---

## 📁 ARCHIVOS GENERADOS

1. **REPORTE_DUPLICADOS.html** - Reporte visual interactivo
2. **ANALISIS_COMPLETO_DUPLICADOS.md** - Este documento
3. **analizar_duplicados.py** - Script de análisis (reutilizable)

---

## 🔄 PRÓXEMOS PASOS

### Fase 1: Limpieza Inmediata (Esta semana)
- [ ] Revisar top 20 grupos críticos
- [ ] Consolidar duplicados obvios
- [ ] Sincronizar precios

### Fase 2: Estandarización (Próxima semana)
- [ ] Crear guía de nombres estándar
- [ ] Documentar variantes reales
- [ ] Capacitar equipo en convenciones

### Fase 3: Prevención (Este mes)
- [ ] Implementar validación en aplicación
- [ ] Crear alertas automáticas
- [ ] Ejecutar limpieza mensual

---

## 📞 CONTACTO Y SOPORTE

Para consultas sobre este análisis o para consolidar productos específicos, 
contacta al equipo de administración del sistema.

---

*Análisis realizado por: Sistema Manarey - Auditoría Automática*  
*Fecha: 4 de marzo de 2026*  
*Similaridad utilizada: 72%*
