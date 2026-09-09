"""Catalogo de equipo medico e insumos.

Lectura para todos los roles; la edicion es exclusiva de revisor_admin.
"""

from datetime import date

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app.blueprints.catalogo import bp
from app.blueprints.catalogo.formularios import HospitalForm, TarifaForm
from app.constantes import Rol, TipoItem
from app.extensions import db
from app.models import EquipoMedico, Hospital, Insumo, TarifaEquipo
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


# --- Hospitales y tarifas ---------------------------------------------------


@bp.route("/hospitales")
@login_required
def hospitales():
    lista = Hospital.query.order_by(Hospital.nombre).all()
    return render_template("catalogo/hospitales.html", hospitales=lista)


@bp.route("/hospitales/nuevo", methods=["GET", "POST"])
@bp.route("/hospitales/<int:hospital_id>", methods=["GET", "POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def editar_hospital(hospital_id=None):
    hospital = Hospital.query.get_or_404(hospital_id) if hospital_id else None
    form = HospitalForm(obj=hospital)

    if form.validate_on_submit():
        if hospital is None:
            hospital = Hospital()
            db.session.add(hospital)
        form.populate_obj(hospital)
        hospital.nombre = hospital.nombre.strip()
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(f"Ya existe un hospital llamado {hospital.nombre}.", "danger")
        else:
            flash(f"Hospital {hospital.nombre} guardado.", "success")
            return redirect(url_for("catalogo.hospitales"))

    return render_template("catalogo/hospital_form.html", form=form,
                           hospital=hospital)


@bp.route("/tarifas", methods=["GET", "POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def tarifas():
    """Precio de renta por equipo y hospital."""
    form = TarifaForm()
    form.equipo_id.choices = [
        (e.id, f"{e.descripcion} ({e.codigo_barras})")
        for e in EquipoMedico.query.filter_by(activo=True)
        .order_by(EquipoMedico.nombre).all()
    ]
    form.hospital_id.choices = [
        (h.id, h.nombre)
        for h in Hospital.query.filter_by(activo=True)
        .order_by(Hospital.nombre).all()
    ]
    if not form.vigente_desde.data:
        form.vigente_desde.data = date.today()

    if form.validate_on_submit():
        tarifa = TarifaEquipo(
            equipo_id=form.equipo_id.data,
            hospital_id=form.hospital_id.data,
            precio_renta=form.precio_renta.data,
            vigente_desde=form.vigente_desde.data,
        )
        db.session.add(tarifa)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ya hay una tarifa para ese equipo, hospital y fecha.",
                  "danger")
        else:
            flash("Tarifa guardada.", "success")
            return redirect(url_for("catalogo.tarifas"))

    lista = (TarifaEquipo.query
             .order_by(TarifaEquipo.hospital_id, TarifaEquipo.vigente_desde.desc())
             .all())
    return render_template("catalogo/tarifas.html", form=form, tarifas=lista)


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
