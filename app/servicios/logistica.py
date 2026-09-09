"""Logistica: checklist de doble verificacion, entrega y regreso de equipo.

Aqui es donde el inventario deja de estar solo apartado y se mueve de verdad.

Momento del descuento: los insumos se descuentan al marcar la entrega, no al
salir del almacen. Es lo que dice el flujo acordado ("al cerrar, los insumos se
descuentan definitivamente"). Mientras el tecnico va en camino siguen contando
como existencia apartada, asi que nadie mas puede comprometerlos.
"""

from datetime import datetime, timezone

from app.constantes import (Checklist, EstadoEquipo, EstadoNota, Movimiento,
                            TipoItem)
from app.extensions import db
from app.models import ChecklistItem, Entrega
from app.servicios.inventario import registrar_movimiento


class ErrorDeLogistica(Exception):
    """Problema que el tecnico puede entender y corregir."""


def _ahora():
    return datetime.now(timezone.utc)


def obtener_o_crear_entrega(nota, tecnico):
    """Asigna la nota a un tecnico y prepara su checklist.

    Se crean dos renglones de checklist por articulo, uno para el almacen y
    otro para el hospital: esa es la doble verificacion.
    """
    if nota.entrega:
        return nota.entrega

    if nota.estado not in (EstadoNota.REMISION_GENERADA, EstadoNota.EN_LOGISTICA):
        raise ErrorDeLogistica(
            f"Una nota {nota.estado_etiqueta.lower()} todavia no sale a "
            "logistica. Falta generar la remision."
        )

    entrega = Entrega(nota_venta_id=nota.id, tecnico_id=tecnico.id)
    db.session.add(entrega)
    db.session.flush()

    for detalle in nota.detalles:
        for etapa in Checklist.ETAPAS:
            db.session.add(ChecklistItem(
                entrega_id=entrega.id, detalle_id=detalle.id, etapa=etapa
            ))

    db.session.commit()
    return entrega


def items_de(entrega, etapa):
    return [i for i in entrega.checklist if i.etapa == etapa]


def etapa_completa(entrega, etapa):
    items = items_de(entrega, etapa)
    return bool(items) and all(i.verificado for i in items)


def verificar_por_codigo(entrega, etapa, codigo):
    """Marca un articulo como verificado si el codigo escaneado es el suyo.

    Devuelve el renglon verificado. Que el codigo tenga que coincidir con el
    articulo asignado es justamente el control: no basta con escanear
    cualquier cosa.
    """
    codigo = (codigo or "").strip()
    if not codigo:
        raise ErrorDeLogistica("No se leyo ningun codigo.")

    if etapa not in Checklist.ETAPAS:
        raise ErrorDeLogistica("Etapa de checklist desconocida.")

    if etapa == Checklist.ETAPA_HOSPITAL and not entrega.checklist_almacen_ok:
        raise ErrorDeLogistica(
            "Primero hay que completar la verificacion en almacen."
        )

    pendientes = [i for i in items_de(entrega, etapa) if not i.verificado]

    for item in pendientes:
        articulo = item.detalle.item
        if articulo is not None and articulo.codigo_barras == codigo:
            item.verificado = True
            item.codigo_escaneado = codigo
            item.fecha = _ahora()
            _cerrar_etapa_si_toca(entrega, etapa)
            db.session.commit()
            return item

    # Distinguir "ya lo escaneaste" de "ese no va en esta entrega" le ahorra
    # al tecnico buscar un error que no existe.
    ya_verificados = [
        i for i in items_de(entrega, etapa)
        if i.verificado and i.codigo_escaneado == codigo
    ]
    if ya_verificados:
        raise ErrorDeLogistica("Ese articulo ya estaba verificado.")

    raise ErrorDeLogistica(
        f"El codigo {codigo} no corresponde a ningun articulo de esta entrega."
    )


def _cerrar_etapa_si_toca(entrega, etapa):
    if not etapa_completa(entrega, etapa):
        return

    if etapa == Checklist.ETAPA_ALMACEN:
        entrega.checklist_almacen_ok = True
        entrega.fecha_checklist_almacen = _ahora()
        _registrar_salida(entrega)
    else:
        entrega.checklist_hospital_ok = True
        entrega.fecha_checklist_hospital = _ahora()


def _registrar_salida(entrega):
    """El cargamento sale del almacen con el tecnico.

    No descuenta piezas: solo deja constancia de que salieron y de que el
    equipo ya no esta fisicamente en el almacen.

    Cada renglon anota de que almacen salio. Sin eso, preguntarle al kardex
    "que salio de Central" no devolveria las salidas, que es justo lo que se
    quiere saber.
    """
    nota = entrega.nota
    quien = entrega.tecnico

    for detalle in nota.detalles:
        articulo = detalle.item
        if articulo is None:
            continue

        if detalle.tipo == TipoItem.EQUIPO:
            articulo.ubicacion_actual = "En ruta"
            registrar_movimiento(
                TipoItem.EQUIPO, articulo.id, Movimiento.SALIDA, quien,
                cantidad=1,
                almacen_origen_id=articulo.almacen_id,
                nota_venta_id=nota.id,
                detalle=f"Salida de almacen con {quien.nombre}",
            )
            continue

        # Los insumos pudieron apartarse en varios almacenes: sale un renglon
        # por cada uno, igual que al apartar y al consumir.
        pendiente = detalle.cantidad
        for existencia in articulo.existencias:
            if pendiente <= 0:
                break
            toma = min(existencia.apartado, pendiente)
            if toma <= 0:
                continue
            pendiente -= toma
            registrar_movimiento(
                TipoItem.INSUMO, articulo.id, Movimiento.SALIDA, quien,
                cantidad=toma,
                saldo_anterior=existencia.cantidad,
                saldo_nuevo=existencia.cantidad,
                almacen_origen_id=existencia.almacen_id,
                nota_venta_id=nota.id,
                detalle=f"Salida de {existencia.almacen.nombre} con {quien.nombre}",
            )

    if nota.puede_pasar_a(EstadoNota.EN_LOGISTICA):
        nota.estado = EstadoNota.EN_LOGISTICA


