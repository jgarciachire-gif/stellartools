"""Pruebas del flujo sin inicializar config ni conectarse a la base de datos.

Se compilan los handlers reales con sus dependencias externas simuladas.
Ejecutar: python -m unittest discover -s tests -v
"""
import ast
import io
import json
import math
import re
import traceback
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS
from typing import List, Optional


class Response:
    def __init__(self, content=None, status_code=200, **kwargs):
        self.content = content
        self.status_code = status_code


class Database:
    def __init__(self, failure=None):
        self.calls = []
        self.failure = failure

    def rpc(self, name, params):
        self.calls.append((name, params))
        return self

    def table(self, name):
        self.calls.append((name, None))
        return self

    def __getattr__(self, name):
        return lambda *args, **kwargs: self

    async def execute(self):
        if self.failure:
            raise self.failure
        return NS(data=[{"id": 1}]) if self.calls[-1][0] == 'crear_orden_completa' else NS(data=[])


def handler(path, name, **overrides):
    node = next(n for n in ast.parse(Path(path).read_text(encoding='utf-8')).body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    node.decorator_list = []

    async def user(*args):
        return NS(id='user-1')

    env = dict(Request=object, UploadFile=object, List=List, Optional=Optional,
               Form=lambda default=None: default, Cookie=lambda default=None: default,
               File=lambda default=None: default, JSONResponse=Response,
               RedirectResponse=Response, obtener_usuario_actual=user,
               json=json, math=math, datetime=datetime, traceback=traceback, io=io, re=re)
    env.update(overrides)
    exec(compile(ast.Module(body=[node], type_ignores=[]), path, 'exec'), env)
    return env[name], env


class CrearOrdenTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = Database()
        self.save, self.env = handler('routes/ordenes.py', 'crear_orden', config=NS(supabase_async=self.db))
        self.valid = dict(request=object(), numero_orden='OC-1', proveedor='Proveedor', tienda_destino='Tienda',
                          monto_total='1234.56', fecha_emision='2026-10-30', fecha_envio='', dias_inventario='15',
                          productos_json=json.dumps([{'codigo': '123456', 'cantidad': 6, 'emp': 2, 'pre': 3, 'precio_unitario': 2.5}]))

    async def test_guardado_atomico_y_decimales(self):
        result = await self.save(**self.valid)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(self.db.calls), 1)
        name, params = self.db.calls[0]
        self.assertEqual(name, 'crear_orden_completa')
        self.assertEqual(params['p_monto_total'], 1234.56)
        self.assertEqual(params['p_fecha_envio'], '2026-10-30')
        self.assertEqual(params['p_productos'][0]['cantidad'], 6)

    async def test_datos_invalidos_no_escriben(self):
        cases = [('numero_orden', '  '), ('proveedor', ''), ('tienda_destino', ''),
                 ('monto_total', 'NaN'), ('monto_total', 'Infinity'), ('monto_total', '-1'),
                 ('monto_total', 'abc'), ('dias_inventario', '1.5'), ('dias_inventario', '100'),
                 ('dias_inventario', '0'), ('fecha_emision', ''), ('fecha_emision', '2026-02-30'),
                 ('fecha_envio', 'bad'), ('productos_json', 'invalid'), ('productos_json', '{}'),
                 ('productos_json', '[]'), ('productos_json', '[null]'),
                 ('productos_json', '[{"cantidad": 1}]'),
                 ('productos_json', '[{"codigo":"1", "cantidad": -1}]'),
                 ('productos_json', '[{"codigo":"1", "precio_unitario": "nan"}]')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                result = await self.save(**(self.valid | {field: value}))
                self.assertEqual(result.status_code, 422)
                self.assertEqual(self.db.calls, [])

    async def test_sesion_expirada(self):
        async def no_user(*args):
            return None
        self.env['obtener_usuario_actual'] = no_user
        result = await self.save(**self.valid)
        self.assertEqual(result.status_code, 401)
        self.assertEqual(self.db.calls, [])

    async def test_duplicada_y_error_de_base_de_datos(self):
        for failure, expected in [(Exception('ya se encuentra registrada'), 409),
                                  (Exception('secret database internal detail'), 500)]:
            with self.subTest(status=expected):
                self.db.failure = failure
                result = await self.save(**self.valid)
                self.assertEqual(result.status_code, expected)
                self.assertNotIn('secret database', result.content['mensaje'])


class Upload:
    def __init__(self, name, content=b'%PDF-1.7 valid'):
        self.filename, self.content = name, content

    async def read(self, size):
        return self.content[:size]


class OrdenesSinPagosTests(unittest.IsolatedAsyncioTestCase):
    async def test_actualizar_recepcion_conserva_vencimiento_sin_marcar_pagos(self):
        class FechaDatabase(Database):
            def update(self, values):
                self.values = values
                return self

            async def execute(self):
                return NS(data=[{'proveedores': {'dias_credito': 30}}])

        for reception, expected in [('2026-10-30', '29/11/2026'), ('', '')]:
            with self.subTest(reception=reception):
                db = FechaDatabase()
                update, _ = handler('routes/ordenes.py', 'actualizar_orden',
                    config=NS(supabase_async=db), timedelta=timedelta)
                response = await update(1, NS(headers={'accept': 'application/json'}), '2026-10-29', reception)
                self.assertEqual(response['vencimiento_factura_str'], expected)
                self.assertEqual(set(response), {'status', 'estatus', 'vencimiento_factura_str'})
                self.assertNotIn('pagada', db.values)
                self.assertTrue(all(name == 'ordenes_compra' for name, _ in db.calls))

    async def test_listado_conserva_vencimiento_y_no_expone_alertas(self):
        class ListaDatabase(Database):
            def select(self, fields):
                self.fields = fields
                return self

            async def execute(self):
                return NS(data=[{'id': 1, 'fecha_envio': '2026-10-29', 'fecha_recepcion': '2026-10-30',
                    'proveedores': {'nombre': 'Proveedor', 'dias_credito': 30}, 'detalles_productos': []}])

        db = ListaDatabase()
        listing, _ = handler('routes/ordenes.py', 'listar_ordenes', config=NS(supabase_async=db),
            timedelta=timedelta, templates=NS(TemplateResponse=lambda **kwargs: kwargs['context']))
        result = await listing(object())
        order = result['ordenes_agrupadas']['Octubre 2026'][0]
        self.assertEqual(order['vencimiento_factura_str'], '29/11/2026')
        self.assertEqual(order['estatus'], 'Despacho Recibido')
        self.assertNotIn('pagada', db.fields)
        self.assertNotIn('alerta_text', order)
        self.assertNotIn('alerta_color', order)


class ProcesarPDFTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = Database()
        self.extracted = []

        async def extract(function, stream):
            self.extracted.append(stream.getvalue())
            if b'corrupt' in stream.getvalue():
                return {'error_extraccion': 'PDF dañado'}
            if b'empty' in stream.getvalue():
                return {'productos': []}
            if b'invalid-numbers' in stream.getvalue():
                return {'productos': [{'codigo': '123456', 'descripcion': 'Producto', 'cantidad': 2, 'precio_unitario': 'nan'}]}
            return {'numero_orden': 'OC-1', 'proveedor': 'Proveedor', 'productos': [
                {'codigo': '123456', 'descripcion': 'Producto', 'cantidad': 2, 'precio_unitario': 3}
            ]}

        self.process, self.env = handler('routes/escanear.py', 'procesar_pdf',
            config=NS(supabase_async=self.db), run_in_threadpool=extract,
            extraer_datos_oc=object(), sanitizar_numero=float)
        self.request = NS(headers={'accept': 'application/json'})

    async def test_exito_parcial(self):
        result = await self.process(self.request, [Upload('ok.pdf'), Upload('bad.pdf', b'%PDF-corrupt'),
            Upload('scan.pdf', b'%PDF-empty'), Upload('other.txt'), Upload('fake.pdf', b'not pdf')])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.content['ordenes']), 1)
        self.assertEqual(len(result.content['errores']), 4)
        self.assertEqual(result.content['ordenes'][0]['monto_total'], 6)

    async def test_cero_resultados(self):
        result = await self.process(self.request, [Upload('scan.pdf', b'%PDF-empty')])
        self.assertEqual(result.status_code, 422)
        self.assertFalse(result.content['success'])
        self.assertEqual(self.db.calls, [])

    async def test_error_al_preparar_una_orden_no_pierde_las_demas(self):
        result = await self.process(self.request, [Upload('ok.pdf'), Upload('bad.pdf', b'%PDF-invalid-numbers')])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.content['ordenes']), 1)
        self.assertEqual(len(result.content['errores']), 1)

    async def test_limites(self):
        for files, expected in [([], 400), ([Upload('a.pdf')] * 21, 400),
                                ([Upload('a.pdf', b'x' * (4 * 1024 * 1024 + 1))], 413)]:
            with self.subTest(status=expected, count=len(files)):
                result = await self.process(self.request, files)
                self.assertEqual(result.status_code, expected)
                self.assertEqual(self.extracted, [])
                self.assertEqual(self.db.calls, [])

    async def test_catalogo_no_disponible_conserva_extraccion(self):
        self.db.failure = Exception('unavailable')
        result = await self.process(self.request, [Upload('a.pdf')])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.content['ordenes']), 1)
        self.assertEqual(len(result.content['advertencias']), 2)

    async def test_sesion_expirada(self):
        async def no_user(*args):
            return None
        self.env['obtener_usuario_actual'] = no_user
        result = await self.process(self.request, [Upload('a.pdf')])
        self.assertEqual(result.status_code, 401)
        self.assertEqual(self.extracted, [])


if __name__ == '__main__':
    unittest.main()
