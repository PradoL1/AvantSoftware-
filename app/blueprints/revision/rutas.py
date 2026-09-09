"""Revision de notas y generacion de remisiones (rol revisor_admin)."""

from flask import flash, redirect, render_template, url_for
from flask_login import login_required

from app.blueprints.revision import bp
from app.constantes import EstadoNota, Rol
from app.models import NotaVenta
from app.utils.decoradores import rol_requerido


@bp.route("/")
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def bandeja():
    notas = (
        NotaVenta.query.filter_by(estado=EstadoNota.PENDIENTE_REVISION)
        .order_by(NotaVenta.fecha_requerida)
        .all()
    )
    return render_template("revision/bandeja.html", notas=notas)


@bp.route("/<int:nota_id>")
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def revisar(nota_id):
    nota = NotaVenta.query.get_or_404(nota_id)
    # TODO: calcular disponibilidad renglon por renglon antes de mostrar.
    return render_template("revision/revisar.html", nota=nota)


# --- Por implementar -------------------------------------------------------


@bp.route("/<int:nota_id>/aprobar", methods=["POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def aprobar(nota_id):
    # TODO: validar disponibilidad, apartar stock/equipo, registrar historial y
    # pasar a EstadoNota.APROBADA.
    flash("La aprobacion esta por implementarse.", "info")
    return redirect(url_for("revision.revisar", nota_id=nota_id))


@bp.route("/<int:nota_id>/rechazar", methods=["POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def rechazar(nota_id):
    # TODO: guardar motivo_rechazo y notificar al vendedor.
    flash("El rechazo esta por implementarse.", "info")
    return redirect(url_for("revision.revisar", nota_id=nota_id))


@bp.route("/<int:nota_id>/remision", methods=["POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def generar_remision(nota_id):
    # TODO: crear Remision, generar el PDF (ReportLab) y guardarlo en
    # config PDF_REMISIONES_DIR.
    flash("La generacion de remisiones esta por implementarse.", "info")
    return redirect(url_for("revision.revisar", nota_id=nota_id))
