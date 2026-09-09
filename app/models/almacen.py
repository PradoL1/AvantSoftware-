from app.extensions import db


class Almacen(db.Model):
    """Ubicacion fisica del inventario.

    El sistema anterior maneja cuatro: Central, Operaciones, Resteril y
    Transicion, con traspasos entre ellas. Se modela como tabla y no como lista
    fija para poder abrir o cerrar almacenes sin migrar.
    """

    __tablename__ = "almacenes"

    # Los cuatro del sistema anterior, para sembrar la base.
    INICIALES = ("Central", "Operaciones", "Resteril", "Transicion")

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    descripcion = db.Column(db.String(200))
    activo = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<Almacen {self.nombre}>"


class Existencia(db.Model):
    """Cuantas piezas de un insumo hay en un almacen.

    Sustituye al contador unico que tenia Insumo: con varios almacenes, el
    stock deja de ser un numero y pasa a ser un reparto.
    """

    __tablename__ = "existencias"
    __table_args__ = (
        db.UniqueConstraint("insumo_id", "almacen_id", name="uq_existencia_insumo_almacen"),
    )

    id = db.Column(db.Integer, primary_key=True)

    insumo_id = db.Column(
        db.Integer, db.ForeignKey("insumos.id"), nullable=False, index=True
    )
    insumo = db.relationship("Insumo", back_populates="existencias")

    almacen_id = db.Column(
        db.Integer, db.ForeignKey("almacenes.id"), nullable=False, index=True
    )
    almacen = db.relationship("Almacen")

    cantidad = db.Column(db.Integer, nullable=False, default=0)
    # Comprometido en notas aprobadas que aun no se cierran.
    apartado = db.Column(db.Integer, nullable=False, default=0)

    def __init__(self, **kwargs):
        # El default de la columna solo se aplica al insertar. Sin esto, una
        # existencia recien construida trae None y cualquier comparacion o
        # suma revienta antes del flush.
        kwargs.setdefault("cantidad", 0)
        kwargs.setdefault("apartado", 0)
        super().__init__(**kwargs)

    @property
    def disponible(self):
        return (self.cantidad or 0) - (self.apartado or 0)

    def __repr__(self):
        return f"<Existencia insumo={self.insumo_id} almacen={self.almacen_id} {self.cantidad}>"
