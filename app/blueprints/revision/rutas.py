"""Revision de notas y generacion de remisiones (rol revisor_admin)."""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.revision import bp
from app.constantes import EstadoNota, Rol
from app.models import NotaVenta
from app.servicios.revision import (ErrorDeRevision, aprobar, cancelar,
                                    hay_faltantes, rechazar,
                                    revisar_disponibilidad)
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
    filas = revisar_disponibilidad(nota)
    return render_template(
        "revision/revisar.html",
        nota=nota,
        filas=filas,
        faltantes=hay_faltantes(filas),
    )


@bp.route("/<int:nota_id>/aprobar", methods=["POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def aprobar_nota(nota_id):
    nota = NotaVenta.query.get_or_404(nota_id)
    try:
        aprobar(nota, current_user)
    except ErrorDeRevision as e:
        flash(str(e), "danger")
    except Exception as e:  # InventarioInsuficiente y similares
        flash(f"No se pudo aprobar: {e}", "danger")
    else:
        flash(
            f"Nota {nota.folio} aprobada. El inventario quedo apartado.",
            "success",
        )
        return redirect(url_for("revision.bandeja"))

    return redirect(url_for("revision.revisar", nota_id=nota_id))


@bp.route("/<int:nota_id>/rechazar", methods=["POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def rechazar_nota(nota_id):
    nota = NotaVenta.query.get_or_404(nota_id)
    try:
        rechazar(nota, current_user, request.form.get("motivo"))
    except ErrorDeRevision as e:
        flash(str(e), "danger")
        return redirect(url_for("revision.revisar", nota_id=nota_id))

    flash(f"Nota {nota.folio} rechazada. Se le avisa al vendedor.", "info")
    return redirect(url_for("revision.bandeja"))


@bp.route("/<int:nota_id>/cancelar", methods=["POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def cancelar_nota(nota_id):
    nota = NotaVenta.query.get_or_404(nota_id)
    motivo = (request.form.get("motivo") or "Nota cancelada").strip()
    try:
        cancelar(nota, current_user, motivo)
    except ErrorDeRevision as e:
        flash(str(e), "danger")
    else:
        flash(
            f"Nota {nota.folio} cancelada. Lo apartado volvio al almacen.",
            "info",
        )
    return redirect(url_for("revision.revisar", nota_id=nota_id))


# --- Por implementar -------------------------------------------------------


@bp.route("/<int:nota_id>/remision", methods=["POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def generar_remision(nota_id):
    # TODO: crear las dos remisiones (insumos y equipos), generar el PDF con
    # ReportLab y guardarlo en config PDF_REMISIONES_DIR.
    flash("La generacion de remisiones esta por implementarse.", "info")
    return redirect(url_for("revision.revisar", nota_id=nota_id))
