"""Aprobacion, rechazo y cancelacion, con apartado de inventario y kardex."""

import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date  # noqa: E402

from app import create_app  # noqa: E402
from app.constantes import (EstadoEquipo, EstadoNota, Movimiento, Rol,  # noqa: E402
                            TipoItem)
from app.extensions import db  # noqa: E402

app = create_app("development")
app.config["WTF_CSRF_ENABLED"] = False
fallos = []


def check(etiqueta, obtenido, esperado):
    if obtenido != esperado:
        fallos.append(f"{etiqueta}: obtuvo {obtenido!r}, esperaba {esperado!r}")
    else:
        print(f"  ok  {etiqueta} = {obtenido!r}")


def nueva_nota(vendedor_id, insumo_id, cantidad, equipo_id=None, folio="AVS-2026-0001"):
    from app.models import DetalleNotaVenta, NotaVenta

    nota = NotaVenta(folio=folio, vendedor_id=vendedor_id,
                     hospital="Hospital Angeles Pedregal",
                     direccion_entrega="Quirofano 2",
                     fecha_requerida=date(2026, 10, 15))
    nota.detalles.append(DetalleNotaVenta(tipo=TipoItem.INSUMO, item_id=insumo_id,
                                          cantidad=cantidad, precio_unitario=38,
                                          descripcion_snapshot="Jeringa"))
    if equipo_id:
        nota.detalles.append(DetalleNotaVenta(tipo=TipoItem.EQUIPO, item_id=equipo_id,
                                             cantidad=1, precio_unitario=0,
                                             descripcion_snapshot="Torre"))
    db.session.add(nota)
    db.session.commit()
    return nota.id


