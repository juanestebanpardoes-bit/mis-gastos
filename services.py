"""Reglas de negocio y validaciones de Mis Gastos.

Todas las consultas SQL usan parámetros (?) para evitar inyección SQL.
Los errores de datos se avisan con ValueError y los registros ausentes
con LookupError, ambos con mensajes claros en español.
"""

import hashlib
import hmac
import math
import re
import secrets
import threading
from datetime import date

import database

CATEGORIAS = database.CATEGORIAS
_FORMATO_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTO_MINIMO = 100  # Pesos colombianos.

# Las sesiones se guardan en memoria: token -> id de usuario.
_SESIONES = {}
_BLOQUEO_SESIONES = threading.Lock()


def _hash_contrasena(contrasena, sal):
    """Deriva una clave segura con PBKDF2-HMAC-SHA256 (100.000 iteraciones)."""
    return hashlib.pbkdf2_hmac(
        "sha256", contrasena.encode("utf-8"), bytes.fromhex(sal), 100_000
    ).hex()


def _validar_nombre(valor):
    """Comprueba que el nombre de usuario tenga entre 3 y 30 caracteres."""
    if not isinstance(valor, str):
        raise ValueError("El usuario debe ser texto.")
    nombre = valor.strip()
    if not (3 <= len(nombre) <= 30) or not nombre.replace("_", "").isalnum():
        raise ValueError("El usuario debe tener entre 3 y 30 letras, números o guiones bajos.")
    return nombre


def _validar_contrasena(valor):
    """Comprueba que la contraseña tenga al menos 6 caracteres."""
    if not isinstance(valor, str) or len(valor) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    return valor


