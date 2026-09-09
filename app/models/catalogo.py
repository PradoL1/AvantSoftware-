from datetime import datetime, timezone

from app.constantes import EstadoEquipo
from app.extensions import db


class EquipoMedico(db.Model):
    """Bien retornable: se renta, se entrega y debe regresar al almacen."""

    __tablename__ = "equipo_medico"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(160), nullable=False)
    marca = db.Column(db.String(80))
    modelo = db.Column(db.String(80))
    numero_serie = db.Column(db.String(80), unique=True)
    codigo_barras = db.Column(db.String(64), unique=True, nullable=False, index=True)
    estado = db.Column(db.String(20), nullable=False, default=EstadoEquipo.DISPONIBLE)
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
    def descripcion(self):
        partes = [self.nombre, self.marca, self.modelo]
        return " ".join(p for p in partes if p)

    def __repr__(self):
        return f"<EquipoMedico {self.codigo_barras} {self.nombre}>"


class Insumo(db.Model):
    """Bien consumible: se descuenta del stock al cerrar la nota."""

    __tablename__ = "insumos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(160), nullable=False)
    unidad_medida = db.Column(db.String(30), nullable=False, default="pieza")
    codigo_barras = db.Column(db.String(64), unique=True, nullable=False, index=True)
    stock_actual = db.Column(db.Integer, nullable=False, default=0)
    stock_minimo = db.Column(db.Integer, nullable=False, default=0)
    # Cantidad comprometida en notas aprobadas que todavia no se cierran.
    stock_apartado = db.Column(db.Integer, nullable=False, default=0)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_alta = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    @property
    def stock_disponible(self):
        """Lo que realmente se puede comprometer en una nota nueva."""
        return self.stock_actual - self.stock_apartado

    @property
    def bajo_minimo(self):
        return self.stock_disponible <= self.stock_minimo

    @property
    def descripcion(self):
        return self.nombre

    def __repr__(self):
        return f"<Insumo {self.codigo_barras} {self.nombre}>"
