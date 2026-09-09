from flask_wtf import FlaskForm
from wtforms import (BooleanField, DateField, DecimalField, IntegerField,
                     SelectField, StringField, SubmitField, TextAreaField)
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


class EquipoForm(FlaskForm):
    """Alta y edicion de una pieza de equipo medico."""

    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=160)])
    tipo_equipo = StringField("Tipo de equipo",
                              validators=[Optional(), Length(max=80)])
    marca = StringField("Marca", validators=[Optional(), Length(max=80)])
    modelo = StringField("Modelo", validators=[Optional(), Length(max=80)])
    numero_serie = StringField("Numero de serie",
                               validators=[Optional(), Length(max=80)])
    codigo_barras = StringField(
        "Codigo de barras",
        validators=[DataRequired("Hace falta el codigo."), Length(max=64)],
        description="Se sugiere uno al escribir el nombre; se puede cambiar.",
    )
    empresa_propietaria = SelectField(
        "Empresa propietaria",
        choices=[(k, v["razon_social"]) for k, v in Empresa.DATOS.items()],
        validators=[DataRequired()],
    )
    moi = DecimalField(
        "Valor de reposicion (MOI)", places=2,
        validators=[Optional(), NumberRange(min=0)],
        description="Es la cifra que el hospital se compromete a cubrir en la "
                    "carta responsiva.",
    )
    almacen_id = SelectField("Almacen", coerce=int, validators=[Optional()])
    observaciones = TextAreaField("Observaciones", validators=[Optional()])
    activo = BooleanField("Activo", default=True)
    submit = SubmitField("Guardar equipo")


class InsumoForm(FlaskForm):
    """Alta y edicion de un insumo. Las existencias van aparte."""

    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=160)])
    sku = StringField("SKU", validators=[Optional(), Length(max=40)])
    unidad_medida = StringField("Unidad de medida",
                                validators=[DataRequired(), Length(max=30)],
                                default="pieza")
    codigo_barras = StringField(
        "Codigo de barras",
        validators=[DataRequired("Hace falta el codigo."), Length(max=64)],
    )
    # Los insumos no tienen precio de venta: se negocia en cada nota. El costo
    # si vive aqui, porque es lo que valua el kardex.
    costo_unitario = DecimalField("Costo unitario", places=2,
                                  validators=[Optional(), NumberRange(min=0)])
    stock_minimo = IntegerField("Stock minimo", default=0,
                                validators=[Optional(), NumberRange(min=0)])
    proveedor = StringField("Proveedor", validators=[Optional(), Length(max=160)])
    activo = BooleanField("Activo", default=True)
    submit = SubmitField("Guardar insumo")
