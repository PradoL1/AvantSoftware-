"""Generacion de remisiones y del PDF."""

import os
import sys
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date  # noqa: E402

from app import create_app  # noqa: E402
from app.constantes import EstadoNota, Rol, TipoItem, TipoRemision  # noqa: E402
from app.extensions import db  # noqa: E402

app = create_app("development")
app.config["WTF_CSRF_ENABLED"] = False
# Los PDF de la prueba no deben ensuciar el repositorio.
app.config["PDF_REMISIONES_DIR"] = Path(tempfile.mkdtemp(prefix="avant-pdf-"))

fallos = []


def check(etiqueta, obtenido, esperado):
    if obtenido != esperado:
        fallos.append(f"{etiqueta}: obtuvo {obtenido!r}, esperaba {esperado!r}")
    else:
        print(f"  ok  {etiqueta} = {obtenido!r}")


with app.app_context():
    db.create_all()
    from app.models import (Almacen, DetalleNotaVenta, EquipoMedico,
                            Existencia, Insumo, NotaVenta, Usuario)
    from app.servicios.remisiones import ErrorDeRemision, generar_remisiones
    from app.servicios.revision import aprobar

    admin = Usuario(nombre="Admin", email="a@a.mx", rol=Rol.REVISOR_ADMIN)
    admin.set_password("avant123")
    vendedor = Usuario(nombre="Vende", email="v@a.mx", rol=Rol.VENDEDOR)
    vendedor.set_password("avant123")
    db.session.add_all([admin, vendedor])

    central = Almacen(nombre="Central")
    db.session.add(central)
    db.session.flush()

    ins = Insumo(nombre="Jeringa 20 ml", codigo_barras="IN1", stock_minimo=5, unidad_medida="pieza")
    ins.existencias.append(Existencia(almacen=central, cantidad=100))
    eq = EquipoMedico(nombre="Torre laparoscopia", codigo_barras="TOLA1",
                      numero_serie="SN-1", almacen=central)
    db.session.add_all([ins, eq])
    db.session.commit()
    ins_id, eq_id, admin_id, vend_id = ins.id, eq.id, admin.id, vendedor.id

    nota = NotaVenta(folio="AVS-2026-0001", vendedor_id=vend_id,
                     hospital="Hospital Angeles Pedregal",
                     ciudad="Ciudad de Mexico",
                     direccion_entrega="Quirofano 2",
                     doctor="Dr. Juan Perez", cirugia="Colecistectomia",
                     fecha_requerida=date(2026, 10, 15))
    nota.detalles.append(DetalleNotaVenta(tipo=TipoItem.INSUMO, item_id=ins_id,
                                          cantidad=10, precio_unitario=38,
                                          descripcion_snapshot="Jeringa 20 ml",
                                          unidad_snapshot="pieza"))
    nota.detalles.append(DetalleNotaVenta(tipo=TipoItem.EQUIPO, item_id=eq_id,
                                          cantidad=1, precio_unitario=0,
                                          descripcion_snapshot="Torre laparoscopia"))
    db.session.add(nota)
    db.session.commit()
    nota_id = nota.id

    print("No se puede remisionar sin aprobar:")
    try:
        generar_remisiones(nota, admin)
        check("remision sin aprobar", "no fallo", "deberia fallar")
    except ErrorDeRemision:
        print("  ok  remision sin aprobar rechazada")

    print("\nGenerar tras aprobar:")
    aprobar(nota, admin)
    nota = db.session.get(NotaVenta, nota_id)
    creadas = generar_remisiones(nota, admin)
    nota = db.session.get(NotaVenta, nota_id)

    check("se emiten dos (insumos y equipos)", len(creadas), 2)
    check("estado de la nota", nota.estado, EstadoNota.REMISION_GENERADA)

    insumos = nota.remision_de(TipoRemision.INSUMOS)
    equipos = nota.remision_de(TipoRemision.EQUIPOS)
    check("existe la de insumos", insumos is not None, True)
    check("existe la de equipos", equipos is not None, True)
    check("folios distintos", insumos.folio != equipos.folio, True)
    check("prefijo del folio", insumos.folio.startswith("REM-AVS-"), True)

    print("\nDatos fiscales congelados:")
    check("razon social", insumos.razon_social, "AVANT SOLUCIONES MEDICAS")
    check("rfc", insumos.rfc, "MPB210816298")
    check("subtotal de insumos (10 x 38)", float(insumos.subtotal), 380.0)
    check("iva", float(insumos.iva), 60.8)
    check("total", float(insumos.total), 440.8)
    # El equipo se renta: sin tarifa en el catalogo, va en cero.
    check("total de la de equipos", float(equipos.total), 0.0)

    print("\nEl PDF:")
    carpeta = app.config["PDF_REMISIONES_DIR"]
    ruta = carpeta / f"{insumos.folio}.pdf"
    check("se escribio el archivo", ruta.exists(), True)
    check("pdf_path guardado", insumos.pdf_path, f"{insumos.folio}.pdf")
    contenido = ruta.read_bytes()
    check("es un PDF de verdad", contenido[:5], b"%PDF-")
    check("pesa algo razonable", len(contenido) > 1500, True)

    print("\nNo duplica al volver a generar:")
    otra_vez = generar_remisiones(nota, admin)
    check("no crea remisiones nuevas", len(otra_vez), 0)
    check("siguen siendo dos", len(db.session.get(NotaVenta, nota_id).remisiones), 2)

    print("\nHospital no-Angeles usa la otra razon social:")
    nota2 = NotaVenta(folio="AVS-2026-0002", vendedor_id=vend_id,
                      hospital="Bite Medica", direccion_entrega="Quirofano 1",
                      fecha_requerida=date(2026, 10, 20))
    nota2.detalles.append(DetalleNotaVenta(tipo=TipoItem.INSUMO, item_id=ins_id,
                                           cantidad=2, precio_unitario=29,
                                           descripcion_snapshot="Jeringa 20 ml"))
    db.session.add(nota2)
    db.session.commit()
    aprobar(nota2, admin)
    generar_remisiones(nota2, admin)
    r2 = nota2.remision_de(TipoRemision.INSUMOS)
    check("razon social", r2.razon_social, "AVANT GARDE MEDIC SERVICE")
    check("rfc", r2.rfc, "AGM210811HD9")
    check("solo emite la de insumos", len(nota2.remisiones), 1)
    nota2_id, rem_id = nota2.id, r2.id

