"""Comandos de terminal:  flask <comando>"""

import click
from flask.cli import with_appcontext

from app.constantes import EstadoEquipo, Rol
from app.extensions import db


def registrar(app):
    app.cli.add_command(crear_usuario)
    app.cli.add_command(sembrar_demo)


@click.command("crear-usuario")
@click.option("--nombre", prompt=True)
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--rol", type=click.Choice(Rol.TODOS), prompt=True)
@with_appcontext
def crear_usuario(nombre, email, password, rol):
    """Da de alta un usuario (el primer revisor_admin se crea con esto)."""
    from app.models import Usuario

    email = email.strip().lower()
    if Usuario.query.filter_by(email=email).first():
        raise click.ClickException(f"Ya existe un usuario con el correo {email}")

    usuario = Usuario(nombre=nombre, email=email, rol=rol)
    usuario.set_password(password)
    db.session.add(usuario)
    db.session.commit()
    click.echo(f"Usuario creado: {email} ({Rol.ETIQUETAS[rol]})")


@click.command("sembrar-demo")
@with_appcontext
def sembrar_demo():
    """Carga usuarios y catalogo de ejemplo para probar la app.

    NO usar en produccion: las contrasenas son publicas.
    """
    from app.models import EquipoMedico, Insumo, Usuario

    if Usuario.query.first():
        raise click.ClickException(
            "La base ya tiene usuarios. Este comando es solo para una base vacia."
        )

    usuarios = [
        ("Admin AVANT", "admin@avant.mx", Rol.REVISOR_ADMIN),
        ("Vendedor Demo", "vendedor@avant.mx", Rol.VENDEDOR),
        ("Tecnico Demo", "tecnico@avant.mx", Rol.TECNICO),
    ]
    for nombre, email, rol in usuarios:
        u = Usuario(nombre=nombre, email=email, rol=rol)
        u.set_password("avant123")
        db.session.add(u)

    equipos = [
        ("Bomba de infusion", "BRAUN", "Infusomat", "SN-10021", "EQ0000000001"),
        ("Monitor de signos vitales", "Mindray", "uMEC12", "SN-10022", "EQ0000000002"),
        ("Ventilador volumetrico", "Hamilton", "C1", "SN-10023", "EQ0000000003"),
    ]
    for nombre, marca, modelo, serie, codigo in equipos:
        db.session.add(
            EquipoMedico(
                nombre=nombre,
                marca=marca,
                modelo=modelo,
                numero_serie=serie,
                codigo_barras=codigo,
                estado=EstadoEquipo.DISPONIBLE,
            )
        )

    insumos = [
        ("Set de infusion estandar", "pieza", "IN0000000001", 250, 40),
        ("Jeringa 20 ml", "pieza", "IN0000000002", 800, 100),
        ("Electrodo ECG adulto", "paquete", "IN0000000003", 60, 20),
    ]
    for nombre, unidad, codigo, stock, minimo in insumos:
        db.session.add(
            Insumo(
                nombre=nombre,
                unidad_medida=unidad,
                codigo_barras=codigo,
                stock_actual=stock,
                stock_minimo=minimo,
            )
        )

    db.session.commit()
    click.echo("Datos de demostracion cargados. Contrasena de todos: avant123")