def crear_usuario(nombre, contrasena, cargar_ejemplos=True):
    """Registra un usuario y devuelve sus datos públicos."""
    nombre = _validar_nombre(nombre)
    contrasena = _validar_contrasena(contrasena)
    sal = secrets.token_hex(16)
    with database.conexion_abierta() as conexion:
        existe = conexion.execute(
            "SELECT 1 FROM usuarios WHERE nombre = ?", (nombre,)
        ).fetchone()
        if existe:
            raise ValueError("Ya existe un usuario con ese nombre.")
        cursor = conexion.execute(
            "INSERT INTO usuarios (nombre, contrasena, sal) VALUES (?, ?, ?)",
            (nombre, _hash_contrasena(contrasena, sal), sal),
        )
        id_usuario = cursor.lastrowid
        if cargar_ejemplos:
            conexion.executemany(
                """
                INSERT INTO gastos (usuario_id, descripcion, monto, categoria, fecha)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(id_usuario,) + gasto for gasto in database.GASTOS_EJEMPLO],
            )
    return {"id": id_usuario, "nombre": nombre}


def iniciar_sesion(nombre, contrasena):
    """Verifica credenciales y devuelve un token de sesión."""
    if not isinstance(nombre, str) or not isinstance(contrasena, str):
        raise ValueError("Usuario y contraseña son obligatorios.")
    nombre = nombre.strip()
    with database.conexion_abierta() as conexion:
        fila = conexion.execute(
            "SELECT id, nombre, contrasena, sal FROM usuarios WHERE nombre = ?", (nombre,)
        ).fetchone()
    if fila is None or not hmac.compare_digest(
        fila["contrasena"], _hash_contrasena(contrasena, fila["sal"])
    ):
        raise ValueError("Usuario o contraseña incorrectos.")
    token = secrets.token_urlsafe(32)
    with _BLOQUEO_SESIONES:
        _SESIONES[token] = fila["id"]
    return {"token": token, "nombre": fila["nombre"]}


def usuario_de_token(token):
    """Devuelve el id del usuario asociado al token, o None si no es válido."""
    if not token:
        return None
    with _BLOQUEO_SESIONES:
        return _SESIONES.get(token)


def cerrar_sesion(token):
    """Elimina una sesión activa."""
    if token:
        with _BLOQUEO_SESIONES:
            _SESIONES.pop(token, None)


def nombre_de_usuario(id_usuario):
    """Devuelve el nombre público de un usuario."""
    with database.conexion_abierta() as conexion:
        fila = conexion.execute(
            "SELECT nombre FROM usuarios WHERE id = ?", (id_usuario,)
        ).fetchone()
    if fila is None:
        raise LookupError("No existe ese usuario.")
    return fila["nombre"]


def _validar_descripcion(valor):
    """Comprueba que la descripción sea texto y no esté vacía."""
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError("La descripción es obligatoria y no puede estar vacía.")
    return valor.strip()


def _validar_monto(valor):
    """Comprueba que el monto sea un número finito de al menos 100 COP."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError("El monto debe ser un número de al menos 100 pesos colombianos.")
    monto = float(valor)
    if not math.isfinite(monto) or monto < MONTO_MINIMO:
        raise ValueError("El monto debe ser un número de al menos 100 pesos colombianos.")
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


def crear(id_usuario, descripcion, monto, categoria, fecha):
    """Crea un gasto nuevo para el usuario y lo devuelve con su id."""
    datos = _validar_gasto(descripcion, monto, categoria, fecha)
    with database.conexion_abierta() as conexion:
        cursor = conexion.execute(
            """
            INSERT INTO gastos (usuario_id, descripcion, monto, categoria, fecha)
            VALUES (?, ?, ?, ?, ?)
            """,
            (id_usuario,) + datos,
        )
        id_nuevo = cursor.lastrowid
    return obtener(id_usuario, id_nuevo)


def listar(id_usuario, filtro=None):
    """Devuelve los gastos del usuario, o solo los que coinciden con un texto."""
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
            WHERE usuario_id = ? AND
                  (LOWER(descripcion) LIKE LOWER(?) OR LOWER(categoria) LIKE LOWER(?))
            ORDER BY fecha DESC, id DESC
            """,
            (id_usuario, patron, patron),
        ).fetchall()
    return [_fila_a_dict(fila) for fila in filas]


def obtener(id_usuario, id_gasto):
    """Devuelve un gasto del usuario por su id o lanza LookupError."""
    id_gasto = _validar_id(id_gasto)
    with database.conexion_abierta() as conexion:
        fila = conexion.execute(
            """
            SELECT id, descripcion, monto, categoria, fecha
            FROM gastos
            WHERE id = ? AND usuario_id = ?
            """,
            (id_gasto, id_usuario),
        ).fetchone()
    if fila is None:
        raise LookupError(f"No existe un gasto con id {id_gasto}.")
    return _fila_a_dict(fila)


def actualizar(id_usuario, id_gasto, descripcion, monto, categoria, fecha):
    """Reemplaza todos los campos de un gasto existente del usuario."""
    id_gasto = _validar_id(id_gasto)
    datos = _validar_gasto(descripcion, monto, categoria, fecha)
    with database.conexion_abierta() as conexion:
        cursor = conexion.execute(
            """
            UPDATE gastos
            SET descripcion = ?, monto = ?, categoria = ?, fecha = ?
            WHERE id = ? AND usuario_id = ?
            """,
            datos + (id_gasto, id_usuario),
        )
        if cursor.rowcount == 0:
            raise LookupError(f"No existe un gasto con id {id_gasto}.")
    return obtener(id_usuario, id_gasto)


def eliminar(id_usuario, id_gasto):
    """Elimina un gasto del usuario por su id o lanza LookupError."""
    id_gasto = _validar_id(id_gasto)
    with database.conexion_abierta() as conexion:
        cursor = conexion.execute(
            "DELETE FROM gastos WHERE id = ? AND usuario_id = ?",
            (id_gasto, id_usuario),
        )
        if cursor.rowcount == 0:
            raise LookupError(f"No existe un gasto con id {id_gasto}.")
    return {"mensaje": "Gasto eliminado correctamente.", "id": id_gasto}


def resumen(id_usuario):
    """Devuelve el total gastado y el total por categoría del usuario."""
    with database.conexion_abierta() as conexion:
        total = conexion.execute(
            "SELECT COALESCE(SUM(monto), 0) FROM gastos WHERE usuario_id = ?",
            (id_usuario,),
        ).fetchone()[0]
        filas = conexion.execute(
            """
            SELECT categoria, COALESCE(SUM(monto), 0) AS total
            FROM gastos
            WHERE usuario_id = ?
            GROUP BY categoria
            """,
            (id_usuario,),
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
