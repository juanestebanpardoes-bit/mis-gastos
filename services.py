"""Reglas de negocio y validaciones de Mis Gastos.

Todas las consultas SQL usan parámetros (?) para evitar inyección SQL.
Los errores de datos se avisan con ValueError y los registros ausentes
con LookupError, ambos con mensajes claros en español.
"""

import math
import re
from datetime import date

import database

CATEGORIAS = database.CATEGORIAS
_FORMATO_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validar_descripcion(valor):
    """Comprueba que la descripción sea texto y no esté vacía."""
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError("La descripción es obligatoria y no puede estar vacía.")
    return valor.strip()


def _validar_monto(valor):
    """Comprueba que el monto sea un número finito mayor que cero."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError("El monto debe ser un número mayor que 0.")
    monto = float(valor)
    if not math.isfinite(monto) or monto <= 0:
        raise ValueError("El monto debe ser un número mayor que 0.")
    return monto


def _validar_categoria(valor):
    """Comprueba que la categoría sea una de las permitidas."""
    if not isinstance(valor, str) or valor not in CATEGORIAS:
        raise ValueError(
            "La categoría debe ser una de: " + ", ".join(CATEGORIAS) + "."
        )
    return valor


def _validar_fecha(valor):
    """Comprueba que la fecha tenga formato AAAA-MM-DD y sea real."""
    if not isinstance(valor, str) or not _FORMATO_FECHA.fullmatch(valor):
        raise ValueError("La fecha debe tener el formato AAAA-MM-DD.")
    try:
        date.fromisoformat(valor)
    except ValueError:
        raise ValueError("La fecha no es válida: revisa el día y el mes.") from None
    return valor


def _validar_id(valor):
    """Comprueba que el identificador sea un entero positivo."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise ValueError("El id debe ser un entero positivo.")
    return valor


def _validar_gasto(descripcion, monto, categoria, fecha):
    """Valida todos los campos de un gasto y devuelve una tupla limpia."""
    return (
        _validar_descripcion(descripcion),
        _validar_monto(monto),
        _validar_categoria(categoria),
        _validar_fecha(fecha),
    )


def _fila_a_dict(fila):
    """Convierte una fila de SQLite en un diccionario JSON-friendly."""
    return {
        "id": fila["id"],
        "descripcion": fila["descripcion"],
        "monto": fila["monto"],
        "categoria": fila["categoria"],
        "fecha": fila["fecha"],
    }


def crear(descripcion, monto, categoria, fecha):
    """Crea un gasto nuevo y lo devuelve con su id asignado."""
    datos = _validar_gasto(descripcion, monto, categoria, fecha)
    with database.conexion_abierta() as conexion:
        cursor = conexion.execute(
            """
            INSERT INTO gastos (descripcion, monto, categoria, fecha)
            VALUES (?, ?, ?, ?)
            """,
            datos,
        )
        id_nuevo = cursor.lastrowid
    return obtener(id_nuevo)


def listar(filtro=None):
    """Devuelve todos los gastos, o solo los que coinciden con un texto."""
    if filtro is None:
        filtro = ""
    if not isinstance(filtro, str):
        raise ValueError("El filtro de búsqueda debe ser texto.")
    patron = "%" + filtro.strip() + "%"
    with database.conexion_abierta() as conexion:
        filas = conexion.execute(
            """
            SELECT id, descripcion, monto, categoria, fecha
            FROM gastos
            WHERE LOWER(descripcion) LIKE LOWER(?) OR LOWER(categoria) LIKE LOWER(?)
            ORDER BY fecha DESC, id DESC
            """,
            (patron, patron),
        ).fetchall()
    return [_fila_a_dict(fila) for fila in filas]


def obtener(id_gasto):
    """Devuelve un gasto por su id o lanza LookupError si no existe."""
    id_gasto = _validar_id(id_gasto)
    with database.conexion_abierta() as conexion:
        fila = conexion.execute(
            """
            SELECT id, descripcion, monto, categoria, fecha
            FROM gastos
            WHERE id = ?
            """,
            (id_gasto,),
        ).fetchone()
    if fila is None:
        raise LookupError(f"No existe un gasto con id {id_gasto}.")
    return _fila_a_dict(fila)


def actualizar(id_gasto, descripcion, monto, categoria, fecha):
    """Reemplaza todos los campos de un gasto existente."""
    id_gasto = _validar_id(id_gasto)
    datos = _validar_gasto(descripcion, monto, categoria, fecha)
    with database.conexion_abierta() as conexion:
        cursor = conexion.execute(
            """
            UPDATE gastos
            SET descripcion = ?, monto = ?, categoria = ?, fecha = ?
            WHERE id = ?
            """,
            datos + (id_gasto,),
        )
        if cursor.rowcount == 0:
            raise LookupError(f"No existe un gasto con id {id_gasto}.")
    return obtener(id_gasto)


def eliminar(id_gasto):
    """Elimina un gasto por su id o lanza LookupError si no existe."""
    id_gasto = _validar_id(id_gasto)
    with database.conexion_abierta() as conexion:
        cursor = conexion.execute(
            "DELETE FROM gastos WHERE id = ?", (id_gasto,)
        )
        if cursor.rowcount == 0:
            raise LookupError(f"No existe un gasto con id {id_gasto}.")
    return {"mensaje": "Gasto eliminado correctamente.", "id": id_gasto}


def resumen():
    """Devuelve el total gastado y el total por cada categoría."""
    with database.conexion_abierta() as conexion:
        total = conexion.execute(
            "SELECT COALESCE(SUM(monto), 0) FROM gastos"
        ).fetchone()[0]
        filas = conexion.execute(
            """
            SELECT categoria, COALESCE(SUM(monto), 0) AS total
            FROM gastos
            GROUP BY categoria
            """
        ).fetchall()

    por_categoria = {categoria: 0.0 for categoria in CATEGORIAS}
    for fila in filas:
        por_categoria[fila["categoria"]] = fila["total"]

    return {
        "total": round(float(total), 2),
        "por_categoria": {
            categoria: round(valor, 2) for categoria, valor in por_categoria.items()
        },
    }
