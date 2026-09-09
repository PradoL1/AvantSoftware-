"""Alta y edicion de notas de venta, extremo a extremo por HTTP."""

import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date  # noqa: E402

from app import create_app  # noqa: E402
from app.constantes import EstadoNota, Rol, TipoItem  # noqa: E402
from app.extensions import db  # noqa: E402

app = create_app("development")
app.config["WTF_CSRF_ENABLED"] = False
fallos = []


def check(etiqueta, obtenido, esperado):
    if obtenido != esperado:
        fallos.append(f"{etiqueta}: obtuvo {obtenido!r}, esperaba {esperado!r}")
    else:
        print(f"  ok  {etiqueta} = {obtenido!r}")


with app.app_context():
    db.create_all()
    from app.models import (Almacen, EquipoMedico, Existencia, Hospital,
                            Insumo, TarifaEquipo, Usuario)

    for nombre, email, rol in [
        ("Vende", "v@a.mx", Rol.VENDEDOR),
        ("Otro", "o@a.mx", Rol.VENDEDOR),
        ("Admin", "a@a.mx", Rol.REVISOR_ADMIN),
    ]:
        u = Usuario(nombre=nombre, email=email, rol=rol)
        u.set_password("avant123")
        db.session.add(u)

    central = Almacen(nombre="Central")
    db.session.add(central)
    db.session.flush()

    ins = Insumo(nombre="Jeringa 20 ml", sku="JER-020", codigo_barras="IN0002",
                 stock_minimo=10)
    hosp_a = Hospital(nombre="Hospital Angeles Pedregal",
                      empresa="soluciones", ciudad="Ciudad de Mexico")
    hosp_b = Hospital(nombre="Bite Medica", empresa="garde")
    db.session.add_all([hosp_a, hosp_b])
    ins.existencias.append(Existencia(almacen=central, cantidad=100))
    eq = EquipoMedico(nombre="Torre laparoscopia", codigo_barras="TOLA1",
                      numero_serie="SN-1", moi=320000, almacen=central)
    db.session.add_all([ins, eq])
    db.session.commit()
    ins_id, eq_id = ins.id, eq.id
    hosp_a_id, hosp_b_id = hosp_a.id, hosp_b.id
    db.session.add(TarifaEquipo(equipo_id=eq_id, hospital_id=hosp_a_id,
                                precio_renta=8500,
                                vigente_desde=date(2026, 1, 1)))
    db.session.commit()


def entrar(cliente, email):
    return cliente.post("/auth/login", data={"email": email, "password": "avant123"},
                        follow_redirects=True)


BASE = {
    "hospital_id": None,   # se rellena abajo, ya con el id real
    "ciudad": "Ciudad de Mexico",
    "direccion_entrega": "Quirofano 2",
    "fecha_requerida": "2026-10-15",
    "fecha_procedimiento": "2026-10-16",
    "especialidad": "Laparoscopia",
    "cirugia": "Colecistectomia",
    "doctor": "Dr. Juan Perez",
    "verificado_con": "Doctor",
    "tipo_paciente": "Particular",
    "metodo_pago": "Efectivo",
    "observaciones": "Llevar fibra optica extra",
}
BASE["hospital_id"] = hosp_a_id

