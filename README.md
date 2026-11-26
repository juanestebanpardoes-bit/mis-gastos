# Mis Gastos

Aplicación web para registrar gastos personales y ver cuánto se gasta por categoría.
Está hecha **desde cero con Python 3.10+ y solo la biblioteca estándar**: usa
`sqlite3` como base de datos y `http.server` como servidor. No hay que instalar
ningún paquete con `pip`.

## Cómo ejecutarla

Desde esta carpeta:

```bash
python app.py
```

Abre <http://127.0.0.1:8000> en el navegador. La primera vez se crea
automáticamente el archivo `datos.db` con 3 gastos de ejemplo. Para detener el
servidor, pulsa `Ctrl+C`.

## Cómo probarla

```bash
python -m unittest -v
```

Las pruebas usan una base de datos temporal y un servidor en un puerto libre,
por lo que no modifican tus datos reales.

## Estructura de archivos

| Archivo | Contenido |
| --- | --- |
| `database.py` | Conexión a SQLite, creación de `datos.db`, tabla `gastos` y ejemplos. |
| `services.py` | Validaciones (reglas de negocio) y operaciones sobre los gastos. |
| `app.py` | Servidor HTTP, página web y API REST en JSON. |
| `static/index.html` | Interfaz en un solo archivo (HTML + CSS + JavaScript con `fetch`). |
| `test_app.py` | Pruebas con `unittest` de servicios y de la API. |
| `.gitignore` | Ignora `*.db` y `__pycache__/`. |

## Entidad Gasto

| Campo | Tipo | Regla |
| --- | --- | --- |
| `id` | entero | Generado automáticamente por SQLite. |
| `descripcion` | texto | Obligatoria, no puede estar vacía. |
| `monto` | número | Debe ser mayor que 0. |
| `categoria` | texto | `comida`, `transporte`, `estudio`, `ocio` u `otros`. |
| `fecha` | texto | Fecha válida con formato `AAAA-MM-DD`. |

## Rutas de la API

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/api/salud` | Comprueba que el servidor funciona. |
| `GET` | `/api/gastos` | Lista todos los gastos. Admite `?filtro=texto`. |
| `POST` | `/api/gastos` | Crea un gasto. Devuelve 201. |
| `GET` | `/api/gastos/{id}` | Obtiene un gasto por su id. |
| `PUT` | `/api/gastos/{id}` | Actualiza todos los campos de un gasto. |
| `DELETE` | `/api/gastos/{id}` | Elimina un gasto. |
| `GET` | `/api/resumen` | Total gastado y total por categoría. |

Ejemplo de cuerpo para `POST` y `PUT`:

```json
{
  "descripcion": "Compra en el supermercado",
  "monto": 23.45,
  "categoria": "comida",
  "fecha": "2026-11-26"
}
```

Ejemplo de respuesta de `/api/resumen`:

```json
{
  "total": 74.7,
  "por_categoria": {
    "comida": 35.95,
    "transporte": 8.75,
    "estudio": 30.0,
    "ocio": 0.0,
    "otros": 0.0
  }
}
```

Los errores de validación devuelven `400`, los registros inexistentes `404` y
las rutas desconocidas `404`, siempre con un objeto JSON `{"error": "..."}` con
el mensaje en español.
