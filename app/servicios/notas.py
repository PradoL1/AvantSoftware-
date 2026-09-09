"""Operaciones sobre notas de venta.

Viven aqui y no en las vistas porque tocan varias tablas a la vez y deben
quedar en una sola transaccion.
"""

from sqlalchemy.exc import IntegrityError

from app.constantes import TipoItem
from app.extensions import db
from app.models import DetalleNotaVenta, EquipoMedico, Insumo, NotaVenta
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


def _construir_detalle(tipo, item_id, cantidad, hospital):
    """Crea el renglon copiando descripcion y precio del catalogo.

    El precio se congela aqui: si manana cambia la lista, la nota ya capturada
    sigue valiendo lo que valia. Y depende del hospital, porque el Grupo
    Angeles tiene su propia tarifa.
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
            precio_unitario=insumo.precio_para(hospital),
        )

    equipo = db.session.get(EquipoMedico, item_id)
    if equipo is None or not equipo.activo:
        raise ErrorDeNota(f"El equipo {item_id} ya no esta en el catalogo.")
    return DetalleNotaVenta(
        tipo=tipo,
        item_id=equipo.id,
        cantidad=cantidad,
        descripcion_snapshot=equipo.descripcion,
        unidad_snapshot="pieza",
        # El equipo se renta, no se vende: no hay tarifa de renta en el
        # catalogo todavia (ver README, alcance pendiente), asi que va en cero.
        precio_unitario=0,
    )


def crear_nota(form, renglones, vendedor):
    """Guarda la nota completa. Devuelve la NotaVenta ya persistida."""
    detalles = [
        _construir_detalle(tipo, item_id, cantidad, form.hospital.data)
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
                _construir_detalle(tipo, item_id, cantidad, form.hospital.data)
                for tipo, item_id, cantidad in renglones
            ]


def actualizar_nota(nota, form, renglones):
    """Reemplaza encabezado y renglones de una nota que sigue editable."""
    if not nota.editable:
        raise ErrorDeNota("Esta nota ya no se puede editar en su estado actual.")

    detalles = [
        _construir_detalle(tipo, item_id, cantidad, form.hospital.data)
        for tipo, item_id, cantidad in renglones
    ]

    _volcar_form(form, nota)
    nota.detalles = detalles
    db.session.commit()
    return nota


def _volcar_form(form, nota):
    """Copia los campos del formulario al modelo, normalizando los vacios."""
    nota.hospital = form.hospital.data.strip()
    nota.ciudad = (form.ciudad.data or "").strip() or None
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
