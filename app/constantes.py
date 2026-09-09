"""Valores fijos del dominio (roles, estados, tipos de movimiento).

Se guardan como texto en la BD en lugar de ENUM nativo de PostgreSQL: agregar
un valor nuevo no obliga a una migracion de tipo.
"""


class Rol:
    VENDEDOR = "vendedor"
    REVISOR_ADMIN = "revisor_admin"
    TECNICO = "tecnico"

    TODOS = (VENDEDOR, REVISOR_ADMIN, TECNICO)
    ETIQUETAS = {
        VENDEDOR: "Vendedor",
        REVISOR_ADMIN: "Revisor-Administrativo",
        TECNICO: "Tecnico",
    }


class EstadoNota:
    PENDIENTE_REVISION = "pendiente_revision"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    REMISION_GENERADA = "remision_generada"
    EN_LOGISTICA = "en_logistica"
    ENTREGADA = "entregada"
    CERRADA = "cerrada"
    CANCELADA = "cancelada"

    TODOS = (
        PENDIENTE_REVISION,
        APROBADA,
        RECHAZADA,
        REMISION_GENERADA,
        EN_LOGISTICA,
        ENTREGADA,
        CERRADA,
        CANCELADA,
    )

    ETIQUETAS = {
        PENDIENTE_REVISION: "Pendiente de revision",
        APROBADA: "Aprobada",
        RECHAZADA: "Rechazada",
        REMISION_GENERADA: "Remision generada",
        EN_LOGISTICA: "En logistica",
        ENTREGADA: "Entregada",
        CERRADA: "Cerrada",
        CANCELADA: "Cancelada",
    }

    # Color de badge Bootstrap por estado.
    COLORES = {
        PENDIENTE_REVISION: "warning",
        APROBADA: "info",
        RECHAZADA: "danger",
        REMISION_GENERADA: "primary",
        EN_LOGISTICA: "primary",
        ENTREGADA: "success",
        CERRADA: "secondary",
        CANCELADA: "dark",
    }

    # Transiciones permitidas. Cualquier cambio de estado se valida contra esto.
    TRANSICIONES = {
        PENDIENTE_REVISION: (APROBADA, RECHAZADA, CANCELADA),
        APROBADA: (REMISION_GENERADA, CANCELADA),
        RECHAZADA: (),
        REMISION_GENERADA: (EN_LOGISTICA, CANCELADA),
        EN_LOGISTICA: (ENTREGADA,),
        ENTREGADA: (CERRADA,),
        CERRADA: (),
        CANCELADA: (),
    }

    @classmethod
    def puede_pasar_a(cls, actual, nuevo):
        return nuevo in cls.TRANSICIONES.get(actual, ())


class EstadoEquipo:
    DISPONIBLE = "disponible"
    APARTADO = "apartado"          # comprometido en una nota aprobada
    RENTADO = "rentado"            # entregado en el hospital
    MANTENIMIENTO = "mantenimiento"
    BAJA = "baja"

    TODOS = (DISPONIBLE, APARTADO, RENTADO, MANTENIMIENTO, BAJA)
    ETIQUETAS = {
        DISPONIBLE: "Disponible",
        APARTADO: "Apartado",
        RENTADO: "Rentado",
        MANTENIMIENTO: "En mantenimiento",
        BAJA: "Baja",
    }
    COLORES = {
        DISPONIBLE: "success",
        APARTADO: "warning",
        RENTADO: "primary",
        MANTENIMIENTO: "danger",
        BAJA: "dark",
    }


class TipoItem:
    EQUIPO = "equipo"
    INSUMO = "insumo"

    TODOS = (EQUIPO, INSUMO)
    ETIQUETAS = {EQUIPO: "Equipo medico", INSUMO: "Insumo"}


class Movimiento:
    """Eventos que se escriben en historial_movimientos (trazabilidad)."""

    ALTA = "alta"
    APARTADO = "apartado"
    LIBERADO = "liberado"            # se cancelo/rechazo la nota
    SALIDA = "salida"                # salio del almacen con el tecnico
    ENTREGADO = "entregado"
    REGRESO_ALMACEN = "regreso_almacen"
    CONSUMIDO = "consumido"          # insumos descontados al cerrar
    AJUSTE_STOCK = "ajuste_stock"
    A_MANTENIMIENTO = "a_mantenimiento"
    DE_MANTENIMIENTO = "de_mantenimiento"