with app.app_context():
    db.create_all()
    from app.models import (Almacen, EquipoMedico, Existencia,
                            HistorialMovimiento, Insumo, NotaVenta, Usuario)
    from app.servicios.inventario import InventarioInsuficiente
    from app.servicios.revision import (aprobar, cancelar, rechazar,
                                        revisar_disponibilidad)

    admin = Usuario(nombre="Admin", email="a@a.mx", rol=Rol.REVISOR_ADMIN)
    admin.set_password("avant123")
    vendedor = Usuario(nombre="Vende", email="v@a.mx", rol=Rol.VENDEDOR)
    vendedor.set_password("avant123")
    db.session.add_all([admin, vendedor])

    central = Almacen(nombre="Central")
    resteril = Almacen(nombre="Resteril")
    db.session.add_all([central, resteril])
    db.session.flush()

    # 30 en Central + 20 en Resteril = 50 disponibles.
    ins = Insumo(nombre="Jeringa 20 ml", codigo_barras="IN1", stock_minimo=5)
    ins.existencias.append(Existencia(almacen=central, cantidad=30))
    ins.existencias.append(Existencia(almacen=resteril, cantidad=20))
    eq = EquipoMedico(nombre="Torre", codigo_barras="TOLA1", numero_serie="SN-1",
                      almacen=central)
    db.session.add_all([ins, eq])
    db.session.commit()
    ins_id, eq_id, admin_id, vend_id = ins.id, eq.id, admin.id, vendedor.id

    print("Disponibilidad antes de aprobar:")
    nota_id = nueva_nota(vend_id, ins_id, 40, eq_id)
    nota = db.session.get(NotaVenta, nota_id)
    filas = revisar_disponibilidad(nota)
    check("renglones revisados", len(filas), 2)
    check("insumo alcanza (40 de 50)", filas[0]["ok"], True)
    check("equipo disponible", filas[1]["ok"], True)

    print("\nAprobar aparta y escribe kardex:")
    aprobar(nota, admin)
    ins = db.session.get(Insumo, ins_id)
    eq = db.session.get(EquipoMedico, eq_id)
    nota = db.session.get(NotaVenta, nota_id)

    check("estado", nota.estado, EstadoNota.APROBADA)
    check("quedo registrado quien reviso", nota.revisado_por_id, admin_id)
    check("stock fisico intacto", ins.stock_actual, 50)
    check("apartado", ins.stock_apartado, 40)
    check("disponible baja", ins.stock_disponible, 10)
    check("equipo apartado", eq.estado, EstadoEquipo.APARTADO)

    # 40 piezas: 30 salen de Central y 10 de Resteril.
    check("Central apartado", ins.existencia_en(central.id).apartado, 30)
    check("Resteril apartado", ins.existencia_en(resteril.id).apartado, 10)

    movs = HistorialMovimiento.query.filter_by(
        movimiento=Movimiento.APARTADO).all()
    check("renglones de kardex (2 almacenes + 1 equipo)", len(movs), 3)
    mov_central = [m for m in movs if m.almacen_origen_id == central.id
                   and m.item_tipo == TipoItem.INSUMO][0]
    check("kardex: cantidad apartada en Central", mov_central.cantidad, 30)
    # Apartar no saca piezas: el saldo fisico no cambia.
    check("kardex: saldo anterior", mov_central.saldo_anterior, 30)
    check("kardex: saldo nuevo", mov_central.saldo_nuevo, 30)
    check("kardex: ligado a la nota", mov_central.nota_venta_id, nota_id)

    print("\nNo se puede aprobar dos veces:")
    try:
        aprobar(nota, admin)
        check("segunda aprobacion", "no fallo", "deberia fallar")
    except Exception as e:
        check("segunda aprobacion rechazada", type(e).__name__, "ErrorDeRevision")

    print("\nUna segunda nota no puede llevarse lo que ya no hay:")
    nota2_id = nueva_nota(vend_id, ins_id, 20, folio="AVS-2026-0002")
    nota2 = db.session.get(NotaVenta, nota2_id)
    filas2 = revisar_disponibilidad(nota2)
    check("la pantalla avisa del faltante", filas2[0]["ok"], False)
    check("dice cuantas faltan", filas2[0]["aviso"], "Faltan 10")

    try:
        aprobar(nota2, admin)
        check("aprobacion sin stock", "no fallo", "deberia fallar")
    except InventarioInsuficiente:
        print("  ok  aprobacion sin stock rechazada")

    ins = db.session.get(Insumo, ins_id)
    check("el rollback dejo el apartado intacto", ins.stock_apartado, 40)
    check("nota2 sigue pendiente",
          db.session.get(NotaVenta, nota2_id).estado, EstadoNota.PENDIENTE_REVISION)

    print("\nCancelar devuelve lo apartado:")
    nota = db.session.get(NotaVenta, nota_id)
    cancelar(nota, admin, "Se suspendio la cirugia")
    ins = db.session.get(Insumo, ins_id)
    eq = db.session.get(EquipoMedico, eq_id)
    check("estado", db.session.get(NotaVenta, nota_id).estado, EstadoNota.CANCELADA)
    check("apartado liberado", ins.stock_apartado, 0)
    check("disponible restaurado", ins.stock_disponible, 50)
    check("equipo vuelve a disponible", eq.estado, EstadoEquipo.DISPONIBLE)
    liberados = HistorialMovimiento.query.filter_by(
        movimiento=Movimiento.LIBERADO).count()
    check("kardex registra la liberacion", liberados, 3)

    print("\nRechazo:")
    nota2 = db.session.get(NotaVenta, nota2_id)
    try:
        rechazar(nota2, admin, "   ")
        check("rechazo sin motivo", "no fallo", "deberia fallar")
    except Exception as e:
        check("rechazo sin motivo se bloquea", type(e).__name__, "ErrorDeRevision")

    rechazar(nota2, admin, "No hay stock hasta el jueves")
    nota2 = db.session.get(NotaVenta, nota2_id)
    check("estado", nota2.estado, EstadoNota.RECHAZADA)
    check("motivo guardado", nota2.motivo_rechazo, "No hay stock hasta el jueves")
    check("rechazar no toca inventario",
          db.session.get(Insumo, ins_id).stock_apartado, 0)
    check("rechazada es final", nota2.puede_pasar_a(EstadoNota.APROBADA), False)

print("\nPor HTTP:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "a@a.mx", "password": "avant123"},
           follow_redirects=True)
    with app.app_context():
        from app.models import NotaVenta
        nid = nueva_nota(vend_id, ins_id, 5, folio="AVS-2026-0003")

    r = c.get(f"/revision/{nid}")
    check("GET revisar", r.status_code, 200)
    check("muestra disponibilidad", "Disponibilidad" in r.get_data(as_text=True), True)

    r = c.post(f"/revision/{nid}/aprobar", follow_redirects=True)
    check("POST aprobar", r.status_code, 200)
    check("confirma el apartado", "apartado" in r.get_data(as_text=True).lower(), True)

    with app.app_context():
        from app.models import NotaVenta
        check("estado tras aprobar por HTTP",
              db.session.get(NotaVenta, nid).estado, EstadoNota.APROBADA)

# Un vendedor no debe poder aprobar.
with app.test_client() as c:
    c.post("/auth/login", data={"email": "v@a.mx", "password": "avant123"},
           follow_redirects=True)
    r = c.post(f"/revision/{nid}/aprobar")
    check("vendedor no puede aprobar", r.status_code, 403)

print("\n" + "=" * 50)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo paso.")
