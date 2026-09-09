from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.constantes import Especialidad, MetodoPago, TipoPaciente, VerificadoCon


def _opciones(valores, vacio="-- Seleccionar --"):
    return [("", vacio)] + [(v, v) for v in valores]


class NotaVentaForm(FlaskForm):
    """Encabezado de la nota.

    Los renglones (equipos e insumos) no son campos de WTForms: se capturan con
    JavaScript y llegan como listas paralelas en request.form. Se validan en
    app/servicios/notas.py.
    """

    # --- Destino ---
    hospital = StringField(
        "Hospital / Clinica",
        validators=[DataRequired("Indica el hospital."), Length(max=200)],
    )
    ciudad = StringField("Ciudad", validators=[Optional(), Length(max=120)],
                         default="Ciudad de Mexico")
    direccion_entrega = TextAreaField(
        "Direccion de entrega",
        validators=[DataRequired("Indica donde se entrega.")],
    )
    contacto_nombre = StringField(
        "Contacto en el hospital", validators=[Optional(), Length(max=120)]
    )
    contacto_telefono = StringField(
        "Telefono del contacto", validators=[Optional(), Length(max=40)]
    )
    fecha_requerida = DateField(
        "Fecha requerida de entrega",
        validators=[DataRequired("Indica para cuando se necesita.")],
    )

    # --- Procedimiento ---
    fecha_procedimiento = DateField("Fecha del procedimiento", validators=[Optional()])
    especialidad = SelectField(
        "Especialidad medica", choices=_opciones(Especialidad.TODAS),
        validators=[Optional()],
    )
    cirugia = StringField("Cirugia / procedimiento",
                          validators=[Optional(), Length(max=200)])
    doctor = StringField("Doctor(a)", validators=[Optional(), Length(max=160)])
    verificado_con = SelectField(
        "Verificado con", choices=_opciones(VerificadoCon.TODOS),
        validators=[Optional()],
    )

    # --- Cobro ---
    tipo_paciente = SelectField(
        "Tipo de paciente / cobro", choices=_opciones(TipoPaciente.TODOS),
        validators=[Optional()],
    )
    # Sin Optional(): ese validador corta la cadena cuando el campo viene vacio
    # y validate_metodo_pago nunca correria, que es justo el caso a detectar.
    metodo_pago = SelectField(
        "Metodo de pago", choices=_opciones(MetodoPago.TODOS, "-- Seleccionar metodo --"),
    )

    observaciones = TextAreaField("Observaciones e indicaciones",
                                  validators=[Optional()])
    submit = SubmitField("Guardar nota")

    def validate_metodo_pago(self, campo):
        """Como en el sistema anterior: solo el particular paga de su bolsillo."""
        if self.tipo_paciente.data == TipoPaciente.PARTICULAR and not campo.data:
            raise ValidationError(
                "Un paciente particular necesita metodo de pago."
            )
        if self.tipo_paciente.data != TipoPaciente.PARTICULAR and campo.data:
            raise ValidationError(
                "El metodo de pago solo aplica a pacientes particulares."
            )
