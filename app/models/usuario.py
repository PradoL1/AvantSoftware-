from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.constantes import Rol
from app.extensions import db


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    fecha_creacion = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Flask-Login consulta is_active para bloquear el login de usuarios dados
    # de baja sin borrarlos (se conserva su historial).
    @property
    def is_active(self):
        return self.activo

    @property
    def es_vendedor(self):
        return self.rol == Rol.VENDEDOR

    @property
    def es_revisor(self):
        return self.rol == Rol.REVISOR_ADMIN

    @property
    def es_tecnico(self):
        return self.rol == Rol.TECNICO

    @property
    def rol_etiqueta(self):
        return Rol.ETIQUETAS.get(self.rol, self.rol)

    def __repr__(self):
        return f"<Usuario {self.email} ({self.rol})>"
