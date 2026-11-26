"""Servidor web de Mis Gastos usando solo la biblioteca estándar.

Sirve la página en / y expone una API REST en JSON. Este archivo no contiene
reglas de negocio: solo traduce HTTP a llamadas a services.py y viceversa.
"""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import database
import services

RUTA_INDEX = Path(__file__).resolve().parent / "static" / "index.html"
_RUTA_GASTO_ID = re.compile(r"^/api/gastos/([^/]+)$")


class ManejadorAPI(BaseHTTPRequestHandler):
    """Atiende las peticiones HTTP y delega el trabajo a services.py."""

    # Permite varias peticiones a la vez desde el navegador.
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *argumentos):
        """Silencia los registro por defecto para que la consola quede limpia."""
        return

    def do_GET(self):
        self._despachar("GET")

    def do_POST(self):
        self._despachar("POST")

    def do_PUT(self):
        self._despachar("PUT")

    def do_DELETE(self):
        self._despachar("DELETE")

    def _enviar(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        """Envía una respuesta con Content-Length para HTTP/1.1."""
        if isinstance(cuerpo, (dict, list)):
            contenido = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        else:
            contenido = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(contenido)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(contenido)

    def _enviar_json(self, codigo, datos):
        self._enviar(codigo, datos)

    def _enviar_error(self, codigo, mensaje):
        self._enviar_json(codigo, {"error": mensaje})

    def _leer_json(self):
        """Lee el cuerpo de la petición y comprueba que sea un objeto JSON."""
        longitud = self.headers.get("Content-Length")
        if not longitud:
            raise ValueError("Se esperaba un cuerpo JSON con los datos del gasto.")
        try:
            cuerpo = self.rfile.read(int(longitud)).decode("utf-8")
            datos = json.loads(cuerpo)
        except (ValueError, UnicodeDecodeError):
            raise ValueError("El cuerpo de la petición no es un JSON válido.") from None
        if not isinstance(datos, dict):
            raise ValueError("El cuerpo de la petición debe ser un objeto JSON.")
        return datos

    def _despachar(self, metodo):
        """Enruta la petición a la operación correspondiente."""
        partes = urlsplit(self.path)
        ruta = partes.path

        try:
            if ruta in ("/", "/index.html"):
                if metodo != "GET":
                    self._enviar_error(405, "Método no permitido para esta ruta.")
                    return
                self._servir_index()
                return

            if ruta == "/api/salud":
                if metodo != "GET":
                    self._enviar_error(405, "Método no permitido para esta ruta.")
                    return
                self._enviar_json(200, {"estado": "ok", "aplicacion": "Mis Gastos"})
                return

            if ruta == "/api/gastos":
                if metodo == "GET":
                    filtro = parse_qs(partes.query).get("filtro", [""])[0]
                    self._enviar_json(200, services.listar(filtro))
                elif metodo == "POST":
                    datos = self._leer_json()
                    gasto = services.crear(
                        datos.get("descripcion"),
                        datos.get("monto"),
                        datos.get("categoria"),
                        datos.get("fecha"),
                    )
                    self._enviar_json(201, gasto)
                else:
                    self._enviar_error(405, "Método no permitido para esta ruta.")
                return

            coincidencia = _RUTA_GASTO_ID.fullmatch(ruta)
            if coincidencia:
                try:
                    id_gasto = int(coincidencia.group(1))
                except ValueError:
                    raise ValueError("El id del gasto debe ser un entero positivo.") from None

                if metodo == "GET":
                    self._enviar_json(200, services.obtener(id_gasto))
                elif metodo == "PUT":
                    datos = self._leer_json()
                    gasto = services.actualizar(
                        id_gasto,
                        datos.get("descripcion"),
                        datos.get("monto"),
                        datos.get("categoria"),
                        datos.get("fecha"),
                    )
                    self._enviar_json(200, gasto)
                elif metodo == "DELETE":
                    self._enviar_json(200, services.eliminar(id_gasto))
                else:
                    self._enviar_error(405, "Método no permitido para esta ruta.")
                return

            if ruta == "/api/resumen":
                if metodo != "GET":
                    self._enviar_error(405, "Método no permitido para esta ruta.")
                    return
                self._enviar_json(200, services.resumen())
                return

            self._enviar_error(404, "La ruta solicitada no existe.")

        except ValueError as error:
            self._enviar_error(400, str(error))
        except LookupError as error:
            self._enviar_error(404, str(error))

    def _servir_index(self):
        """Sirve el único archivo HTML de la interfaz."""
        try:
            contenido = RUTA_INDEX.read_text(encoding="utf-8")
        except OSError:
            self._enviar_error(404, "No se encontró la página principal.")
            return
        self._enviar(200, contenido, "text/html; charset=utf-8")


def crear_servidor(host="127.0.0.1", puerto=8000):
    """Crea el servidor HTTP; con puerto=0 el sistema elige uno libre."""
    return ThreadingHTTPServer((host, puerto), ManejadorAPI)


def main():
    """Inicializa la base de datos y deja el servidor escuchando."""
    database.iniciar_db()
    servidor = crear_servidor()
    print("Mis Gastos disponible en http://127.0.0.1:8000")
    print("Pulsa Ctrl+C para detener el servidor.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
