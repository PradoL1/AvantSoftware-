"""Modelos de datos.

Se importan todos aqui para que Flask-Migrate los detecte al autogenerar las
migraciones (basta con importar app.models).
"""

from app.models.almacen import Almacen, Existencia
from app.models.catalogo import EquipoMedico, Insumo
from app.models.historial import HistorialMovimiento
from app.models.logistica import ChecklistItem, Entrega, Remision, Responsiva
from app.models.nota_venta import DetalleNotaVenta, NotaVenta
from app.models.usuario import Usuario

__all__ = [
    "Usuario",
    "Almacen",
    "Existencia",
    "EquipoMedico",
    "Insumo",
    "NotaVenta",
    "DetalleNotaVenta",
    "Remision",
    "Entrega",
    "ChecklistItem",
    "Responsiva",
    "HistorialMovimiento",
]
