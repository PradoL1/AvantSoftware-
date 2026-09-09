from datetime import datetime, timezone

from app.constantes import Empresa, EstadoEquipo
from app.extensions import db


class EquipoMedico(db.Model):
    """Bien retornable: se renta, se entrega y debe regresar al almacen."""

    __tablename__ = "equipo_medico"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(160), nullable=False)
    tipo_equipo = db.Column(db.String(80))
    marca = db.Column(db.String(80))
    modelo = db.Column(db.String(80))
    numero_serie = db.Column(db.String(80), unique=True)
    codigo_barras = db.Column(db.String(64), unique=True, nullable=False, index=True)

    estado = db.Column(db.String(20), nullable=False, default=EstadoEquipo.DISPONIBLE)

    # Cada activo pertenece a una de las dos razones sociales.
    empresa_propietaria = db.Column(db.String(20), default=Empresa.GARDE)

    # MOI: monto original de la inversion. Es el valor de reposicion que se
    # imprime en la carta responsiva y que el receptor se compromete a cubrir.
    moi = db.Column(db.Numeric(12, 2), default=0)

    almacen_id = db.Column(db.Integer, db.ForeignKey("almacenes.id"))
    almacen = db.relationship("Almacen")
    ubicacion_actual = db.Column(db.String(160), default="Almacen")

    observaciones = db.Column(db.Text)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_alta = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    @property
    def disponible(self):
        return self.activo and self.estado == EstadoEquipo.DISPONIBLE

    @property
    def estado_etiqueta(self):
        return EstadoEquipo.ETIQUETAS.get(self.estado, self.estado)

    @property
    def razon_social(self):
        datos = Empresa.DATOS.get(self.empresa_propietaria)
        return datos["razon_social"] if datos else ""

    @property
    def descripcion(self):
        partes = [self.nombre, self.marca, self.modelo]
        return " ".join(p for p in partes if p)

    def __repr__(self):
        return f"<EquipoMedico {self.codigo_barras} {self.nombre}>"


class Insumo(db.Model):
    """Bien consumible: se descuenta del stock al cerrar la nota.

    El stock no vive aqui sino en `existencias`, una fila por almacen.
    """

    __tablename__ = "insumos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(160), nullable=False)
    sku = db.Column(db.String(40), unique=True, index=True)
    unidad_medida = db.Column(db.String(30), nullable=False, default="pieza")
    codigo_barras = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # Dos listas de precios, como en el sistema anterior: los hospitales del
    # Grupo Angeles tienen su propia tarifa.
    precio_angeles = db.Column(db.Numeric(12, 2), default=0)
    precio_otros = db.Column(db.Numeric(12, 2), default=0)
    costo_unitario = db.Column(db.Numeric(12, 2), default=0)

    stock_minimo = db.Column(db.Integer, nullable=False, default=0)
    proveedor = db.Column(db.String(160))

    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_alta = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    existencias = db.relationship(
        "Existencia",
        back_populates="insumo",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # --- Stock agregado sobre todos los almacenes ---

    @property
    def stock_actual(self):
        return sum(e.cantidad for e in self.existencias)

    @property
    def stock_apartado(self):
        return sum(e.apartado for e in self.existencias)

    @property
    def stock_disponible(self):
        return self.stock_actual - self.stock_apartado

    @property
    def bajo_minimo(self):
        return self.stock_disponible <= self.stock_minimo

    def existencia_en(self, almacen_id):
        for e in self.existencias:
            if e.almacen_id == almacen_id:
                return e
        return None

    def precio_para(self, hospital):
        """La tarifa depende de si el hospital es del Grupo Angeles."""
        if Empresa.para_hospital(hospital) == Empresa.SOLUCIONES:
            return self.precio_angeles or 0
        return self.precio_otros or 0

    @property
    def descripcion(self):
        return self.nombre

    def __repr__(self):
        return f"<Insumo {self.codigo_barras} {self.nombre}>"
