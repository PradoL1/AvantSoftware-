"""Catalogo de hospitales, tarifario de renta y captura de precios."""

import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date  # noqa: E402

from app import create_app  # noqa: E402
from app.constantes import Empresa, EstadoNota, Rol, TipoItem  # noqa: E402
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

    admin = Usuario(nombre="Admin", email="a@a.mx", rol=Rol.REVISOR_ADMIN)
    admin.set_password("avant123")
    vend = Usuario(nombre="Vende", email="v@a.mx", rol=Rol.VENDEDOR)
    vend.set_password("avant123")
    db.session.add_all([admin, vend])

    central = Almacen(nombre="Central")
    db.session.add(central)
    db.session.flush()

    ins = Insumo(nombre="Jeringa 20 ml", codigo_barras="IN1", stock_minimo=5)
    ins.existencias.append(Existencia(almacen=central, cantidad=100))
    eq = EquipoMedico(nombre="Torre", codigo_barras="TOLA1", numero_serie="SN-1",
                      almacen=central)
    db.session.add_all([ins, eq])
    db.session.commit()
    ins_id, eq_id, vend_id = ins.id, eq.id, vend.id

print("Alta de hospital por HTTP:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "a@a.mx", "password": "avant123"},
           follow_redirects=True)

    r = c.get("/catalogo/hospitales")
    check("GET hospitales", r.status_code, 200)
    check("avisa que no hay ninguno",
          "Aun no hay hospitales" in r.get_data(as_text=True), True)

    r = c.post("/catalogo/hospitales/nuevo", data={
        "nombre": "Hospital Angeles Pedregal",
        "empresa": Empresa.SOLUCIONES,
        "ciudad": "Ciudad de Mexico",
        "activo": "y",
    }, follow_redirects=True)
    check("POST alta", r.status_code, 200)

    r = c.post("/catalogo/hospitales/nuevo", data={
        "nombre": "Bite Medica", "empresa": Empresa.GARDE,
        "ciudad": "Ciudad de Mexico", "activo": "y",
    }, follow_redirects=True)

    with app.app_context():
        from app.models import Hospital
        check("se guardaron dos", Hospital.query.count(), 2)
        angeles = Hospital.query.filter_by(nombre="Hospital Angeles Pedregal").first()
        bite = Hospital.query.filter_by(nombre="Bite Medica").first()
        check("razon social capturada", angeles.razon_social,
              "AVANT SOLUCIONES MEDICAS")
        check("rfc que le toca", angeles.datos_empresa["rfc"], "MPB210816298")
        ang_id, bite_id = angeles.id, bite.id

    # El nombre es unico: no puede haber dos hospitales iguales.
    r = c.post("/catalogo/hospitales/nuevo", data={
        "nombre": "Bite Medica", "empresa": Empresa.GARDE, "activo": "y",
    }, follow_redirects=True)
    check("nombre duplicado se rechaza",
          "Ya existe un hospital" in r.get_data(as_text=True), True)
    with app.app_context():
        from app.models import Hospital
        check("y no se creo de mas", Hospital.query.count(), 2)

    print("\nTarifario de renta:")
    r = c.post("/catalogo/tarifas", data={
        "equipo_id": eq_id, "hospital_id": ang_id,
        "precio_renta": "8500.00", "vigente_desde": "2026-01-01",
    }, follow_redirects=True)
    check("POST tarifa", r.status_code, 200)

    c.post("/catalogo/tarifas", data={
        "equipo_id": eq_id, "hospital_id": bite_id,
        "precio_renta": "7200.00", "vigente_desde": "2026-01-01",
    }, follow_redirects=True)

    with app.app_context():
        from app.models import EquipoMedico, Hospital, precio_renta
        equipo = db.session.get(EquipoMedico, eq_id)
        check("precio en un hospital",
              float(precio_renta(equipo, db.session.get(Hospital, ang_id))), 8500.0)
        check("precio en el otro",
              float(precio_renta(equipo, db.session.get(Hospital, bite_id))), 7200.0)

