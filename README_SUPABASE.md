# 🎯 Configuración Rápida de Supabase

## ¿Qué es esto?

Manarey ahora soporta **sincronización en la nube** usando Supabase (PostgreSQL).

**Esto significa:**
- ✅ Todas las PCs comparten la misma base de datos
- ✅ Si agregás un producto en una PC, aparece en TODAS
- ✅ Stock sincronizado en tiempo real
- ✅ Plan GRATUITO hasta 500MB

---

## 🚀 Inicio Rápido (5 minutos)

### 1. Instalar dependencias

Abrí terminal en la carpeta de Manarey y ejecutá:

```bash
pip install -r requirements.txt
```

Esto instala `psycopg2-binary` que se necesita para PostgreSQL.

### 2. Configurar Supabase

**Método 1: Interfaz gráfica (Recomendado)**

1. Ejecutá:
   ```bash
   python -m views.database_config_view
   ```

2. Seleccioná "☁️ Base de Datos en la Nube"

3. Pegá tu URL de Supabase

4. Hacé clic en "Probar Conexión"

5. Guardar y listo!

**Método 2: Manual**

Editá `config.json`:

```json
{
  "database_type": "postgresql",
  "database_url": "postgresql://postgres.xxxxx:tu-password@xxxxx.supabase.co:5432/postgres"
}
```

### 3. Migrar datos existentes (Opcional)

Si ya tenías datos en SQLite local:

```bash
python migrate_to_postgres.py
```

Seguí las instrucciones en pantalla.

---

## 📖 Guía Completa

Leé **GUIA_SUPABASE.md** para instrucciones paso a paso con capturas.

Incluye:
- Cómo crear cuenta en Supabase
- Dónde obtener la URL de conexión
- Cómo verificar que funciona
- Solución de problemas

---

## 🔄 Volver a SQLite Local

Si querés volver a usar SQLite local (sin sincronización):

**Método 1: Interfaz gráfica**
```bash
python -m views.database_config_view
```
Seleccioná "🖥️ Base de Datos Local (SQLite)"

**Método 2: Manual**

Editá `config.json`:
```json
{
  "database_type": "sqlite",
  "database_url": ""
}
```

---

## ⚡ Comandos Útiles

### Verificar conexión actual
```bash
python -c "from models.db import is_postgres; print('PostgreSQL' if is_postgres() else 'SQLite')"
```

### Abrir configurador
```bash
python -m views.database_config_view
```

### Migrar a PostgreSQL
```bash
python migrate_to_postgres.py
```

### Backup de SQLite local
```bash
# Windows
copy manarey.db manarey_backup_%date%.db

# Linux/Mac
cp manarey.db manarey_backup_$(date +%Y%m%d).db
```

---

## 🆘 Problemas Comunes

### "No module named 'psycopg2'"

Solución:
```bash
pip install psycopg2-binary
```

### "Connection refused"

- Verificá que la URL de Supabase sea correcta
- Verificá que hayas reemplazado `[YOUR-PASSWORD]` con tu contraseña real
- Verificá tu conexión a internet

### "Permission denied"

- Verificá que la contraseña en la URL sea correcta
- Probá resetear la contraseña en Supabase

### Muy lento

- Normal: la nube tiene 100-300ms de latencia
- Si es intolerable, considerá PC como servidor local
- O upgradea al plan Pro de Supabase

---

## 📊 Límites del Plan Gratuito

| Recurso | Límite |
|---------|--------|
| Tamaño DB | 500 MB |
| Productos estimados | ~200,000 |
| Transferencia mensual | 2 GB |
| Conexiones simultáneas | 60 |
| Backups | 7 días |

¿Necesitás más? → Plan Pro: $25/mes (8GB de DB)

---

## 🎓 Más Información

- **Guía completa:** GUIA_SUPABASE.md
- **Docs de Supabase:** https://supabase.com/docs
- **Precios:** https://supabase.com/pricing

---

## ✅ Checklist de Instalación

- [ ] `pip install -r requirements.txt` ejecutado
- [ ] Cuenta de Supabase creada
- [ ] Proyecto de Supabase creado
- [ ] URL de conexión copiada
- [ ] Contraseña reemplazada en la URL
- [ ] `config.json` configurado
- [ ] Conexión probada (botón "Probar Conexión")
- [ ] Datos migrados (si los tenías)
- [ ] Probado en 2 PCs diferentes
- [ ] Sincronización verificada

---

¡Listo! Ahora tenés Manarey sincronizado en la nube 🎉
