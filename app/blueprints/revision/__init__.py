from flask import Blueprint

bp = Blueprint("revision", __name__)

from app.blueprints.revision import rutas  # noqa: E402,F401
