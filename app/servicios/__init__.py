"""Capa de servicios.

Las operaciones que tocan varias tablas a la vez (crear una nota, aprobarla,
apartar stock, cerrar una entrega) viven aqui y no en las vistas, para que cada
una sea una sola transaccion y se pueda probar sin HTTP.
"""
