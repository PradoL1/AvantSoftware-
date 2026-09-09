from flask import Blueprint

bp = Blueprint("notas", __name__)

from app.blueprints.notas import rutas  # noqa: E402,F401
