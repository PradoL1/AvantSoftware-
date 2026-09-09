"""Instancias de las extensiones.

Viven en su propio modulo para que los modelos puedan importar `db` sin crear
un import circular con la fabrica de aplicacion (`app/__init__.py`).
"""

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = "Inicia sesion para continuar."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def cargar_usuario(user_id):
    from app.models import Usuario

    return db.session.get(Usuario, int(user_id))
