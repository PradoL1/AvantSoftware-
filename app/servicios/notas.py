"""Operaciones sobre notas de venta.

Viven aqui y no en las vistas porque tocan varias tablas a la vez y deben
quedar en una sola transaccion.
"""

from sqlalchemy.exc import IntegrityError

from app.constantes import TipoItem
from app.extensions import db
from app.models import (DetalleNotaVenta, EquipoMedico, Hospital, Insumo,
                        NotaVenta, precio_renta)
from app.utils.folios import siguiente_folio_nota

# Cuantas veces reintentar si dos vendedores guardan a la vez y chocan folios.
INTENTOS_FOLIO = 5


class ErrorDeNota(Exception):
    """Problema de captura que el usuario puede corregir."""


def leer_renglones(form):
    """Saca los renglones del formulario, que llegan como listas paralelas.

    Devuelve [(tipo, item_id, cantidad), ...] ya validado en forma, sin tocar
    todavia la base.
    """
    renglones = []

    for prefijo, tipo in (("insumo", TipoItem.INSUMO), ("equipo", TipoItem.EQUIPO)):
        ids = form.getlist(f"{prefijo}_id[]")
        cantidades = form.getlist(f"{prefijo}_cantidad[]")

        if len(ids) != len(cantidades):
            raise ErrorDeNota("Los renglones llegaron incompletos. Vuelve a intentar.")

        for item_id, cantidad in zip(ids, cantidades):
            if not item_id:
                continue
            try:
                item_id = int(item_id)
                cantidad = int(cantidad)
            except (TypeError, ValueError):
                raise ErrorDeNota("Hay una cantidad que no es un numero entero.")

            if cantidad < 1:
                raise ErrorDeNota("Las cantidades deben ser de al menos 1.")

            renglones.append((tipo, item_id, cantidad))

    if not renglones:
        raise ErrorDeNota("Agrega al menos un equipo o un insumo a la nota.")

    return renglones


def _construir_detalle(tipo, item_id, cantidad, hospital_ref):
    """Crea el renglon copiando del catalogo lo que no debe cambiar despues.

    Los precios funcionan distinto segun el articulo:

    - El equipo se renta a una tarifa que depende del hospital, asi que sale
      del tarifario y se congela aqui.
    - Los insumos no tienen precio de lista: se negocian en cada venta y el
      precio lo captura el revisor. Entran en cero.
    """
    if tipo == TipoItem.INSUMO:
        insumo = db.session.get(Insumo, item_id)
        if insumo is None or not insumo.activo:
            raise ErrorDeNota(f"El insumo {item_id} ya no esta en el catalogo.")
        return DetalleNotaVenta(
            tipo=tipo,
            item_id=insumo.id,
            cantidad=cantidad,
            descripcion_snapshot=insumo.descripcion,
            unidad_snapshot=insumo.unidad_medida,
            precio_unitario=0,
        )

    equipo = db.session.get(EquipoMedico, item_id)
    if equipo is None or not equipo.activo:
        raise ErrorDeNota(f"El equipo {item_id} ya no esta en el catalogo.")

    tarifa = precio_renta(equipo, hospital_ref)
    return DetalleNotaVenta(
        tipo=tipo,
        item_id=equipo.id,
        cantidad=cantidad,
        descripcion_snapshot=equipo.descripcion,
        unidad_snapshot="pieza",
        # Sin tarifa capturada va en cero, pero la pantalla de revision lo
        # senala: que falte un precio no debe impedir levantar la nota.
        precio_unitario=tarifa if tarifa is not None else 0,
    )


def crear_nota(form, renglones, vendedor):
    """Guarda la nota completa. Devuelve la NotaVenta ya persistida."""
    hospital = _hospital_de(form)
    detalles = [
        _construir_detalle(tipo, item_id, cantidad, hospital)
        for tipo, item_id, cantidad in renglones
    ]

    # MAX(folio)+1 no es atomico: si otro vendedor gana la carrera, el UNIQUE
    # revienta y se vuelve a intentar con el siguiente numero.
    for intento in range(INTENTOS_FOLIO):
        nota = NotaVenta(folio=siguiente_folio_nota(), vendedor_id=vendedor.id)
        _volcar_form(form, nota)
        nota.detalles = list(detalles)

        db.session.add(nota)
        try:
            db.session.commit()
            return nota
        except IntegrityError:
            db.session.rollback()
            if intento == INTENTOS_FOLIO - 1:
                raise ErrorDeNota(
                    "No se pudo asignar folio despues de varios intentos. "
                    "Vuelve a guardar."
                )
            # Los detalles quedaron desasociados tras el rollback; se rehacen.
            detalles = [
                _construir_detalle(tipo, item_id, cantidad, hospital)
                for tipo, item_id, cantidad in renglones
            ]


def actualizar_nota(nota, form, renglones):
    """Reemplaza encabezado y renglones de una nota que sigue editable."""
    if not nota.editable:
        raise ErrorDeNota("Esta nota ya no se puede editar en su estado actual.")

    hospital = _hospital_de(form)
    detalles = [
        _construir_detalle(tipo, item_id, cantidad, hospital)
        for tipo, item_id, cantidad in renglones
    ]

    _volcar_form(form, nota)
    nota.detalles = detalles
    db.session.commit()
    return nota


def _hospital_de(form):
    """El hospital del catalogo que eligio el vendedor."""
    hospital = db.session.get(Hospital, form.hospital_id.data)
    if hospital is None or not hospital.activo:
        raise ErrorDeNota(
            "Elige un hospital del catalogo. Si falta, pide al area "
            "administrativa que lo de de alta."
        )
    return hospital


def _volcar_form(form, nota):
    """Copia los campos del formulario al modelo, normalizando los vacios."""
    hospital = _hospital_de(form)
    nota.hospital_id = hospital.id
    # Copia del nombre para que los documentos ya emitidos no cambien si el
    # catalogo se corrige despues.
    nota.hospital = hospital.nombre

    nota.ciudad = (form.ciudad.data or "").strip() or hospital.ciudad
    nota.direccion_entrega = form.direccion_entrega.data.strip()
    nota.contacto_nombre = (form.contacto_nombre.data or "").strip() or None
    nota.contacto_telefono = (form.contacto_telefono.data or "").strip() or None
    nota.fecha_requerida = form.fecha_requerida.data

    nota.fecha_procedimiento = form.fecha_procedimiento.data
    nota.especialidad = form.especialidad.data or None
    nota.cirugia = (form.cirugia.data or "").strip() or None
    nota.doctor = (form.doctor.data or "").strip() or None
    nota.verificado_con = form.verificado_con.data or None

    nota.tipo_paciente = form.tipo_paciente.data or None
    nota.metodo_pago = form.metodo_pago.data or None

    nota.observaciones = (form.observaciones.data or "").strip() or None
