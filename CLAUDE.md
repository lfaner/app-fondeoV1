# CLAUDE.md — app-fondeoV1

Sistema de gestión de fondeos para Capital Gain Bursatil (CGB).
Reescritura completa de `app_fondeo` con mejores prácticas.

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Flask 3.1 + Blueprints |
| ORM | SQLAlchemy + Flask-Migrate |
| DB | PostgreSQL |
| Auth | Flask-Login |
| UI | Bootstrap 5 + DataTables |
| Prod | Gunicorn + Nginx (pendiente) |

---

## Estructura

```
app-fondeoV1/
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── config.py            # DevelopmentConfig / ProductionConfig
│   ├── extensions.py        # db, migrate, login_manager
│   ├── models.py            # User, Comprobante, Multiplicador, Movimiento, Caso, ConfigSistema
│   ├── auth/                # Blueprint: /login /register /logout
│   ├── fondeos/             # Blueprint: / /upload /download /eliminar /exportar
│   ├── perfil/              # Blueprint: /perfil-transaccional /perfil-transaccional/exportar
│   ├── casos/               # Blueprint: /casos /casos/cerrados /casos/crear /casos/cerrar/<id>
│   ├── admin/               # Blueprint prefix /admin: /usuarios /multiplicadores /depositos
│   └── templates/
│       ├── base.html        # Layout con sidebar Bootstrap 5
│       ├── base_auth.html   # Layout centrado para login/register
│       └── {blueprint}/     # Templates por blueprint
├── scripts/
│   └── actualizar_movimientos.py  # Descarga movimientos de API Aunesa → PostgreSQL
├── run.py                   # Entrypoint: python run.py
├── requirements.txt
├── .env                     # NO se sube a git (contiene credenciales)
├── .env.example             # Template sin valores reales
├── cuentas.txt              # NO se sube (datos sensibles) — lista de cuentas a monitorear
├── cuentas.example.txt      # Template
└── fechas_config.json       # Rango de fechas para actualizar_movimientos.py
```

---

## Modelos (PostgreSQL)

| Tabla | Descripción |
|---|---|
| `users` | Usuarios con rol (admin/user) y aprobación |
| `comprobantes` | Documentos de origen de fondos subidos |
| `multiplicadores` | Tipos de origen con su multiplicador anual |
| `movimientos` | Depósitos/extracciones traídos de API Aunesa |
| `casos` | Casos de exceso (cupo < depósitos) |
| `config_sistema` | Config clave-valor (ej: ultima_actualizacion) |

---

## Variables de entorno (.env)

```env
FLASK_ENV=development
SECRET_KEY=clave-secreta-larga
DATABASE_URL=postgresql://postgres:PASSWORD@localhost:55433/fondeo
UPLOAD_FOLDER=           # vacío = usa uploads/ dentro del proyecto
AUNESA_USERNAME=CGBSAS
AUNESA_PASSWORD=PASSWORD
AUNESA_HOST=https://becerra.aunesa.com/Irmo
AUNESA_CLIENT_ID=
USD_MEP=1168
```

**Conexión PostgreSQL:** via túnel SSH al VPS.
El usuario se conecta con túnel en `localhost:55433`.

---

## Setup local

```bash
# 1. Crear venv e instalar dependencias
python -m venv venv
venv/Scripts/pip.exe install -r requirements.txt

# 2. Copiar y completar .env
cp .env.example .env

# 3. Crear base de datos (una sola vez)
python -c "
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
conn = psycopg2.connect(host='localhost', port=55433, user='postgres', password='PASSWORD')
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
conn.cursor().execute('CREATE DATABASE fondeo')
conn.close()
"

# 4. Crear tablas
python -c "from app import create_app; from app.extensions import db; app=create_app(); app.app_context().push(); db.create_all()"

# 5. Crear usuario admin
python -c "
from app import create_app; from app.extensions import db; from app.models import User
app=create_app(); ctx=app.app_context(); ctx.push()
u=User(username='admin',role='admin',aprobado=True); u.set_password('admin123')
db.session.add(u); db.session.commit(); print('admin creado')
"

# 6. Correr
python run.py
```

---

## Correr en local

```bash
cd "C:/Users/leona/OneDrive - Capital Gain Bursatil/Proyectos/app-fondeoV1"
venv/Scripts/python.exe run.py
# → http://localhost:5000
# Login: admin / admin123
```

---

## Archivos subidos (comprobantes)

- **Local:** carpeta `uploads/` dentro del proyecto (auto-creada)
- **Producción (pendiente):** Cloudflare R2 (S3-compatible, gratis hasta 10 GB)
- Los archivos se organizan por cuenta: `uploads/{cuenta}/{filename}`

---

## Script de movimientos

```bash
# Editar fechas_config.json con el rango deseado, luego:
venv/Scripts/python.exe scripts/actualizar_movimientos.py
```

- Conecta a API Aunesa con credenciales del `.env`
- Lee cuentas de `cuentas.txt`
- Elimina registros del período antes de insertar (evita duplicados)
- Guarda en tabla `movimientos` de PostgreSQL

---

## Convenciones de código

- **tipos_origen** se guardan en **minúsculas** en DB y se comparan con `.lower()`
- Fechas en DB como `DATE` (no string), se convierten con `date.fromisoformat()`
- Blueprints no tienen prefijo de URL salvo `admin` (`/admin/...`)
- Flash messages usan categorías: `'success'`, `'error'`, `'warning'`
- `admin_required` decorator en `app/admin/routes.py` (usa `@wraps` + `@login_required`)

---

## Pendientes / Próximos pasos

### Deploy en VPS
1. Instalar Gunicorn: `pip install gunicorn`
2. Configurar Nginx como reverse proxy
3. Crear servicio systemd para auto-start
4. Configurar `FLASK_ENV=production` y `SECRET_KEY` fuerte

### Almacenamiento de archivos en producción
- Migrar uploads a **Cloudflare R2** (boto3, S3-compatible)
- Variable `R2_BUCKET` en `.env` para activar R2 vs local

### Mejoras identificadas
- Flask-Migrate para migraciones (ya instalado, falta inicializar: `flask db init`)
- Importar multiplicadores actuales desde `multiplicadores.txt` a la DB
- Importar comprobantes históricos desde `data.db` de app_fondeo
- Paginación server-side en tablas grandes
- Notificaciones cuando vence un comprobante

---

## Repos relacionados

| Repo | Descripción |
|---|---|
| `lfaner/app-fondeoV1` | Esta app (reescritura) |
| `lfaner/app-fondeoV1` (rama legacy) | Código original migrado |
| `lfaner/cgb-utils` | Utilidades compartidas CGB (ej: multiplicadores centralizados) |

---

## Contexto del proyecto

- **Empresa:** Capital Gain Bursatil (CGB)
- **Propósito:** Compliance — gestionar origen de fondos de clientes, calcular cupos anuales vs depósitos reales, generar casos cuando se excede el cupo
- **Lógica clave:** `cupo_anual = SUM(monto_comprobante × multiplicador_tipo)` solo para comprobantes no expirados. Si `cupo_anual + depositos < 0` → caso excedido
- **API externa:** Becerra/Aunesa (`https://becerra.aunesa.com/Irmo`) — sistema de custodia de valores donde están los movimientos reales de los clientes
- **Tipo de cambio:** USD MEP hardcodeado en `.env` como `USD_MEP`, actualizar manualmente
