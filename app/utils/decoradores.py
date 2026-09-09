"""Control de acceso por rol."""

from functools import wraps

from flask import abort
from flask_login import current_user

from app.constantes import Rol


def rol_requerido(*roles):
    """Restringe una vista a los roles indicados.

    Uso:
        @bp.route("/aprobar/<int:id>")
        @login_required
        @rol_requerido(Rol.REVISOR_ADMIN)
        def aprobar(id): ...

    Debe ir DESPUES de @login_required para que current_user ya este resuelto.
    """

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.rol not in roles:
                abort(403)
            return vista(*args, **kwargs)

        return envoltura

    return decorador


def solo_revisor(vista):
    return rol_requerido(Rol.REVISOR_ADMIN)(vista)


def solo_vendedor(vista):
    return rol_requerido(Rol.VENDEDOR)(vista)


def solo_tecnico(vista):
    return rol_requerido(Rol.TECNICO)(vista)
