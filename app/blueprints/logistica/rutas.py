"""Logistica y entrega en hospital (rol tecnico)."""

from io import BytesIO

from flask import (current_app, flash, jsonify, redirect, render_template,
                   request, send_file, url_for)
from flask_login import current_user, login_required

from app.blueprints.logistica import bp
from app.constantes import Checklist, EstadoEquipo, EstadoNota, Rol
from app.models import EquipoMedico, NotaVenta, Responsiva
from app.servicios.logistica import (ErrorDeLogistica, equipo_pendiente_de_regreso,
                                     etapa_completa, items_de,
                                     marcar_entregada, obtener_o_crear_entrega,
                                     registrar_regreso, verificar_por_codigo)
from app.servicios.responsivas import (ErrorDeResponsiva, emitir_responsivas,
                                       regenerar_pdf)
from app.utils.decoradores import rol_requerido

EN_CAMPO = (
    EstadoNota.REMISION_GENERADA,
    EstadoNota.EN_LOGISTICA,
    EstadoNota.ENTREGADA,
)


@bp.route("/")
@login_required
@rol_requerido(Rol.TECNICO, Rol.REVISOR_ADMIN)
def bandeja():
    notas = (
        NotaVenta.query.filter(NotaVenta.estado.in_(EN_CAMPO))
        .order_by(NotaVenta.fecha_requerida)
        .all()
    )
    return render_template("logistica/bandeja.html", notas=notas)


@bp.route("/<int:nota_id>")
@login_required
@rol_requerido(Rol.TECNICO, Rol.REVISOR_ADMIN)
def detalle(nota_id):
    nota = NotaVenta.query.get_or_404(nota_id)
    return render_template(
        "logistica/detalle.html",
        nota=nota,
        entrega=nota.entrega,
        pendientes_regreso=equipo_pendiente_de_regreso(nota),
    )


@bp.route("/<int:nota_id>/tomar", methods=["POST"])
@login_required
@rol_requerido(Rol.TECNICO)
def tomar(nota_id):
    """El tecnico se asigna la entrega y se prepara su checklist."""
    nota = NotaVenta.query.get_or_404(nota_id)
    try:
        obtener_o_crear_entrega(nota, current_user)
    except ErrorDeLogistica as e:
        flash(str(e), "danger")
        return redirect(url_for("logistica.detalle", nota_id=nota_id))

    flash("Entrega asignada. Empieza por el checklist de almacen.", "success")
    return redirect(url_for("logistica.checklist", nota_id=nota_id,
                            etapa=Checklist.ETAPA_ALMACEN))


@bp.route("/<int:nota_id>/checklist/<etapa>")
@login_required
@rol_requerido(Rol.TECNICO, Rol.REVISOR_ADMIN)
def checklist(nota_id, etapa):
    nota = NotaVenta.query.get_or_404(nota_id)
    if etapa not in Checklist.ETAPAS:
        flash("Etapa de checklist desconocida.", "danger")
        return redirect(url_for("logistica.detalle", nota_id=nota_id))

    if not nota.entrega:
        flash("Primero hay que tomar la entrega.", "warning")
        return redirect(url_for("logistica.detalle", nota_id=nota_id))

    return render_template(
        "logistica/checklist.html",
        nota=nota,
        entrega=nota.entrega,
        etapa=etapa,
        items=items_de(nota.entrega, etapa),
        completa=etapa_completa(nota.entrega, etapa),
    )


@bp.route("/<int:nota_id>/checklist/<etapa>/verificar", methods=["POST"])
@login_required
@rol_requerido(Rol.TECNICO)
def verificar(nota_id, etapa):
    """Recibe un codigo escaneado. Responde JSON para no recargar la pagina."""
    nota = NotaVenta.query.get_or_404(nota_id)
    if not nota.entrega:
        return jsonify({"ok": False, "error": "La entrega no esta asignada."}), 400

    codigo = (request.json or {}).get("codigo") if request.is_json else \
        request.form.get("codigo")

    try:
        item = verificar_por_codigo(nota.entrega, etapa, codigo)
    except ErrorDeLogistica as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    return jsonify({
        "ok": True,
        "detalle_id": item.detalle_id,
        "descripcion": item.detalle.descripcion,
        "completa": etapa_completa(nota.entrega, etapa),
    })


