"""Catalogo de equipo medico e insumos.

Lectura para todos los roles; la edicion es exclusiva de revisor_admin.
"""

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.blueprints.catalogo import bp
from app.constantes import Rol, TipoItem
from app.models import EquipoMedico, Insumo
from app.utils.decoradores import rol_requerido


@bp.route("/equipo")
@login_required
def equipo():
    equipos = EquipoMedico.query.filter_by(activo=True).order_by(EquipoMedico.nombre).all()
    return render_template("catalogo/equipo.html", equipos=equipos)


@bp.route("/insumos")
@login_required
def insumos():
    lista = Insumo.query.filter_by(activo=True).order_by(Insumo.nombre).all()
    return render_template("catalogo/insumos.html", insumos=lista)


@bp.route("/api/codigo")
@login_required
def buscar_por_codigo():
    """Resuelve un codigo de barras escaneado.

    Lo consume el lector (fisico o camara) desde el formulario de la nota, el
    checklist de entrega y el regreso a almacen.
    """
    codigo = (request.args.get("codigo") or "").strip()
    if not codigo:
        return jsonify({"encontrado": False, "error": "Codigo vacio"}), 400

    equipo_item = EquipoMedico.query.filter_by(codigo_barras=codigo, activo=True).first()
    if equipo_item:
        return jsonify(
            {
                "encontrado": True,
                "tipo": TipoItem.EQUIPO,
                "id": equipo_item.id,
                "descripcion": equipo_item.descripcion,
                "numero_serie": equipo_item.numero_serie,
                "estado": equipo_item.estado,
                "disponible": equipo_item.disponible,
                "unidad": "pieza",
            }
        )

    insumo_item = Insumo.query.filter_by(codigo_barras=codigo, activo=True).first()
    if insumo_item:
        return jsonify(
            {
                "encontrado": True,
                "tipo": TipoItem.INSUMO,
                "id": insumo_item.id,
                "descripcion": insumo_item.descripcion,
                "unidad": insumo_item.unidad_medida,
                "stock_disponible": insumo_item.stock_disponible,
            }
        )

    return jsonify({"encontrado": False, "error": "Codigo no registrado"}), 404


# --- Por implementar -------------------------------------------------------


@bp.route("/equipo/nuevo", methods=["GET", "POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def nuevo_equipo():
    # TODO: alta de equipo con generacion automatica de codigo de barras.
    flash("El alta de equipo esta por implementarse.", "info")
    return redirect(url_for("catalogo.equipo"))


@bp.route("/insumos/nuevo", methods=["GET", "POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def nuevo_insumo():
    # TODO: alta de insumo con generacion automatica de codigo de barras.
    flash("El alta de insumos esta por implementarse.", "info")
    return redirect(url_for("catalogo.insumos"))


@bp.route("/etiquetas")
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def etiquetas():
    # TODO: hoja de etiquetas imprimible con JsBarcode.
    flash("La impresion de etiquetas esta por implementarse.", "info")
    return redirect(url_for("catalogo.equipo"))
