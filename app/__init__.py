"""Fabrica de la aplicacion Flask.

Patron application factory: nada se crea a nivel de modulo, asi se pueden
levantar varias instancias (tests, scripts, produccion) con configuraciones
distintas.
"""

from flask import Flask, render_template

from app.constantes import (EstadoEquipo, EstadoNota, Movimiento, Rol,
                            TipoItem, TipoRemision)
from app.extensions import csrf, db, login_manager, migrate
from config import config_por_nombre


def create_app(nombre_config="default"):
    app = Flask(__name__)
    app.config.from_object(
        config_por_nombre.get(nombre_config, config_por_nombre["default"])
    )

    _registrar_extensiones(app)
    _registrar_blueprints(app)
    _registrar_errores(app)
    _registrar_contexto_plantillas(app)

    from app import cli

    cli.registrar(app)

    # Carpeta donde se guardan los PDF de remisiones.
    app.config["PDF_REMISIONES_DIR"].mkdir(parents=True, exist_ok=True)

    return app


def _registrar_extensiones(app):
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Importar los modelos antes de Migrate para que autogenerate los vea.
    from app import models  # noqa: F401

    migrate.init_app(app, db)


def _registrar_blueprints(app):
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.catalogo import bp as catalogo_bp
    from app.blueprints.logistica import bp as logistica_bp
    from app.blueprints.main import bp as main_bp
    from app.blueprints.notas import bp as notas_bp
    from app.blueprints.reportes import bp as reportes_bp
    from app.blueprints.revision import bp as revision_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(notas_bp, url_prefix="/notas")
    app.register_blueprint(revision_bp, url_prefix="/revision")
    app.register_blueprint(catalogo_bp, url_prefix="/catalogo")
    app.register_blueprint(logistica_bp, url_prefix="/logistica")
    app.register_blueprint(reportes_bp, url_prefix="/reportes")


def _registrar_errores(app):
    @app.errorhandler(403)
    def prohibido(e):
        return render_template("errores/403.html"), 403

    @app.errorhandler(404)
    def no_encontrado(e):
        return render_template("errores/404.html"), 404

    @app.errorhandler(500)
    def error_interno(e):
        db.session.rollback()
        return render_template("errores/500.html"), 500


def _registrar_contexto_plantillas(app):
    """Deja las constantes del dominio disponibles en todas las plantillas.

    Se registran como globals de Jinja y no con un context_processor: un macro
    importado con {% from "_macros.html" import ... %} no recibe el contexto de
    la plantilla que lo llama, pero los globals si los ve.
    """
    app.jinja_env.globals.update(
        Rol=Rol,
        EstadoNota=EstadoNota,
        EstadoEquipo=EstadoEquipo,
        TipoItem=TipoItem,
        TipoRemision=TipoRemision,
        Movimiento=Movimiento,
    )
