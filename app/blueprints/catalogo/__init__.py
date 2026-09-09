from flask import Blueprint

bp = Blueprint("catalogo", __name__)

from app.blueprints.catalogo import rutas  # noqa: E402,F401
