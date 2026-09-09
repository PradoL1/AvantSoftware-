"""Comandos de terminal:  flask <comando>"""

from datetime import date

import click
from flask.cli import with_appcontext

from app.constantes import Empresa, EstadoEquipo, Rol
from app.extensions import db


def registrar(app):
    app.cli.add_command(crear_usuario)
    app.cli.add_command(sembrar_almacenes)
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


@click.command("sembrar-almacenes")
@with_appcontext
def sembrar_almacenes():
    """Crea los cuatro almacenes del sistema anterior si faltan.

    Sirve tambien en produccion: no borra nada y se puede correr de nuevo.
    """
    from app.models import Almacen

    creados = 0
    for nombre in Almacen.INICIALES:
        if not Almacen.query.filter_by(nombre=nombre).first():
            db.session.add(Almacen(nombre=nombre))
            creados += 1

    db.session.commit()
    click.echo(f"Almacenes creados: {creados} (ya existian {len(Almacen.INICIALES) - creados})")


@click.command("sembrar-demo")
@with_appcontext
def sembrar_demo():
    """Carga usuarios, almacenes y catalogo de ejemplo para probar la app.

    NO usar en produccion: las contrasenas son publicas.
    """
    from app.models import (Almacen, EquipoMedico, Existencia, Hospital,
                            Insumo, TarifaEquipo, Usuario)

    if Usuario.query.first():
        raise click.ClickException(
            "La base ya tiene usuarios. Este comando es solo para una base vacia."
        )

    for nombre, email, rol in [
        ("Admin AVANT", "admin@avant.mx", Rol.REVISOR_ADMIN),
        ("Vendedor Demo", "vendedor@avant.mx", Rol.VENDEDOR),
        ("Tecnico Demo", "tecnico@avant.mx", Rol.TECNICO),
    ]:
        u = Usuario(nombre=nombre, email=email, rol=rol)
        u.set_password("avant123")
        db.session.add(u)

    almacenes = {}
    for nombre in Almacen.INICIALES:
        a = Almacen.query.filter_by(nombre=nombre).first() or Almacen(nombre=nombre)
        db.session.add(a)
        almacenes[nombre] = a
    db.session.flush()

    central = almacenes["Central"]
    resteril = almacenes["Resteril"]

    equipos = [
        ("Torre de Laparoscopia", "Laparoscopia", "Karl Storz", "Image1", "SN-10021",
         "TOLA1", Empresa.GARDE, 320000),
        ("Energia Bipolar", "Electrocirugia", "Erbe", "VIO 300D", "SN-10022",
         "ENBO1", Empresa.SOLUCIONES, 185000),
        ("Monitor de Signos Vitales", "Monitoreo", "Mindray", "uMEC12", "SN-10023",
         "MOSV1", Empresa.GARDE, 74000),
    ]
    for nombre, tipo, marca, modelo, serie, codigo, empresa, moi in equipos:
        db.session.add(
            EquipoMedico(
                nombre=nombre,
                tipo_equipo=tipo,
                marca=marca,
                modelo=modelo,
                numero_serie=serie,
                codigo_barras=codigo,
                empresa_propietaria=empresa,
                moi=moi,
                almacen=central,
                estado=EstadoEquipo.DISPONIBLE,
            )
        )

    # Sin precio: los insumos se negocian en cada venta y el precio lo captura
    # el revisor. Aqui solo el costo, que es lo que valua el kardex.
    insumos = [
        ("Set de infusion estandar", "SET-001", "pieza", "IN0001", 40, 210, 180, 70),
        ("Jeringa 20 ml", "JER-020", "pieza", "IN0002", 100, 14, 600, 200),
        ("Electrodo ECG adulto", "ECG-ADU", "paquete", "IN0003", 20, 120, 12, 4),
    ]
    for (nombre, sku, unidad, codigo, minimo, costo,
         en_central, en_resteril) in insumos:
        insumo = Insumo(
            nombre=nombre,
            sku=sku,
            unidad_medida=unidad,
            codigo_barras=codigo,
            stock_minimo=minimo,
            costo_unitario=costo,
        )
        insumo.existencias.append(Existencia(almacen=central, cantidad=en_central))
        insumo.existencias.append(Existencia(almacen=resteril, cantidad=en_resteril))
        db.session.add(insumo)

    # Uno de cada razon social, para poder ver que la remision cambia de RFC.
    hospitales = [
        ("Hospital Angeles Pedregal", Empresa.SOLUCIONES, "Ciudad de Mexico"),
        ("Bite Medica", Empresa.GARDE, "Ciudad de Mexico"),
    ]
    creados = {}
    for nombre, empresa, ciudad in hospitales:
        h = Hospital(nombre=nombre, empresa=empresa, ciudad=ciudad)
        db.session.add(h)
        creados[nombre] = h
    db.session.flush()

    # La renta del mismo equipo cuesta distinto en cada hospital.
    tarifas = [
        ("TOLA1", "Hospital Angeles Pedregal", 8500),
        ("TOLA1", "Bite Medica", 7200),
        ("ENBO1", "Hospital Angeles Pedregal", 4300),
        ("ENBO1", "Bite Medica", 3900),
    ]
    for codigo, hospital, precio in tarifas:
        equipo = EquipoMedico.query.filter_by(codigo_barras=codigo).first()
        if equipo:
            db.session.add(TarifaEquipo(
                equipo_id=equipo.id,
                hospital_id=creados[hospital].id,
                precio_renta=precio,
                vigente_desde=date.today(),
            ))

    db.session.commit()
    click.echo("Datos de demostracion cargados. Contrasena de todos: avant123")
