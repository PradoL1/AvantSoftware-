"""Configuracion de la aplicacion, leida desde variables de entorno (.env)."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-inseguro-cambiar")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'avant.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Supabase cierra conexiones ociosas; reciclar evita errores "server closed
    # the connection unexpectedly" tras periodos de inactividad.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    # Negocio
    FOLIO_PREFIJO = os.environ.get("FOLIO_PREFIJO", "AVS")
    PDF_REMISIONES_DIR = BASE_DIR / "app" / "static" / "pdf" / "remisiones"

    # Sesion
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


config_por_nombre = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
