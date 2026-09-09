"""Humo: levanta la app sobre SQLite en memoria, siembra datos y pide cada
pantalla con cada rol para confirmar que las plantillas renderizan."""

import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "smoke-test"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.constantes import Rol  # noqa: E402
from app.extensions import db  # noqa: E402

app = create_app("development")
# El cliente de prueba no manda token CSRF; se desactiva solo aqui.
app.config["WTF_CSRF_ENABLED"] = False
fallos = []

with app.app_context():
    db.create_all()

    from app.models import Almacen, EquipoMedico, Existencia, Insumo, Usuario

    for nombre, email, rol in [
        ("Admin", "admin@avant.mx", Rol.REVISOR_ADMIN),
        ("Vende", "vendedor@avant.mx", Rol.VENDEDOR),
        ("Tec", "tecnico@avant.mx", Rol.TECNICO),
    ]:
        u = Usuario(nombre=nombre, email=email, rol=rol)
        u.set_password("avant123")
        db.session.add(u)

    central = Almacen(nombre="Central")
    db.session.add(central)
    db.session.flush()

    db.session.add(
        EquipoMedico(nombre="Torre laparoscopia", codigo_barras="EQ1",
                     numero_serie="S1", moi=320000, almacen=central)
    )
    ins = Insumo(nombre="Jeringa 20ml", codigo_barras="IN1", stock_minimo=10)
    ins.existencias.append(Existencia(almacen=central, cantidad=5))
    db.session.add(ins)
    db.session.commit()

RUTAS = {
    Rol.REVISOR_ADMIN: ["/", "/notas/", "/revision/", "/catalogo/equipo",
                        "/catalogo/insumos", "/logistica/", "/catalogo/api/codigo?codigo=EQ1"],
    Rol.VENDEDOR: ["/", "/notas/", "/catalogo/equipo", "/catalogo/insumos"],
    Rol.TECNICO: ["/", "/logistica/", "/catalogo/insumos"],
}

CORREOS = {
    Rol.REVISOR_ADMIN: "admin@avant.mx",
    Rol.VENDEDOR: "vendedor@avant.mx",
    Rol.TECNICO: "tecnico@avant.mx",
}


def revisar(cliente, ruta, etiqueta, esperado=200):
    try:
        r = cliente.get(ruta, follow_redirects=False)
    except Exception as e:  # noqa: BLE001
        fallos.append(f"{etiqueta} {ruta} -> EXCEPCION {type(e).__name__}: {e}")
        return
    if r.status_code != esperado:
        fallos.append(f"{etiqueta} {ruta} -> {r.status_code} (esperado {esperado})")
    else:
        print(f"  ok  {r.status_code}  {ruta}")


with app.test_client() as c:
    print("Sin sesion:")
    revisar(c, "/auth/login", "anon")
    revisar(c, "/", "anon", esperado=302)
    revisar(c, "/no-existe", "anon", esperado=404)

for rol, rutas in RUTAS.items():
    print(f"\nRol {rol}:")
    with app.test_client() as c:
        r = c.post(
            "/auth/login",
            data={"email": CORREOS[rol], "password": "avant123"},
            follow_redirects=True,
        )
        if r.status_code != 200 or b"Panel" not in r.data:
            fallos.append(f"{rol}: login fallo ({r.status_code})")
            continue
        for ruta in rutas:
            revisar(c, ruta, rol)

        # El vendedor no debe poder entrar a revision.
        if rol == Rol.VENDEDOR:
            revisar(c, "/revision/", rol, esperado=403)

print("\n" + "=" * 50)
if fallos:
    print(f"{len(fallos)} FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo paso.")
