"""Consulta del kardex.

Los movimientos se vienen escribiendo desde el modulo de revision, pero hasta
ahora no habia forma de verlos. Esto es solo lectura: el historial es
append-only y no se edita desde ninguna pantalla.
"""

from datetime import datetime, time

from sqlalchemy import or_

from app.constantes import TipoItem
from app.extensions import db
from app.models import (EquipoMedico, HistorialMovimiento, Insumo, NotaVenta,
                        Usuario)

POR_PAGINA = 50


def _ids_que_coinciden(texto):
    """Ids de equipos e insumos cuyo nombre, SKU o codigo coincide."""
    patron = f"%{texto}%"

    equipos = [
        e.id for e in EquipoMedico.query.filter(
            or_(EquipoMedico.nombre.ilike(patron),
                EquipoMedico.codigo_barras.ilike(patron),
                EquipoMedico.numero_serie.ilike(patron))
        ).all()
    ]
    insumos = [
        i.id for i in Insumo.query.filter(
            or_(Insumo.nombre.ilike(patron),
                Insumo.codigo_barras.ilike(patron),
                Insumo.sku.ilike(patron))
        ).all()
    ]
    return equipos, insumos


def construir_consulta(filtros):
    """Arma la consulta del kardex a partir de los filtros de la pantalla."""
    consulta = HistorialMovimiento.query

    texto = (filtros.get("texto") or "").strip()
    if texto:
        equipos, insumos = _ids_que_coinciden(texto)
        condiciones = [HistorialMovimiento.detalle.ilike(f"%{texto}%")]
        if equipos:
            condiciones.append(db.and_(
                HistorialMovimiento.item_tipo == TipoItem.EQUIPO,
                HistorialMovimiento.item_id.in_(equipos),
            ))
        if insumos:
            condiciones.append(db.and_(
                HistorialMovimiento.item_tipo == TipoItem.INSUMO,
                HistorialMovimiento.item_id.in_(insumos),
            ))
        consulta = consulta.filter(or_(*condiciones))

    if filtros.get("movimiento"):
        consulta = consulta.filter(
            HistorialMovimiento.movimiento == filtros["movimiento"])

    if filtros.get("item_tipo"):
        consulta = consulta.filter(
            HistorialMovimiento.item_tipo == filtros["item_tipo"])

    if filtros.get("almacen_id"):
        almacen_id = int(filtros["almacen_id"])
        consulta = consulta.filter(or_(
            HistorialMovimiento.almacen_origen_id == almacen_id,
            HistorialMovimiento.almacen_destino_id == almacen_id,
        ))

    # Las fechas del formulario son dias; el movimiento tiene hora. Se abre el
    # rango al dia completo para que "hasta hoy" incluya lo de hoy.
    if filtros.get("desde"):
        consulta = consulta.filter(
            HistorialMovimiento.fecha >= datetime.combine(
                filtros["desde"], time.min))
    if filtros.get("hasta"):
        consulta = consulta.filter(
            HistorialMovimiento.fecha <= datetime.combine(
                filtros["hasta"], time.max))

    if filtros.get("item_tipo_exacto") and filtros.get("item_id"):
        consulta = consulta.filter(
            HistorialMovimiento.item_tipo == filtros["item_tipo_exacto"],
            HistorialMovimiento.item_id == filtros["item_id"],
        )

    return consulta.order_by(HistorialMovimiento.fecha.desc(),
                             HistorialMovimiento.id.desc())


def describir(movimientos):
    """Resuelve la descripcion de cada articulo de una sola vez.

    item_id es una FK polimorfica, asi que no se puede hacer join. Sin esto
    seria una consulta por renglon.
    """
    ids_equipo = {m.item_id for m in movimientos if m.item_tipo == TipoItem.EQUIPO}
    ids_insumo = {m.item_id for m in movimientos if m.item_tipo == TipoItem.INSUMO}

    equipos = {}
    if ids_equipo:
        equipos = {
            e.id: e for e in
            EquipoMedico.query.filter(EquipoMedico.id.in_(ids_equipo)).all()
        }
    insumos = {}
    if ids_insumo:
        insumos = {
            i.id: i for i in
            Insumo.query.filter(Insumo.id.in_(ids_insumo)).all()
        }

    filas = []
    for mov in movimientos:
        fuente = equipos if mov.item_tipo == TipoItem.EQUIPO else insumos
        articulo = fuente.get(mov.item_id)
        filas.append({
            "mov": mov,
            "articulo": articulo,
            "descripcion": articulo.descripcion if articulo
                           else f"(articulo {mov.item_id} dado de baja)",
            "codigo": getattr(articulo, "codigo_barras", "") if articulo else "",
            "sku": getattr(articulo, "sku", None) if articulo else None,
        })
    return filas


def resumen(consulta):
    """Totales del filtro actual, para el encabezado de la pantalla."""
    movimientos = consulta.all()
    return {
        "renglones": len(movimientos),
        "piezas": sum(m.cantidad or 0 for m in movimientos),
        "importe": sum(float(m.importe or 0) for m in movimientos),
    }


def a_csv(filas):
    """Genera el CSV del kardex, con las mismas columnas de la pantalla."""
    import csv
    import io

    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow([
        "Folio mov", "Fecha", "Movimiento", "Tipo", "Codigo", "SKU",
        "Descripcion", "Cantidad", "Saldo anterior", "Saldo nuevo",
        "Origen", "Destino", "Costo unitario", "Importe", "Proveedor",
        "Pagado el", "Nota", "Operador", "Observaciones",
    ])

    for fila in filas:
        m = fila["mov"]
        escritor.writerow([
            m.id,
            m.fecha.strftime("%d/%m/%Y %H:%M") if m.fecha else "",
            m.movimiento,
            m.item_tipo,
            fila["codigo"],
            fila["sku"] or "",
            fila["descripcion"],
            m.cantidad if m.cantidad is not None else "",
            m.saldo_anterior if m.saldo_anterior is not None else "",
            m.saldo_nuevo if m.saldo_nuevo is not None else "",
            m.almacen_origen.nombre if m.almacen_origen else "",
            m.almacen_destino.nombre if m.almacen_destino else "",
            f"{float(m.costo_unitario):.2f}" if m.costo_unitario else "",
            f"{float(m.importe):.2f}" if m.importe else "",
            m.proveedor or "",
            m.fecha_pago.strftime("%d/%m/%Y") if m.fecha_pago else "",
            m.nota.folio if m.nota else "",
            m.usuario.nombre if m.usuario else "",
            m.detalle or "",
        ])

    # utf-8-sig para que Excel respete los acentos al abrir el archivo.
    return salida.getvalue().encode("utf-8-sig")
