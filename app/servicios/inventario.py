"""Apartado, liberacion y escritura del kardex.

Ninguna funcion de aqui hace commit: quien orquesta la operacion decide cuando
cerrar la transaccion, para que apartar diez renglones sea todo o nada.
"""

from app.constantes import Movimiento, TipoItem
from app.constantes import EstadoEquipo
from app.extensions import db
from app.models import HistorialMovimiento


class InventarioInsuficiente(Exception):
    """No alcanza el stock o el equipo no esta disponible."""


def registrar_movimiento(item_tipo, item_id, movimiento, usuario, **extra):
    """Escribe un renglon del kardex. Nunca se edita ni se borra."""
    mov = HistorialMovimiento(
        item_tipo=item_tipo,
        item_id=item_id,
        movimiento=movimiento,
        usuario_id=usuario.id if usuario else None,
        **extra,
    )
    db.session.add(mov)
    return mov


# --- Insumos ---------------------------------------------------------------


def apartar_insumo(insumo, cantidad, usuario, nota=None):
    """Compromete `cantidad` piezas repartiendolas entre almacenes.

    Toma de los almacenes que tengan disponible, en el orden en que esten
    dados de alta (Central primero). No mueve piezas fisicamente: solo las
    reserva, por eso el saldo del kardex no cambia.
    """
    if cantidad < 1:
        raise InventarioInsuficiente("La cantidad a apartar debe ser positiva.")

    if insumo.stock_disponible < cantidad:
        raise InventarioInsuficiente(
            f"{insumo.nombre}: se piden {cantidad} y hay "
            f"{insumo.stock_disponible} disponibles."
        )

    por_apartar = cantidad
    for existencia in insumo.existencias:
        if por_apartar == 0:
            break
        toma = min(existencia.disponible, por_apartar)
        if toma <= 0:
            continue

        existencia.apartado += toma
        por_apartar -= toma

        registrar_movimiento(
            TipoItem.INSUMO, insumo.id, Movimiento.APARTADO, usuario,
            cantidad=toma,
            # El apartado no saca piezas del almacen: el saldo fisico es el
            # mismo antes y despues. Lo que cambia es cuanto queda libre.
            saldo_anterior=existencia.cantidad,
            saldo_nuevo=existencia.cantidad,
            almacen_origen_id=existencia.almacen_id,
            nota_venta_id=nota.id if nota else None,
            detalle=f"Apartado en {existencia.almacen.nombre}",
        )

    if por_apartar:
        # No deberia ocurrir: se valido arriba. Si pasa, algo cambio en medio.
        raise InventarioInsuficiente(
            f"{insumo.nombre}: no se pudo apartar el total solicitado."
        )


def liberar_insumo(insumo, cantidad, usuario, nota=None, motivo="Liberado"):
    """Devuelve al disponible lo que se habia apartado."""
    por_liberar = cantidad
    for existencia in insumo.existencias:
        if por_liberar == 0:
            break
        suelta = min(existencia.apartado, por_liberar)
        if suelta <= 0:
            continue

        existencia.apartado -= suelta
        por_liberar -= suelta

        registrar_movimiento(
            TipoItem.INSUMO, insumo.id, Movimiento.LIBERADO, usuario,
            cantidad=suelta,
            saldo_anterior=existencia.cantidad,
            saldo_nuevo=existencia.cantidad,
            almacen_origen_id=existencia.almacen_id,
            nota_venta_id=nota.id if nota else None,
            detalle=f"{motivo} en {existencia.almacen.nombre}",
        )


# --- Equipo medico ---------------------------------------------------------


def apartar_equipo(equipo, usuario, nota=None):
    """Marca una pieza como comprometida. El equipo va por numero de serie."""
    if not equipo.disponible:
        raise InventarioInsuficiente(
            f"{equipo.descripcion}: esta {equipo.estado_etiqueta.lower()}, "
            "no disponible."
        )

    equipo.estado = EstadoEquipo.APARTADO
    registrar_movimiento(
        TipoItem.EQUIPO, equipo.id, Movimiento.APARTADO, usuario,
        cantidad=1,
        almacen_origen_id=equipo.almacen_id,
        nota_venta_id=nota.id if nota else None,
        detalle=f"Apartado para {nota.folio}" if nota else "Apartado",
    )


def liberar_equipo(equipo, usuario, nota=None, motivo="Liberado"):
    """Regresa la pieza a disponible.

    Solo si sigue apartada: si ya salio del almacen o esta en mantenimiento,
    liberarla aqui falsearia donde esta fisicamente.
    """
    if equipo.estado != EstadoEquipo.APARTADO:
        return

    equipo.estado = EstadoEquipo.DISPONIBLE
    registrar_movimiento(
        TipoItem.EQUIPO, equipo.id, Movimiento.LIBERADO, usuario,
        cantidad=1,
        almacen_origen_id=equipo.almacen_id,
        nota_venta_id=nota.id if nota else None,
        detalle=motivo,
    )
