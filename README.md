# AVANT — Inventario y logística de equipo médico

Aplicación web (Flask) para controlar el flujo de venta, revisión, remisión y
logística de equipo médico e insumos hacia hospitales.

El alcance, los roles y el modelo de datos están en
[CONTEXTO_PROYECTO.md](CONTEXTO_PROYECTO.md). Este README solo explica cómo
levantar y trabajar el proyecto.

## Requisitos

- **Python 3.11 o 3.12** — descargar de [python.org](https://www.python.org/downloads/windows/)
  y marcar **"Add python.exe to PATH"** durante la instalación.
  (El `python` que trae Windows por defecto es solo un acceso directo a la
  Microsoft Store y no sirve.)
- Git (ya instalado).

## Puesta en marcha

```powershell
# 1. Entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Dependencias
pip install -r requirements.txt

# 3. Configuración
Copy-Item .env.example .env
#    Editar .env: poner un SECRET_KEY real. Para empezar se puede dejar
#    DATABASE_URL en SQLite y cambiarlo a Supabase más adelante.
python -c "import secrets; print(secrets.token_hex(32))"   # genera SECRET_KEY

# 4. Base de datos
flask db init          # solo la primera vez
flask db migrate -m "esquema inicial"
flask db upgrade

# 5. Usuarios y catálogo de prueba
flask sembrar-demo     # crea 3 usuarios demo, contraseña avant123
#    o, para crear un usuario real uno por uno:
flask crear-usuario

# 6. Arrancar
python run.py          # http://localhost:5000
```

Para probar el escaneo desde el celular, `run.py` ya escucha en `0.0.0.0`:
entra desde el teléfono a `http://<IP-de-la-PC>:5000` estando en la misma red.

## Estructura

```
config.py                  Configuración por entorno, leída de .env
run.py                     Punto de entrada de desarrollo
app/
  __init__.py              create_app(): fábrica de la aplicación
  extensions.py            db, migrate, login_manager (evita imports circulares)
  constantes.py            Roles, estados y transiciones válidas del flujo
  cli.py                   Comandos: crear-usuario, sembrar-demo
  models/                  Las 8 tablas del contexto §5
  blueprints/
    auth/                  Login y logout (funcional)
    main/                  Tablero por rol (funcional)
    notas/                 Notas de venta — vendedor
    revision/              Revisión, aprobación y remisiones — revisor_admin
    catalogo/              Equipo, insumos y API de código de barras
    logistica/             Checklist, entrega y regreso — técnico
  utils/
    decoradores.py         @rol_requerido para el control de permisos
    folios.py              Folios consecutivos AVS-2026-0001
  templates/               Jinja2 (base provisional con Bootstrap)
  static/                  CSS, JS y PDFs generados
```

## Qué ya funciona y qué falta

**Funciona:** login con roles, tablero por rol, listado y detalle de notas,
bandejas de revisión y logística, catálogo de equipo e insumos, API
`/catalogo/api/codigo` para resolver un código de barras escaneado, páginas de
error, comandos de terminal.

**Falta (marcado con `TODO` en el código):**

1. Alta y edición de notas de venta, con renglones dinámicos y escaneo.
2. Verificación de disponibilidad + aprobación/rechazo, con apartado de stock.
3. Generación del PDF de remisión (ReportLab).
4. Checklist de doble verificación, entrega y regreso de equipo.
5. Escritura del historial de movimientos en cada transición de estado.
6. ABC de usuarios y catálogos (el formulario `UsuarioForm` ya está hecho).
7. Impresión de etiquetas con JsBarcode.
8. Reportes y trazabilidad.

## Pendientes técnicos

- **Folios:** `utils/folios.py` usa `MAX(folio)+1`, que no es atómico. Con 11
  usuarios el riesgo es bajo, pero la vista que crea la nota debe reintentar si
  el `UNIQUE` del folio falla.
- **Capa de servicios:** las transiciones de estado (apartar, entregar, cerrar)
  tocan varias tablas a la vez. Conviene meterlas en `app/servicios/` con una
  transacción por operación, en lugar de repartirlas entre las vistas.
- **WeasyPrint:** daría PDFs más bonitos reusando el HTML de las plantillas,
  pero en Windows necesita GTK instalado aparte. Por eso `requirements.txt`
  trae ReportLab. Si se instala GTK, se puede cambiar el generador.
- **Supabase:** al pasar de SQLite a PostgreSQL, usar la cadena del *pooler* en
  modo Session (puerto 5432) y volver a correr `flask db upgrade`.

## Decisiones abiertas con el jefe

Siguen sin resolverse las cinco de [CONTEXTO_PROYECTO.md](CONTEXTO_PROYECTO.md)
§9. Dos afectan el código pronto:

- Qué pasa al cancelar una nota aprobada con remisión generada. El modelo ya
  tiene `Remision.cancelada` previendo que se anule, pero la regla no está
  definida.
- Si hay uno o varios almacenes. Hoy `ubicacion_actual` es texto libre; si son
  varios, hace falta una tabla `ubicaciones`.
