"""Comprueba las reglas de negocio sacadas del sistema anterior."""

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
fallos = []


def check(etiqueta, obtenido, esperado):
    if obtenido != esperado:
        fallos.append(f"{etiqueta}: obtuvo {obtenido!r}, esperaba {esperado!r}")
    else:
        print(f"  ok  {etiqueta} = {obtenido!r}")


with app.app_context():
    db.create_all()
    from app.models import (Almacen, DetalleNotaVenta, Existencia, Insumo,
                            NotaVenta, Usuario)

    print("Regla de razon social (del template de remision):")
    check("Hospital Angeles Pedregal", Empresa.para_hospital("Hospital Angeles Pedregal"),
          Empresa.SOLUCIONES)
    check("Hospital Ángeles (con acento)", Empresa.para_hospital("Hospital Ángeles del Carmen"),
          Empresa.SOLUCIONES)
    check("Bite Medica", Empresa.para_hospital("Bite Medica"), Empresa.GARDE)
    check("RFC Angeles",
          Empresa.datos_para_hospital("Angeles Lomas")["rfc"], "MPB210816298")
    check("RFC otros",
          Empresa.datos_para_hospital("Medica Sur")["rfc"], "AGM210811HD9")

    print("\nEl catalogo de hospitales manda sobre el nombre:")
    from app.models import EquipoMedico, Hospital, TarifaEquipo, precio_renta

    # Un hospital del Grupo Angeles marcado a proposito como la otra empresa:
    # debe ganar el dato capturado, no lo que sugiere el nombre.
    raro = Hospital(nombre="Hospital Angeles del Norte", empresa=Empresa.GARDE)
    bite = Hospital(nombre="Bite Medica", empresa=Empresa.GARDE)
    angeles = Hospital(nombre="Hospital Angeles Pedregal",
                       empresa=Empresa.SOLUCIONES)
    db.session.add_all([raro, bite, angeles])
    db.session.commit()
    check("el dato capturado gana al nombre", raro.empresa, Empresa.GARDE)
    check("y la regla de texto habria dicho otra cosa",
          Empresa.para_hospital(raro.nombre), Empresa.SOLUCIONES)

    print("\nTarifa de renta por hospital:")
    equipo = EquipoMedico(nombre="Torre", codigo_barras="TOLA9")
    db.session.add(equipo)
    db.session.commit()
    db.session.add_all([
        TarifaEquipo(equipo_id=equipo.id, hospital_id=angeles.id,
                     precio_renta=8500, vigente_desde=date(2026, 1, 1)),
        TarifaEquipo(equipo_id=equipo.id, hospital_id=bite.id,
                     precio_renta=7200, vigente_desde=date(2026, 1, 1)),
    ])
    db.session.commit()
    check("mismo equipo, un hospital", float(precio_renta(equipo, angeles)), 8500.0)
    check("mismo equipo, otro hospital", float(precio_renta(equipo, bite)), 7200.0)
    # Sin tarifa devuelve None, no cero: son cosas distintas.
    check("sin tarifa capturada", precio_renta(equipo, raro), None)

    insumo = Insumo(nombre="Set", codigo_barras="X1", stock_minimo=10)
    db.session.add(insumo)
    db.session.commit()

    print("\nStock repartido en almacenes:")
    central = Almacen(nombre="Central")
    resteril = Almacen(nombre="Resteril")
    db.session.add_all([central, resteril])
    db.session.flush()
    insumo.existencias.append(Existencia(almacen=central, cantidad=180, apartado=30))
    insumo.existencias.append(Existencia(almacen=resteril, cantidad=70))
    db.session.commit()
    check("stock_actual suma almacenes", insumo.stock_actual, 250)
    check("stock_apartado", insumo.stock_apartado, 30)
    check("stock_disponible", insumo.stock_disponible, 220)
    check("existencia_en(Central)", insumo.existencia_en(central.id).cantidad, 180)
    check("bajo_minimo con 220 disp. y min 10", insumo.bajo_minimo, False)

    print("\nTotales de la nota con IVA 16%:")
    u = Usuario(nombre="V", email="v@a.mx", rol=Rol.VENDEDOR)
    u.set_password("x")
    db.session.add(u)
    db.session.flush()

    nota = NotaVenta(folio="AVS-2026-0001", vendedor_id=u.id,
                     hospital="Hospital Angeles Pedregal",
                     direccion_entrega="Quirofano 2",
                     fecha_requerida=date(2026, 10, 1))
    nota.detalles.append(DetalleNotaVenta(tipo=TipoItem.INSUMO, item_id=insumo.id,
                                          cantidad=2, precio_unitario=480))
    nota.detalles.append(DetalleNotaVenta(tipo=TipoItem.INSUMO, item_id=insumo.id,
                                          cantidad=1, precio_unitario=40))
    db.session.add(nota)
    db.session.commit()

    check("subtotal", float(nota.subtotal), 1000.0)
    check("iva", float(nota.iva), 160.0)
    check("total", float(nota.total), 1160.0)
    check("empresa por hospital", nota.datos_empresa["razon_social"],
          "AVANT SOLUCIONES MEDICAS")

    print("\nTransiciones de estado:")
    check("pendiente -> aprobada", nota.puede_pasar_a(EstadoNota.APROBADA), True)
    check("pendiente -> entregada (invalida)",
          nota.puede_pasar_a(EstadoNota.ENTREGADA), False)
    check("rechazada es final",
          EstadoNota.puede_pasar_a(EstadoNota.RECHAZADA, EstadoNota.APROBADA), False)

print("\n" + "=" * 50)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo paso.")
