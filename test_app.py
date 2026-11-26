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

    def test_iniciar_db_carga_tres_ejemplos(self):
        gastos = services.listar()
        self.assertEqual(len(gastos), 3)
        self.assertTrue(all("id" in gasto for gasto in gastos))

        # Una segunda llamada no debe duplicar los ejemplos.
        database.iniciar_db()
        self.assertEqual(len(services.listar()), 3)

    def test_crear_y_obtener(self):
        gasto = services.crear("Curso de Python", 45500, "estudio", "2026-11-25")
        self.assertIsInstance(gasto["id"], int)
        self.assertEqual(gasto["descripcion"], "Curso de Python")
        self.assertEqual(gasto["monto"], 45500)
        self.assertEqual(gasto["categoria"], "estudio")
        self.assertEqual(gasto["fecha"], "2026-11-25")
        self.assertEqual(services.obtener(gasto["id"]), gasto)

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
                    services.crear(*datos)

    def test_listar_con_filtro(self):
        services.crear("Café con leche", 3200, "comida", "2026-11-24")
        services.crear("Peaje", 5000, "transporte", "2026-11-24")
        resultados = services.listar("café")
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["descripcion"], "Café con leche")
        self.assertEqual(len(services.listar()), 5)

    def test_actualizar(self):
        gasto = services.crear("Cine", 9000, "ocio", "2026-11-23")
        actualizado = services.actualizar(gasto["id"], "Cine 3D", 12000, "ocio", "2026-11-24")
        self.assertEqual(actualizado["descripcion"], "Cine 3D")
        self.assertEqual(actualizado["monto"], 12000)
        self.assertEqual(actualizado["fecha"], "2026-11-24")

        with self.assertRaises(LookupError):
            services.actualizar(9999, "Cine", 9000, "ocio", "2026-11-23")

    def test_eliminar(self):
        gasto = services.crear("Taxi", 15000, "transporte", "2026-11-22")
        services.eliminar(gasto["id"])
        with self.assertRaises(LookupError):
            services.obtener(gasto["id"])
        with self.assertRaises(LookupError):
            services.eliminar(gasto["id"])

    def test_resumen(self):
        services.crear("Cuaderno", 20000, "estudio", "2026-11-25")
        resumen = services.resumen()
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

    def pedir(self, ruta, metodo="GET", cuerpo=None):
        """Hace una petición y devuelve (código, datos_json)."""
        contenido = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
        solicitud = urllib.request.Request(
            self.base_url + ruta,
            data=contenido,
            method=metodo,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(solicitud, timeout=5) as respuesta:
                return respuesta.status, json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def crear_gasto(self, descripcion="Prueba API", monto=7250):
        codigo, gasto = self.pedir(
            "/api/gastos",
            "POST",
            {
                "descripcion": descripcion,
                "monto": monto,
                "categoria": "otros",
                "fecha": "2026-11-26",
            },
        )
        self.assertEqual(codigo, 201)
        return gasto

    def test_salud(self):
        codigo, datos = self.pedir("/api/salud")
        self.assertEqual(codigo, 200)
        self.assertEqual(datos["estado"], "ok")

    def test_listar_gastos_y_filtro(self):
        codigo, datos = self.pedir("/api/gastos")
        self.assertEqual(codigo, 200)
        self.assertGreaterEqual(len(datos), 3)

        codigo, filtrados = self.pedir("/api/gastos?filtro=libro")
        self.assertEqual(codigo, 200)
        self.assertEqual(len(filtrados), 1)
        self.assertEqual(filtrados[0]["descripcion"], "Libro de programación")

    def test_crear_y_obtener(self):
        gasto = self.crear_gasto("Entradas de museo", 14000)
        codigo, obtenido = self.pedir("/api/gastos/" + str(gasto["id"]))
        self.assertEqual(codigo, 200)
        self.assertEqual(obtenido, gasto)
        self.pedir("/api/gastos/" + str(gasto["id"]), "DELETE")

    def test_crear_invalido_devuelve_400(self):
        codigo, datos = self.pedir(
            "/api/gastos",
            "POST",
            {
                "descripcion": "Gasto malo",
                "monto": -5,
                "categoria": "comida",
                "fecha": "2026-11-26",
            },
        )
        self.assertEqual(codigo, 400)
        self.assertIn("monto", datos["error"])

    def test_json_mal_formado_devuelve_400(self):
        solicitud = urllib.request.Request(
            self.base_url + "/api/gastos",
            data=b"{no es json",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as contexto:
            urllib.request.urlopen(solicitud, timeout=5)
        self.assertEqual(contexto.exception.code, 400)

    def test_actualizar_y_eliminar(self):
        gasto = self.crear_gasto("Alquiler de bici", 10000)
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
        )
        self.assertEqual(codigo, 200)
        self.assertEqual(actualizado["monto"], 18500)

        codigo, mensaje = self.pedir("/api/gastos/" + str(id_gasto), "DELETE")
        self.assertEqual(codigo, 200)
        self.assertIn("eliminado", mensaje["mensaje"].lower())

        codigo, datos = self.pedir("/api/gastos/" + str(id_gasto))
        self.assertEqual(codigo, 404)
        self.assertIn("error", datos)

    def test_no_encontrado(self):
        codigo, datos = self.pedir("/api/gastos/99999")
        self.assertEqual(codigo, 404)

        codigo, datos = self.pedir("/ruta-inexistente")
        self.assertEqual(codigo, 404)

    def test_resumen(self):
        codigo, datos = self.pedir("/api/resumen")
        self.assertEqual(codigo, 200)
        self.assertIn("total", datos)
        self.assertIn("por_categoria", datos)
        self.assertIn("comida", datos["por_categoria"])


if __name__ == "__main__":
    unittest.main()
