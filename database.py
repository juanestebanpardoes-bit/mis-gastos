"""Capa de acceso a datos de Mis Gastos.

Este módulo solo se encarga de SQLite: crear el archivo, crear las tablas y
cargar algunos registros de ejemplo. No contiene reglas de negocio.
"""

import os
import sqlite3
from contextlib import contextmanager

# Ruta de la base de datos. Se puede cambiar con la variable de entorno
# MISGASTOS_DB (útil para las pruebas) o se cambia desde los propios tests.
RUTA_DB = os.environ.get("MISGASTOS_DB", "datos.db")

CATEGORIAS = ("comida", "transporte", "estudio", "ocio", "otros")

# Datos iniciales que se insertan solo cuando la tabla del usuario está vacía.
GASTOS_EJEMPLO = (
    ("Almuerzo del día", 12500, "comida", "2026-11-20"),
    ("Billete de autobús", 8750, "transporte", "2026-11-21"),
    ("Libro de programación", 30000, "estudio", "2026-11-22"),
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
    """Crea las tablas de usuarios y gastos, y migra datos anteriores.

    Se puede llamar las veces que se quiera: no borra lo que ya exista.
    """
    with conexion_abierta() as conexion:
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                contrasena    TEXT    NOT NULL,
                sal           TEXT    NOT NULL,
                fecha_creacion TEXT   NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conexion.execute(
            """
            CREATE TABLE IF NOT EXISTS gastos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
                descripcion TEXT    NOT NULL,
                monto       REAL    NOT NULL CHECK (monto >= 100),
                categoria   TEXT    NOT NULL CHECK (
                    categoria IN ('comida', 'transporte', 'estudio', 'ocio', 'otros')
                ),
                fecha       TEXT    NOT NULL
            )
            """
        )
        # Migración: bases de datos creadas antes de los usuarios.
        columnas = {fila["name"] for fila in conexion.execute("PRAGMA table_info(gastos)")}
        if "usuario_id" not in columnas:
            conexion.execute("ALTER TABLE gastos ADD COLUMN usuario_id INTEGER")

        # Un usuario invitado para los gastos de ejemplo de instalaciones previas.
        fila = conexion.execute(
            "SELECT id FROM usuarios WHERE nombre = ?", ("demo",)
        ).fetchone()
        if fila is None:
            from services import crear_usuario  # Import diferido para evitar ciclo.

            try:
                crear_usuario("demo", "demo1234", cargar_ejemplos=False)
            except ValueError:
                pass
        id_demo = conexion.execute(
            "SELECT id FROM usuarios WHERE nombre = ?", ("demo",)
        ).fetchone()["id"]

        # Asigna al usuario demo los gastos antiguos que no tengan dueño.
        conexion.execute(
            "UPDATE gastos SET usuario_id = ? WHERE usuario_id IS NULL", (id_demo,)
        )

        cantidad = conexion.execute(
            "SELECT COUNT(*) FROM gastos WHERE usuario_id = ?", (id_demo,)
        ).fetchone()[0]
        if cantidad == 0:
            conexion.executemany(
                """
                INSERT INTO gastos (usuario_id, descripcion, monto, categoria, fecha)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(id_demo,) + gasto for gasto in GASTOS_EJEMPLO],
            )
    return RUTA_DB
