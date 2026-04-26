# 🚀 Guía Completa: Configurar Supabase para Manarey

## 📋 ¿Qué vas a lograr?

Al terminar esta guía, tendrás:
- ✅ Base de datos PostgreSQL en la nube (GRATIS)
- ✅ Sincronización automática entre todas las PCs
- ✅ Acceso desde cualquier lugar con WiFi
- ✅ Backups automáticos incluidos
- ✅ Hasta 500MB gratis (≈200,000 productos)

**Tiempo estimado:** 10 minutos

---

## 📝 Paso 1: Crear cuenta en Supabase

1. **Entrá a:** https://supabase.com

2. Hacé clic en **"Start your project"** (Comenzar tu proyecto)

3. Elegí cómo registrarte:
   - Con GitHub (recomendado)
   - Con Google
   - Con email

4. Confirmá tu email si te lo pide

---

## 🏗️ Paso 2: Crear tu Proyecto

1. Una vez dentro, hacé clic en **"New Project"** (Nuevo Proyecto)

2. Completá los datos:
   - **Name** (Nombre): `manarey-db` (o el que quieras)
   - **Database Password** (Contraseña): una contraseña segura
     - ⚠️ **ANOTÁ ESTA CONTRASEÑA**, la vas a necesitar
   - **Region** (Región): Elegí la más cercana
     - Si hay "South America (São Paulo)" elegí esa
     - Si no, elegí "East US (North Virginia)"
   - **Pricing Plan**: Dejá "Free" (Gratis)

3. Hacé clic en **"Create new project"** (Crear proyecto)

4. **Esperá 2-3 minutos** mientras se crea el proyecto
   - Vas a ver una barra de progreso
   - Cuando termine, aparecerá el dashboard del proyecto

---

## 🔗 Paso 3: Obtener la URL de Conexión

1. En el panel izquierdo, hacé clic en **"Settings"** (Configuración)
   - Es el ícono de engranaje ⚙️

2. En el menú de Settings, hacé clic en **"Database"**

3. Buscá la sección **"Connection String"** (Cadena de Conexión)

4. Dentro vas a ver diferentes formatos. Hacé clic en **"URI"**