print("\nPor HTTP:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "a@a.mx", "password": "avant123"},
           follow_redirects=True)

    r = c.get(f"/revision/{nota_id}")
    check("la pantalla lista las remisiones",
          "Remisiones emitidas" in r.get_data(as_text=True), True)

    r = c.get(f"/revision/remision/{rem_id}.pdf")
    check("descarga el PDF", r.status_code, 200)
    check("content-type", r.headers["Content-Type"], "application/pdf")
    check("el cuerpo es un PDF", r.data[:5], b"%PDF-")

    # Si el archivo se borra, se regenera al pedirlo.
    with app.app_context():
        from app.models import Remision
        rem = db.session.get(Remision, rem_id)
        (app.config["PDF_REMISIONES_DIR"] / rem.pdf_path).unlink()
    r = c.get(f"/revision/remision/{rem_id}.pdf")
    check("regenera el PDF si falta", r.data[:5], b"%PDF-")

with app.test_client() as c:
    c.post("/auth/login", data={"email": "v@a.mx", "password": "avant123"},
           follow_redirects=True)
    r = c.post(f"/revision/{nota_id}/remision")
    check("un vendedor no puede generar remisiones", r.status_code, 403)
    r = c.get(f"/revision/remision/{rem_id}.pdf")
    check("ni descargarlas", r.status_code, 403)

print("\n" + "=" * 50)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo paso.")
