"""Revision de notas y generacion de remisiones (rol revisor_admin)."""

from io import BytesIO

from flask import (current_app, flash, redirect, render_template, request,
                   send_file, url_for)
from flask_login import current_user, login_required

from app.blueprints.revision import bp
from app.constantes import EstadoNota, Rol
from app.models import NotaVenta, Remision
from app.servicios.remisiones import (ErrorDeRemision, generar_remisiones,
                                      regenerar_pdf)
from app.servicios.revision import (ErrorDeRevision, aprobar, cancelar,
                                    guardar_precios, hay_faltantes, rechazar,
                                    renglones_sin_precio,
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
        sin_precio=renglones_sin_precio(nota),
    )


@bp.route("/<int:nota_id>/precios", methods=["POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def capturar_precios(nota_id):
    nota = NotaVenta.query.get_or_404(nota_id)
    try:
        guardar_precios(nota, request.form, current_user)
    except ErrorDeRevision as e:
        flash(str(e), "danger")
    else:
        flash("Precios guardados.", "success")
    return redirect(url_for("revision.revisar", nota_id=nota_id))


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


@bp.route("/<int:nota_id>/remision", methods=["POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def generar_remision(nota_id):
    nota = NotaVenta.query.get_or_404(nota_id)
    try:
        creadas = generar_remisiones(nota, current_user)
    except ErrorDeRemision as e:
        flash(str(e), "danger")
    else:
        if creadas:
            folios = ", ".join(r.folio for r in creadas)
            flash(f"Remisiones generadas: {folios}.", "success")
        else:
            flash("La nota ya tenia todas sus remisiones.", "info")
    return redirect(url_for("revision.revisar", nota_id=nota_id))


@bp.route("/remision/<int:remision_id>.pdf")
@login_required
@rol_requerido(Rol.REVISOR_ADMIN, Rol.TECNICO)
def descargar_remision(remision_id):
    """Descarga o reimprime la remision. Si el PDF falta, se regenera."""
    remision = Remision.query.get_or_404(remision_id)
    carpeta = current_app.config["PDF_REMISIONES_DIR"]
    ruta = carpeta / (remision.pdf_path or f"{remision.folio}.pdf")

    if not ruta.exists():
        try:
            ruta = regenerar_pdf(remision)
        except Exception as e:  # noqa: BLE001
            flash(f"No se pudo generar el PDF: {e}", "danger")
            return redirect(
                url_for("revision.revisar", nota_id=remision.nota_venta_id)
            )

    # Se sirve desde memoria y no con la ruta: en Windows send_file deja el
    # archivo abierto y una reimpresion posterior no podria sobrescribirlo.
    # Las remisiones pesan unos pocos KB, asi que no compensa arriesgarlo.
    return send_file(
        BytesIO(ruta.read_bytes()),
        mimetype="application/pdf",
        download_name=f"{remision.folio}.pdf",
    )
