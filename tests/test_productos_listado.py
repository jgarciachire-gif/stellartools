"""Listado de productos sin inicializar config ni acceder a la base de datos."""
import ast
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Optional

from fastapi import Request
from fastapi.responses import RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.orders = []
        self.bounds = None

    def select(self, *args, **kwargs):
        return self

    def ilike(self, column, pattern):
        self.rows = [r for r in self.rows if pattern.strip('%').lower() in r[column].lower()]
        return self

    def or_(self, conditions):
        # These tests use simple text terms and no supplier matches.
        terms = [part.split('.', 2) for part in conditions.split(',')]
        self.rows = [r for r in self.rows if any(
            value.strip('%').lower() in str(r.get(column, '')).lower()
            for column, operator, value in terms if operator == 'ilike')]
        return self

    def eq(self, column, value):
        self.rows = [r for r in self.rows if r.get(column) == value]
        return self

    def order(self, column, desc=False):
        self.orders.append((column, desc))
        return self

    def range(self, first, last):
        self.bounds = (first, last)
        return self

    async def execute(self):
        rows = self.rows[:]
        for column, descending in reversed(self.orders):
            rows.sort(key=lambda r: r.get(column, ''), reverse=descending)
        count = len(rows)
        if self.bounds:
            first, last = self.bounds
            rows = rows[first:last + 1]
        return NS(data=rows, count=count)


class ProductListTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.rows = [dict(id=i, codigo_st=f'{i:06}', descripcion=f'Producto {i:03}',
                          precio=i * .5, unidad_manejo=i % 7 + 1, proveedor_id=None,
                          codigo_ean='', departamento='', grupo='', subgrupo='', marca='')
                     for i in range(1, 46)]

        async def user(*args):
            return NS(id='user')

        async def retry(function):
            return await function()

        self.env = Environment(loader=FileSystemLoader('templates'), autoescape=select_autoescape())
        self.env.globals['asset_url'] = lambda path: '/static/' + path
        env = dict(Optional=Optional, Request=Request, Cookie=lambda default: default,
                   RedirectResponse=RedirectResponse, re=re, obtener_usuario_actual=user,
                   ejecutar_supabase_con_reintento_async=retry,
                   config=NS(supabase_async=NS(table=lambda name: Query(self.rows[:] if name == 'productos' else []))),
                   templates=NS(TemplateResponse=lambda **kwargs: kwargs))
        node = next(n for n in ast.parse(Path('routes/productos.py').read_text(encoding='utf-8')).body
                    if isinstance(n, ast.AsyncFunctionDef) and n.name == 'vista_productos')
        node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'routes/productos.py', 'exec'), env)
        self.handler = env['vista_productos']

    async def request(self, query=''):
        request = Request(dict(type='http', method='GET', scheme='http', server=('test', 80),
                               path='/productos', query_string=query.encode(), headers=[]))
        request.state.perfil = None
        response = await self.handler(request=request)
        if isinstance(response, dict):
            response['context']['request'] = request
        return response

    async def test_pages_are_limited_and_do_not_overlap(self):
        first = (await self.request())['context']
        second = (await self.request('page=2'))['context']
        last = (await self.request('page=3'))['context']
        self.assertEqual([len(p['productos']) for p in [first, second, last]], [20, 20, 5])
        self.assertEqual(first['total_productos'], 45)
        self.assertEqual(first['total_paginas'], 3)
        self.assertFalse({p['id'] for p in first['productos']} & {p['id'] for p in second['productos']})

    async def test_sort_applies_before_pagination(self):
        context = (await self.request('sort=precio&dir=desc&page=2'))['context']
        self.assertEqual([p['id'] for p in context['productos']], list(range(25, 5, -1)))

    async def test_filter_count_and_selected_product_are_independent(self):
        context = (await self.request('q=045&select=1'))['context']
        self.assertEqual(context['total_productos'], 1)
        self.assertEqual(context['productos'][0]['id'], 45)
        self.assertEqual(context['prov_obj']['id'], 1)

    async def test_invalid_page_and_sort_use_defaults(self):
        context = (await self.request('page=invalid&sort=unknown&dir=invalid'))['context']
        self.assertEqual(context['pagina_actual'], 1)
        self.assertEqual(context['orden_productos'], 'descripcion')
        self.assertEqual(context['direccion_productos'], 'asc')
        self.assertEqual((await self.request('page=-10'))['context']['pagina_actual'], 1)

    async def test_out_of_range_page_redirect_preserves_filters(self):
        response = await self.request('page=99&q=045&sort=precio&dir=desc')
        self.assertEqual(response.status_code, 303)
        self.assertIn('page=1', response.headers['location'])
        self.assertIn('q=045', response.headers['location'])
        self.assertIn('sort=precio', response.headers['location'])

    async def test_empty_results_render(self):
        response = await self.request('q=missing')
        html = self.env.get_template('productos.html').render(**response['context'])
        self.assertIn('No se encontraron productos.', ' '.join(html.split()))
        self.assertIn('0 productos', ' '.join(html.split()))

    async def test_ficha_and_pagination_render_with_escaped_data(self):
        self.rows[0]['descripcion'] = '<Producto especial>'
        response = await self.request('select=1&sort=precio&dir=desc&page=2')
        html = self.env.get_template('productos.html').render(**response['context'])
        self.assertEqual(html.count('class="fila-producto '), 20)
        self.assertIn('<dialog id="modal-ficha-producto"', html)
        self.assertIn('id="form-producto-ficha"', html)
        self.assertIn('&lt;Producto especial&gt;', html)
        self.assertIn('name="page" value="2"', html)
        self.assertIn('aria-sort="descending"', html)


if __name__ == '__main__':
    unittest.main()
