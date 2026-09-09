from datetime import datetime, timezone

from app.extensions import db


class HistorialMovimiento(db.Model):
    """Kardex: bitacora append-only del inventario.

    A diferencia de una bitacora simple, cada renglon guarda el saldo antes y
    despues del movimiento. Eso es lo que permite reconstruir el inventario a
    cualquier fecha sin recalcular toda la historia, y es como lo presenta el
    sistema anterior (Inv. Inicial / Cant. Mov. / Inv. Final).

    Nunca se edita ni se borra. El sistema anterior permitia "eliminar y
    revertir" un movimiento; aqui una correccion es un movimiento de ajuste
    nuevo, para que la historia no se pueda reescribir.
    """

    __tablename__ = "historial_movimientos"

    id = db.Column(db.Integer, primary_key=True)
    item_tipo = db.Column(db.String(10), nullable=False)  # TipoItem
    item_id = db.Column(db.Integer, nullable=False, index=True)
    movimiento = db.Column(db.String(30), nullable=False)  # Movimiento
    cantidad = db.Column(db.Integer)

    # Saldos del insumo en el almacen afectado, antes y despues.
    saldo_anterior = db.Column(db.Integer)
    saldo_nuevo = db.Column(db.Integer)

    # Traspasos: de donde sale y a donde entra.
    almacen_origen_id = db.Column(db.Integer, db.ForeignKey("almacenes.id"))
    almacen_origen = db.relationship("Almacen", foreign_keys=[almacen_origen_id])
    almacen_destino_id = db.Column(db.Integer, db.ForeignKey("almacenes.id"))
    almacen_destino = db.relationship("Almacen", foreign_keys=[almacen_destino_id])

    # Costeo y cuentas por pagar.
    costo_unitario = db.Column(db.Numeric(12, 2))
    importe = db.Column(db.Numeric(12, 2))
    proveedor = db.Column(db.String(160))
    fecha_pago = db.Column(db.Date)

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

    @property
    def pagado(self):
        return self.fecha_pago is not None

    def __repr__(self):
        return f"<Movimiento {self.movimiento} {self.item_tipo}:{self.item_id}>"
