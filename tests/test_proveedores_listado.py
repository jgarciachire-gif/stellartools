"""Paginación y ficha de proveedores sin acceso a servicios externos."""
import ast
import unicodedata
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace as NS

from fastapi import Request
from fastapi.responses import RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from test_productos_listado import Query
from fakes_listados import ListadosRPC


class SupplierListTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.rows = [dict(id=i, codigo=f'{i:06}', nombre=f'Proveedor {i:03}',
                          contacto=f'Atención {i:03}', telefono=f'0414-{i:07}',
                          email=f'contacto{i}@example.com', categorias=['Lácteos'] if i % 2 else ['Víveres'])
                     for i in range(1, 46)]

        async def user(*args):
            return NS(id='user')

        async def database():
            return self.client

        self.client = ListadosRPC(lambda: self.rows, user_id='user')
        self.client.table = lambda name: Query([])

        self.env = Environment(loader=FileSystemLoader('templates'), autoescape=select_autoescape())
        self.env.globals['asset_url'] = lambda path: '/static/' + path
        env = dict(Request=Request, Cookie=lambda value: value,
                   RedirectResponse=RedirectResponse, unicodedata=unicodedata,
                   obtener_usuario_actual=user, _db=database,
                   templates=NS(TemplateResponse=lambda **kwargs: kwargs))
        node = next(n for n in ast.parse(Path('routes/proveedores.py').read_text(encoding='utf-8')).body
                    if isinstance(n, ast.AsyncFunctionDef) and n.name == 'vista_proveedores')
        node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'routes/proveedores.py', 'exec'), env)
        self.handler = env['vista_proveedores']

    async def request(self, query='', selected=None):
        request = Request(dict(type='http', method='GET', scheme='http', server=('test', 80),
                               path='/proveedores', query_string=query.encode(), headers=[]))
        request.state.perfil = None
        response = await self.handler(request=request, select=selected)
        if isinstance(response, dict):
            response['context']['request'] = request
        return response

    async def test_pages_are_limited_and_do_not_overlap(self):
        pages = [(await self.request(f'page={number}'))['context'] for number in [1, 2, 3]]
        self.assertEqual([len(p['proveedores']) for p in pages], [20, 20, 5])
        self.assertEqual(pages[0]['total_proveedores'], 45)
        ids = [p['id'] for page in pages for p in page['proveedores']]
        self.assertEqual(len(set(ids)), 45)
        self.assertEqual(len(self.client.rpc_calls), 3)

    async def test_sort_applies_before_pagination(self):
        context = (await self.request('page=2&sort=nombre&dir=desc'))['context']
        self.assertEqual([p['id'] for p in context['proveedores']], list(range(25, 5, -1)))

    async def test_badges_match_categories_accents_and_all_contact_fields(self):
        for term, expected in [('lacteos', 23), ('atencion', 45), ('0414', 45),
                               ('contacto45@example.com', 1), ('000045', 1), ('Proveedor', 45)]:
            with self.subTest(term=term):
                context = (await self.request(f'tags={term}'))['context']
                self.assertEqual(context['total_proveedores'], expected)
        context = (await self.request('tags=lacteos,045'))['context']
        self.assertEqual([p['id'] for p in context['proveedores']], [45])

    async def test_selected_supplier_is_available_outside_filtered_page(self):
        context = (await self.request('tags=000045', selected=1))['context']
        self.assertEqual(context['proveedores'][0]['id'], 45)
        self.assertEqual(context['prov_obj']['id'], 1)

    async def test_invalid_and_out_of_range_pages(self):
        context = (await self.request('page=invalid&sort=unknown&dir=invalid'))['context']
        self.assertEqual(context['pagina_actual'], 1)
        self.assertEqual(context['orden_proveedores'], 'nombre')
        response = await self.request('tags=000045&page=99')
        self.assertEqual(response.status_code, 303)
        self.assertIn('page=1', response.headers['location'])
        self.assertIn('tags=000045', response.headers['location'])

    async def test_oversized_page_and_selection_are_bounded_before_rpc(self):
        response = await self.request('page=99999999999999999999999', selected=2**60)
        self.assertEqual(response.status_code, 303)
        name, params = self.client.rpc_calls[-1]
        self.assertEqual(name, 'st_listar_proveedores')
        self.assertEqual(params['p_pagina'], 2147483647)
        self.assertIsNone(params['p_seleccion'])

    async def test_directory_larger_than_api_limit_is_not_truncated(self):
        self.rows = [dict(self.rows[0], id=i, nombre=f'Proveedor {i:04}') for i in range(1, 1026)]
        context = (await self.request('page=52'))['context']
        self.assertEqual(context['total_proveedores'], 1025)
        self.assertEqual(len(context['proveedores']), 5)

    async def test_template_contains_dialog_and_five_columns_with_unique_ids(self):
        response = await self.request('page=2&sort=email&dir=desc', selected=1)
        html = self.env.get_template('proveedores.html').render(**response['context'])
        class Page(HTMLParser):
            ids = []
            def handle_starttag(self, tag, attrs):
                self.ids.extend(value for key, value in attrs if key == 'id')
        page = Page()
        page.feed(html)
        self.assertFalse([key for key, count in Counter(page.ids).items() if count > 1])
        self.assertIn('<dialog id="modal-ficha-proveedor"', html)
        self.assertEqual(html.count('class="fila-proveedor '), 20)
        self.assertEqual(html.count('<th scope="col"'), 5)
        self.assertIn('id="form-proveedor-ficha"', html)
        self.assertIn('name="page" value="2"', html)

    async def test_empty_results_keep_edit_helpers_available(self):
        response = await self.request('tags=missing')
        html = self.env.get_template('proveedores.html').render(**response['context'])
        self.assertIn('No se encontraron proveedores.', ' '.join(html.split()))
        self.assertIn('function habilitarEdicion()', html)
        self.assertIn('function sincronizarCategoriasSubmit(', html)

    async def test_ficha_preserves_zero_days_and_legacy_search_filters(self):
        self.rows[0]['dias_despacho'] = 0
        self.rows[0]['dias_credito'] = None
        response = await self.request('q=lacteos', selected=1)
        html = self.env.get_template('proveedores.html').render(**response['context'])
        self.assertIn('name="dias_despacho" value="0"', html)
        self.assertIn('name="dias_credito" value="0"', html)
        self.assertIn('name="tags" value="lacteos"', html)


if __name__ == '__main__':
    unittest.main()
