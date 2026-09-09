"""Generacion de remisiones.

Como en el sistema anterior, una nota produce hasta dos remisiones: una de
insumos y otra de equipos. Solo se emite la que tenga renglones.
"""

from decimal import Decimal

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.constantes import IVA, Empresa, EstadoNota, TipoRemision
from app.extensions import db
from app.models import Remision
from app.utils.folios import siguiente_folio_remision
from app.utils.pdf import generar_pdf_remision

INTENTOS_FOLIO = 5


class ErrorDeRemision(Exception):
    """Problema que el revisor puede entender."""


def _detalles_de(nota, tipo):
    if tipo == TipoRemision.INSUMOS:
        return nota.detalles_insumo
    return nota.detalles_equipo


def _importes(detalles):
    subtotal = sum((d.importe for d in detalles), Decimal(0))
    iva = subtotal * Decimal(str(IVA))
    return subtotal, iva, subtotal + iva


def _ruta_pdf(remision):
    carpeta = current_app.config["PDF_REMISIONES_DIR"]
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / f"{remision.folio}.pdf"


def generar_remisiones(nota, usuario):
    """Emite las remisiones que falten y pasa la nota a remision_generada.

    Devuelve las remisiones creadas en esta llamada. Volver a llamarla no
    duplica: si la de insumos ya existe, solo emite la de equipos.
    """
    if nota.estado not in (EstadoNota.APROBADA, EstadoNota.REMISION_GENERADA):
        raise ErrorDeRemision(
            f"Una nota {nota.estado_etiqueta.lower()} no puede generar "
            "remisiones. Primero hay que aprobarla."
        )

    datos_empresa = Empresa.datos_para_hospital(nota.hospital)
    creadas = []

    for tipo in TipoRemision.TODOS:
        detalles = _detalles_de(nota, tipo)
        if not detalles:
            continue
        if nota.remision_de(tipo):
            continue

        subtotal, iva, total = _importes(detalles)
        remision = _crear_con_folio(
            nota=nota,
            tipo=tipo,
            usuario=usuario,
            # Se congelan: si manana cambia el RFC o la lista de precios, la
            # remision ya emitida debe seguir diciendo lo que decia.
            razon_social=datos_empresa["razon_social"],
            rfc=datos_empresa["rfc"],
            subtotal=subtotal,
            iva=iva,
            total=total,
        )
        creadas.append(remision)

    if not creadas and not nota.remisiones:
        raise ErrorDeRemision("La nota no tiene renglones que remisionar.")

    # El PDF se escribe despues del commit: si falla el disco, la remision ya
    # esta en la base y se puede regenerar sin perder el folio.
    for remision in creadas:
        try:
            ruta = _ruta_pdf(remision)
            generar_pdf_remision(remision, ruta)
            remision.pdf_path = str(ruta.name)
        except Exception as e:  # noqa: BLE001
            current_app.logger.exception("Fallo el PDF de %s", remision.folio)
            raise ErrorDeRemision(
                f"La remision {remision.folio} se guardo, pero el PDF fallo: {e}"
            )

    if nota.estado == EstadoNota.APROBADA:
        nota.estado = EstadoNota.REMISION_GENERADA

    db.session.commit()
    return creadas


def _crear_con_folio(nota, tipo, usuario, **campos):
    """Inserta la remision reintentando si el folio choca."""
    for intento in range(INTENTOS_FOLIO):
        remision = Remision(
            folio=siguiente_folio_remision(),
            nota_venta_id=nota.id,
            tipo=tipo,
            generado_por_id=usuario.id,
            **campos,
        )
        db.session.add(remision)
        try:
            db.session.flush()
            return remision
        except IntegrityError:
            db.session.rollback()
            if intento == INTENTOS_FOLIO - 1:
                raise ErrorDeRemision(
                    "No se pudo asignar folio de remision. Vuelve a intentar."
                )


def regenerar_pdf(remision):
    """Vuelve a escribir el PDF de una remision ya emitida (reimpresion)."""
    ruta = _ruta_pdf(remision)
    generar_pdf_remision(remision, ruta)
    remision.pdf_path = str(ruta.name)
    db.session.commit()
    return ruta
