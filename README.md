# Mis Gastos

Aplicación web para registrar gastos personales y ver cuánto se gasta por categoría.
Los valores se guardan en **pesos colombianos (COP)** y se pueden visualizar en
**COP, dólares (USD) o euros (EUR)** con el selector de moneda de la esquina
superior derecha. Las tasas son de referencia fijas (1 USD = 4.000 COP,
1 EUR = 4.300 COP); al crear o editar un gasto, el valor introducido en la
moneda elegida se convierte a COP antes de guardarse, respetando el mínimo de
100 COP. La interfaz también permite cambiar entre **español e inglés**, y ambas
elecciones se recuerdan en el navegador. El color verde y el amarillo de la
interfaz están inspirados en la bandera de Colombia.

Cada persona debe **registrarse con usuario y contraseña** para entrar: la
pantalla de acceso aparece al abrir la página. Cada usuario ve **solo sus propios
gastos**. Las contraseñas se guardan con un hash PBKDF2 saltado (nunca en texto
plano) y la sesión se mantiene mediante una cookie `HttpOnly`.
Usuario de prueba: `demo` / `demo1234` (sus gastos son los ejemplos iniciales).
Está hecha **desde cero con Python 3.10+ y solo la biblioteca estándar**: usa
`sqlite3` como base de datos y `http.server` como servidor. No hay que instalar
ningún paquete con `pip`.

## Cómo ejecutarla

Desde esta carpeta (en Windows usa la ruta completa de Python; ver nota más abajo):

```bash
"C:\Users\juan\AppData\Local\Programs\Python\Python312\python.exe" app.py
```

O, si `python` te funciona en la terminal:

```bash
python app.py
```

Más fácil todavía: haz doble clic en **`iniciar.bat`**. Abrirá el navegador en
la página y arrancará el servidor con el Python correcto.

Abre <http://127.0.0.1:8000> en el navegador. La primera vez se crea
automáticamente el archivo `datos.db` con el usuario `demo` (contraseña
`demo1234`) y 3 gastos de ejemplo. También puedes crear tu propia cuenta con el
botón **Registrarse**. Para detener el servidor, pulsa `Ctrl+C`.

> **Nota (importante en esta máquina):** el comando `python` puede mostrar el
> error *"Python was not found... Microsoft Store"*. Es un alias de Windows que
> no ejecuta tu Python real. Usa siempre la ruta completa indicada arriba o
> selecciona ese intérprete en VS Code (`Ctrl+Shift+P` → *Python: Select
> Interpreter* → `C:\Users\juan\AppData\Local\Programs\Python\Python312\python.exe`).
> No hace falta instalar nada con `pip`.

### Desde Visual Studio Code

1. Abre esta carpeta con `File > Open Folder...`.
2. Instala la extensión oficial de **Python** (no necesitas instalar paquetes con `pip`).
3. Selecciona el intérprete de Python 3.12 ubicado en
   `C:\Users\juan\AppData\Local\Programs\Python\Python312\python.exe`.
4. Pulsa **F5**: la configuración incluida en `.vscode/launch.json` ya apunta a
   ese intérprete y arranca `app.py`. También puedes ejecutar en la terminal
   integrada:
   ```powershell
   & "C:\Users\juan\AppData\Local\Programs\Python\Python312\python.exe" app.py
   ```

## Cómo probarla

```bash
"C:\Users\juan\AppData\Local\Programs\Python\Python312\python.exe" -m unittest -v
```

Las pruebas usan una base de datos temporal y un servidor en un puerto libre,
por lo que no modifican tus datos reales.

## Estructura de archivos

| Archivo | Contenido |
| --- | --- |
| `database.py` | Conexión a SQLite, tablas `usuarios` y `gastos`, ejemplos y migración. |
| `services.py` | Registro/login con hash PBKDF2, sesiones, validaciones y gastos por usuario. |
| `app.py` | Servidor HTTP, página web y API REST en JSON con cookie de sesión. |
| `static/index.html` | Interfaz (HTML + CSS + JavaScript con `fetch`), acceso y selector de moneda/idioma. |
| `test_app.py` | Pruebas con `unittest` de servicios, autenticación y API. |
| `iniciar.bat` | Arranque rápido en Windows con el intérprete correcto. |
| `.vscode/launch.json` | Configuración para iniciar el servidor con F5 en VS Code. |
| `.gitignore` | Ignora `*.db` y `__pycache__/`. |

## Entidad Gasto

| Campo | Tipo | Regla |
| --- | --- | --- |
| `id` | entero | Generado automáticamente por SQLite. |
| `descripcion` | texto | Obligatoria, no puede estar vacía. |
| `monto` | número | Debe ser al menos 100 pesos colombianos (COP). |
| `categoria` | texto | `comida`, `transporte`, `estudio`, `ocio` u `otros`. |
| `fecha` | texto | Fecha válida con formato `AAAA-MM-DD`. |

## Rutas de la API

| Método | Ruta | Descripción |
| --- | --- | --- |
| `GET` | `/api/salud` | Comprueba que el servidor funciona. |
| `POST` | `/api/registro` | Crea una cuenta con `{ "nombre", "contrasena" }`. |
| `POST` | `/api/login` | Inicia sesión y devuelve token + cookie. |
| `GET` | `/api/sesion` | Indica si hay sesión activa y el nombre de usuario. |
| `POST` | `/api/logout` | Cierra la sesión. |
| `GET` | `/api/gastos` | Lista los gastos del usuario. Admite `?filtro=texto`. Requiere sesión. |
| `POST` | `/api/gastos` | Crea un gasto. Devuelve 201. Requiere sesión. |
| `GET` | `/api/gastos/{id}` | Obtiene un gasto propio por su id. Requiere sesión. |
| `PUT` | `/api/gastos/{id}` | Actualiza un gasto propio. Requiere sesión. |
| `DELETE` | `/api/gastos/{id}` | Elimina un gasto propio. Requiere sesión. |
| `GET` | `/api/resumen` | Total gastado y por categoría del usuario. Requiere sesión. |

Las rutas de gastos devuelven `401` si no hay sesión iniciada, y `404` si el
gasto pertenece a otro usuario.

Ejemplo de cuerpo para `POST` y `PUT`:

```json
{
  "descripcion": "Compra en el supermercado",
  "monto": 23450,
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
