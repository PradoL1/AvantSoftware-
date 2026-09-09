from flask_wtf import FlaskForm
from wtforms import (BooleanField, DateField, DecimalField, SelectField,
                     StringField, SubmitField, TextAreaField)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.constantes import Empresa


class HospitalForm(FlaskForm):
    nombre = StringField(
        "Nombre del hospital",
        validators=[DataRequired("Escribe el nombre."), Length(max=200)],
    )
    # De este campo depende que RFC lleva la remision, por eso es obligatorio
    # y no se deduce del nombre.
    empresa = SelectField(
        "Razon social que le factura",
        choices=[(k, v["razon_social"]) for k, v in Empresa.DATOS.items()],
        validators=[DataRequired()],
    )
    ciudad = StringField("Ciudad", validators=[Optional(), Length(max=120)],
                         default="Ciudad de Mexico")
    direccion = TextAreaField("Direccion", validators=[Optional()])
    contacto_nombre = StringField("Contacto", validators=[Optional(), Length(max=120)])
    contacto_telefono = StringField("Telefono", validators=[Optional(), Length(max=40)])
    notas = TextAreaField("Notas", validators=[Optional()])
    activo = BooleanField("Activo", default=True)
    submit = SubmitField("Guardar hospital")


class TarifaForm(FlaskForm):
    """Precio de renta de una pieza de equipo en un hospital."""

    equipo_id = SelectField("Equipo", coerce=int, validators=[DataRequired()])
    hospital_id = SelectField("Hospital", coerce=int, validators=[DataRequired()])
    precio_renta = DecimalField(
        "Precio de renta",
        places=2,
        validators=[DataRequired("Escribe el precio."),
                    NumberRange(min=0, message="No puede ser negativo.")],
    )
    vigente_desde = DateField("Vigente desde", validators=[DataRequired()])
    submit = SubmitField("Guardar tarifa")
