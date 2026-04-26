Manarey — Notas rápidas de configuración

Este README explica cómo configurar la base de datos y dónde encontrar `config.json` en instalaciones empaquetadas.

1) `config.json`
- En desarrollo (ejecutando `app.py` desde el código fuente) el archivo `config.json` se encuentra en la raíz del proyecto: `./config.json`.
- En instalaciones empaquetadas (PyInstaller / instalador), la aplicación copia/usa `config.json` desde `%LOCALAPPDATA%/Manarey/config.json` (Windows). Si quieres forzar el uso de una base de datos remota, ajusta:

  {
    "database_type": "postgresql",
    "database_url": "postgresql://user:pass@host:port/dbname"
  }

- Si `database_type` es `sqlite` o está vacío, la app usará SQLite local.

2) Archivo de base de datos (SQLite)
- En desarrollo, la ruta por defecto usada por la app es `manarey.db` dentro del directorio del proyecto (ej: `C:\path\to\Manarey\manarey.db`).
- En la versión empaquetada en Windows, la ruta es:
  `%LOCALAPPDATA%\Manarey\manarey.db`
  Es decir: `C:\Users\<tu_usuario>\AppData\Local\Manarey\manarey.db`.

3) Usuarios y sincronización
- La app incluye usuarios semilla: `Administrador` (contraseña por defecto `lautaro10`) y usuarios de locales: `Cane`, `Vidriera`, `Longchamps`, `Glew` (contraseña por defecto `Manarey10`).
- Si en otra PC no puedes iniciar sesión con dichos usuarios, revisa qué base está usando la app (ver punto 1). Si apunta a Supabase/Postgres, la tabla `usuarios` en esa instancia determina las credenciales.
- Para sincronizar usuarios localmente puedes ejecutar el script `scripts/ensure_local_users.py` desde la carpeta del proyecto. Ejemplo (PowerShell):

```powershell
cd C:\ruta\a\Manarey
python .\scripts\ensure_local_users.py
```

4) Variables de entorno útiles (diagnóstico/control)
- `MANAREY_DEBUG=1` — activa mensajes de depuración en la ventana de login y genera logs de autenticación en `./logs/auth.log` (solo registra `username` y `reason`, nunca contraseñas).
- `MANAREY_RESEED_USERS=1` — al ejecutar `app.py` (o al llamar `init_db()`), forzará la restauración de los usuarios semilla (actualiza contraseña/role/local para los usuarios definidos).

- Para confirmación interactiva puedes ejecutar el script:

```powershell
python .\scripts\reseed_users.py
```

  El script preguntará si deseas proceder y luego aplicará el reseed (forzará la contraseña/role/local de los usuarios semilla).

7) Export / Import de usuarios
- Para exportar la tabla de usuarios a JSON:

```powershell
python .\scripts\export_users.py
```

- Para importar desde un JSON (hashará contraseñas no hasheadas automáticamente):

```powershell
python .\scripts\import_users.py
```

8) Hashing de contraseñas
- A partir de esta versión las contraseñas se almacenan como hash bcrypt.
- Si tu instalación tiene contraseñas en texto plano puedes migrarlas con:

```powershell
python .\scripts\hash_passwords.py
```


5) Notas de seguridad
- Por ahora las contraseñas se guardan en texto claro (como en la versión original). Se recomienda migrar a hashes (bcrypt/argon2) si el sistema se usa en producción o expone la DB.

6) Soporte
- Si necesitas que genere un instalador o que sincronice usuarios entre instancias Postgres/Supabase, puedo preparar scripts de export/import.

9) Actualizaciones (GitHub Releases + Supabase)
- Las actualizaciones ya no dependen de la misma red/WiFi.
- Crea un repositorio **publico** en GitHub (ej: `mana1023/manarey-updates`).
- Genera un **token** de GitHub con permiso `repo` y configuralo en la PC administradora.
- Ejecuta `actualizacion.bat` (o `actualizacion.ps1`). El script genera el instalador, lo sube a GitHub Releases y guarda el registro en la tabla `app_updates` en Supabase.
- Al abrir Manarey, los clientes consultan Supabase y muestran el aviso de actualizacion. Si lo cierran, queda un boton abajo a la izquierda para descargar.
- Si pasan 2 dias sin actualizar, la app se bloquea hasta que instalen la version nueva.

Ejemplo:
```powershell
setx GITHUB_REPO "mana1023/manarey-updates"
setx GITHUB_TOKEN "<tu_token>"
.ctualizacion.bat -Version 1.0.5 -Notes "Correcciones varias"
```

Opcional:
- `-SkipBuild` para no recompilar.
- `-Mandatory` para marcar la actualizacion como obligatoria inmediatamente.

