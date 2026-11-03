import ast
import hashlib
import json
import threading
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace as NS

from fastapi import Request
from starlette.datastructures import URL
from starlette.concurrency import run_in_threadpool
from jinja2 import Environment, FileSystemLoader, select_autoescape

from test_ordenes_carga import handler, Response


class Query:
    def __init__(self, rows):
        self.rows, self.filters, self.bounds, self.fields, self.executions = rows, [], None, '', []

    def table(self, name):
        self.filters, self.bounds = [], None
        return self

    def select(self, fields):
        self.fields = fields
        return self

    def eq(self, name, value):
        self.filters.append((name, value))
        return self

    def order(self, *args, **kwargs):
        return self

    def range(self, start, end):
        self.bounds = (start, end)
        return self

    def limit(self, count):
        return self.range(0, count - 1)

    async def execute(self):
        rows = [r for r in self.rows if all(r.get(k) == v for k, v in self.filters)]
        if self.bounds:
            a, b = self.bounds
            rows = rows[a:b + 1]
        self.executions.append((self.fields, list(self.filters), self.bounds))
        return NS(data=rows)


class OrdenesListadoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.rows = [dict(id=i, usuario_id='user-1', numero_orden=f'OC-{i:04}', proveedor='Proveedor',
            proveedores={'nombre': 'Proveedor', 'dias_credito': 30}, tienda_destino='CENTRO' if i % 2 else 'SAN DIEGO',
            fecha_envio='2026-10-01', fecha_recepcion='2026-10-02' if i % 3 == 0 else None,
            monto_total=10, detalles_productos=[dict(codigo='001', descripcion='<script>prueba</script>',
                cantidad='1,200', pre=6, emp=200, precio_unitario=2)]) for i in range(1, 1052)]
        self.rows.append(dict(self.rows[0], id=5000, usuario_id='otra-persona'))
        self.db = Query(self.rows)
        self.template = NS(TemplateResponse=lambda **kw: kw['context'])

    async def list(self, params):
        fn, _ = handler('routes/ordenes.py', 'listar_ordenes', config=NS(supabase_async=self.db), templates=self.template, timedelta=timedelta)
        return await fn(NS(query_params=params))

    async def test_pagination_reads_all_headers_but_only_renders_20_and_no_lines(self):
        result = await self.list({'page': '53'})
        rows = [r for group in result['ordenes_agrupadas'].values() for r in group]
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[0]['id'], 1041)
        self.assertEqual(result['total_ordenes'], 1051)
        self.assertEqual(result['total_paginas'], 53)
        self.assertEqual(len(self.db.executions), 2)
        self.assertTrue(all('detalles_productos' not in fields for fields, _, _ in self.db.executions))
        self.assertTrue(all(('usuario_id', 'user-1') in filters for _, filters, _ in self.db.executions))

    async def test_filters_search_beyond_first_page_and_combine_tags_status_and_date(self):
        result = await self.list({'q': 'OC-1005', 'tags': json.dumps([{'tipo': 'tienda', 'valor': 'CENTRO'},
            {'tipo': 'estatus', 'valor': 'Recibido'}]), 'fecha': '2026-10-02'})
        self.assertEqual(result['total_ordenes'], 1)
        self.assertEqual(next(iter(result['ordenes_agrupadas'].values()))[0]['id'], 1005)

    async def test_invalid_page_and_tags_are_safe(self):
        result = await self.list({'page': 'abc', 'tags': '{', 'q': 'no existe'})
        self.assertEqual(result['total_ordenes'], 0)
        self.assertEqual(result['pagina_actual'], 1)

    async def test_detail_enforces_owner_and_handles_missing_documents(self):
        fn, _ = handler('routes/ordenes.py', 'detalle_orden_listado', config=NS(supabase_async=self.db), templates=self.template)
        self.assertEqual((await fn(5000, object())).status_code, 404)
        result = await fn(1, object())
        self.assertEqual(result['o']['id'], 1)
        self.assertIn(('usuario_id', 'user-1'), self.db.executions[-1][1])
        async def anonymous(*args): return None
        fn, _ = handler('routes/ordenes.py', 'detalle_orden_listado', obtener_usuario_actual=anonymous)
        self.assertEqual((await fn(1, object())).status_code, 401)

    async def test_templates_render_pagination_and_escape_detail(self):
        env = Environment(loader=FileSystemLoader('templates'), autoescape=select_autoescape())
        env.filters['limpiar_cantidad'] = lambda value: float(str(value).replace(',', ''))
        context = await self.list({'q': 'OC-0001'})
        context.update(request=NS(url=URL('http://test/ordenes'), state=NS(perfil={}, user=NS(id='user-1'))),
                       asset_url=lambda name: '/static/' + name)
        html = env.get_template('ordenes.html').render(**context)
        self.assertEqual(html.count('class="hover:bg-slate-50/80 transition-colors row-orden'), 1)
        self.assertNotIn('prueba&lt;', html)
        detail = env.get_template('componentes/orden_detalle.html').render(o=self.rows[0])
        self.assertIn('&lt;script&gt;', detail)
        self.assertIn('$2.400,00', detail)


class PerfilNoBloqueanteTests(unittest.IsolatedAsyncioTestCase):
    async def test_profile_and_category_queries_run_outside_event_loop_with_owner_filter(self):
        main_thread = threading.get_ident()
        calls = []
        class DB:
            def __getattr__(self, name):
                def call(*args, **kw):
                    if name == 'execute':
                        calls.append(threading.get_ident())
                        return NS(data=[])
                    if name == 'eq' and args[0] == 'usuario_id':
                        self.assert_owner = args[1]
                    return self
                return call
        db = DB()
        for name, kwargs in [('vista_perfil', {'request': object()}), ('crear_categoria', {'nombre': 'Prueba'}),
            ('actualizar_categoria', {'cat_id': 1, 'nombre': 'Cambio'}), ('eliminar_categoria', {'cat_id': 1})]:
            fn, _ = handler('routes/auth.py', name, supabase=db, run_in_threadpool=run_in_threadpool,
                            templates=NS(TemplateResponse=lambda **kw: kw))
            await fn(**kwargs)
            self.assertEqual(db.assert_owner, 'user-1')
        self.assertEqual(len(calls), 5)
        self.assertTrue(all(thread != main_thread for thread in calls))


class InventarioMigracionTests(unittest.TestCase):
    def test_extracted_blocks_retain_their_migration_checksums(self):
        for entry in json.loads(Path('tests/inventario-migracion.json').read_text()):
            with self.subTest(asset=entry['asset']):
                self.assertEqual(hashlib.sha256(Path(entry['asset']).read_text(encoding='utf-8').encode()).hexdigest(), entry['sha256'])