@bp.route("/<int:nota_id>/entregar", methods=["POST"])
@login_required
@rol_requerido(Rol.TECNICO)
def entregar(nota_id):
    nota = NotaVenta.query.get_or_404(nota_id)
    if not nota.entrega:
        flash("Primero hay que tomar la entrega.", "warning")
        return redirect(url_for("logistica.detalle", nota_id=nota_id))

    try:
        marcar_entregada(
            nota.entrega, current_user,
            recibe_nombre=request.form.get("recibe_nombre"),
            observaciones=request.form.get("observaciones"),
        )
    except ErrorDeLogistica as e:
        flash(str(e), "danger")
        return redirect(url_for("logistica.detalle", nota_id=nota_id))

    # El equipo entregado queda en custodia del hospital: eso se documenta.
    if nota.detalles_equipo:
        try:
            emitidas = emitir_responsivas(
                nota.entrega, current_user,
                responsable=request.form.get("recibe_nombre"),
                paciente_folio=request.form.get("paciente_folio"),
            )
            if emitidas:
                flash(
                    "Responsivas emitidas: "
                    + ", ".join(r.folio for r in emitidas),
                    "info",
                )
        except ErrorDeResponsiva as e:
            flash(str(e), "warning")

    flash(f"Nota {nota.folio} entregada.", "success")
    return redirect(url_for("logistica.detalle", nota_id=nota_id))


@bp.route("/<int:nota_id>/regreso", methods=["POST"])
@login_required
@rol_requerido(Rol.TECNICO)
def regreso_equipo(nota_id):
    """Registra el regreso de una pieza, identificada por su codigo."""
    nota = NotaVenta.query.get_or_404(nota_id)
    if not nota.entrega:
        flash("Esta nota no tiene entrega registrada.", "warning")
        return redirect(url_for("logistica.detalle", nota_id=nota_id))

    codigo = (request.form.get("codigo") or "").strip()
    equipo = EquipoMedico.query.filter_by(codigo_barras=codigo).first()
    if equipo is None:
        flash(f"El codigo {codigo} no corresponde a ningun equipo.", "danger")
        return redirect(url_for("logistica.detalle", nota_id=nota_id))

    estado = request.form.get("estado") or EstadoEquipo.DISPONIBLE
    try:
        registrar_regreso(nota.entrega, equipo, current_user, estado,
                          request.form.get("observaciones"))
    except ErrorDeLogistica as e:
        flash(str(e), "danger")
        return redirect(url_for("logistica.detalle", nota_id=nota_id))

    if nota.estado == EstadoNota.CERRADA:
        flash(f"Regreso registrado. La nota {nota.folio} queda cerrada.",
              "success")
    else:
        flash(f"{equipo.descripcion} regreso al almacen.", "success")
    return redirect(url_for("logistica.detalle", nota_id=nota_id))


@bp.route("/responsiva/<int:responsiva_id>.pdf")
@login_required
@rol_requerido(Rol.TECNICO, Rol.REVISOR_ADMIN)
def descargar_responsiva(responsiva_id):
    responsiva = Responsiva.query.get_or_404(responsiva_id)
    carpeta = current_app.config["PDF_REMISIONES_DIR"]
    ruta = carpeta / (responsiva.pdf_path or f"{responsiva.folio}.pdf")

    if not ruta.exists():
        ruta = regenerar_pdf(responsiva)

    # Desde memoria: en Windows send_file deja el archivo abierto.
    return send_file(BytesIO(ruta.read_bytes()), mimetype="application/pdf",
                     download_name=f"{responsiva.folio}.pdf")
