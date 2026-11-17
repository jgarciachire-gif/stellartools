"""Comprueba el formulario HTTP y los datos enviados al RPC de Supabase."""
import importlib.util
import io
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from openpyxl import Workbook


class ImportacionProductosTests(unittest.TestCase):
    def setUp(self):
        config = ModuleType("config")
        config.templates = Mock()
        config.obtener_usuario_actual = AsyncMock(return_value=SimpleNamespace(id="usuario"))
        config.script_alerta_modal = Mock(return_value=RedirectResponse("/productos", status_code=303))
        config.supabase_async = self.db = Mock()
        self.auth = config.obtener_usuario_actual
        self.guardar = self.db.rpc.return_value.execute = AsyncMock(return_value=SimpleNamespace(data={
            "creados": 0, "actualizados": 1, "sin_cambios": 0, "omitidos": 0,
        }))
        modelos = ModuleType("models")
        modelos.CodigosProductosRequest = dict
        ruta = Path(__file__).resolve().parents[1] / "routes/productos.py"
        spec = importlib.util.spec_from_file_location("productos_importacion_prueba", ruta)
        modulo = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"config": config, "models": modelos}):
            spec.loader.exec_module(modulo)

        self.logger = modulo.logger
        app = FastAPI()
        app.include_router(modulo.router)
        self.cliente = self.enterContext(TestClient(app, follow_redirects=False))

    def importar(self, contenido, nombre="lista.csv", ajax=True):
        headers = {"Accept": "application/json"} if ajax else {}
        return self.cliente.post(
            "/productos/cargar-lista", headers=headers, files={"archivo": (nombre, contenido)},
        )

    def producto_enviado(self):
        nombre, argumentos = self.db.rpc.call_args.args
        self.assertEqual(nombre, "importar_productos_masivo")
        return argumentos["p_productos"][0]

    def test_csv_encabezados_en_cualquier_orden_y_costo_cero(self):
        respuesta = self.importar("CostoActual;Descripción;Código;Ignorar\n0;;000123;x\n".encode("utf-8-sig"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["resumen"]["actualizados"], 1)
        producto = self.producto_enviado()
        self.assertEqual(producto["codigo_st"], "000123")
        self.assertEqual(producto["precio_nuevo"], 0)
        self.assertIsNone(producto["descripcion"])
        self.assertIsNone(producto["unidad_manejo"])
        self.db.table.assert_not_called()

    def test_xlsx_y_xml_parciales(self):
        libro = Workbook()
        libro.active.append(["UM", "CodigoDelProducto"])
        libro.active.append([12, "000123"])
        archivo = io.BytesIO()
        libro.save(archivo)
        xml = b"<Productos><Producto><um>12</um><codigo>000123</codigo></Producto></Productos>"
        for contenido, nombre in ((archivo.getvalue(), "lista.xlsx"), (xml, "lista.xml")):
            with self.subTest(nombre=nombre):
                respuesta = self.importar(contenido, nombre)
                self.assertEqual(respuesta.status_code, 200)
                producto = self.producto_enviado()
                self.assertEqual(producto["codigo_st"], "000123")
                self.assertEqual(producto["unidad_manejo"], 12)
                self.assertIsNone(producto["precio_nuevo"])

    def test_encabezados_invalidos_y_archivo_ausente_no_guardan(self):
        for contenido in (b"descripcion,costo\nTexto,1\n", b"codigo,precio,costo\n123,1,2\n", b"codigo\n123\n"):
            with self.subTest(contenido=contenido):
                respuesta = self.importar(contenido)
                self.assertEqual(respuesta.status_code, 422)
                self.assertFalse(respuesta.json()["ok"])
        respuesta = self.cliente.post("/productos/cargar-lista", headers={"Accept": "application/json"})
        self.assertEqual(respuesta.status_code, 422)
        self.assertFalse(respuesta.json()["ok"])
        self.db.rpc.assert_not_called()

    def test_advertencia_conserva_el_campo_invalido_y_detalla_la_fila(self):
        respuesta = self.importar("codigo,descripcion,um\n123,Texto,0\n")
        self.assertEqual(respuesta.json()["tipo"], "warning")
        self.assertIn("Fila 2", respuesta.json()["advertencias"][0])
        self.assertIsNone(self.producto_enviado()["unidad_manejo"])

    def test_proveedor_por_nombre_se_consulta_en_multiples_paginas(self):
        consulta = self.db.table.return_value.select.return_value.order.return_value
        consulta.range.return_value.execute = AsyncMock(side_effect=[
            SimpleNamespace(data=[{"id": 1, "nombre": "Otro"}]),
            SimpleNamespace(data=[{"id": 2, "nombre": "Mi proveedor"}]),
            SimpleNamespace(data=[]),
        ])
        respuesta = self.importar("codigo,proveedor\n123,MI PROVEEDOR\n")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.producto_enviado()["proveedor_id"], 2)
        self.assertEqual(consulta.range.call_count, 3)

    def test_fallo_de_guardado_reporta_incertidumbre_sin_reintentar(self):
        self.guardar.side_effect = RuntimeError("detalle interno")
        with self.assertLogs(self.logger, level="ERROR"):
            respuesta = self.importar("codigo,descripcion\n123,Texto\n")
        self.assertEqual(respuesta.status_code, 503)
        self.assertTrue(respuesta.json()["resultado_incierto"])
        self.assertNotIn("detalle interno", respuesta.text)
        self.guardar.assert_awaited_once()

    def test_sesion_vencida_no_guarda_y_conserva_redireccion_html(self):
        self.auth.return_value = None
        contenido = "codigo,descripcion\n123,Texto\n"
        self.assertEqual(self.importar(contenido).status_code, 401)
        respuesta = self.importar(contenido, ajax=False)
        self.assertEqual(respuesta.status_code, 303)
        self.assertEqual(respuesta.headers["location"], "/login")
        self.db.rpc.assert_not_called()
