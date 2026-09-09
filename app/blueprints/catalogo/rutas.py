"""Catalogo de equipo medico e insumos.

Lectura para todos los roles; la edicion es exclusiva de revisor_admin.
"""

from datetime import date

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.blueprints.catalogo import bp
from app.blueprints.catalogo.formularios import (EquipoForm, HospitalForm,
                                                InsumoForm, TarifaForm)
from app.constantes import EstadoEquipo, Rol, TipoItem
from app.extensions import db
from app.models import (Almacen, EquipoMedico, Hospital, Insumo, TarifaEquipo)
from app.servicios.catalogo import (ErrorDeCatalogo, ajustar_existencia,
                                    sugerir_codigo, validar_codigo_libre)
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


# --- Alta y edicion del catalogo --------------------------------------------


def _almacenes():
    return Almacen.query.filter_by(activo=True).order_by(Almacen.nombre).all()


@bp.route("/equipo/nuevo", methods=["GET", "POST"])
@bp.route("/equipo/<int:equipo_id>", methods=["GET", "POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def editar_equipo(equipo_id=None):
    pieza = EquipoMedico.query.get_or_404(equipo_id) if equipo_id else None
    form = EquipoForm(obj=pieza)
    form.almacen_id.choices = [(0, "-- Sin asignar --")] + [
        (a.id, a.nombre) for a in _almacenes()
    ]

    if form.validate_on_submit():
        try:
            codigo = validar_codigo_libre(
                form.codigo_barras.data, EquipoMedico,
                pieza.id if pieza else None,
            )
        except ErrorDeCatalogo as e:
            flash(str(e), "danger")
        else:
            # El almacen se resuelve ANTES de tocar la sesion: cualquier
            # consulta posterior dispara un autoflush, y si ese flush choca con
            # un unique, el error salta fuera del try de abajo.
            almacen_id = form.almacen_id.data or None
            almacen = db.session.get(Almacen, almacen_id) if almacen_id else None

            if pieza is None:
                pieza = EquipoMedico()
                db.session.add(pieza)
            form.populate_obj(pieza)
            pieza.codigo_barras = codigo
            pieza.almacen_id = almacen_id
            # El estado lo maneja el flujo (apartado, rentado...), no este
            # formulario: aqui solo se da de alta o se corrigen los datos.
            if not pieza.estado:
                pieza.estado = EstadoEquipo.DISPONIBLE
            if not pieza.ubicacion_actual and almacen:
                pieza.ubicacion_actual = almacen.nombre

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("Ese numero de serie ya esta registrado.", "danger")
            else:
                flash(f"Equipo {pieza.descripcion} guardado.", "success")
                return redirect(url_for("catalogo.equipo"))

    if pieza is None and not form.codigo_barras.data and form.nombre.data:
        form.codigo_barras.data = sugerir_codigo(form.nombre.data,
                                                 form.modelo.data)

    return render_template("catalogo/equipo_form.html", form=form, equipo=pieza)


@bp.route("/insumos/nuevo", methods=["GET", "POST"])
@bp.route("/insumos/<int:insumo_id>", methods=["GET", "POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def editar_insumo(insumo_id=None):
    insumo = Insumo.query.get_or_404(insumo_id) if insumo_id else None
    form = InsumoForm(obj=insumo)
    almacenes = _almacenes()

    if form.validate_on_submit():
        try:
            codigo = validar_codigo_libre(
                form.codigo_barras.data, Insumo,
                insumo.id if insumo else None,
            )
        except ErrorDeCatalogo as e:
            flash(str(e), "danger")
        else:
            nuevo = insumo is None
            if nuevo:
                insumo = Insumo()
                db.session.add(insumo)
            form.populate_obj(insumo)
            insumo.codigo_barras = codigo
            insumo.sku = (form.sku.data or "").strip() or None
            db.session.flush()

            # Primero se convierten todos los valores y despues se ajusta. Si
            # se mezclan las dos cosas en un solo try, un error de la capa de
            # inventario acaba reportandose como "no es un numero", que manda
            # a buscar el problema al lugar equivocado.
            cantidades = []
            error = None
            for almacen in almacenes:
                crudo = request.form.get(f"existencia_{almacen.id}")
                if crudo is None or crudo.strip() == "":
                    continue
                try:
                    cantidades.append((almacen, int(crudo)))
                except (TypeError, ValueError):
                    error = (f"'{crudo}' no es una cantidad valida para "
                             f"{almacen.nombre}.")
                    break

            if error is None:
                try:
                    for almacen, cantidad in cantidades:
                        ajustar_existencia(
                            insumo, almacen, cantidad, current_user,
                            motivo="Alta inicial" if nuevo else None,
                        )
                except ErrorDeCatalogo as e:
                    error = str(e)

            if error:
                db.session.rollback()
                flash(error, "danger")
            else:
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    flash("Ese SKU ya esta registrado.", "danger")
                else:
                    flash(f"Insumo {insumo.nombre} guardado.", "success")
                    return redirect(url_for("catalogo.insumos"))

    if insumo is None and not form.codigo_barras.data and form.nombre.data:
        form.codigo_barras.data = sugerir_codigo(form.nombre.data)

    return render_template("catalogo/insumo_form.html", form=form,
                           insumo=insumo, almacenes=almacenes)


# --- Por implementar -------------------------------------------------------


@bp.route("/etiquetas")
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def etiquetas():
    # TODO: hoja de etiquetas imprimible con JsBarcode.
    flash("La impresion de etiquetas esta por implementarse.", "info")
    return redirect(url_for("catalogo.equipo"))
