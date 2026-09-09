from datetime import date

from sqlalchemy import or_

from app.constantes import Empresa
from app.extensions import db


class Hospital(db.Model):
    """Cliente destino.

    Deja de ser texto libre en la nota por dos razones: el precio de renta del
    equipo depende del hospital, y la razon social que factura tambien. Con
    texto libre, un dedazo cambiaba el RFC de la remision.
    """

    __tablename__ = "hospitales"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), unique=True, nullable=False)
    ciudad = db.Column(db.String(120), default="Ciudad de Mexico")
    direccion = db.Column(db.Text)

    # Que empresa factura a este hospital. Antes se adivinaba buscando
    # "ANGELES" en el nombre; ahora es un dato que alguien captura a proposito.
    empresa = db.Column(db.String(20), nullable=False, default=Empresa.GARDE)

    contacto_nombre = db.Column(db.String(120))
    contacto_telefono = db.Column(db.String(40))
    notas = db.Column(db.Text)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    tarifas = db.relationship(
        "TarifaEquipo", back_populates="hospital", cascade="all, delete-orphan"
    )

    @property
    def datos_empresa(self):
        return Empresa.DATOS[self.empresa]

    @property
    def razon_social(self):
        return self.datos_empresa["razon_social"]

    def __repr__(self):
        return f"<Hospital {self.nombre}>"


class TarifaEquipo(db.Model):
    """Precio de renta de una pieza de equipo en un hospital.

    Lleva vigencia porque un cambio de precio no debe reescribir la historia:
    se agrega una tarifa nueva y la anterior queda como estaba. De todos modos
    la nota congela el precio en su renglon al guardarse, asi que los documentos
    ya emitidos nunca cambian.
    """

    __tablename__ = "tarifas_equipo"
    __table_args__ = (
        db.UniqueConstraint(
            "equipo_id", "hospital_id", "vigente_desde",
            name="uq_tarifa_equipo_hospital_desde",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    equipo_id = db.Column(
        db.Integer, db.ForeignKey("equipo_medico.id"), nullable=False, index=True
    )
    equipo = db.relationship("EquipoMedico", back_populates="tarifas")

    hospital_id = db.Column(
        db.Integer, db.ForeignKey("hospitales.id"), nullable=False, index=True
    )
    hospital = db.relationship("Hospital", back_populates="tarifas")

    precio_renta = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    vigente_desde = db.Column(db.Date, nullable=False, default=date.today)
    vigente_hasta = db.Column(db.Date)

    def vigente_en(self, dia=None):
        dia = dia or date.today()
        if self.vigente_desde > dia:
            return False
        return self.vigente_hasta is None or self.vigente_hasta >= dia

    def __repr__(self):
        return f"<TarifaEquipo equipo={self.equipo_id} hospital={self.hospital_id}>"


def precio_renta(equipo, hospital, dia=None):
    """Tarifa vigente del equipo en ese hospital, o None si no hay.

    Devolver None y no cero es a proposito: 'no hay tarifa capturada' y 'la
    renta es gratis' son cosas distintas, y quien llama decide como avisarlo.
    """
    if equipo is None or hospital is None:
        return None

    dia = dia or date.today()
    tarifa = (
        TarifaEquipo.query.filter(
            TarifaEquipo.equipo_id == equipo.id,
            TarifaEquipo.hospital_id == hospital.id,
            TarifaEquipo.vigente_desde <= dia,
            or_(TarifaEquipo.vigente_hasta.is_(None),
                TarifaEquipo.vigente_hasta >= dia),
        )
        .order_by(TarifaEquipo.vigente_desde.desc())
        .first()
    )
    return tarifa.precio_renta if tarifa else None
