DEPLOY QUEUE (Worker) - Manarey

Resumen

Este documento explica cómo desplegar y ejecutar el worker de procesamiento de la cola de stock (`op_queue`) en entornos locales, Windows y en plataformas que usan PostgreSQL/Supabase.

Archivos relevantes

- `models/stock_queue_api.py` - API para encolar operaciones y procesarlas (funciones: enqueue_op, process_queue_once, execute_increment, execute_add_product).
- `scripts/stock_queue_worker.py` - entrada para ejecutar el worker en modo continuo.
- `models/db.py` - manejador de conexión (detecta Postgres vía `DATABASE_URL` o usa SQLite local `manarey.db`).

Requisitos

- Python 3.10+ (la base usa 3.13 en desarrollo), virtualenv recomendado.
- Dependencias listadas en `requirements.txt` (instalar en entorno virtual):
  - reportlab (opcional para generar boletas)
  - psycopg2-binary (solo si usas PostgreSQL / Supabase)

Comandos básicos (desarrollo local)

1. Activar virtualenv (Windows PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

2. Ejecutar worker en primer plano (modo development, re-usar ventana):

```powershell
python -m scripts.stock_queue_worker
```

3. Ejecutar worker en segundo plano (PowerShell):

```powershell
Start-Process -FilePath python -ArgumentList '.\scripts\stock_queue_worker.py' -NoNewWindow
```

4. Ejecutar single-run (procesar una vez) para pruebas:

```powershell
python -c "from models.stock_queue_api import process_queue_once; print(process_queue_once())"
```

Notas para Supabase / Postgres free-tier

- Supabase impone límites de conexiones; recomendamos reducir el pool de conexiones cuando despliegues muchas instancias.
- Configura la variable de entorno `DATABASE_URL` apuntando a tu instancia Postgres. `models/db.py` detectará Postgres y usará psycopg2.
- Ajustes recomendados para entornos con límites (ejemplo para Supabase):
  - MANAREY_PG_POOL_MAX=6
  - MANAREY_PG_POOL_RETRIES=3
  - MANAREY_PG_POOL_DELAY=0.2

- Si tienes problemas SSL con psycopg2 en Windows, revisa la configuración de `sslmode` o el `sslrootcert`. Para pruebas locales puedes configurar `sslmode=disable` en la URL, pero no es recomendable en producción.

Estrategia de despliegue

- Worker único por mueblería: en mueble's deployments, corre un worker por mueblería si tienes tráfico moderado.
- Workers múltiples: asegúrate de configurar `MANAREY_PG_POOL_MAX` para que el total máximo de conexiones simultáneas no supere el límite del host. Ejemplo: 2 workers con pool=5 resultan 10 conexiones.

Consideraciones de fiabilidad

- El worker implementa reintentos (hasta 5 attempts) y marca como failed si excede el tope.
- Las operaciones críticas usan `execute_increment` y `execute_add_product`, que son atómicas y pueden ejecutarse sin depender de `models.stock_model`.

Monitorización y mantenimiento

- Revisa la tabla `op_queue` para pendientes, fallos y reintentos (`status`): 0=pending,1=processing,2=done,3=failed.
- Para limpiar items completados puedes usar un script simple que borre `status=2` si ya no los necesitas.

Ejemplo: servicio Windows (opcional)

Usa `nssm` o el Programador de tareas para lanzar `python -m scripts.stock_queue_worker` al inicio del sistema.

Resumen operativo

- Para un despliegue en Supabase: configurar `DATABASE_URL`, ajustar `MANAREY_PG_POOL_MAX` y asegurarse de instalar `psycopg2-binary`.
- Para desarrollo local: usar SQLite (por defecto `models/db.py` apunta a `manarey.db`) y ejecutar worker en background con `Start-Process`.

Problemas comunes

- "database is locked" en SQLite: ocurre si intentas encolar desde dentro de la misma transacción que crea la venta. Solución: encolar después del commit (ya implementado en `models/ventas_model.py`).
- Mismatch entre `db.py` raíz y `models/db.py`: usar siempre `models.db.get_connection()` para consistencia.

Contacto

Si necesitas adaptar el worker a un sistema de colas externo (Redis, RabbitMQ), puedo ayudarte a generar adaptadores.
