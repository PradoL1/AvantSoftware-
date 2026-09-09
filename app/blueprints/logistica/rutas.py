"""Logistica y entrega en hospital (rol tecnico)."""

from flask import flash, redirect, render_template, url_for
from flask_login import login_required

from app.blueprints.logistica import bp
from app.constantes import EstadoNota, Rol
from app.models import NotaVenta
from app.utils.decoradores import rol_requerido


@bp.route("/")
@login_required
@rol_requerido(Rol.TECNICO, Rol.REVISOR_ADMIN)
def bandeja():
    notas = (
        NotaVenta.query.filter(
            NotaVenta.estado.in_(
                (
                    EstadoNota.REMISION_GENERADA,
                    EstadoNota.EN_LOGISTICA,
                    EstadoNota.ENTREGADA,
                )
            )
        )
        .order_by(NotaVenta.fecha_requerida)
        .all()
    )
    return render_template("logistica/bandeja.html", notas=notas)


@bp.route("/<int:nota_id>")
@login_required
@rol_requerido(Rol.TECNICO, Rol.REVISOR_ADMIN)
def detalle(nota_id):
    nota = NotaVenta.query.get_or_404(nota_id)
    return render_template("logistica/detalle.html", nota=nota)


# --- Por implementar -------------------------------------------------------


@bp.route("/<int:nota_id>/checklist/<etapa>", methods=["GET", "POST"])
@login_required
@rol_requerido(Rol.TECNICO)
def checklist(nota_id, etapa):
    # TODO: doble verificacion por escaneo (etapa almacen y etapa hospital).
    flash("El checklist esta por implementarse.", "info")
    return redirect(url_for("logistica.detalle", nota_id=nota_id))


@bp.route("/<int:nota_id>/entregar", methods=["POST"])
@login_required
@rol_requerido(Rol.TECNICO)
def entregar(nota_id):
    # TODO: exigir checklist completo, marcar equipo como rentado, descontar
    # insumos y pasar la nota a ENTREGADA.
    flash("El registro de entrega esta por implementarse.", "info")
    return redirect(url_for("logistica.detalle", nota_id=nota_id))


@bp.route("/<int:nota_id>/regreso", methods=["POST"])
@login_required
@rol_requerido(Rol.TECNICO)
def regreso_equipo(nota_id):
    # TODO: escanear el equipo de regreso, marcarlo DISPONIBLE y cerrar la nota
    # cuando todo el equipo haya vuelto.
    flash("El registro de regreso esta por implementarse.", "info")
    return redirect(url_for("logistica.detalle", nota_id=nota_id))
