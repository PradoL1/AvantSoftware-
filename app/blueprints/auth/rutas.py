from urllib.parse import urlparse

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth import bp
from app.blueprints.auth.formularios import LoginForm, UsuarioForm
from app.constantes import Rol
from app.extensions import db
from app.utils.decoradores import rol_requerido
from app.models import Usuario


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.inicio"))

    form = LoginForm()
    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(email=form.email.data.strip().lower()).first()

        if usuario is None or not usuario.check_password(form.password.data):
            # Mismo mensaje en ambos casos: no revela si el correo existe.
            flash("Correo o contrasena incorrectos.", "danger")
            return render_template("auth/login.html", form=form)

        if not usuario.activo:
            flash("Tu usuario esta desactivado. Contacta al administrador.", "warning")
            return render_template("auth/login.html", form=form)

        login_user(usuario, remember=form.recordarme.data)

        # Solo se acepta un destino relativo: evita redirigir a un sitio externo.
        siguiente = request.args.get("next")
        if not siguiente or urlparse(siguiente).netloc:
            siguiente = url_for("main.inicio")
        return redirect(siguiente)

    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesion cerrada.", "info")
    return redirect(url_for("auth.login"))


# --- Usuarios (solo revisor_admin) ------------------------------------------


@bp.route("/usuarios")
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def usuarios():
    lista = Usuario.query.order_by(Usuario.nombre).all()
    return render_template("auth/usuarios.html", usuarios=lista)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@bp.route("/usuarios/<int:usuario_id>", methods=["GET", "POST"])
@login_required
@rol_requerido(Rol.REVISOR_ADMIN)
def editar_usuario(usuario_id=None):
    usuario = Usuario.query.get_or_404(usuario_id) if usuario_id else None
    form = UsuarioForm(obj=usuario)
    es_uno_mismo = usuario is not None and usuario.id == current_user.id

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        repetido = Usuario.query.filter_by(email=email).first()
        if repetido and (usuario is None or repetido.id != usuario.id):
            flash(f"Ya hay un usuario con el correo {email}.", "danger")
            return render_template("auth/usuario_form.html", form=form,
                                   usuario=usuario, es_uno_mismo=es_uno_mismo)

        if usuario is None and not form.password.data:
            flash("Un usuario nuevo necesita contrasena.", "danger")
            return render_template("auth/usuario_form.html", form=form,
                                   usuario=usuario, es_uno_mismo=es_uno_mismo)

        # Nadie puede quitarse a si mismo el acceso: si el ultimo revisor se
        # desactiva o se cambia de rol, no queda quien administre el sistema.
        if es_uno_mismo and (not form.activo.data
                             or form.rol.data != Rol.REVISOR_ADMIN):
            flash(
                "No puedes quitarte a ti mismo el rol de administrador ni "
                "desactivar tu propia cuenta. Pide a otro administrador que "
                "lo haga.",
                "danger",
            )
            return render_template("auth/usuario_form.html", form=form,
                                   usuario=usuario, es_uno_mismo=es_uno_mismo)

        if usuario is None:
            usuario = Usuario()
            db.session.add(usuario)

        usuario.nombre = form.nombre.data.strip()
        usuario.email = email
        usuario.rol = form.rol.data
        usuario.activo = form.activo.data
        # En blanco al editar significa "dejala como esta".
        if form.password.data:
            usuario.set_password(form.password.data)

        db.session.commit()
        flash(f"Usuario {usuario.nombre} guardado.", "success")
        return redirect(url_for("auth.usuarios"))

    return render_template("auth/usuario_form.html", form=form, usuario=usuario,
                           es_uno_mismo=es_uno_mismo)
