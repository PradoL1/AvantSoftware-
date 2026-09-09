from flask import render_template
from flask_login import current_user, login_required

from app.blueprints.main import bp
from app.constantes import EstadoEquipo, EstadoNota
from app.extensions import db
from app.models import EquipoMedico, Insumo, NotaVenta


def _contar_notas(estado, **filtros):
    return (
        db.session.query(db.func.count(NotaVenta.id))
        .filter_by(estado=estado, **filtros)
        .scalar()
    )


@bp.route("/")
@login_required
def inicio():
    """Tablero. Cada rol ve el resumen que le toca."""
    datos = {}

    if current_user.es_vendedor:
        mias = {"vendedor_id": current_user.id}
        datos["kpis"] = [
            ("Pendientes de revision", _contar_notas(EstadoNota.PENDIENTE_REVISION, **mias), "kcard-aviso"),
            ("Aprobadas", _contar_notas(EstadoNota.APROBADA, **mias), ""),
            ("Entregadas", _contar_notas(EstadoNota.ENTREGADA, **mias), "kcard-exito"),
            ("Rechazadas", _contar_notas(EstadoNota.RECHAZADA, **mias), "kcard-peligro"),
        ]
        datos["mis_notas"] = (
            NotaVenta.query.filter_by(vendedor_id=current_user.id)
            .order_by(NotaVenta.fecha_creacion.desc())
            .limit(10)
            .all()
        )

    elif current_user.es_revisor:
        pendientes = (
            NotaVenta.query.filter_by(estado=EstadoNota.PENDIENTE_REVISION)
            .order_by(NotaVenta.fecha_requerida)
            .all()
        )
        insumos = Insumo.query.filter_by(activo=True).all()
        bajo_minimo = [i for i in insumos if i.bajo_minimo]

        equipo_disponible = (
            db.session.query(db.func.count(EquipoMedico.id))
            .filter_by(estado=EstadoEquipo.DISPONIBLE, activo=True)
            .scalar()
        )
        equipo_rentado = (
            db.session.query(db.func.count(EquipoMedico.id))
            .filter_by(estado=EstadoEquipo.RENTADO, activo=True)
            .scalar()
        )

        datos["kpis"] = [
            ("Pendientes de revision", len(pendientes), "kcard-aviso"),
            ("Equipo disponible", equipo_disponible, "kcard-exito"),
            ("Equipo rentado", equipo_rentado, ""),
            ("Insumos bajo minimo", len(bajo_minimo), "kcard-peligro"),
        ]
        datos["pendientes"] = pendientes
        datos["insumos_bajo_minimo"] = bajo_minimo

    elif current_user.es_tecnico:
        en_logistica = (
            NotaVenta.query.filter(
                NotaVenta.estado.in_(
                    (EstadoNota.REMISION_GENERADA, EstadoNota.EN_LOGISTICA)
                )
            )
            .order_by(NotaVenta.fecha_requerida)
            .all()
        )
        datos["kpis"] = [
            ("Por recoger en almacen", _contar_notas(EstadoNota.REMISION_GENERADA), "kcard-aviso"),
            ("En ruta", _contar_notas(EstadoNota.EN_LOGISTICA), ""),
            ("Entregadas sin cerrar", _contar_notas(EstadoNota.ENTREGADA), "kcard-exito"),
        ]
        datos["en_logistica"] = en_logistica

    return render_template("main/inicio.html", **datos)
