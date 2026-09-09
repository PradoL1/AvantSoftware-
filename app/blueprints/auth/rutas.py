from urllib.parse import urlparse

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth import bp
from app.blueprints.auth.formularios import LoginForm
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
