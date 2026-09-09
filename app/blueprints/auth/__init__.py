from flask import Blueprint

bp = Blueprint("auth", __name__)

from app.blueprints.auth import rutas  # noqa: E402,F401
