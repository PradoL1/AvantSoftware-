from flask import render_template
from flask_login import current_user, login_required

from app.blueprints.main import bp
from app.constantes import EstadoNota
from app.models import Insumo, NotaVenta


@bp.route("/")
@login_required
def inicio():
    """Tablero. Cada rol ve el resumen que le toca."""
    datos = {}

    if current_user.es_vendedor:
        datos["mis_notas"] = (
            NotaVenta.query.filter_by(vendedor_id=current_user.id)
            .order_by(NotaVenta.fecha_creacion.desc())
            .limit(10)
            .all()
        )

    elif current_user.es_revisor:
        datos["pendientes"] = (
            NotaVenta.query.filter_by(estado=EstadoNota.PENDIENTE_REVISION)
            .order_by(NotaVenta.fecha_requerida)
            .all()
        )
        datos["insumos_bajo_minimo"] = [
            i for i in Insumo.query.filter_by(activo=True).all() if i.bajo_minimo
        ]

    elif current_user.es_tecnico:
        datos["en_logistica"] = (
            NotaVenta.query.filter(
                NotaVenta.estado.in_(
                    (EstadoNota.REMISION_GENERADA, EstadoNota.EN_LOGISTICA)
                )
            )
            .order_by(NotaVenta.fecha_requerida)
            .all()
        )

    return render_template("main/inicio.html", **datos)