print("\nLa nota toma la tarifa del hospital elegido:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "v@a.mx", "password": "avant123"},
           follow_redirects=True)

    datos = {
        "hospital_id": bite_id,
        "ciudad": "Ciudad de Mexico",
        "direccion_entrega": "Quirofano 1",
        "fecha_requerida": "2026-10-15",
        "insumo_id[]": str(ins_id), "insumo_cantidad[]": "4",
        "equipo_id[]": str(eq_id), "equipo_cantidad[]": "1",
    }
    r = c.post("/notas/nueva", data=datos, follow_redirects=True)
    check("se creo la nota", r.status_code, 200)

    with app.app_context():
        from app.models import NotaVenta
        nota = NotaVenta.query.first()
        check("hospital ligado al catalogo", nota.hospital_id, bite_id)
        check("nombre copiado en la nota", nota.hospital, "Bite Medica")
        check("razon social del catalogo", nota.datos_empresa["razon_social"],
              "AVANT GARDE MEDIC SERVICE")
        equipo_det = [d for d in nota.detalles if d.tipo == TipoItem.EQUIPO][0]
        insumo_det = [d for d in nota.detalles if d.tipo == TipoItem.INSUMO][0]
        check("el equipo trae la tarifa de ESE hospital",
              float(equipo_det.precio_unitario), 7200.0)
        check("el insumo entra sin precio",
              float(insumo_det.precio_unitario), 0.0)
        nota_id, det_insumo_id = nota.id, insumo_det.id

print("\nEl vendedor no puede poner precios:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "v@a.mx", "password": "avant123"},
           follow_redirects=True)
    r = c.post(f"/revision/{nota_id}/precios",
               data={f"precio_{det_insumo_id}": "125.50"})
    check("403 al intentar", r.status_code, 403)
    with app.app_context():
        from app.models import DetalleNotaVenta
        check("el precio sigue en cero",
              float(db.session.get(DetalleNotaVenta, det_insumo_id).precio_unitario),
              0.0)

print("\nEl revisor captura el precio negociado:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "a@a.mx", "password": "avant123"},
           follow_redirects=True)

    r = c.get(f"/revision/{nota_id}")
    check("la pantalla avisa de renglones sin precio",
          "Sin precio capturado" in r.get_data(as_text=True), True)

    r = c.post(f"/revision/{nota_id}/precios",
               data={f"precio_{det_insumo_id}": "125.50"}, follow_redirects=True)
    check("POST precios", r.status_code, 200)

    with app.app_context():
        from app.models import DetalleNotaVenta, NotaVenta
        det = db.session.get(DetalleNotaVenta, det_insumo_id)
        nota = db.session.get(NotaVenta, nota_id)
        check("precio guardado", float(det.precio_unitario), 125.5)
        check("importe del renglon (4 x 125.50)", float(det.importe), 502.0)
        # 502 del insumo + 7200 del equipo.
        check("subtotal de la nota", float(nota.subtotal), 7702.0)

    r = c.post(f"/revision/{nota_id}/precios",
               data={f"precio_{det_insumo_id}": "-5"}, follow_redirects=True)
    check("precio negativo se rechaza",
          "no pueden ser negativos" in r.get_data(as_text=True), True)

    r = c.post(f"/revision/{nota_id}/precios",
               data={f"precio_{det_insumo_id}": "abc"}, follow_redirects=True)
    check("precio no numerico se rechaza",
          "no es un precio valido" in r.get_data(as_text=True), True)

    with app.app_context():
        from app.models import DetalleNotaVenta
        check("y el precio bueno sigue ahi",
              float(db.session.get(DetalleNotaVenta, det_insumo_id).precio_unitario),
              125.5)

print("\nAprobada la nota, los precios se congelan:")
with app.app_context():
    from app.models import NotaVenta, Usuario
    from app.servicios.revision import ErrorDeRevision, aprobar, guardar_precios
    nota = db.session.get(NotaVenta, nota_id)
    admin = Usuario.query.filter_by(email="a@a.mx").first()
    aprobar(nota, admin)
    check("estado", nota.estado, EstadoNota.APROBADA)
    try:
        guardar_precios(nota, {f"precio_{det_insumo_id}": "1"}, admin)
        check("cambiar precios tras aprobar", "no fallo", "deberia fallar")
    except ErrorDeRevision as e:
        check("cambiar precios tras aprobar se bloquea",
              "mientras la nota esta en revision" in str(e), True)