def marcar_entregada(entrega, tecnico, recibe_nombre=None, observaciones=None):
    """Cierra la entrega en el hospital y descuenta el inventario.

    Aqui los insumos salen definitivamente del stock y el equipo pasa a
    rentado. Exige la doble verificacion completa.
    """
    nota = entrega.nota

    if not entrega.checklist_almacen_ok:
        raise ErrorDeLogistica("Falta la verificacion en almacen.")
    if not entrega.checklist_hospital_ok:
        raise ErrorDeLogistica("Falta la verificacion en el hospital.")
    if not nota.puede_pasar_a(EstadoNota.ENTREGADA):
        raise ErrorDeLogistica(
            f"Una nota {nota.estado_etiqueta.lower()} no se puede entregar."
        )

    for detalle in nota.detalles:
        articulo = detalle.item
        if articulo is None:
            continue

        if detalle.tipo == TipoItem.INSUMO:
            _consumir_insumo(articulo, detalle.cantidad, tecnico, nota)
        else:
            articulo.estado = EstadoEquipo.RENTADO
            articulo.ubicacion_actual = nota.hospital
            registrar_movimiento(
                TipoItem.EQUIPO, articulo.id, Movimiento.ENTREGADO, tecnico,
                cantidad=1,
                almacen_origen_id=articulo.almacen_id,
                nota_venta_id=nota.id,
                detalle=f"Entregado en {nota.hospital}",
            )

    entrega.fecha_entrega = _ahora()
    entrega.recibe_nombre = (recibe_nombre or "").strip() or None
    entrega.observaciones = (observaciones or "").strip() or None
    nota.estado = EstadoNota.ENTREGADA

    # Una nota sin equipo no tiene nada que esperar de vuelta.
    if not nota.detalles_equipo:
        nota.estado = EstadoNota.CERRADA

    db.session.commit()
    return entrega


def _consumir_insumo(insumo, cantidad, usuario, nota):
    """Descuenta piezas de los almacenes donde estaban apartadas."""
    por_consumir = cantidad

    for existencia in insumo.existencias:
        if por_consumir == 0:
            break
        toma = min(existencia.apartado, por_consumir)
        if toma <= 0:
            continue

        saldo_anterior = existencia.cantidad
        existencia.cantidad -= toma
        existencia.apartado -= toma
        por_consumir -= toma

        registrar_movimiento(
            TipoItem.INSUMO, insumo.id, Movimiento.CONSUMIDO, usuario,
            cantidad=toma,
            saldo_anterior=saldo_anterior,
            saldo_nuevo=existencia.cantidad,
            almacen_origen_id=existencia.almacen_id,
            nota_venta_id=nota.id,
            costo_unitario=insumo.costo_unitario,
            importe=(insumo.costo_unitario or 0) * toma,
            detalle=f"Consumido en {nota.hospital}",
        )

    if por_consumir:
        raise ErrorDeLogistica(
            f"{insumo.nombre}: faltaron {por_consumir} piezas apartadas. "
            "Revisa si la nota se modifico despues de aprobarse."
        )


def registrar_regreso(entrega, equipo, tecnico, estado_recibido, observaciones=None):
    """Devuelve una pieza al almacen. Cierra la nota cuando vuelve todo."""
    nota = entrega.nota

    if estado_recibido not in (EstadoEquipo.DISPONIBLE, EstadoEquipo.MANTENIMIENTO):
        raise ErrorDeLogistica(
            "Al recibir, el equipo solo puede quedar disponible o en "
            "mantenimiento."
        )

    if equipo.estado != EstadoEquipo.RENTADO:
        raise ErrorDeLogistica(
            f"{equipo.descripcion} no esta rentado; esta "
            f"{equipo.estado_etiqueta.lower()}."
        )

    equipo.estado = estado_recibido
    equipo.ubicacion_actual = (
        equipo.almacen.nombre if equipo.almacen else "Almacen"
    )

    registrar_movimiento(
        TipoItem.EQUIPO, equipo.id, Movimiento.REGRESO_ALMACEN, tecnico,
        cantidad=1,
        almacen_destino_id=equipo.almacen_id,
        nota_venta_id=nota.id,
        detalle=observaciones or f"Regreso al almacen ({estado_recibido})",
    )

    for responsiva in entrega.responsivas:
        if responsiva.equipo_id == equipo.id and not responsiva.cerrada:
            responsiva.fecha_devolucion = _ahora()

    if _todo_el_equipo_regreso(nota):
        entrega.fecha_regreso_equipo = _ahora()
        if nota.puede_pasar_a(EstadoNota.CERRADA):
            nota.estado = EstadoNota.CERRADA

    db.session.commit()
    return equipo


def _todo_el_equipo_regreso(nota):
    for detalle in nota.detalles_equipo:
        equipo = detalle.item
        if equipo is not None and equipo.estado == EstadoEquipo.RENTADO:
            return False
    return True


def equipo_pendiente_de_regreso(nota):
    """Piezas de esta nota que siguen en el hospital."""
    pendientes = []
    for detalle in nota.detalles_equipo:
        equipo = detalle.item
        if equipo is not None and equipo.estado == EstadoEquipo.RENTADO:
            pendientes.append(equipo)
    return pendientes
