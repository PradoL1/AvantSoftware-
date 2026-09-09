"""Notas de venta: las crea y consulta el vendedor."""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.notas import bp
from app.blueprints.notas.formularios import NotaVentaForm
from app.constantes import Rol
from app.models import EquipoMedico, Insumo, NotaVenta
from app.servicios.notas import (ErrorDeNota, actualizar_nota, crear_nota,
                                 leer_renglones)
from app.utils.decoradores import rol_requerido


def _nota_visible_o_403(nota_id):
    """Un vendedor solo puede ver sus propias notas (contexto, seccion 3)."""
    nota = NotaVenta.query.get_or_404(nota_id)
    if current_user.es_vendedor and nota.vendedor_id != current_user.id:
        abort(403)
    return nota


def _catalogo():
    """Lo que el formulario ofrece para elegir, ya ordenado."""
    return {
        "insumos": Insumo.query.filter_by(activo=True).order_by(Insumo.nombre).all(),
        "equipos": EquipoMedico.query.filter_by(activo=True)
        .order_by(EquipoMedico.nombre)
        .all(),
    }


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


@bp.route("/nueva", methods=["GET", "POST"])
@login_required
@rol_requerido(Rol.VENDEDOR, Rol.REVISOR_ADMIN)
def nueva():
    form = NotaVentaForm()

    if form.validate_on_submit():
        try:
            renglones = leer_renglones(request.form)
            nota = crear_nota(form, renglones, current_user)
        except ErrorDeNota as e:
            flash(str(e), "danger")
        else:
            flash(f"Nota {nota.folio} creada y enviada a revision.", "success")
            return redirect(url_for("notas.detalle", nota_id=nota.id))

    return render_template(
        "notas/formulario.html", form=form, nota=None, **_catalogo()
    )


@bp.route("/<int:nota_id>/editar", methods=["GET", "POST"])
@login_required
def editar(nota_id):
    nota = _nota_visible_o_403(nota_id)
    if not nota.editable:
        flash("Esta nota ya no se puede editar.", "warning")
        return redirect(url_for("notas.detalle", nota_id=nota.id))

    form = NotaVentaForm(obj=nota)

    if form.validate_on_submit():
        try:
            renglones = leer_renglones(request.form)
            actualizar_nota(nota, form, renglones)
        except ErrorDeNota as e:
            flash(str(e), "danger")
        else:
            flash(f"Nota {nota.folio} actualizada.", "success")
            return redirect(url_for("notas.detalle", nota_id=nota.id))

    return render_template(
        "notas/formulario.html", form=form, nota=nota, **_catalogo()
    )
