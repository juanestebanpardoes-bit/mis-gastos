"""Capa de acceso a datos de Mis Gastos.

Este módulo solo se encarga de SQLite: crear el archivo, crear la tabla y
cargar algunos registros de ejemplo. No contiene reglas de negocio.
"""

import os
import sqlite3
from contextlib import contextmanager

# Ruta de la base de datos. Se puede cambiar con la variable de entorno
# MISGASTOS_DB (útil para las pruebas) o se cambia desde los propios tests.
RUTA_DB = os.environ.get("MISGASTOS_DB", "datos.db")

CATEGORIAS = ("comida", "transporte", "estudio", "ocio", "otros")

# Datos iniciales que se insertan solo cuando la tabla está vacía.
GASTOS_EJEMPLO = (
    ("Almuerzo del día", 12.50, "comida", "2026-11-20"),
    ("Billete de autobús", 8.75, "transporte", "2026-11-21"),
    ("Libro de programación", 30.00, "estudio", "2026-11-22"),
)


def conectar():
    """Devuelve una conexión a SQLite con filas convertidas en diccionarios."""
    conexion = sqlite3.connect(RUTA_DB)
    conexion.row_factory = sqlite3.Row
    return conexion


@contextmanager
def conexion_abierta():
    """Abre, confirma y cierra la conexión (importante en Windows)."""
    conexion = conectar()
    try:
        with conexion:
            yield conexion
    finally:
        conexion.close()


def iniciar_db():
    """Crea el archivo datos.db, la tabla gastos y los registros de ejemplo.

    Esta función se puede llamar las veces que se quiera: si la tabla ya
    existe no la borra y, si ya tiene datos, no vuelve a cargar ejemplos.
    """
    with conexion_abierta() as conexion:
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS gastos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                descripcion TEXT    NOT NULL,
                monto       REAL    NOT NULL CHECK (monto > 0),
                categoria   TEXT    NOT NULL CHECK (
                    categoria IN ('comida', 'transporte', 'estudio', 'ocio', 'otros')
                ),
                fecha       TEXT    NOT NULL
            )
            """
        )
        cantidad = conexion.execute("SELECT COUNT(*) FROM gastos").fetchone()[0]
        if cantidad == 0:
            conexion.executemany(
                """
                INSERT INTO gastos (descripcion, monto, categoria, fecha)
                VALUES (?, ?, ?, ?)
                """,
                GASTOS_EJEMPLO,
            )
    return RUTA_DB
