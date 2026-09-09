"""Alta y edicion de equipo, insumos y usuarios."""

import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.constantes import Empresa, EstadoEquipo, Movimiento, Rol  # noqa: E402
from app.extensions import db  # noqa: E402

app = create_app("development")
app.config["WTF_CSRF_ENABLED"] = False
fallos = []


def check(etiqueta, obtenido, esperado):
    if obtenido != esperado:
        fallos.append(f"{etiqueta}: obtuvo {obtenido!r}, esperaba {esperado!r}")
    else:
        print(f"  ok  {etiqueta} = {obtenido!r}")


with app.app_context():
    db.create_all()
    from app.models import Almacen, Usuario

    admin = Usuario(nombre="Admin", email="a@a.mx", rol=Rol.REVISOR_ADMIN)
    admin.set_password("avant123")
    vend = Usuario(nombre="Vende", email="v@a.mx", rol=Rol.VENDEDOR)
    vend.set_password("avant123")
    db.session.add_all([admin, vend])

    central = Almacen(nombre="Central")
    resteril = Almacen(nombre="Resteril")
    db.session.add_all([central, resteril])
    db.session.commit()
    central_id, resteril_id, admin_id = central.id, resteril.id, admin.id

print("Sugerencia de codigo de barras:")
with app.app_context():
    from app.servicios.catalogo import sugerir_codigo
    # Como en el sistema anterior: TOLA1 para "Torre de Laparoscopia".
    check("dos palabras", sugerir_codigo("Torre de Laparoscopia"), "TOLA1")
    check("una palabra", sugerir_codigo("Bisturi"), "BIST1")
    check("ignora palabras de enlace",
          sugerir_codigo("Set de infusion"), "SEIN1")

print("\nAlta de equipo:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "a@a.mx", "password": "avant123"},
           follow_redirects=True)

    r = c.get("/catalogo/equipo/nuevo")
    check("GET alta", r.status_code, 200)

    r = c.post("/catalogo/equipo/nuevo", data={
        "nombre": "Torre de Laparoscopia", "tipo_equipo": "Laparoscopia",
        "marca": "Karl Storz", "modelo": "Image1", "numero_serie": "SN-1",
        "codigo_barras": "TOLA1", "empresa_propietaria": Empresa.GARDE,
        "moi": "320000", "almacen_id": central_id, "activo": "y",
    }, follow_redirects=True)
    check("POST alta", r.status_code, 200)

    with app.app_context():
        from app.models import EquipoMedico
        eq = EquipoMedico.query.first()
        check("se guardo", eq.nombre, "Torre de Laparoscopia")
        check("estado inicial", eq.estado, EstadoEquipo.DISPONIBLE)
        check("valor de reposicion", float(eq.moi), 320000.0)
        check("ubicacion tomada del almacen", eq.ubicacion_actual, "Central")
        eq_id = eq.id

    # El codigo de barras es unico entre equipos e insumos.
    r = c.post("/catalogo/equipo/nuevo", data={
        "nombre": "Otra torre", "codigo_barras": "TOLA1",
        "empresa_propietaria": Empresa.GARDE, "almacen_id": central_id,
        "activo": "y",
    }, follow_redirects=True)
    check("codigo repetido se rechaza",
          "ya lo usa" in r.get_data(as_text=True), True)

    r = c.post("/catalogo/equipo/nuevo", data={
        "nombre": "Otra torre", "codigo_barras": "TOLA2", "numero_serie": "SN-1",
        "empresa_propietaria": Empresa.GARDE, "almacen_id": central_id,
        "activo": "y",
    }, follow_redirects=True)
    check("numero de serie repetido se rechaza",
          "numero de serie ya esta registrado" in r.get_data(as_text=True), True)

    print("\nEdicion de equipo:")
    r = c.post(f"/catalogo/equipo/{eq_id}", data={
        "nombre": "Torre de Laparoscopia HD", "tipo_equipo": "Laparoscopia",
        "marca": "Karl Storz", "modelo": "Image1 Rubina", "numero_serie": "SN-1",
        "codigo_barras": "TOLA1", "empresa_propietaria": Empresa.SOLUCIONES,
        "moi": "487500", "almacen_id": central_id, "activo": "y",
    }, follow_redirects=True)
    with app.app_context():
        from app.models import EquipoMedico
        eq = db.session.get(EquipoMedico, eq_id)
        check("nombre actualizado", eq.nombre, "Torre de Laparoscopia HD")
        check("empresa actualizada", eq.empresa_propietaria, Empresa.SOLUCIONES)
        check("conserva su codigo", eq.codigo_barras, "TOLA1")

