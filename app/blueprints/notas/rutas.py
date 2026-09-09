"""Notas de venta: las crea y consulta el vendedor.

Estado: el listado y el detalle funcionan; el alta y la edicion estan por
implementar (siguiente etapa del plan).
"""

from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.blueprints.notas import bp
from app.constantes import Rol
from app.models import NotaVenta
from app.utils.decoradores import rol_requerido


def _nota_visible_o_403(nota_id):
    """Un vendedor solo puede ver sus propias notas (contexto, seccion 3)."""
    nota = NotaVenta.query.get_or_404(nota_id)
    if current_user.es_vendedor and nota.vendedor_id != current_user.id:
        abort(403)
    return nota


@bp.route("/")
@login_required
def listar():
    consulta = NotaVenta.query
    if current_user.es_vendedor:
        consulta = consulta.filter_by(vendedor_id=current_user.id)
    notas = consulta.order_by(NotaVenta.fecha_creacion.desc()).all()
    return render_template("notas/listar.html", notas=notas)


@bp.route("/<int:nota_id>")
@login_required
def detalle(nota_id):
    nota = _nota_visible_o_403(nota_id)
    return render_template("notas/detalle.html", nota=nota)


# --- Por implementar -------------------------------------------------------


@bp.route("/nueva", methods=["GET", "POST"])
@login_required
@rol_requerido(Rol.VENDEDOR, Rol.REVISOR_ADMIN)
def nueva():
    # TODO: formulario con renglones dinamicos (equipo/insumo), alta por
    # escaneo de codigo de barras y folio via utils.folios.siguiente_folio_nota.
    flash("El alta de notas de venta esta por implementarse.", "info")
    return redirect(url_for("notas.listar"))


@bp.route("/<int:nota_id>/editar", methods=["GET", "POST"])
@login_required
def editar(nota_id):
    nota = _nota_visible_o_403(nota_id)
    if not nota.editable:
        abort(403)
    # TODO: reutilizar el formulario del alta.
    flash("La edicion de notas esta por implementarse.", "info")
    return redirect(url_for("notas.detalle", nota_id=nota.id))
