from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Email, Length, Optional

from app.constantes import Rol


class LoginForm(FlaskForm):
    email = StringField(
        "Correo",
        validators=[DataRequired("Escribe tu correo."), Email("Correo invalido.")],
    )
    password = PasswordField(
        "Contrasena", validators=[DataRequired("Escribe tu contrasena.")]
    )
    recordarme = BooleanField("Mantener sesion iniciada")
    submit = SubmitField("Entrar")


class UsuarioForm(FlaskForm):
    """Alta/edicion de usuarios (solo revisor_admin)."""

    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=120)])
    email = StringField("Correo", validators=[DataRequired(), Email(), Length(max=120)])
    rol = SelectField(
        "Rol",
        choices=[(r, Rol.ETIQUETAS[r]) for r in Rol.TODOS],
        validators=[DataRequired()],
    )
    # Optional() permite dejarlo vacio al editar y conservar la contrasena actual.
    password = PasswordField(
        "Contrasena",
        validators=[Optional(), Length(min=8, max=128, message="Minimo 8 caracteres.")],
        description="Al editar, dejar en blanco para conservar la actual.",
    )
    activo = BooleanField("Usuario activo", default=True)
    submit = SubmitField("Guardar")
