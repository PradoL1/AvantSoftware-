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

    TODOS = (
        ALTA, APARTADO, LIBERADO, SALIDA, ENTREGADO, REGRESO_ALMACEN,
        CONSUMIDO, AJUSTE_STOCK, A_MANTENIMIENTO, DE_MANTENIMIENTO,
    )

    ETIQUETAS = {
        ALTA: "Alta",
        APARTADO: "Apartado",
        LIBERADO: "Liberado",
        SALIDA: "Salida de almacen",
        ENTREGADO: "Entregado",
        REGRESO_ALMACEN: "Regreso a almacen",
        CONSUMIDO: "Consumido",
        AJUSTE_STOCK: "Ajuste",
        A_MANTENIMIENTO: "A mantenimiento",
        DE_MANTENIMIENTO: "De mantenimiento",
    }

    COLORES = {
        ALTA: "success",
        APARTADO: "warning",
        LIBERADO: "info",
        SALIDA: "primary",
        ENTREGADO: "primary",
        REGRESO_ALMACEN: "success",
        CONSUMIDO: "danger",
        AJUSTE_STOCK: "secondary",
        A_MANTENIMIENTO: "danger",
        DE_MANTENIMIENTO: "success",
    }

    # Movimientos que sacan piezas del almacen. Sirve para pintar el signo.
    RESTAN = (CONSUMIDO,)
    SUMAN = (ALTA, REGRESO_ALMACEN)


# --- Lo que salio de revisar el sistema anterior (_diseno_anterior/) ---------


class Empresa:
    """Las dos razones sociales que factura AVANT.

    La regla vive en el sistema anterior dentro de la plantilla de la remision:
    si el hospital es del Grupo Angeles factura una empresa, si no, la otra.
    Aqui queda en un solo lugar porque decide razon social, RFC y lista de
    precios.
    """

    SOLUCIONES = "soluciones"
    GARDE = "garde"

    TODOS = (SOLUCIONES, GARDE)

    DATOS = {
        SOLUCIONES: {
            "razon_social": "AVANT SOLUCIONES MEDICAS",
            "rfc": "MPB210816298",
        },
        GARDE: {
            "razon_social": "AVANT GARDE MEDIC SERVICE",
            "rfc": "AGM210811HD9",
        },
    }

    DIRECCION = (
        "Calle 3 24, San Pedro de los Pinos, Benito Juarez, 03800, "
        "Ciudad de Mexico, CDMX"
    )
    TELEFONOS = ("55 4503 9502", "55 35 72 87 84")
    CORREO = "medicallfacturacion@gmail.com"

    @classmethod
    def para_hospital(cls, hospital):
        """Grupo Angeles -> AVANT SOLUCIONES MEDICAS; el resto -> AVANT GARDE."""
        nombre = (hospital or "").upper()
        es_angeles = "ANGELES" in nombre or "ÁNGELES" in nombre
        return cls.SOLUCIONES if es_angeles else cls.GARDE

    @classmethod
    def datos_para_hospital(cls, hospital):
        return cls.DATOS[cls.para_hospital(hospital)]


class Especialidad:
    """Lista cerrada tomada del formulario de captura anterior."""

    TODAS = (
        "Otorrinolaringologia",
        "Laparoscopia",
        "Ginecologia",
        "Urologia",
        "Cirugia General",
        "Otra",
    )


class VerificadoCon:
    TODOS = ("Doctor", "Asistente", "Enfermera")


class TipoPaciente:
    PARTICULAR = "Particular"
    SEGURO = "Seguro"

    TODOS = (PARTICULAR, SEGURO)


class MetodoPago:
    """Solo aplica cuando el paciente es particular."""

    EFECTIVO = "Efectivo"
    TRANSFERENCIA = "Transferencia"

    TODOS = (EFECTIVO, TRANSFERENCIA)


class TipoRemision:
    """El sistema anterior emite dos remisiones por nota: insumos y equipos."""

    INSUMOS = "insumos"
    EQUIPOS = "equipos"

    TODOS = (INSUMOS, EQUIPOS)
    ETIQUETAS = {INSUMOS: "Insumos", EQUIPOS: "Equipos"}


class Checklist:
    """Contenido real del checklist de salida de equipo."""

    ACCESORIOS = (
        "Cable de Poder",
        "Pedal Doble/Sencillo",
        "Fibra Optica",
        "Fuente de Luz",
        "Maletin Rigido",
        "Pieza de Mano/Camisa",
    )

    INSPECCION = (
        "Chasis Limpio/Intacto",
        "Opticas Sin Rayaduras",
        "Conectores Integros",
        "Prueba de Encendido OK",
    )

    ETAPA_ALMACEN = "almacen"
    ETAPA_HOSPITAL = "hospital"
    ETAPAS = (ETAPA_ALMACEN, ETAPA_HOSPITAL)


# IVA vigente. En el sistema anterior estaba escrito a mano en el JavaScript
# de la remision; aqui es un solo valor configurable.
IVA = 0.16
