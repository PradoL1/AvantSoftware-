"""Emision de cartas responsivas de custodia.

Una por pieza de equipo entregada. Es un contrato: el receptor acepta cubrir
el valor de reposicion si el equipo se dana o se pierde, asi que todo lo que
sustenta esa obligacion se copia al emitirla y no se vuelve a leer del
catalogo.
"""

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.constantes import Checklist
from app.extensions import db
from app.models import Responsiva
from app.utils.folios import _siguiente
from app.utils.pdf import generar_pdf_responsiva

INTENTOS_FOLIO = 5


class ErrorDeResponsiva(Exception):
    """Problema que el tecnico puede entender."""


def siguiente_folio_responsiva():
    prefijo = f"RESP-{current_app.config['FOLIO_PREFIJO']}"
    return _siguiente(Responsiva, prefijo)


def _ruta_pdf(responsiva):
    carpeta = current_app.config["PDF_REMISIONES_DIR"]
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / f"{responsiva.folio}.pdf"


def emitir_responsivas(entrega, usuario, responsable=None, paciente_folio=None,
                       accesorios=None, inspeccion=None, notas=None):
    """Emite una responsiva por cada equipo de la nota que no tenga una.

    Devuelve las emitidas en esta llamada.
    """
    nota = entrega.nota
    if not nota.detalles_equipo:
        return []

    ya_emitidas = {r.equipo_id for r in entrega.responsivas if not r.cerrada}
    creadas = []

    for detalle in nota.detalles_equipo:
        equipo = detalle.item
        if equipo is None or equipo.id in ya_emitidas:
            continue

        responsiva = _crear_con_folio(
            entrega_id=entrega.id,
            equipo_id=equipo.id,
            emitida_por_id=usuario.id,
            empresa_propietaria=equipo.empresa_propietaria,
            # Se congela el MOI: es la cifra que el receptor se compromete a
            # cubrir, y no puede cambiar si manana se revalua el activo.
            valor_reposicion=equipo.moi or 0,
            responsable_custodia=(responsable or nota.doctor or "").strip() or None,
            paciente_folio=(paciente_folio or "").strip() or None,
            accesorios=accesorios or ", ".join(Checklist.ACCESORIOS),
            checklist_salida=inspeccion or ", ".join(Checklist.INSPECCION),
            notas=(notas or "").strip() or None,
        )
        creadas.append(responsiva)

    db.session.flush()

    for responsiva in creadas:
        try:
            ruta = _ruta_pdf(responsiva)
            generar_pdf_responsiva(responsiva, ruta)
            responsiva.pdf_path = ruta.name
        except Exception as e:  # noqa: BLE001
            current_app.logger.exception("Fallo el PDF de %s", responsiva.folio)
            raise ErrorDeResponsiva(
                f"La responsiva {responsiva.folio} se guardo, pero el PDF "
                f"fallo: {e}"
            )

    db.session.commit()
    return creadas


def _crear_con_folio(**campos):
    for intento in range(INTENTOS_FOLIO):
        responsiva = Responsiva(folio=siguiente_folio_responsiva(), **campos)
        db.session.add(responsiva)
        try:
            db.session.flush()
            return responsiva
        except IntegrityError:
            db.session.rollback()
            if intento == INTENTOS_FOLIO - 1:
                raise ErrorDeResponsiva(
                    "No se pudo asignar folio de responsiva. Vuelve a intentar."
                )


def regenerar_pdf(responsiva):
    ruta = _ruta_pdf(responsiva)
    generar_pdf_responsiva(responsiva, ruta)
    responsiva.pdf_path = ruta.name
    db.session.commit()
    return ruta
