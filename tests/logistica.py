"""Checklist de doble verificacion, entrega, responsivas y regreso de equipo."""

import os
import sys
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date  # noqa: E402

from app import create_app  # noqa: E402
from app.constantes import (Checklist, EstadoEquipo, EstadoNota,  # noqa: E402
                            Movimiento, Rol, TipoItem)
from app.extensions import db  # noqa: E402

app = create_app("development")
app.config["WTF_CSRF_ENABLED"] = False
app.config["PDF_REMISIONES_DIR"] = Path(tempfile.mkdtemp(prefix="avant-log-"))

fallos = []


def check(etiqueta, obtenido, esperado):
    if obtenido != esperado:
        fallos.append(f"{etiqueta}: obtuvo {obtenido!r}, esperaba {esperado!r}")
    else:
        print(f"  ok  {etiqueta} = {obtenido!r}")


with app.app_context():
    db.create_all()
    from app.models import (Almacen, DetalleNotaVenta, EquipoMedico,
                            Existencia, HistorialMovimiento, Insumo,
                            NotaVenta, Usuario)
    from app.servicios.logistica import (ErrorDeLogistica, etapa_completa,
                                         marcar_entregada,
                                         obtener_o_crear_entrega,
                                         registrar_regreso,
                                         verificar_por_codigo)
    from app.servicios.remisiones import generar_remisiones
    from app.servicios.responsivas import emitir_responsivas
    from app.servicios.revision import aprobar

    admin = Usuario(nombre="Admin", email="a@a.mx", rol=Rol.REVISOR_ADMIN)
    admin.set_password("avant123")
    tec = Usuario(nombre="Tec Uno", email="t@a.mx", rol=Rol.TECNICO)
    tec.set_password("avant123")
    vend = Usuario(nombre="Vende", email="v@a.mx", rol=Rol.VENDEDOR)
    vend.set_password("avant123")
    db.session.add_all([admin, tec, vend])

    central = Almacen(nombre="Central")
    db.session.add(central)
    db.session.flush()

    ins = Insumo(nombre="Jeringa 20 ml", codigo_barras="IN0002", stock_minimo=5,
                 precio_angeles=38, precio_otros=29, costo_unitario=14)
    ins.existencias.append(Existencia(almacen=central, cantidad=100))
    eq = EquipoMedico(nombre="Torre laparoscopia", codigo_barras="TOLA1",
                      numero_serie="SN-1", moi=320000, almacen=central,
                      marca="Karl Storz", modelo="Image1", tipo_equipo="Laparoscopia")
    db.session.add_all([ins, eq])
    db.session.commit()
    ins_id, eq_id = ins.id, eq.id

    nota = NotaVenta(folio="AVS-2026-0001", vendedor_id=vend.id,
                     hospital="Hospital Angeles Pedregal",
                     direccion_entrega="Quirofano 2",
                     doctor="Dr. Juan Perez", cirugia="Colecistectomia",
                     fecha_requerida=date(2026, 10, 15))
    nota.detalles.append(DetalleNotaVenta(tipo=TipoItem.INSUMO, item_id=ins_id,
                                          cantidad=10, precio_unitario=38,
                                          descripcion_snapshot="Jeringa 20 ml"))
    nota.detalles.append(DetalleNotaVenta(tipo=TipoItem.EQUIPO, item_id=eq_id,
                                          cantidad=1, precio_unitario=0,
                                          descripcion_snapshot="Torre laparoscopia"))
    db.session.add(nota)
    db.session.commit()
    nota_id = nota.id

    print("No se puede tomar antes de la remision:")
    try:
        obtener_o_crear_entrega(nota, tec)
        check("tomar sin remision", "no fallo", "deberia fallar")
    except ErrorDeLogistica:
        print("  ok  tomar sin remision rechazado")

    aprobar(nota, admin)
    generar_remisiones(nota, admin)
    nota = db.session.get(NotaVenta, nota_id)

    print("\nTomar la entrega prepara el checklist:")
    entrega = obtener_o_crear_entrega(nota, tec)
    check("renglones de checklist (2 articulos x 2 etapas)", len(entrega.checklist), 4)
    check("tomarla otra vez no duplica",
          len(obtener_o_crear_entrega(nota, tec).checklist), 4)

    print("\nEl checklist del hospital no se puede adelantar:")
    try:
        verificar_por_codigo(entrega, Checklist.ETAPA_HOSPITAL, "IN0002")
        check("hospital antes que almacen", "no fallo", "deberia fallar")
    except ErrorDeLogistica:
        print("  ok  hospital antes que almacen rechazado")

    print("\nUn codigo ajeno no verifica nada:")
    try:
        verificar_por_codigo(entrega, Checklist.ETAPA_ALMACEN, "NO-EXISTE")
        check("codigo ajeno", "no fallo", "deberia fallar")
    except ErrorDeLogistica as e:
        check("codigo ajeno rechazado", "no corresponde" in str(e), True)

    print("\nVerificacion en almacen:")
    verificar_por_codigo(entrega, Checklist.ETAPA_ALMACEN, "IN0002")
    check("una etapa a medias no se cierra",
          etapa_completa(entrega, Checklist.ETAPA_ALMACEN), False)
    check("y la nota sigue en remision generada",
          db.session.get(NotaVenta, nota_id).estado, EstadoNota.REMISION_GENERADA)

    try:
        verificar_por_codigo(entrega, Checklist.ETAPA_ALMACEN, "IN0002")
        check("reescanear", "no fallo", "deberia fallar")
    except ErrorDeLogistica as e:
        check("reescanear avisa que ya estaba", "ya estaba" in str(e), True)

    verificar_por_codigo(entrega, Checklist.ETAPA_ALMACEN, "TOLA1")
    entrega = db.session.get(NotaVenta, nota_id).entrega
    check("etapa almacen completa", entrega.checklist_almacen_ok, True)
    check("la nota pasa a en logistica",
          db.session.get(NotaVenta, nota_id).estado, EstadoNota.EN_LOGISTICA)
    check("el equipo figura en ruta",
          db.session.get(EquipoMedico, eq_id).ubicacion_actual, "En ruta")
    check("salida registrada en kardex",
          HistorialMovimiento.query.filter_by(movimiento=Movimiento.SALIDA).count(), 2)

    print("\nNo se entrega sin la segunda verificacion:")
    try:
        marcar_entregada(entrega, tec)
        check("entregar sin checklist hospital", "no fallo", "deberia fallar")
    except ErrorDeLogistica as e:
        check("entregar sin checklist hospital se bloquea",
              "hospital" in str(e).lower(), True)

    print("\nVerificacion en hospital y entrega:")
    verificar_por_codigo(entrega, Checklist.ETAPA_HOSPITAL, "IN0002")
    verificar_por_codigo(entrega, Checklist.ETAPA_HOSPITAL, "TOLA1")
    entrega = db.session.get(NotaVenta, nota_id).entrega
    check("doble verificacion completa", entrega.checklist_ok, True)

    marcar_entregada(entrega, tec, recibe_nombre="Enf. Ana Ruiz")
    nota = db.session.get(NotaVenta, nota_id)
    ins = db.session.get(Insumo, ins_id)
    eq = db.session.get(EquipoMedico, eq_id)

    check("estado", nota.estado, EstadoNota.ENTREGADA)
    check("quien recibio", nota.entrega.recibe_nombre, "Enf. Ana Ruiz")
    check("insumo descontado de verdad", ins.stock_actual, 90)
    check("y ya no queda apartado", ins.stock_apartado, 0)
    check("equipo rentado", eq.estado, EstadoEquipo.RENTADO)
    check("equipo ubicado en el hospital", eq.ubicacion_actual,
          "Hospital Angeles Pedregal")

    consumo = HistorialMovimiento.query.filter_by(
        movimiento=Movimiento.CONSUMIDO).first()
    check("kardex: saldo anterior", consumo.saldo_anterior, 100)
    check("kardex: saldo nuevo", consumo.saldo_nuevo, 90)
    check("kardex: costo del movimiento", float(consumo.importe), 140.0)

    print("\nResponsiva de custodia:")
    emitidas = emitir_responsivas(nota.entrega, tec, responsable="Dr. Juan Perez")
    check("una por equipo", len(emitidas), 1)
    resp = emitidas[0]
    check("folio", resp.folio.startswith("RESP-AVS-"), True)
    check("valor de reposicion congelado", float(resp.valor_reposicion), 320000.0)
    check("razon social del equipo", resp.razon_social, "AVANT GARDE MEDIC SERVICE")
    ruta_resp = app.config["PDF_REMISIONES_DIR"] / resp.pdf_path
    check("PDF escrito", ruta_resp.exists(), True)
    check("es un PDF", ruta_resp.read_bytes()[:5], b"%PDF-")
    check("no duplica", len(emitir_responsivas(nota.entrega, tec)), 0)
    resp_id = resp.id

    print("\nRegreso del equipo:")
    try:
        registrar_regreso(nota.entrega, eq, tec, "inventado")
        check("estado invalido", "no fallo", "deberia fallar")
    except ErrorDeLogistica:
        print("  ok  estado de recepcion invalido rechazado")

    registrar_regreso(nota.entrega, eq, tec, EstadoEquipo.MANTENIMIENTO,
                      "Optica rayada")
    nota = db.session.get(NotaVenta, nota_id)
    eq = db.session.get(EquipoMedico, eq_id)
    check("equipo a mantenimiento", eq.estado, EstadoEquipo.MANTENIMIENTO)
    check("regresa al almacen", eq.ubicacion_actual, "Central")
    check("la nota se cierra sola", nota.estado, EstadoNota.CERRADA)
    check("responsiva cerrada",
          db.session.get(type(resp), resp_id).cerrada, True)
    check("regreso en kardex",
          HistorialMovimiento.query.filter_by(
              movimiento=Movimiento.REGRESO_ALMACEN).count(), 1)

    try:
        registrar_regreso(nota.entrega, eq, tec, EstadoEquipo.DISPONIBLE)
        check("regresar dos veces", "no fallo", "deberia fallar")
    except ErrorDeLogistica:
        print("  ok  regresar dos veces rechazado")

print("\nPor HTTP:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "t@a.mx", "password": "avant123"},
           follow_redirects=True)
    r = c.get(f"/logistica/{nota_id}")
    check("GET detalle", r.status_code, 200)
    r = c.get(f"/logistica/{nota_id}/checklist/almacen")
    check("GET checklist", r.status_code, 200)
    check("trae el escaner", b"escaner" in r.data, True)
    r = c.get(f"/logistica/responsiva/{resp_id}.pdf")
    check("descarga la responsiva", r.data[:5], b"%PDF-")

    # El endpoint de verificacion responde JSON.
    r = c.post(f"/logistica/{nota_id}/checklist/almacen/verificar",
               json={"codigo": "NO-EXISTE"})
    check("codigo malo responde 400", r.status_code, 400)
    check("y explica por que", r.get_json()["ok"], False)

with app.test_client() as c:
    c.post("/auth/login", data={"email": "v@a.mx", "password": "avant123"},
           follow_redirects=True)
    r = c.get(f"/logistica/{nota_id}")
    check("un vendedor no entra a logistica", r.status_code, 403)

print("\n" + "=" * 50)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo paso.")
