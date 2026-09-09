from datetime import datetime, timezone

from app.constantes import EstadoNota, TipoItem
from app.extensions import db


class NotaVenta(db.Model):
    __tablename__ = "notas_venta"

    id = db.Column(db.Integer, primary_key=True)
    folio = db.Column(db.String(30), unique=True, nullable=False, index=True)

    vendedor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    vendedor = db.relationship("Usuario", foreign_keys=[vendedor_id])

    hospital = db.Column(db.String(200), nullable=False)
    contacto_nombre = db.Column(db.String(120))
    contacto_telefono = db.Column(db.String(40))
    direccion_entrega = db.Column(db.Text, nullable=False)

    fecha_creacion = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    fecha_requerida = db.Column(db.Date, nullable=False)

    estado = db.Column(
        db.String(30), nullable=False, default=EstadoNota.PENDIENTE_REVISION, index=True
    )
    observaciones = db.Column(db.Text)

    # Revision
    revisado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    revisado_por = db.relationship("Usuario", foreign_keys=[revisado_por_id])
    fecha_revision = db.Column(db.DateTime(timezone=True))
    motivo_rechazo = db.Column(db.Text)

    detalles = db.relationship(
        "DetalleNotaVenta",
        back_populates="nota",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    remision = db.relationship(
        "Remision", back_populates="nota", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def estado_etiqueta(self):
        return EstadoNota.ETIQUETAS.get(self.estado, self.estado)

    @property
    def estado_color(self):
        return EstadoNota.COLORES.get(self.estado, "secondary")

    @property
    def detalles_equipo(self):
        return [d for d in self.detalles if d.tipo == TipoItem.EQUIPO]

    @property
    def detalles_insumo(self):
        return [d for d in self.detalles if d.tipo == TipoItem.INSUMO]

    @property
    def editable(self):
        return self.estado == EstadoNota.PENDIENTE_REVISION

    def puede_pasar_a(self, nuevo_estado):
        return EstadoNota.puede_pasar_a(self.estado, nuevo_estado)

    def __repr__(self):
        return f"<NotaVenta {self.folio} {self.estado}>"


class DetalleNotaVenta(db.Model):
    """Renglon de la nota. item_id apunta a equipo_medico o insumos segun tipo.

    Es una FK polimorfica: no hay restriccion en la BD, la integridad se cuida
    en la capa de servicios (ver app/servicios/).
    """

    __tablename__ = "detalle_nota_venta"

    id = db.Column(db.Integer, primary_key=True)
    nota_venta_id = db.Column(
        db.Integer, db.ForeignKey("notas_venta.id"), nullable=False, index=True
    )
    nota = db.relationship("NotaVenta", back_populates="detalles")

    tipo = db.Column(db.String(10), nullable=False)  # TipoItem
    item_id = db.Column(db.Integer, nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)

    # Copia del nombre al momento de crear la nota: si el catalogo cambia
    # despues, la remision impresa sigue coincidiendo con lo que se pidio.
    descripcion_snapshot = db.Column(db.String(200))
    unidad_snapshot = db.Column(db.String(30))

    @property
    def item(self):
        from app.models.catalogo import EquipoMedico, Insumo

        modelo = EquipoMedico if self.tipo == TipoItem.EQUIPO else Insumo
        return db.session.get(modelo, self.item_id)

    @property
    def descripcion(self):
        if self.descripcion_snapshot:
            return self.descripcion_snapshot
        item = self.item
        return item.descripcion if item else "(articulo eliminado)"

    def __repr__(self):
        return f"<Detalle {self.tipo}:{self.item_id} x{self.cantidad}>"
