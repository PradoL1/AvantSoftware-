from flask import Blueprint

bp = Blueprint("logistica", __name__)

from app.blueprints.logistica import rutas  # noqa: E402,F401
