"""Generacion de folios consecutivos por anio: AVS-2026-0001."""

# NOTA: con 11 usuarios la probabilidad de colision es baja, pero MAX()+1 no es
# atomico. Si dos notas se crean en el mismo instante, el UNIQUE del folio hara
# fallar una: la vista debe reintentar. Ver README (pendientes tecnicos).

from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import func

from app.extensions import db


def _siguiente(modelo, prefijo):
    anio = datetime.now(timezone.utc).year
    patron = f"{prefijo}-{anio}-%"

    ultimo = (
        db.session.query(func.max(modelo.folio))
        .filter(modelo.folio.like(patron))
        .scalar()
    )
    consecutivo = int(ultimo.rsplit("-", 1)[1]) + 1 if ultimo else 1
    return f"{prefijo}-{anio}-{consecutivo:04d}"


def siguiente_folio_nota():
    from app.models import NotaVenta

    prefijo = current_app.config["FOLIO_PREFIJO"]
    return _siguiente(NotaVenta, prefijo)


def siguiente_folio_remision():
    from app.models import Remision

    prefijo = f"REM-{current_app.config['FOLIO_PREFIJO']}"
    return _siguiente(Remision, prefijo)