5. Vas a ver algo así:
   ```
   postgresql://postgres.[TU-PROYECTO]:[TU-CONTRASEÑA]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

6. Hacé clic en el botón **"Copy"** (Copiar) al lado de la URL

7. **MUY IMPORTANTE:** 
   - La URL tiene `[YOUR-PASSWORD]` en el medio
   - Reemplazá `[YOUR-PASSWORD]` con la contraseña que pusiste en el Paso 2
   - Por ejemplo, si tu contraseña es `MiPass123`, cambiá:
     ```
     postgres:[YOUR-PASSWORD]@aws
     ```
     Por:
     ```
     postgres:MiPass123@aws
     ```

---

## 💻 Paso 4: Configurar Manarey

### Opción A: Primera instalación

1. Abrí Manarey por primera vez

2. Te va a aparecer la ventana de configuración automáticamente

3. Seleccioná **"☁️ Base de Datos en la Nube (PostgreSQL/Supabase)"**

4. Pegá la URL completa que copiaste (con tu contraseña)

5. Hacé clic en **"🔌 Probar Conexión"** para verificar

6. Si funciona, hacé clic en **"💾 Guardar y Continuar"**

### Opción B: Ya tenés Manarey instalado

1. Cerrá Manarey si está abierto

2. Abrí el archivo `config.json` que está en la carpeta de Manarey

3. Cambiá el contenido a:
   ```json
   {
     "database_type": "postgresql",
     "database_url": "TU-URL-COMPLETA-AQUÍ"
   }
   ```

4. Guardá el archivo

5. Abrí Manarey

---

## 📦 Paso 5: Migrar Datos Existentes (Opcional)

**Si ya tenías productos/ventas en SQLite local:**

1. Cerrá Manarey

2. Buscá el archivo `migrate_to_postgres.py` en la carpeta de Manarey

3. Hacé doble clic en él (o ejecutalo desde terminal):
   ```
   python migrate_to_postgres.py
   ```

4. Seguí las instrucciones en pantalla:
   - Te va a pedir la URL de Supabase (pegala)
   - Confirmá que querés migrar
   - Esperá a que termine (puede tardar según cuántos datos tengas)

5. **Listo!** Todos tus datos ahora están en Supabase

---

## ✅ Verificación Final

### Probá la sincronización:

1. **En la PC A:**
   - Abrí Manarey
   - Agregá un producto de prueba: "PRUEBA SYNC"
   - Cerrá Manarey

2. **En la PC B** (otra computadora):
   - Instalá Manarey
   - Configurá con la MISMA URL de Supabase
   - Abrí la app e iniciá sesión
   - Buscá el producto "PRUEBA SYNC"

3. **Si lo ves → ¡FUNCIONA!** 🎉
   - Ambas PCs ahora comparten la misma base de datos
   - Cualquier cambio en una se refleja en la otra

---

## 🔧 Solución de Problemas

### Error: "No se pudo conectar"

**Posibles causas:**

1. **URL incorrecta**
   - Verificá que copiaste la URL completa
   - Asegurate de haber reemplazado `[YOUR-PASSWORD]` con tu contraseña real

2. **Contraseña incorrecta**
   - La contraseña es case-sensitive (distingue mayúsculas)
   - Si la olvidaste, podés resetearla en Settings → Database → Reset password

3. **Falta psycopg2**
   - Abrí terminal en la carpeta de Manarey
   - Ejecutá: `pip install psycopg2-binary`

### Error: "Permission denied"

- Revisá que tu usuario de Supabase tenga permisos
- Intentá crear el proyecto de nuevo con otro nombre

### La sincronización es lenta

- Normal: cada cambio viaja a la nube y vuelve (100-300ms)
- Si es muy lento, verificá tu conexión a internet
- Considerá usar el plan pago ($25/mes) para mejor rendimiento

---

## 📊 Monitoreo del Proyecto

### Ver cuánto espacio estás usando:

1. En Supabase, andá a **"Settings"** → **"Usage"**

2. Vas a ver:
   - Database size (Tamaño de la base de datos)
   - Rows (Cantidad de filas)
   - Storage (Almacenamiento usado)

3. El plan gratis incluye:
   - 500 MB de base de datos
   - 1 GB de almacenamiento de archivos
   - 2 GB de transferencia mensual

### ¿Qué pasa si te quedás sin espacio?

- Opción 1: Borrar datos viejos (historial antiguo, etc.)
- Opción 2: Pasar al plan Pro ($25/mes = 8 GB)
- Opción 3: Migrar a tu propia PC como servidor

---

## 🎓 Próximos Pasos

Una vez que tenés Supabase funcionando:

1. **Instalá Manarey en todas las PCs** que quieras
   - Usá la MISMA URL de conexión en todas
   - Todas verán los mismos datos

2. **Creá backups regulares** (opcional)
   - Supabase hace backups automáticos
   - Pero podés descargar un backup manual en Settings → Database

3. **Monitoreá el uso**
   - Revisá cada mes cuánto espacio usás
   - Si te acercás al límite, optimizá o upgradea

4. **Disfrutá la sincronización!**
   - Agregá un producto en un local → aparece en todos
   - Hacé una venta → se actualiza el stock en tiempo real
   - Todo funciona automáticamente ✨

---

## 💡 Consejos Pro

1. **Guardá la URL en un lugar seguro**
   - Cualquiera con la URL puede acceder a tu base de datos
   - Tratala como una contraseña

2. **Cambiá la contraseña periódicamente**
   - En Settings → Database → Reset password
   - Después actualizá la URL en todas las PCs

3. **Hacé backups antes de cambios grandes**
   - En Settings → Database → Create backup

4. **Monitoreá los logs**
   - En el dashboard podés ver todas las consultas
   - Útil para debugging

---

## 🆘 Soporte

**Si algo no funciona:**

1. Revisá esta guía de nuevo paso por paso
2. Verificá que la URL sea correcta (sin espacios, con tu contraseña)
3. Probá la conexión desde el botón "Probar Conexión"
4. Revisá los logs de Supabase en Dashboard → Logs

**Documentación oficial de Supabase:**
- https://supabase.com/docs
- https://supabase.com/docs/guides/database

---

## 🎉 ¡Listo!

Ahora tenés Manarey funcionando con Supabase. Todas tus PCs están sincronizadas y podés trabajar desde cualquier lugar.

**¡A vender!** 🚀