with app.test_client() as c:
    entrar(c, "v@a.mx")

    print("Formulario de alta:")
    r = c.get("/notas/nueva")
    check("GET /notas/nueva", r.status_code, 200)
    check("trae el escaner", b"escanerEquipo" in r.data, True)

    print("\nAlta valida:")
    datos = dict(BASE)
    datos["insumo_id[]"] = str(ins_id)
    datos["insumo_cantidad[]"] = "3"
    datos["equipo_id[]"] = str(eq_id)
    datos["equipo_cantidad[]"] = "1"
    r = c.post("/notas/nueva", data=datos, follow_redirects=True)
    check("POST crea y redirige", r.status_code, 200)
    check("confirma el folio", b"AVS-" in r.data, True)

    with app.app_context():
        from app.models import NotaVenta
        nota = NotaVenta.query.first()
        check("folio asignado", nota.folio.startswith("AVS-"), True)
        check("estado inicial", nota.estado, EstadoNota.PENDIENTE_REVISION)
        check("renglones", len(nota.detalles), 2)
        check("campos de cirugia", nota.cirugia, "Colecistectomia")
        check("metodo de pago", nota.metodo_pago, "Efectivo")

        insumo_det = [d for d in nota.detalles if d.tipo == TipoItem.INSUMO][0]
        # Hospital Angeles -> tarifa de Angeles (38), no la de otros (29).
        # Los insumos entran sin precio: lo captura el revisor.
        check("insumo sin precio al capturar", float(insumo_det.precio_unitario), 0.0)
        equipo_det = [d for d in nota.detalles if d.tipo == TipoItem.EQUIPO][0]
        check("el equipo toma la tarifa del hospital",
              float(equipo_det.precio_unitario), 8500.0)
        check("descripcion copiada", insumo_det.descripcion_snapshot, "Jeringa 20 ml")
        nota_id = nota.id

    print("\nValidaciones que deben rechazar:")
    sin_renglones = dict(BASE)
    r = c.post("/notas/nueva", data=sin_renglones, follow_redirects=True)
    check("sin renglones no guarda", "Agrega al menos" in r.get_data(as_text=True), True)

    mal_pago = dict(BASE)
    mal_pago["tipo_paciente"] = "Seguro"          # con metodo de pago puesto
    mal_pago["insumo_id[]"] = str(ins_id)
    mal_pago["insumo_cantidad[]"] = "1"
    r = c.post("/notas/nueva", data=mal_pago, follow_redirects=True)
    check("seguro con metodo de pago se rechaza",
          "solo aplica a pacientes particulares" in r.get_data(as_text=True), True)

    falta_pago = dict(BASE)
    falta_pago["metodo_pago"] = ""
    falta_pago["insumo_id[]"] = str(ins_id)
    falta_pago["insumo_cantidad[]"] = "1"
    r = c.post("/notas/nueva", data=falta_pago, follow_redirects=True)
    check("particular sin metodo de pago se rechaza",
          "necesita metodo de pago" in r.get_data(as_text=True), True)

    cantidad_cero = dict(BASE)
    cantidad_cero["insumo_id[]"] = str(ins_id)
    cantidad_cero["insumo_cantidad[]"] = "0"
    r = c.post("/notas/nueva", data=cantidad_cero, follow_redirects=True)
    check("cantidad 0 se rechaza",
          "al menos 1" in r.get_data(as_text=True), True)

    print("\nEdicion:")
    r = c.get(f"/notas/{nota_id}/editar")
    check("GET editar", r.status_code, 200)
    check("precarga el hospital", b"Hospital Angeles Pedregal" in r.data, True)

    cambio = dict(BASE)
    cambio["hospital_id"] = hosp_b_id    # otro hospital: otra razon social
    cambio["insumo_id[]"] = str(ins_id)
    cambio["insumo_cantidad[]"] = "2"
    r = c.post(f"/notas/{nota_id}/editar", data=cambio, follow_redirects=True)
    check("POST editar", r.status_code, 200)

    with app.app_context():
        from app.models import NotaVenta
        nota = db.session.get(NotaVenta, nota_id)
        check("hospital actualizado", nota.hospital, "Bite Medica")
        check("renglones reemplazados", len(nota.detalles), 1)
        check("razon social recalculada",
              nota.datos_empresa["razon_social"], "AVANT GARDE MEDIC SERVICE")

print("\nAislamiento entre vendedores:")
with app.test_client() as c:
    entrar(c, "o@a.mx")
    r = c.get(f"/notas/{nota_id}")
    check("otro vendedor no ve la nota ajena", r.status_code, 403)
    r = c.get(f"/notas/{nota_id}/editar")
    check("ni la puede editar", r.status_code, 403)

with app.test_client() as c:
    entrar(c, "a@a.mx")
    r = c.get(f"/notas/{nota_id}")
    check("el revisor si la ve", r.status_code, 200)

print("\n" + "=" * 50)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo paso.")