# --- El vendedor propone, el revisor confirma (opcional) --------------------

print("\nEl precio propuesto es opcional:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "v@a.mx", "password": "avant123"},
           follow_redirects=True)

    base = {
        "hospital_id": ang_id,
        "direccion_entrega": "Quirofano 3",
        "fecha_requerida": "2026-11-01",
        "insumo_id[]": str(ins_id), "insumo_cantidad[]": "2",
    }

    # Sin proponer nada: la nota se crea igual.
    r = c.post("/notas/nueva", data=dict(base), follow_redirects=True)
    check("nota sin propuesta se crea", r.status_code, 200)

    # Proponiendo un precio.
    con_propuesta = dict(base)
    con_propuesta["insumo_sugerido[]"] = "150.75"
    r = c.post("/notas/nueva", data=con_propuesta, follow_redirects=True)
    check("nota con propuesta se crea", r.status_code, 200)

    with app.app_context():
        from app.models import NotaVenta
        notas = NotaVenta.query.order_by(NotaVenta.id).all()
        sin_prop = notas[-2]
        con_prop = notas[-1]
        det_sin = sin_prop.detalles[0]
        det_con = con_prop.detalles[0]

        check("sin propuesta queda nulo", det_sin.precio_sugerido, None)
        check("con propuesta se guarda", float(det_con.precio_sugerido), 150.75)
        # Proponer no cobra: el precio que vale sigue en cero.
        check("proponer no fija el precio", float(det_con.precio_unitario), 0.0)
        check("la sugerencia esta pendiente", det_con.sugerencia_pendiente, True)
        check("y se le muestra al revisor precargada",
              float(det_con.precio_a_confirmar), 150.75)
        check("sin propuesta no precarga nada",
              float(det_sin.precio_a_confirmar), 0.0)
        con_prop_id, det_con_id = con_prop.id, det_con.id

    # Un texto invalido en la propuesta se rechaza sin perder la captura.
    malo = dict(base)
    malo["insumo_sugerido[]"] = "como cien"
    r = c.post("/notas/nueva", data=malo, follow_redirects=True)
    check("propuesta no numerica se rechaza",
          "no es un precio valido" in r.get_data(as_text=True), True)

    negativo = dict(base)
    negativo["insumo_sugerido[]"] = "-10"
    r = c.post("/notas/nueva", data=negativo, follow_redirects=True)
    check("propuesta negativa se rechaza",
          "no pueden ser negativos" in r.get_data(as_text=True), True)

print("\nEl revisor confirma la propuesta:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "a@a.mx", "password": "avant123"},
           follow_redirects=True)

    r = c.get(f"/revision/{con_prop_id}")
    texto = r.get_data(as_text=True)
    check("la pantalla muestra lo propuesto", "150.75" in texto, True)

    # Confirmar es guardar el valor precargado.
    r = c.post(f"/revision/{con_prop_id}/precios",
               data={f"precio_{det_con_id}": "150.75"}, follow_redirects=True)
    with app.app_context():
        from app.models import DetalleNotaVenta
        det = db.session.get(DetalleNotaVenta, det_con_id)
        check("precio confirmado", float(det.precio_unitario), 150.75)
        check("ya no esta pendiente", det.sugerencia_pendiente, False)
        check("la propuesta se conserva como historia",
              float(det.precio_sugerido), 150.75)

    # El revisor puede no estar de acuerdo.
    c.post(f"/revision/{con_prop_id}/precios",
           data={f"precio_{det_con_id}": "120.00"}, follow_redirects=True)
    with app.app_context():
        from app.models import DetalleNotaVenta
        det = db.session.get(DetalleNotaVenta, det_con_id)
        check("el revisor puede corregir a la baja",
              float(det.precio_unitario), 120.0)
        check("y se ve que el vendedor habia propuesto otra cosa",
              float(det.precio_sugerido), 150.75)

print("\n" + "=" * 50)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo paso.")
