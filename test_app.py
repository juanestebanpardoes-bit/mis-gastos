"""Pruebas automáticas de Mis Gastos con unittest.

Las pruebas de servicios usan una base de datos temporal y las de la API
levantan el servidor en un puerto libre, así que no tocan datos.db.
"""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from unittest import mock

import app
import database
import services


class ServiciosTest(unittest.TestCase):
    """Prueba las reglas de negocio contra una base de datos temporal."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ruta = os.path.join(temporal.name, "servicios.db")
        parche = mock.patch.object(database, "RUTA_DB", ruta)
        parche.start()
        self.addCleanup(parche.stop)
        database.iniciar_db()
        self.id_usuario = services.iniciar_sesion("demo", "demo1234") and self._id_demo()

    def _id_demo(self):
        with database.conexion_abierta() as conexion:
            return conexion.execute(
                "SELECT id FROM usuarios WHERE nombre = ?", ("demo",)
            ).fetchone()["id"]

    def crear(self, descripcion, monto, categoria="comida", fecha="2026-11-25"):
        return services.crear(
            self.id_usuario, descripcion, monto, categoria, fecha
        )

    def test_iniciar_db_carga_tres_ejemplos(self):
        gastos = services.listar(self.id_usuario)
        self.assertEqual(len(gastos), 3)
        self.assertTrue(all("id" in gasto for gasto in gastos))

        # Una segunda llamada no debe duplicar los ejemplos.
        database.iniciar_db()
        self.assertEqual(len(services.listar(self.id_usuario)), 3)

    def test_registro_y_login(self):
        usuario = services.crear_usuario("prueba", "clave123", cargar_ejemplos=False)
        self.assertEqual(services.nombre_de_usuario(usuario["id"]), "prueba")
        sesion = services.iniciar_sesion("prueba", "clave123")
        self.assertEqual(services.usuario_de_token(sesion["token"]), usuario["id"])
        with self.assertRaises(ValueError):
            services.iniciar_sesion("prueba", "clave incorrecta")
        services.cerrar_sesion(sesion["token"])
        self.assertIsNone(services.usuario_de_token(sesion["token"]))

    def test_registro_rechaza_datos_invalidos(self):
        with self.assertRaises(ValueError):
            services.crear_usuario("ab", "clave123", cargar_ejemplos=False)
        with self.assertRaises(ValueError):
            services.crear_usuario("unico", "123", cargar_ejemplos=False)
        services.crear_usuario("unico", "clave123", cargar_ejemplos=False)
        with self.assertRaises(ValueError):
            services.crear_usuario("unico", "clave123", cargar_ejemplos=False)

    def test_gastos_aislados_por_usuario(self):
        otro = services.crear_usuario("otro", "clave123", cargar_ejemplos=False)
        gasto = self.crear("Gasto privado", 20000)
        self.assertEqual(len(services.listar(otro["id"])), 0)
        with self.assertRaises(LookupError):
            services.obtener(otro["id"], gasto["id"])
        with self.assertRaises(LookupError):
            services.actualizar(otro["id"], gasto["id"], "Cambio", 20000, "ocio", "2026-11-25")
        with self.assertRaises(LookupError):
            services.eliminar(otro["id"], gasto["id"])

    def test_crear_y_obtener(self):
        gasto = self.crear("Curso de Python", 45500, "estudio")
        self.assertIsInstance(gasto["id"], int)
        self.assertEqual(gasto["descripcion"], "Curso de Python")
        self.assertEqual(gasto["monto"], 45500)
        self.assertEqual(gasto["categoria"], "estudio")
        self.assertEqual(gasto["fecha"], "2026-11-25")
        self.assertEqual(services.obtener(self.id_usuario, gasto["id"]), gasto)

    def test_validaciones_de_campos(self):
        casos = [
            ("descripción vacía", ("   ", 1000, "comida", "2026-11-25")),
            ("monto cero", ("Pan", 0, "comida", "2026-11-25")),
            ("monto negativo", ("Pan", -1, "comida", "2026-11-25")),
            ("monto menor al mínimo", ("Pan", 99, "comida", "2026-11-25")),
            ("monto no numérico", ("Pan", "diez", "comida", "2026-11-25")),
            ("categoría desconocida", ("Pan", 1000, "viajes", "2026-11-25")),
            ("fecha con formato incorrecto", ("Pan", 1000, "comida", "25-11-2026")),
            ("fecha inexistente", ("Pan", 1000, "comida", "2026-02-30")),
        ]
        for nombre, datos in casos:
            with self.subTest(nombre=nombre):
                with self.assertRaises(ValueError):
                    self.crear(*datos)

    def test_listar_con_filtro(self):
        self.crear("Café con leche", 3200)
        self.crear("Peaje", 5000, "transporte")
        resultados = services.listar(self.id_usuario, "café")
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["descripcion"], "Café con leche")
        self.assertEqual(len(services.listar(self.id_usuario)), 5)

    def test_actualizar(self):
        gasto = self.crear("Cine", 9000, "ocio", "2026-11-23")
        actualizado = services.actualizar(
            self.id_usuario, gasto["id"], "Cine 3D", 12000, "ocio", "2026-11-24"
        )

        self.assertEqual(actualizado["descripcion"], "Cine 3D")
        self.assertEqual(actualizado["monto"], 12000)
        self.assertEqual(actualizado["fecha"], "2026-11-24")

        with self.assertRaises(LookupError):
            services.actualizar(
                self.id_usuario, 9999, "Cine", 9000, "ocio", "2026-11-23"
            )

    def test_eliminar(self):
        gasto = self.crear("Taxi", 15000, "transporte")
        services.eliminar(self.id_usuario, gasto["id"])
        with self.assertRaises(LookupError):
            services.obtener(self.id_usuario, gasto["id"])
        with self.assertRaises(LookupError):
            services.eliminar(self.id_usuario, gasto["id"])

    def test_resumen(self):
        self.crear("Cuaderno", 20000, "estudio")
        resumen = services.resumen(self.id_usuario)
        self.assertEqual(resumen["total"], 71250)
        self.assertEqual(resumen["por_categoria"]["estudio"], 50000)
        self.assertEqual(resumen["por_categoria"]["comida"], 12500)
        self.assertEqual(resumen["por_categoria"]["otros"], 0.0)
        self.assertEqual(set(resumen["por_categoria"]), set(services.CATEGORIAS))


class APITest(unittest.TestCase):
    """Prueba los endpoints HTTP con el servidor en un puerto libre."""

    @classmethod
    def setUpClass(cls):
        temporal = tempfile.TemporaryDirectory()
        cls.temporal = temporal
        cls.parche = mock.patch.object(
            database, "RUTA_DB", os.path.join(temporal.name, "api.db")
        )
        cls.parche.start()
        database.iniciar_db()

        cls.servidor = app.crear_servidor(puerto=0)
        cls.hilo = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.hilo.start()
        cls.base_url = "http://127.0.0.1:" + str(cls.servidor.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.hilo.join(timeout=5)
        cls.parche.stop()
        cls.temporal.cleanup()

    def nuevo_cliente(self):
        """Crea un opener con cookiejar: simula un navegador."""
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def pedir(self, ruta, metodo="GET", cuerpo=None, cliente=None):
        """Hace una petición y devuelve (código, datos_json)."""
        contenido = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
        solicitud = urllib.request.Request(
            self.base_url + ruta,
            data=contenido,
            method=metodo,
            headers={"Content-Type": "application/json"},
        )
        try:
            abrir = cliente.open if cliente else urllib.request.urlopen
            with abrir(solicitud, timeout=5) as respuesta:
                return respuesta.status, json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def iniciar_sesion(self, nombre="demo", contrasena="demo1234"):
        cliente = self.nuevo_cliente()
        codigo, datos = self.pedir(
            "/api/login", "POST",
            {"nombre": nombre, "contrasena": contrasena}, cliente,
        )
        self.assertEqual(codigo, 200)
        return cliente

    def crear_gasto(self, cliente, descripcion="Prueba API", monto=7250):
        codigo, gasto = self.pedir(
            "/api/gastos",
            "POST",
            {
                "descripcion": descripcion,
                "monto": monto,
                "categoria": "otros",
                "fecha": "2026-11-26",
            },
            cliente,
        )
        self.assertEqual(codigo, 201)
        return gasto

    def test_salud(self):
        codigo, datos = self.pedir("/api/salud")
        self.assertEqual(codigo, 200)
        self.assertEqual(datos["estado"], "ok")

    def test_registro_login_sesion_y_logout(self):
        cliente = self.nuevo_cliente()
        codigo, datos = self.pedir(
            "/api/registro", "POST",
            {"nombre": "nuevo", "contrasena": "clave123"}, cliente,
        )
        self.assertEqual(codigo, 201)
        self.assertEqual(datos["nombre"], "nuevo")

        codigo, sesion = self.pedir("/api/sesion", cliente=cliente)
        self.assertEqual(codigo, 200)
        self.assertTrue(sesion["autenticado"])
        self.assertEqual(sesion["nombre"], "nuevo")

        codigo, datos = self.pedir("/api/logout", "POST", cliente=cliente)
        self.assertEqual(codigo, 200)
        codigo, sesion = self.pedir("/api/sesion", cliente=cliente)
        self.assertFalse(sesion["autenticado"])

    def test_login_incorrecto(self):
        codigo, datos = self.pedir(
            "/api/login", "POST", {"nombre": "demo", "contrasena": "mala"}
        )
        self.assertEqual(codigo, 400)
        self.assertIn("contraseña", datos["error"].lower())

    def test_gastos_requieren_sesion(self):
        for ruta in ("/api/gastos", "/api/resumen"):
            codigo, datos = self.pedir(ruta)
            self.assertEqual(codigo, 401)
            self.assertIn("Inicia sesión", datos["error"])

    def test_aislamiento_de_gastos_entre_usuarios(self):
        cliente1 = self.iniciar_sesion()
        cliente2 = self.nuevo_cliente()
        codigo, _ = self.pedir(
            "/api/registro", "POST",
            {"nombre": "otro_api", "contrasena": "clave123"}, cliente2,
        )
        self.assertEqual(codigo, 201)
        gasto = self.crear_gasto(cliente1, "Secreto de demo", 15000)
        codigo, datos = self.pedir(
            "/api/gastos/" + str(gasto["id"]), cliente=cliente2
        )
        self.assertEqual(codigo, 404)

    def test_listar_gastos_y_filtro(self):
        cliente = self.iniciar_sesion()
        codigo, datos = self.pedir("/api/gastos", cliente=cliente)
        self.assertEqual(codigo, 200)
        self.assertGreaterEqual(len(datos), 3)

        codigo, filtrados = self.pedir("/api/gastos?filtro=libro", cliente=cliente)
        self.assertEqual(codigo, 200)
        self.assertEqual(len(filtrados), 1)
        self.assertEqual(filtrados[0]["descripcion"], "Libro de programación")

    def test_crear_y_obtener(self):
        cliente = self.iniciar_sesion()
        gasto = self.crear_gasto(cliente, "Entradas de museo", 14000)
        codigo, obtenido = self.pedir(
            "/api/gastos/" + str(gasto["id"]), cliente=cliente
        )
        self.assertEqual(codigo, 200)
        self.assertEqual(obtenido, gasto)
        self.pedir("/api/gastos/" + str(gasto["id"]), "DELETE", cliente=cliente)

    def test_crear_invalido_devuelve_400(self):
        cliente = self.iniciar_sesion()
        codigo, datos = self.pedir(
            "/api/gastos",
            "POST",
            {
                "descripcion": "Gasto malo",
                "monto": -5,
                "categoria": "comida",
                "fecha": "2026-11-26",
            },
            cliente,
        )
        self.assertEqual(codigo, 400)
        self.assertIn("monto", datos["error"])

    def test_json_mal_formado_devuelve_400(self):
        cliente = self.iniciar_sesion()
        solicitud = urllib.request.Request(
            self.base_url + "/api/gastos",
            data=b"{no es json",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as contexto:
            cliente.open(solicitud, timeout=5)
        self.assertEqual(contexto.exception.code, 400)

    def test_actualizar_y_eliminar(self):
        cliente = self.iniciar_sesion()
        gasto = self.crear_gasto(cliente, "Alquiler de bici", 10000)
        id_gasto = gasto["id"]
        codigo, actualizado = self.pedir(
            "/api/gastos/" + str(id_gasto),
            "PUT",
            {
                "descripcion": "Alquiler de bici",
                "monto": 18500,
                "categoria": "transporte",
                "fecha": "2026-11-26",
            },
            cliente,
        )
        self.assertEqual(codigo, 200)
        self.assertEqual(actualizado["monto"], 18500)

        codigo, mensaje = self.pedir(
            "/api/gastos/" + str(id_gasto), "DELETE", cliente=cliente
        )
        self.assertEqual(codigo, 200)
        self.assertIn("eliminado", mensaje["mensaje"].lower())

        codigo, datos = self.pedir(
            "/api/gastos/" + str(id_gasto), cliente=cliente
        )
        self.assertEqual(codigo, 404)
        self.assertIn("error", datos)

    def test_no_encontrado(self):
        cliente = self.iniciar_sesion()
        codigo, datos = self.pedir("/api/gastos/99999", cliente=cliente)
        self.assertEqual(codigo, 404)

        codigo, datos = self.pedir("/ruta-inexistente", cliente=cliente)
        self.assertEqual(codigo, 404)

    def test_resumen(self):
        cliente = self.iniciar_sesion()
        codigo, datos = self.pedir("/api/resumen", cliente=cliente)
        self.assertEqual(codigo, 200)
        self.assertIn("total", datos)
        self.assertIn("por_categoria", datos)
        self.assertIn("comida", datos["por_categoria"])


if __name__ == "__main__":
    unittest.main()
