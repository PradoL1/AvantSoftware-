# Contexto del proyecto — Sistema de inventario y logística de equipo médico

> Este archivo resume las decisiones tomadas antes de escribir código, para que Claude Code (o cualquier desarrollador) tenga el contexto completo sin tener que volver a explicarlo. Colócalo en la raíz del repositorio y menciónalo con `@CONTEXTO_PROYECTO.md` al iniciar una sesión.

## 1. Qué es el proyecto

Software a la medida (aplicación web, Flask) para controlar el flujo de venta, revisión, remisión y logística de **equipo médico** (se renta y regresa) e **insumos** (se consumen) hacia hospitales.

Es un proyecto **nuevo desde cero** (no se reutiliza el backend de la app anterior en PythonAnywiere/SQLite), pero sí se reutilizará el **diseño visual** (HTML/CSS/imágenes) del sistema anterior una vez que se exporten `templates/` y `static/`.

Responsable del desarrollo: **Luis**, con apoyo de Claude.

## 2. Flujo de negocio (estados)

```
pendiente_revision → aprobada → remision_generada → en_logistica → entregada → cerrada
                   → rechazada (fin)
```

1. **Vendedor** crea una nota de venta con lo que pide un hospital.
2. **Revisor-Administrativo** revisa; el sistema verifica disponibilidad automáticamente.
3. Si se rechaza → se notifica al vendedor con motivo (fin del flujo).
4. Si se aprueba → se genera la **remisión** en PDF.
5. **Técnico** hace logística: checklist de doble verificación, entrega en hospital.
6. Cierre: los **insumos** se descuentan definitivamente del stock; el **equipo médico** se marca "rentado" y luego se registra su regreso al almacén.

## 3. Roles y permisos

| Rol | # Usuarios | Permisos |
|---|---|---|
| **Vendedor** | 3 | Crear notas de venta. Ver solo sus propias notas. Consultar catálogo (solo lectura). |
| **Revisor-Administrativo** | 3 | Revisar/aprobar/rechazar notas. Ver disponibilidad en tiempo real. Generar y reimprimir remisiones en PDF. Editar catálogos. Crear/editar usuarios. Ver reportes y trazabilidad. Editar/cancelar notas aprobadas. |
| **Técnico** | 5 | Ver remisiones asignadas a logística. Checklist de doble verificación. Marcar entrega completada. Registrar regreso de equipo al almacén. |

Total: **11 usuarios**.

## 4. Nota de venta — campos

| Campo | Descripción |
|---|---|
| Folio | Autogenerado, consecutivo |
| Vendedor | Automático, según sesión |
| Fecha y hora de creación | Automática |
| Hospital / cliente destino | Texto |
| Contacto en el hospital | Nombre y teléfono |
| Dirección de entrega | Texto |
| Fecha requerida de entrega | Fecha |
| Insumos solicitados | Lista: nombre, cantidad, unidad (se puede agregar por escaneo de código de barras) |
| Equipo médico solicitado | Lista: nombre, cantidad, número de serie si aplica (se puede agregar por escaneo) |
| Observaciones | Texto libre |
| Estado | Controlado por el sistema (ver flujo arriba) |
| Motivo de rechazo | Solo si se rechaza |

## 5. Modelo de datos (entidades principales)

```
usuarios
  id, nombre, email, password_hash, rol ('vendedor'|'revisor_admin'|'tecnico'), activo

equipo_medico
  id, nombre, numero_serie, codigo_barras, estado ('disponible'|'rentado'|'mantenimiento'), ubicacion_actual

insumos
  id, nombre, unidad_medida, codigo_barras, stock_actual, stock_minimo

notas_venta
  id, folio, vendedor_id, hospital, contacto, direccion_entrega,
  fecha_creacion, fecha_requerida, estado, motivo_rechazo

detalle_nota_venta
  id, nota_venta_id, tipo ('equipo'|'insumo'), item_id, cantidad

remisiones
  id, nota_venta_id, generado_por_id, fecha_generacion, pdf_path

entregas
  id, remision_id, tecnico_id, fecha_entrega, checklist_ok, fecha_regreso_equipo

historial_movimientos
  id, item_tipo, item_id, movimiento, fecha, usuario_id, nota_venta_id
```

## 6. Control por código de barras

- Cada artículo (equipo e insumo) tiene un `codigo_barras` único.
- Impresión de etiquetas desde el catálogo.
- Escaneo para: agregar artículos a la nota de venta, confirmar en revisión/apartado, confirmar en entrega y en regreso a almacén.
- Escaneo vía cámara del celular (librería web, sin hardware extra) o lector físico USB/Bluetooth (actúa como teclado, sin desarrollo adicional).
- **No incluye RFID** — decisión ya tomada, solo código de barras.

## 7. Stack tecnológico

| Componente | Herramienta |
|---|---|
| Backend | Python + Flask + Flask-SQLAlchemy |
| Autenticación y roles | Flask-Login |
| Base de datos | PostgreSQL (Supabase) |
| Generación de PDF | WeasyPrint o ReportLab |
| Frontend | HTML + Bootstrap o Tailwind CSS (responsive) |
| Escaneo de código de barras | Librería web tipo html5-qrcode |
| Generación de etiquetas | Librería tipo JsBarcode |
| Control de versiones | Git + GitHub |
| Hosting | Render o Railway |

Es **aplicación web** (navegador, responsive), no app de escritorio instalable ni app nativa de celular.

## 8. Decisiones ya tomadas (no volver a preguntar)

- Arquitectura: proyecto nuevo desde cero (opción B), no se reutiliza backend anterior.
- Sí se reutiliza el diseño visual (`templates/`, `static/`) del sistema anterior, adaptando el HTML/Jinja2 al nuevo modelo.
- Revisor y Administrativo son **un solo rol** ("revisor_admin"), decisión consciente de que reduce el doble control interno.
- Solo código de barras, no RFID.
- Sin modo offline — requiere internet.
- Sin app instalable de escritorio ni app nativa (por ahora).
- Sin 2FA ni restricción por IP (por ahora).

## 9. Pendiente de definir con el jefe (no resuelto aún)

- Qué pasa si se cancela una nota ya aprobada con remisión generada (¿se anula automáticamente la remisión?).
- Flujo de mantenimiento del equipo médico (quién lo marca, historial de reparaciones).
- Vigencia máxima de la renta de equipo y alertas si se pasa la fecha.
- Si hay un solo almacén o varias ubicaciones físicas.
- Si se migran datos del sistema anterior o se arranca con catálogos vacíos.

## 10. Cronograma y costo de referencia

- Tiempo estimado: 8 – 10.5 semanas (desarrollador de tiempo completo).
- Honorarios de Luis: pago anticipado (40%) + avance intermedio (30%) + entrega final (30%). Monto exacto pendiente de definir con el jefe.

---

*Este archivo se generó a partir de una sesión de planeación en Claude.ai. El documento formal de alcance (Word) tiene el mismo contenido con más detalle narrativo, pensado para compartir con el jefe o cotizar con terceros.*
