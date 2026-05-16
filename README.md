# Manarey — Sistema de Gestión Interna

Aplicación de escritorio para gestión de **stock, ventas y emisión de boletas**, desarrollada en Python con PyQt5. Utilizada diariamente en una empresa con 4 sucursales.

---

## Características principales

- **Gestión de stock y ventas** — alta, baja y modificación de productos, registro de ventas y generación de boletas en PDF
- **Sincronización offline/online** — funciona sin internet y sincroniza automáticamente con PostgreSQL al recuperar conexión
- **5 niveles de acceso** — 1 administrador general y 4 operadores por sucursal, con autenticación por usuario
- **Actualizaciones automáticas** — sistema de auto-update vía GitHub Releases; más de 87 versiones publicadas sin intervención presencial
- **Panel de administración** — gestión de usuarios, permisos, historial de movimientos y reportes
- **Testing automatizado** — suite de pruebas con pytest ejecutada antes de cada release

---

## Stack tecnológico

| Capa | Tecnologías |
|------|-------------|
| UI / Desktop | Python · PyQt5 |
| Base de datos | PostgreSQL · Supabase · SQLite (offline) |
| Testing | pytest · GitHub Actions |
| Build & Deploy | PyInstaller · NSIS · GitHub Releases · GitHub Actions |

---

## Arquitectura

```
app.py                  # Entry point
├── models/             # Lógica de negocio y acceso a datos
├── views/              # Pantallas (stock, ventas, admin, boletas...)
├── ui/                 # Componentes de interfaz reutilizables
├── workers/            # Procesamiento asíncrono (cola de operaciones)
├── utils/              # Utilidades (PDF, animaciones, escala, etc.)
├── migrations/         # Migraciones de base de datos
├── tests/              # Tests automatizados
├── updater.py          # Sistema de actualizaciones
└── build_release.py    # Pipeline de build y publicación
```

---

## Sistema de actualizaciones

Las sucursales reciben actualizaciones automáticamente al abrir la app:

1. La app consulta la [GitHub Releases API](https://api.github.com/repos/mana1023/manarey-updates/releases/latest)
2. Si hay versión nueva, descarga el instalador o un delta `.zip`
3. Se instala silenciosamente con UAC y la app se relanza sola

Para publicar una nueva versión desde la PC administradora:

```powershell
.\actualizacion.bat -Version 1.0.X -Notes "Descripción del cambio"
```

---

## Configuración local

Copiá `config.example.json` como `config.json` y completá con tus credenciales:

```json
{
  "database_type": "postgresql",
  "database_url": "postgresql://user:pass@host:port/dbname"
}
```

Si `database_type` es `sqlite` o está vacío, la app usa SQLite local.

---

## Instalación para desarrollo

```bash
git clone https://github.com/mana1023/manarey.git
cd manarey
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

---

## Autor

**Lautaro Manavella** — [linkedin.com/in/lautaro-manavella](https://linkedin.com/in/lautaro-manavella)