print("\nAlta de insumo con existencias:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "a@a.mx", "password": "avant123"},
           follow_redirects=True)

    r = c.post("/catalogo/insumos/nuevo", data={
        "nombre": "Jeringa 20 ml", "sku": "JER-020", "unidad_medida": "pieza",
        "codigo_barras": "IN0002", "costo_unitario": "14.50",
        "stock_minimo": "100", "proveedor": "Distribuidora X", "activo": "y",
        f"existencia_{central_id}": "600",
        f"existencia_{resteril_id}": "200",
    }, follow_redirects=True)
    check("POST alta", r.status_code, 200)

    with app.app_context():
        from app.models import HistorialMovimiento, Insumo
        ins = Insumo.query.first()
        check("se guardo", ins.nombre, "Jeringa 20 ml")
        check("costo", float(ins.costo_unitario), 14.5)
        check("existencia total", ins.stock_actual, 800)
        check("en Central", ins.existencia_en(central_id).cantidad, 600)
        check("en Resteril", ins.existencia_en(resteril_id).cantidad, 200)

        # El alta inicial tambien queda en el kardex.
        ajustes = HistorialMovimiento.query.filter_by(
            movimiento=Movimiento.AJUSTE_STOCK).all()
        check("dos movimientos de ajuste", len(ajustes), 2)
        central_mov = [a for a in ajustes if a.almacen_origen_id == central_id][0]
        check("saldo anterior", central_mov.saldo_anterior, 0)
        check("saldo nuevo", central_mov.saldo_nuevo, 600)
        check("valuado al costo", float(central_mov.importe), 8700.0)
        ins_id = ins.id

    print("\nAjuste de existencias:")
    r = c.post(f"/catalogo/insumos/{ins_id}", data={
        "nombre": "Jeringa 20 ml", "sku": "JER-020", "unidad_medida": "pieza",
        "codigo_barras": "IN0002", "costo_unitario": "14.50",
        "stock_minimo": "100", "activo": "y",
        f"existencia_{central_id}": "580",   # conteo fisico: faltaron 20
        f"existencia_{resteril_id}": "200",
    }, follow_redirects=True)

    with app.app_context():
        from app.models import HistorialMovimiento, Insumo
        ins = db.session.get(Insumo, ins_id)
        check("existencia corregida", ins.existencia_en(central_id).cantidad, 580)
        check("el otro almacen no se movio",
              ins.existencia_en(resteril_id).cantidad, 200)
        ajustes = HistorialMovimiento.query.filter_by(
            movimiento=Movimiento.AJUSTE_STOCK).all()
        check("solo se registra lo que cambio", len(ajustes), 3)
        ultimo = ajustes[-1]
        check("saldo anterior", ultimo.saldo_anterior, 600)
        check("saldo nuevo", ultimo.saldo_nuevo, 580)
        check("cantidad del ajuste", ultimo.cantidad, 20)

    # No se puede dejar el saldo por debajo de lo apartado.
    with app.app_context():
        from app.models import Insumo
        ins = db.session.get(Insumo, ins_id)
        ins.existencia_en(central_id).apartado = 100
        db.session.commit()

    r = c.post(f"/catalogo/insumos/{ins_id}", data={
        "nombre": "Jeringa 20 ml", "unidad_medida": "pieza",
        "codigo_barras": "IN0002", "stock_minimo": "100", "activo": "y",
        f"existencia_{central_id}": "50",
    }, follow_redirects=True)
    check("no se puede bajar de lo apartado",
          "apartadas en notas aprobadas" in r.get_data(as_text=True), True)
    with app.app_context():
        from app.models import Insumo
        check("y la existencia no cambio",
              db.session.get(Insumo, ins_id).existencia_en(central_id).cantidad,
              580)

