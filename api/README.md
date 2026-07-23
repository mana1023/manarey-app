# API de Manarey

Servidor que usa la app del celular del jefe.

## Para qué existe

El celular **no puede** llevar la contraseña de la base adentro: cualquiera
podría extraerla del APK y tendría acceso total al negocio. Esta API guarda
esa contraseña del lado del servidor y le entrega al celular solo lo que pide.

Además **reutiliza los `models/` de la app de escritorio**, así:

- El celular usa las mismas reglas de negocio (historial de stock, reservas,
  combos, sincronización de precios entre locales).
- La boleta y el remito salen **idénticos** a los de la PC, porque los genera
  el mismo `boletas_model.py` / `remitos_model.py`.
- Si mañana cambiás el diseño de la boleta en la PC, el celular se actualiza
  solo. No hay dos versiones que se despeguen.

Por eso vive **dentro** de este repo y no en uno aparte.

## Variables de entorno

| Variable | Para qué | Obligatoria |
|---|---|---|
| `DATABASE_URL` | Conexión a Postgres/Supabase | Sí |
| `MANAREY_API_TOKEN` | Clave que usa la app para identificarse | Sí en producción |
| `MANAREY_ENTORNO` | Poner `produccion` para exigir el token | Recomendada |

## Correr en la PC (desarrollo)

```bash
uvicorn api.main:app --reload --port 8000
```

## Correr en un servidor

```bash
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Instalar dependencias con `pip install -r api/requirements.txt`.

## Seguridad

- Todo va por HTTPS (lo da el servidor donde se aloje).
- Cada pedido de la app lleva el token en la cabecera `Authorization`.
- En el celular, ese token queda protegido por la huella digital o el PIN.
- Si `MANAREY_ENTORNO=produccion` y falta el token, la API **no arranca**:
  es preferible que no levante a que quede abierta.
