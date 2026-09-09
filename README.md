# AVANT — Inventario y logística de equipo médico

Aplicación web (Flask) para controlar el flujo de venta, revisión, remisión y
logística de equipo médico e insumos hacia hospitales.

El alcance, los roles y el modelo de datos están en
[CONTEXTO_PROYECTO.md](CONTEXTO_PROYECTO.md). Este README solo explica cómo
levantar y trabajar el proyecto.

## Requisitos

- **Python 3.14** (probado con 3.14.7). Ya instalado en la maquina de Luis en
  `%LOCALAPPDATA%\Programs\Python\Python314`.
- Git.

> Si la terminal responde que no encuentra Python, es porque su PATH es
> anterior a la instalacion: cierra y vuelve a abrir la terminal.

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
  templates/               Jinja2 (base.html con sesion, base_publico.html sin ella)
  static/                  CSS, JS y PDFs generados
```

## Qué ya funciona y qué falta

**Verificado ejecutando la app** (no solo escrito): login con roles, tablero por
rol con indicadores, listado y detalle de notas, bandejas de revisión y
logística, catálogo de equipo e insumos, API `/catalogo/api/codigo`, páginas de
error, permisos por rol (un vendedor recibe 403 en revisión), CSRF activo, y las
reglas de negocio del sistema anterior (razón social por hospital, dos listas de
precios, IVA, stock repartido en almacenes, transiciones de estado).

```powershell
python tests\pantallas.py   # renderiza cada pantalla con cada rol
python tests\reglas.py      # reglas de negocio y cálculos
```

**Falta (marcado con `TODO` en el código):**

1. Alta y edición de notas de venta, con renglones dinámicos y escaneo.
2. Verificación de disponibilidad + aprobación/rechazo, con apartado de stock.
3. Generación del PDF de remisión (ReportLab).
4. Checklist de doble verificación, entrega y regreso de equipo.
5. Carta responsiva de custodia (modelo listo, falta el documento).
6. Escritura del kardex en cada transición de estado.
7. ABC de usuarios y catálogos (el formulario `UsuarioForm` ya está hecho).
8. Impresión de etiquetas con JsBarcode (medidas ya conocidas, ver abajo).
9. Reportes, trazabilidad y planificación de demanda.

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

## Diseño portado del sistema anterior

`_diseno_anterior/` guarda el HTML original como referencia; se borra cuando
termine la migración visual.

Ya portado a [app/static/css/app.css](app/static/css/app.css) y
[app/templates/base.html](app/templates/base.html): barra lateral oscura de
260px con el mismo gradiente, tarjetas con radio 12px y sombra suave, tarjetas
KPI con barra de color a la izquierda, marca de agua del logo, Bootstrap 5.3 +
FontAwesome 6.4.

**Falta que Luis exporte del sistema anterior:**

- `_sidebar.html` — el dashboard lo incluye pero no se exportó. La barra actual
  se reconstruyó con la misma hoja de estilos y la navegación del sistema
  nuevo; cuando aparezca el original, hay que comparar el orden y los iconos.
- `static/logo_avant.png` — va en `app/static/img/`. Sin él, la marca de agua
  simplemente no se pinta (no rompe nada).
- Una pantalla de formulario, para copiar el estilo de los campos.

**Diferencia deliberada:** el sistema anterior no era responsive (barra lateral
fija de 260px, botón de menú oculto). Como el técnico usa logística desde el
celular en el hospital, la barra ahora se colapsa por debajo de 992px.

## Reglas de negocio heredadas del sistema anterior

Todas salieron de leer `_diseno_anterior/`, no del documento de alcance, y están
verificadas en `tests/reglas.py`.

**Dos razones sociales.** Si el hospital contiene "ÁNGELES" factura *AVANT
SOLUCIONES MEDICAS* (RFC MPB210816298); si no, *AVANT GARDE MEDIC SERVICE* (RFC
AGM210811HD9). La regla vive en `Empresa.para_hospital()`, y decide también qué
lista de precios aplica. En el sistema anterior estaba repetida en dos plantillas.

**Dos listas de precios por insumo:** `precio_angeles` y `precio_otros`.

**IVA 16%**, en `constantes.IVA`. Antes estaba escrito a mano en el JavaScript
de la remisión.

**Cuatro almacenes:** Central, Operaciones, Resteril y Transición. El stock de un
insumo ya no es un número sino un reparto (tabla `existencias`), y
`insumo.stock_actual` los suma. `flask sembrar-almacenes` los crea.

**Dos remisiones por nota**, una de insumos y otra de equipos (`Remision.tipo`).

**Carta responsiva** (`responsivas`): contrato de custodia donde el receptor
acepta cubrir el valor de reposición del equipo. Se congela el MOI del activo al
firmar, porque es un documento con efecto legal que debe poder reimprimirse
igual años después.

**Kardex con saldos** (`historial_movimientos`): cada renglón guarda saldo
anterior y nuevo, costo, proveedor y fecha de pago. Diferencia deliberada: el
sistema anterior permitía *borrar y revertir* movimientos; aquí una corrección
es un movimiento de ajuste nuevo, para que la historia no se pueda reescribir.

### Datos útiles ya extraídos

- **Etiquetas de código de barras:** hoja carta, márgenes 10mm × 8mm, rejilla de
  6 × 2 (12 por planilla), cada etiqueta 64mm × 32mm, CODE128, barras de 18mm.
  Para hojas TUK Stik A20.
- **Checklist de salida** — accesorios: Cable de Poder, Pedal Doble/Sencillo,
  Fibra Óptica, Fuente de Luz, Maletín Rígido, Pieza de Mano/Camisa.
  Inspección: Chasis Limpio/Intacto, Ópticas Sin Rayaduras, Conectores Íntegros,
  Prueba de Encendido OK. Todo en `constantes.Checklist`.
- **Firmas de la remisión:** médico, enfermería y técnico.

## Alcance: este sistema reemplaza al anterior

Decisión tomada. Implica que el proyecto es mayor que el del documento original:
precios, IVA, dos razones sociales, cuatro almacenes, carta responsiva y kardex
financiero **no están en CONTEXTO_PROYECTO.md**. El esquema ya los contempla,
pero las pantallas no existen.

**Las 8–10.5 semanas del §10 ya no aplican.** Hay que reestimar con el jefe antes
de comprometer fechas.

Además, el sistema anterior tiene módulos completos que aquí todavía no existen:
planificación de demanda (ROP, stock de seguridad, lead time), costeo por capas,
cuentas por pagar a proveedores y exportación a Excel.

### Lo que no se copió, a propósito

- PINs y claves en el código (`PIN_JEFE = "1234"` estaba en el HTML).
- `session.get('rol', 'admin')`: sin sesión, el sistema anterior te trata como
  administrador.
- Checklist guardado en `localStorage` del navegador del técnico.
- Catálogo de equipos leído desde Google Sheets.
- Borrado de movimientos del kardex.
