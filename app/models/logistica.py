from datetime import datetime, timezone

from app.constantes import Empresa, TipoRemision
from app.extensions import db


class Remision(db.Model):
    __tablename__ = "remisiones"
    # Una remision de cada tipo por nota, no mas.
    __table_args__ = (
        db.UniqueConstraint("nota_venta_id", "tipo", name="uq_remision_nota_tipo"),
    )

    id = db.Column(db.Integer, primary_key=True)
    folio = db.Column(db.String(30), unique=True, nullable=False, index=True)

    nota_venta_id = db.Column(
        db.Integer, db.ForeignKey("notas_venta.id"), nullable=False, index=True
    )
    nota = db.relationship("NotaVenta", back_populates="remisiones")

    generado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    generado_por = db.relationship("Usuario")

    fecha_generacion = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    pdf_path = db.Column(db.String(255))

    # Dos remisiones por nota en el sistema anterior: una de insumos y otra de
    # equipos. El unique de nota_venta_id se abre para permitirlo.
    tipo = db.Column(db.String(20), nullable=False, default=TipoRemision.INSUMOS)

    # Se congelan los datos fiscales al emitir: si manana cambia el RFC, la
    # remision ya impresa debe seguir diciendo lo que decia.
    razon_social = db.Column(db.String(120))
    rfc = db.Column(db.String(20))
    subtotal = db.Column(db.Numeric(12, 2), default=0)
    iva = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), default=0)
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


class Responsiva(db.Model):
    """Carta responsiva de custodia y renta de equipo medico.

    No es un comprobante mas: en el sistema anterior es un contrato firmado
    donde el receptor acepta cubrir el valor de reposicion del equipo si se
    dana o se pierde. Por eso se congela aqui el MOI del activo y el texto de
    los terminos vigentes al momento de firmar, en vez de leerlos del catalogo
    cuando se reimprima.
    """

    __tablename__ = "responsivas"

    id = db.Column(db.Integer, primary_key=True)
    folio = db.Column(db.String(30), unique=True, nullable=False, index=True)

    entrega_id = db.Column(
        db.Integer, db.ForeignKey("entregas.id"), nullable=False, index=True
    )
    entrega = db.relationship("Entrega", backref="responsivas")

    equipo_id = db.Column(
        db.Integer, db.ForeignKey("equipo_medico.id"), nullable=False, index=True
    )
    equipo = db.relationship("EquipoMedico")

    emitida_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    emitida_por = db.relationship("Usuario")

    fecha_emision = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Datos congelados al firmar
    empresa_propietaria = db.Column(db.String(20))
    valor_reposicion = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    responsable_custodia = db.Column(db.String(160))
    paciente_folio = db.Column(db.String(120))
    accesorios = db.Column(db.Text)
    checklist_salida = db.Column(db.Text)
    notas = db.Column(db.Text)

    pdf_path = db.Column(db.String(255))
    fecha_devolucion = db.Column(db.DateTime(timezone=True))

    @property
    def razon_social(self):
        datos = Empresa.DATOS.get(self.empresa_propietaria)
        return datos["razon_social"] if datos else ""

    @property
    def cerrada(self):
        return self.fecha_devolucion is not None

    def __repr__(self):
        return f"<Responsiva {self.folio} equipo={self.equipo_id}>"