print("\nUsuarios:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "a@a.mx", "password": "avant123"},
           follow_redirects=True)

    r = c.get("/auth/usuarios")
    check("GET listado", r.status_code, 200)

    r = c.post("/auth/usuarios/nuevo", data={
        "nombre": "Tecnico Nuevo", "email": "Tecnico@AVANT.MX",
        "rol": Rol.TECNICO, "password": "clave-larga-1", "activo": "y",
    }, follow_redirects=True)
    check("POST alta", r.status_code, 200)

    with app.app_context():
        from app.models import Usuario
        nuevo = Usuario.query.filter_by(nombre="Tecnico Nuevo").first()
        check("correo normalizado a minusculas", nuevo.email, "tecnico@avant.mx")
        check("puede entrar", nuevo.check_password("clave-larga-1"), True)
        nuevo_id = nuevo.id

    r = c.post("/auth/usuarios/nuevo", data={
        "nombre": "Repetido", "email": "tecnico@avant.mx", "rol": Rol.TECNICO,
        "password": "clave-larga-2", "activo": "y",
    }, follow_redirects=True)
    check("correo duplicado se rechaza",
          "Ya hay un usuario con el correo" in r.get_data(as_text=True), True)

    r = c.post("/auth/usuarios/nuevo", data={
        "nombre": "Sin clave", "email": "otro@avant.mx", "rol": Rol.TECNICO,
        "activo": "y",
    }, follow_redirects=True)
    check("usuario nuevo sin contrasena se rechaza",
          "necesita contrasena" in r.get_data(as_text=True), True)

    # Editar sin tocar la contrasena la conserva.
    r = c.post(f"/auth/usuarios/{nuevo_id}", data={
        "nombre": "Tecnico Renombrado", "email": "tecnico@avant.mx",
        "rol": Rol.TECNICO, "password": "", "activo": "y",
    }, follow_redirects=True)
    with app.app_context():
        from app.models import Usuario
        u = db.session.get(Usuario, nuevo_id)
        check("nombre actualizado", u.nombre, "Tecnico Renombrado")
        check("contrasena intacta", u.check_password("clave-larga-1"), True)

    print("\nNadie se puede dejar fuera a si mismo:")
    r = c.post(f"/auth/usuarios/{admin_id}", data={
        "nombre": "Admin", "email": "a@a.mx", "rol": Rol.VENDEDOR,
        "password": "", "activo": "y",
    }, follow_redirects=True)
    check("no puede cambiarse el rol",
          "No puedes quitarte a ti mismo" in r.get_data(as_text=True), True)

    r = c.post(f"/auth/usuarios/{admin_id}", data={
        "nombre": "Admin", "email": "a@a.mx", "rol": Rol.REVISOR_ADMIN,
        "password": "",
    }, follow_redirects=True)
    check("ni desactivarse",
          "No puedes quitarte a ti mismo" in r.get_data(as_text=True), True)

    with app.app_context():
        from app.models import Usuario
        yo = db.session.get(Usuario, admin_id)
        check("sigue siendo administrador", yo.rol, Rol.REVISOR_ADMIN)
        check("y sigue activo", yo.activo, True)

print("\nUn vendedor no administra nada:")
with app.test_client() as c:
    c.post("/auth/login", data={"email": "v@a.mx", "password": "avant123"},
           follow_redirects=True)
    for ruta in ("/auth/usuarios", "/catalogo/equipo/nuevo",
                 "/catalogo/insumos/nuevo", "/catalogo/tarifas"):
        check(f"403 en {ruta}", c.get(ruta).status_code, 403)

print("\n" + "=" * 50)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo paso.")
