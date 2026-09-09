from datetime import datetime, timezone

from app.extensions import db


class HistorialMovimiento(db.Model):
    """Bitacora append-only. Nunca se edita ni se borra: es la trazabilidad."""

    __tablename__ = "historial_movimientos"

    id = db.Column(db.Integer, primary_key=True)
    item_tipo = db.Column(db.String(10), nullable=False)  # TipoItem
    item_id = db.Column(db.Integer, nullable=False, index=True)
    movimiento = db.Column(db.String(30), nullable=False)  # Movimiento
    cantidad = db.Column(db.Integer)

    fecha = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    usuario = db.relationship("Usuario")

    nota_venta_id = db.Column(db.Integer, db.ForeignKey("notas_venta.id"))
    nota = db.relationship("NotaVenta")

    detalle = db.Column(db.Text)

    def __repr__(self):
        return f"<Movimiento {self.movimiento} {self.item_tipo}:{self.item_id}>"
