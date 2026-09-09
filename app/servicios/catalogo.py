"""Altas y ajustes del catalogo.

El ajuste de existencias vive aqui y no en la vista porque mover piezas a mano
tambien es un movimiento de inventario: tiene que quedar en el kardex con su
saldo anterior y nuevo, igual que una salida.
"""

import re

from app.constantes import Movimiento, TipoItem
from app.extensions import db
from app.models import EquipoMedico, Existencia, Insumo
from app.servicios.inventario import registrar_movimiento


class ErrorDeCatalogo(Exception):
    """Problema de captura que el usuario puede corregir."""


def sugerir_codigo(nombre, modelo=None):
    """Propone un codigo de barras corto, al estilo del sistema anterior.

    Alli usaban cosas como TOLA1 para "Torre de Laparoscopia" o ENBO1 para
    "Energia Bipolar": las primeras letras de las dos primeras palabras y un
    consecutivo. Es solo una sugerencia; quien da de alta puede cambiarla.
    """
    palabras = [p for p in re.split(r"\W+", (nombre or "").upper()) if len(p) > 2]
    # Las palabras de enlace no aportan nada al codigo.
    palabras = [p for p in palabras if p not in ("DEL", "LOS", "LAS", "CON", "PARA")]

    if not palabras:
        base = "ART"
    elif len(palabras) == 1:
        base = palabras[0][:4]
    else:
        base = palabras[0][:2] + palabras[1][:2]

    if modelo:
        limpio = re.sub(r"\W+", "", modelo.upper())[:2]
        if limpio:
            base = base[:3] + limpio[:1]

    return _con_consecutivo(base)


def _con_consecutivo(base):
    """Le pega un numero para que no choque con otro ya existente."""
    for numero in range(1, 1000):
        candidato = f"{base}{numero}"
        if not _codigo_ocupado(candidato):
            return candidato
    return base


def _codigo_ocupado(codigo):
    if EquipoMedico.query.filter_by(codigo_barras=codigo).first():
        return True
    return Insumo.query.filter_by(codigo_barras=codigo).first() is not None


def validar_codigo_libre(codigo, modelo, id_actual=None):
    """El codigo de barras es unico entre equipos e insumos, no solo dentro de
    cada tabla: el escaner no sabe de que tipo es lo que lee."""
    codigo = (codigo or "").strip()
    if not codigo:
        raise ErrorDeCatalogo("El codigo de barras no puede quedar vacio.")

    for clase in (EquipoMedico, Insumo):
        existente = clase.query.filter_by(codigo_barras=codigo).first()
        if existente is None:
            continue
        if clase is modelo and id_actual is not None and existente.id == id_actual:
            continue
        etiqueta = "un equipo" if clase is EquipoMedico else "un insumo"
        raise ErrorDeCatalogo(
            f"El codigo {codigo} ya lo usa {etiqueta}: {existente.descripcion}."
        )
    return codigo


def ajustar_existencia(insumo, almacen, cantidad_nueva, usuario, motivo=None):
    """Fija las piezas de un insumo en un almacen y lo deja en el kardex.

    Es la unica forma de mover existencias sin una nota de venta detras: alta
    inicial, conteo fisico, merma. Nunca baja de lo que ya esta apartado,
    porque esas piezas estan comprometidas en notas aprobadas.
    """
    if cantidad_nueva < 0:
        raise ErrorDeCatalogo("Las existencias no pueden ser negativas.")

    existencia = insumo.existencia_en(almacen.id)
    if existencia is None:
        existencia = Existencia(insumo=insumo, almacen=almacen,
                                cantidad=0, apartado=0)
        db.session.add(existencia)
        insumo.existencias.append(existencia)

    if cantidad_nueva < existencia.apartado:
        raise ErrorDeCatalogo(
            f"En {almacen.nombre} hay {existencia.apartado} piezas apartadas "
            f"en notas aprobadas: no se puede dejar el saldo en "
            f"{cantidad_nueva}."
        )

    anterior = existencia.cantidad
    if anterior == cantidad_nueva:
        return existencia

    existencia.cantidad = cantidad_nueva
    diferencia = cantidad_nueva - anterior

    registrar_movimiento(
        TipoItem.INSUMO, insumo.id, Movimiento.AJUSTE_STOCK, usuario,
        cantidad=abs(diferencia),
        saldo_anterior=anterior,
        saldo_nuevo=cantidad_nueva,
        almacen_origen_id=almacen.id,
        costo_unitario=insumo.costo_unitario,
        importe=(insumo.costo_unitario or 0) * abs(diferencia),
        detalle=motivo or (
            f"Ajuste manual en {almacen.nombre} "
            f"({'+' if diferencia > 0 else ''}{diferencia})"
        ),
    )
    return existencia


def alta_inicial(insumo, cantidades_por_almacen, usuario):
    """Carga las existencias de un insumo recien dado de alta."""
    for almacen, cantidad in cantidades_por_almacen:
        if cantidad:
            ajustar_existencia(insumo, almacen, cantidad, usuario,
                               motivo=f"Alta inicial en {almacen.nombre}")
