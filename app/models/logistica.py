from datetime import datetime, timezone

from app.extensions import db


class Remision(db.Model):
    __tablename__ = "remisiones"

    id = db.Column(db.Integer, primary_key=True)
    folio = db.Column(db.String(30), unique=True, nullable=False, index=True)

    nota_venta_id = db.Column(
        db.Integer, db.ForeignKey("notas_venta.id"), nullable=False, unique=True
    )
    nota = db.relationship("NotaVenta", back_populates="remision")

    generado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    generado_por = db.relationship("Usuario")

    fecha_generacion = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    pdf_path = db.Column(db.String(255))
    cancelada = db.Column(db.Boolean, nullable=False, default=False)

    entrega = db.relationship(
        "Entrega", back_populates="remision", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Remision {self.folio}>"


class Entrega(db.Model):
    __tablename__ = "entregas"

    id = db.Column(db.Integer, primary_key=True)
    remision_id = db.Column(
        db.Integer, db.ForeignKey("remisiones.id"), nullable=False, unique=True
    )
    remision = db.relationship("Remision", back_populates="entrega")

    tecnico_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    tecnico = db.relationship("Usuario")

    # Checklist de doble verificacion: en almacen y en el hospital.
    checklist_almacen_ok = db.Column(db.Boolean, nullable=False, default=False)
    fecha_checklist_almacen = db.Column(db.DateTime(timezone=True))
    checklist_hospital_ok = db.Column(db.Boolean, nullable=False, default=False)
    fecha_checklist_hospital = db.Column(db.DateTime(timezone=True))

    fecha_asignacion = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    fecha_entrega = db.Column(db.DateTime(timezone=True))
    recibe_nombre = db.Column(db.String(120))
    observaciones = db.Column(db.Text)

    # Equipo medico (retornable)
    fecha_regreso_equipo = db.Column(db.DateTime(timezone=True))

    @property
    def checklist_ok(self):
        return self.checklist_almacen_ok and self.checklist_hospital_ok

    def __repr__(self):
        return f"<Entrega remision={self.remision_id}>"


class ChecklistItem(db.Model):
    """Verificacion articulo por articulo, escaneando su codigo de barras.

    Se registra dos veces por articulo (etapa = almacen / hospital): eso es la
    doble verificacion del flujo.
    """

    __tablename__ = "checklist_items"

    ETAPA_ALMACEN = "almacen"
    ETAPA_HOSPITAL = "hospital"

    id = db.Column(db.Integer, primary_key=True)
    entrega_id = db.Column(
        db.Integer, db.ForeignKey("entregas.id"), nullable=False, index=True
    )
    entrega = db.relationship(
        "Entrega", backref=db.backref("checklist", lazy="selectin")
    )

    detalle_id = db.Column(
        db.Integer, db.ForeignKey("detalle_nota_venta.id"), nullable=False
    )
    detalle = db.relationship("DetalleNotaVenta")

    etapa = db.Column(db.String(20), nullable=False)
    verificado = db.Column(db.Boolean, nullable=False, default=False)
    codigo_escaneado = db.Column(db.String(64))
    fecha = db.Column(db.DateTime(timezone=True))

    def __repr__(self):
        return f"<ChecklistItem {self.etapa} detalle={self.detalle_id}>"
