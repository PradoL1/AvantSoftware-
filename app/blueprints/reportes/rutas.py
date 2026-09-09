"""Kardex y trazabilidad (rol revisor_admin)."""

from datetime import date, datetime

from flask import Response, render_template, request
from flask_login import login_required

from app.blueprints.reportes import bp
from app.constantes import Movimiento, Rol, TipoItem
from app.models import Almacen, EquipoMedico, Insumo
from app.servicios.kardex import (POR_PAGINA, a_csv, construir_consulta,
                                  describir, resumen)
from app.utils.decoradores import rol_requerido


def _fecha(valor):
    """Convierte una fecha del formulario. Vacia o invalida es None."""
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return None


def _filtros_de(args):
    return {
        "texto": args.get("texto", ""),
        "movimiento": args.get("movimiento", ""),
        "item_tipo": args.get("item_tipo", ""),
        "almacen_id": args.get("almacen_id", ""),
        "desde": _fecha(args.get("desde")),
        "hasta": _fecha(args.get("hasta")),
    }


@bp.route("/kardex")
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def kardex():
    filtros = _filtros_de(request.args)
    consulta = construir_consulta(filtros)

    pagina = request.args.get("pagina", 1, type=int)
    paginado = consulta.paginate(page=pagina, per_page=POR_PAGINA,
                                 error_out=False)

    return render_template(
        "reportes/kardex.html",
        filas=describir(paginado.items),
        paginado=paginado,
        filtros=filtros,
        # Los filtros tal como vinieron, para que los enlaces de pagina los
        # arrastren sin volver a formatear fechas.
        filtros_url={k: v for k, v in request.args.items() if k != "pagina"},
        totales=resumen(consulta),
        almacenes=Almacen.query.order_by(Almacen.nombre).all(),
        hoy=date.today(),
    )


@bp.route("/kardex.csv")
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def kardex_csv():
    """Exporta lo que se ve con los filtros actuales, no toda la tabla."""
    filtros = _filtros_de(request.args)
    filas = describir(construir_consulta(filtros).all())

    nombre = f"kardex_avant_{date.today().isoformat()}.csv"
    return Response(
        a_csv(filas),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


@bp.route("/trazabilidad/<tipo>/<int:item_id>")
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def trazabilidad(tipo, item_id):
    """Historia completa de un solo articulo, de su alta a hoy."""
    if tipo not in TipoItem.TODOS:
        return render_template("errores/404.html"), 404

    modelo = EquipoMedico if tipo == TipoItem.EQUIPO else Insumo
    articulo = modelo.query.get_or_404(item_id)

    consulta = construir_consulta({
        "item_tipo_exacto": tipo,
        "item_id": item_id,
    })

    return render_template(
        "reportes/trazabilidad.html",
        articulo=articulo,
        tipo=tipo,
        filas=describir(consulta.all()),
        totales=resumen(consulta),
        Movimiento=Movimiento,
    )
