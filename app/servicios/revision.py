"""Revision de notas: aprobar, rechazar y cancelar.

Es el paso que el sistema anterior no tenia: alli el vendedor guardaba y las
remisiones salian solas. Aqui alguien verifica disponibilidad antes de
comprometer inventario.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app.constantes import EstadoNota, TipoItem
from app.extensions import db
from app.servicios.inventario import (InventarioInsuficiente, apartar_equipo,
                                      apartar_insumo, liberar_equipo,
                                      liberar_insumo)


class ErrorDeRevision(Exception):
    """Problema que el revisor puede entender y corregir."""


def revisar_disponibilidad(nota):
    """Dice, renglon por renglon, si hay con que surtir.

    Es solo lectura: sirve para pintar la pantalla antes de decidir. La
    comprobacion que manda es la que hace aprobar(), porque entre que se ve la
    pantalla y se pulsa el boton otra nota pudo llevarse el stock.
    """
    filas = []
    for detalle in nota.detalles:
        item = detalle.item
        fila = {
            "detalle": detalle,
            "item": item,
            "descripcion": detalle.descripcion,
            "cantidad": detalle.cantidad,
        }

        if item is None:
            fila.update(ok=False, disponible=0,
                        aviso="El articulo ya no esta en el catalogo.")
        elif detalle.tipo == TipoItem.INSUMO:
            disponible = item.stock_disponible
            fila.update(
                ok=disponible >= detalle.cantidad,
                disponible=disponible,
                aviso=None if disponible >= detalle.cantidad
                else f"Faltan {detalle.cantidad - disponible}",
            )
        else:
            fila.update(
                ok=item.disponible,
                disponible=1 if item.disponible else 0,
                aviso=None if item.disponible else item.estado_etiqueta,
            )

        filas.append(fila)
    return filas


def hay_faltantes(filas):
    return any(not f["ok"] for f in filas)


def aprobar(nota, revisor):
    """Aparta el inventario y pasa la nota a aprobada, todo o nada."""
    if not nota.puede_pasar_a(EstadoNota.APROBADA):
        raise ErrorDeRevision(
            f"Una nota {nota.estado_etiqueta.lower()} no se puede aprobar."
        )

    try:
        for detalle in nota.detalles:
            item = detalle.item
            if item is None:
                raise ErrorDeRevision(
                    f"'{detalle.descripcion}' ya no esta en el catalogo. "
                    "Pide al vendedor que corrija la nota."
                )
            if detalle.tipo == TipoItem.INSUMO:
                apartar_insumo(item, detalle.cantidad, revisor, nota)
            else:
                apartar_equipo(item, revisor, nota)

        nota.estado = EstadoNota.APROBADA
        nota.revisado_por_id = revisor.id
        nota.fecha_revision = datetime.now(timezone.utc)
        nota.motivo_rechazo = None

        db.session.commit()
    except (InventarioInsuficiente, ErrorDeRevision):
        # Sin commit no se aparto nada: el rollback deja el inventario intacto.
        db.session.rollback()
        raise

    return nota


def rechazar(nota, revisor, motivo):
    """Cierra la nota sin tocar inventario. El motivo es obligatorio."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErrorDeRevision("Escribe el motivo del rechazo para el vendedor.")

    if not nota.puede_pasar_a(EstadoNota.RECHAZADA):
        raise ErrorDeRevision(
            f"Una nota {nota.estado_etiqueta.lower()} no se puede rechazar."
        )

    nota.estado = EstadoNota.RECHAZADA
    nota.motivo_rechazo = motivo
    nota.revisado_por_id = revisor.id
    nota.fecha_revision = datetime.now(timezone.utc)
    db.session.commit()
    return nota


def cancelar(nota, usuario, motivo="Nota cancelada"):
    """Cancela y devuelve al almacen lo que estuviera apartado.

    Sin esto, aprobar seria un camino sin retorno: el inventario quedaria
    comprometido para siempre.

    PENDIENTE con el jefe (CONTEXTO_PROYECTO.md, §9): que hacer con una
    remision ya generada. Por ahora se marca cancelada, pero la regla del
    negocio no esta definida.
    """
    if not nota.puede_pasar_a(EstadoNota.CANCELADA):
        raise ErrorDeRevision(
            f"Una nota {nota.estado_etiqueta.lower()} no se puede cancelar."
        )

    estaba_apartada = nota.estado in (
        EstadoNota.APROBADA, EstadoNota.REMISION_GENERADA
    )

    if estaba_apartada:
        for detalle in nota.detalles:
            item = detalle.item
            if item is None:
                continue
            if detalle.tipo == TipoItem.INSUMO:
                liberar_insumo(item, detalle.cantidad, usuario, nota, motivo)
            else:
                liberar_equipo(item, usuario, nota, motivo)

    for remision in nota.remisiones:
        remision.cancelada = True

    nota.estado = EstadoNota.CANCELADA
    db.session.commit()
    return nota


def guardar_precios(nota, form, revisor):
    """Captura los precios negociados de la nota.

    Los insumos no tienen lista: el precio se acuerda en cada venta y solo el
    revisor lo fija. El equipo trae la tarifa del hospital, pero tambien se
    puede corregir aqui.

    Solo se admite mientras la nota siga en revision: una vez aprobada, el
    inventario ya esta comprometido y los documentos emitidos deben cuadrar.
    """
    if nota.estado != EstadoNota.PENDIENTE_REVISION:
        raise ErrorDeRevision(
            "Los precios solo se pueden capturar mientras la nota esta en "
            "revision."
        )

    for detalle in nota.detalles:
        crudo = form.get(f"precio_{detalle.id}")
        if crudo is None or crudo.strip() == "":
            continue
        try:
            precio = Decimal(crudo.strip())
        except (InvalidOperation, ValueError):
            raise ErrorDeRevision(
                f"'{crudo}' no es un precio valido para {detalle.descripcion}."
            )
        if precio < 0:
            raise ErrorDeRevision("Los precios no pueden ser negativos.")
        detalle.precio_unitario = precio

    db.session.commit()
    return nota


def renglones_sin_precio(nota):
    """Renglones en cero. Se avisa, no se bloquea: puede haber cortesias."""
    return [d for d in nota.detalles if not d.precio_unitario]
