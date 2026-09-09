from flask import Blueprint

bp = Blueprint("reportes", __name__)

from app.blueprints.reportes import rutas  # noqa: E402,F401
