"""Consulta del kardex y trazabilidad.

Es la primera vez que se leen los movimientos que se venian escribiendo desde
revision, logistica y catalogo. Aqui se comprueba que la historia que quedo
registrada corresponde con lo que realmente paso.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, timedelta  # noqa: E402

from app import create_app  # noqa: E402
from app.constantes import (Checklist, EstadoEquipo, Movimiento, Rol,  # noqa: E402
                            TipoItem)
from app.extensions import db  # noqa: E402

app = create_app("development")
app.config["WTF_CSRF_ENABLED"] = False
app.config["PDF_REMISIONES_DIR"] = Path(tempfile.mkdtemp(prefix="avant-kdx-"))
fallos = []


def check(etiqueta, obtenido, esperado):
    if obtenido != esperado:
        fallos.append(f"{etiqueta}: obtuvo {obtenido!r}, esperaba {esperado!r}")
    else:
        print(f"  ok  {etiqueta} = {obtenido!r}")


# --- Se corre un ciclo completo para que haya historia que consultar --------

with app.app_context():
    db.create_all()
    from app.models import (Almacen, DetalleNotaVenta, EquipoMedico,
                            Existencia, Hospital, Insumo, NotaVenta, Usuario)
    from app.servicios.catalogo import ajustar_existencia
    from app.servicios.logistica import (marcar_entregada,
                                         obtener_o_crear_entrega,
                                         registrar_regreso,
                                         verificar_por_codigo)
    from app.servicios.remisiones import generar_remisiones
    from app.servicios.revision import aprobar

    admin = Usuario(nombre="Admin", email="a@a.mx", rol=Rol.REVISOR_ADMIN)
    admin.set_password("avant123")
    tec = Usuario(nombre="Tec", email="t@a.mx", rol=Rol.TECNICO)
    tec.set_password("avant123")
    vend = Usuario(nombre="Vende", email="v@a.mx", rol=Rol.VENDEDOR)
    vend.set_password("avant123")
    db.session.add_all([admin, tec, vend])

    central = Almacen(nombre="Central")
    resteril = Almacen(nombre="Resteril")
    db.session.add_all([central, resteril])
    db.session.flush()

    hospital = Hospital(nombre="Hospital Angeles Pedregal", empresa="soluciones")
    ins = Insumo(nombre="Jeringa 20 ml", sku="JER-020", codigo_barras="IN0002",
                 stock_minimo=5, costo_unitario=10)
    eq = EquipoMedico(nombre="Torre", codigo_barras="TOLA1", numero_serie="SN-1",
                      moi=100000, almacen=central)
    db.session.add_all([hospital, ins, eq])
    db.session.commit()

    # 1. Alta de existencias (ajuste)
    ajustar_existencia(ins, central, 100, admin, motivo="Alta inicial")
    db.session.commit()

    # 2. Nota, aprobacion (apartado), remision
    nota = NotaVenta(folio="AVS-2026-0001", vendedor_id=vend.id,
                     hospital_id=hospital.id, hospital=hospital.nombre,
                     direccion_entrega="Quirofano 2",
                     fecha_requerida=date.today())
    nota.detalles.append(DetalleNotaVenta(tipo=TipoItem.INSUMO, item_id=ins.id,
                                          cantidad=30, precio_unitario=50,
                                          descripcion_snapshot="Jeringa 20 ml"))
    nota.detalles.append(DetalleNotaVenta(tipo=TipoItem.EQUIPO, item_id=eq.id,
                                          cantidad=1, precio_unitario=8500,
                                          descripcion_snapshot="Torre"))
    db.session.add(nota)
    db.session.commit()
    nota_id, ins_id, eq_id = nota.id, ins.id, eq.id

    aprobar(nota, admin)
    generar_remisiones(nota, admin)

    # 3. Logistica completa: salida, entrega (consumo) y regreso
    entrega = obtener_o_crear_entrega(nota, tec)
    verificar_por_codigo(entrega, Checklist.ETAPA_ALMACEN, "IN0002")
    verificar_por_codigo(entrega, Checklist.ETAPA_ALMACEN, "TOLA1")
    verificar_por_codigo(entrega, Checklist.ETAPA_HOSPITAL, "IN0002")
    verificar_por_codigo(entrega, Checklist.ETAPA_HOSPITAL, "TOLA1")
    marcar_entregada(entrega, tec, recibe_nombre="Enf. Ana")
    registrar_regreso(entrega, db.session.get(EquipoMedico, eq_id), tec,
                      EstadoEquipo.DISPONIBLE)

print("La historia del insumo cuadra con lo que paso:")
with app.app_context():
    from app.servicios.kardex import construir_consulta, describir, resumen

    consulta = construir_consulta({"item_tipo_exacto": TipoItem.INSUMO,
                                   "item_id": ins_id})
    movs = consulta.all()
    tipos = [m.movimiento for m in movs]

    # Del mas reciente al mas antiguo: consumo, salida, apartado, alta.
    check("cuatro movimientos", len(movs), 4)
    check("orden descendente por fecha", tipos, [
        Movimiento.CONSUMIDO, Movimiento.SALIDA,
        Movimiento.APARTADO, Movimiento.AJUSTE_STOCK,
    ])

    alta = movs[-1]
    check("el alta parte de cero", alta.saldo_anterior, 0)
    check("y deja 100", alta.saldo_nuevo, 100)

    apartado = movs[2]
    check("apartar no mueve el saldo fisico",
          (apartado.saldo_anterior, apartado.saldo_nuevo), (100, 100))
    check("pero registra las piezas comprometidas", apartado.cantidad, 30)

    consumo = movs[0]
    check("el consumo si baja el saldo",
          (consumo.saldo_anterior, consumo.saldo_nuevo), (100, 70))
    check("valuado al costo", float(consumo.importe), 300.0)

    # La cadena de saldos tiene que ser continua leida al reves.
    saldos = [(m.saldo_anterior, m.saldo_nuevo) for m in reversed(movs)
              if m.saldo_anterior is not None]
    continua = all(saldos[i][1] == saldos[i + 1][0] for i in range(len(saldos) - 1))
    check("la cadena de saldos no tiene huecos", continua, True)
    check("el saldo final coincide con la existencia",
          saldos[-1][1], db.session.get(Insumo, ins_id).stock_actual)

print("\nLa historia del equipo:")
with app.app_context():
    from app.servicios.kardex import construir_consulta

    movs = construir_consulta({"item_tipo_exacto": TipoItem.EQUIPO,
                               "item_id": eq_id}).all()
    tipos = [m.movimiento for m in movs]
    check("cuatro movimientos", len(tipos), 4)
    check("regreso, entrega, salida y apartado", tipos, [
        Movimiento.REGRESO_ALMACEN, Movimiento.ENTREGADO,
        Movimiento.SALIDA, Movimiento.APARTADO,
    ])
    check("todos ligados a la nota",
          all(m.nota_venta_id == nota_id for m in movs), True)

print("\nFiltros:")
with app.app_context():
    from app.servicios.kardex import construir_consulta, describir, resumen

    check("sin filtros trae todo", construir_consulta({}).count(), 8)
    check("por tipo de movimiento",
          construir_consulta({"movimiento": Movimiento.APARTADO}).count(), 2)
    check("por tipo de articulo",
          construir_consulta({"item_tipo": TipoItem.EQUIPO}).count(), 4)
    check("por texto en el nombre",
          construir_consulta({"texto": "Jeringa"}).count(), 4)
    check("por SKU", construir_consulta({"texto": "JER-020"}).count(), 4)
    check("por numero de serie",
          construir_consulta({"texto": "SN-1"}).count(), 4)
    check("texto que no existe",
          construir_consulta({"texto": "zzzz"}).count(), 0)

    manana = date.today() + timedelta(days=1)
    check("rango de fechas incluye hoy",
          construir_consulta({"desde": date.today(), "hasta": date.today()}).count(), 8)
    check("un rango futuro no trae nada",
          construir_consulta({"desde": manana, "hasta": manana}).count(), 0)

    # El almacen filtra tanto por origen como por destino.
    from app.models import Almacen
    central_id = Almacen.query.filter_by(nombre="Central").first().id
    # Todos los movimientos anotan su almacen; el unico sin almacen es la
    # entrega en el hospital, que ya no ocurre dentro de un almacen.
    check("por almacen",
          construir_consulta({"almacen_id": central_id}).count(), 8)

    print("\nTotales y descripciones:")
    consulta = construir_consulta({"item_tipo_exacto": TipoItem.INSUMO,
                                   "item_id": ins_id})
    totales = resumen(consulta)
    check("renglones", totales["renglones"], 4)
    check("piezas movidas (100+30+30+30)", totales["piezas"], 190)

    filas = describir(consulta.all())
    check("resuelve la descripcion", filas[0]["descripcion"], "Jeringa 20 ml")
    check("y el codigo", filas[0]["codigo"], "IN0002")
    check("y el SKU", filas[0]["sku"], "JER-020")

print("\nPor HTTP:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "a@a.mx", "password": "avant123"},
           follow_redirects=True)

    r = c.get("/reportes/kardex")
    texto = r.get_data(as_text=True)
    check("GET kardex", r.status_code, 200)
    check("muestra los movimientos", "Jeringa 20 ml" in texto, True)
    check("con sus etiquetas", "Regreso a almacen" in texto, True)

    r = c.get("/reportes/kardex?movimiento=" + Movimiento.CONSUMIDO)
    check("filtra por movimiento", r.status_code, 200)
    # Buscar la etiqueta ausente en el HTML no sirve: el selector de filtros
    # lista todos los movimientos igual. Se comprueba contra el servicio, y el
    # recorte de verdad se verifica abajo con el CSV.
    with app.app_context():
        from app.servicios.kardex import construir_consulta
        check("y deja un solo renglon",
              construir_consulta({"movimiento": Movimiento.CONSUMIDO}).count(), 1)

    r = c.get(f"/reportes/trazabilidad/insumo/{ins_id}")
    check("GET trazabilidad", r.status_code, 200)
    check("trae el historial completo",
          "Historial completo" in r.get_data(as_text=True), True)

    r = c.get(f"/reportes/trazabilidad/equipo/{eq_id}")
    check("trazabilidad de equipo", r.status_code, 200)

    r = c.get("/reportes/trazabilidad/inventado/1")
    check("tipo invalido da 404", r.status_code, 404)

    print("\nExportacion:")
    r = c.get("/reportes/kardex.csv")
    check("GET csv", r.status_code, 200)
    check("content-type", r.headers["Content-Type"].startswith("text/csv"), True)
    check("se descarga como archivo",
          "attachment" in r.headers["Content-Disposition"], True)
    cuerpo = r.data.decode("utf-8-sig")
    check("trae encabezados", cuerpo.splitlines()[0].startswith("Folio mov"), True)
    check("una linea por movimiento mas el encabezado",
          len(cuerpo.strip().splitlines()), 9)

    r = c.get("/reportes/kardex.csv?movimiento=" + Movimiento.CONSUMIDO)
    check("el csv respeta el filtro",
          len(r.data.decode("utf-8-sig").strip().splitlines()), 2)

print("\nSolo el revisor entra:")
for correo in ("t@a.mx", "v@a.mx"):
    with app.test_client() as c:
        c.post("/auth/login", data={"email": correo, "password": "avant123"},
               follow_redirects=True)
        check(f"403 para {correo}", c.get("/reportes/kardex").status_code, 403)
        check(f"403 en el csv para {correo}",
              c.get("/reportes/kardex.csv").status_code, 403)

print("\n" + "=" * 50)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo paso.")
