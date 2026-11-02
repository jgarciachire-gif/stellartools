"""Paginación y permisos del importador, con consultas simuladas."""
import ast
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from fastapi.responses import JSONResponse
from starlette.datastructures import QueryParams


class ImporterPaginationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.rows = [dict(id=i, nombre=f'Conteo {i}', realizado_por='Ana',
                          tienda='CENTRO' if i % 2 else 'SAN DIEGO', estado='completado',
                          updated_at='2026-11-02T12:00:00', created_at='2026-11-01T12:00:00')
                     for i in range(1, 46)]
        self.rows.append(dict(self.rows[0], id=46, estado='borrador'))
        self.queries = []
        self.authenticated = True
        self.profile = {'tipo_usuario': 'normal'}
        self.request = NS(session={'perfil': self.profile}, query_params=QueryParams())
        owner = self

        class Query:
            def __init__(self):
                self.rows = owner.rows[:]
                self.orders = []
                self.bounds = None
                self.filters = []

            def select(self, fields):
                self.fields = fields
                return self

            def eq(self, key, value):
                self.filters.append((key, value))
                self.rows = [row for row in self.rows if row.get(key) == value]
                return self

            def or_(self, expression):
                if expression.startswith('and(updated_at.'):
                    start = re.search(r'updated_at.gte.([^,]+)', expression)[1]
                    end = re.search(r'updated_at.lt.([^\)]+)', expression)[1]
                    self.rows = [row for row in self.rows if start <= (row.get('updated_at') or row['created_at']) < end]
                else:
                    terms = [part.split('.', 2) for part in expression.split(',')]
                    self.rows = [row for row in self.rows if any(
                        value.strip('%').casefold() in str(row.get(key, '')).casefold()
                        for key, operator, value in terms if operator == 'ilike')]
                return self

            def order(self, key, desc=False, **kwargs):
                self.orders.append((key, desc))
                return self

            def range(self, start, end):
                self.bounds = (start, end)
                return self

            async def execute(self):
                owner.queries.append(self)
                for key, desc in reversed(self.orders):
                    self.rows.sort(key=lambda row: row.get(key) or '', reverse=desc)
                start, end = self.bounds
                return NS(data=self.rows[start:end + 1])

        async def user(*args):
            return NS(id='user') if owner.authenticated else None

        self.env = dict(Request=object, Cookie=lambda default: default, JSONResponse=JSONResponse,
                        re=re, obtener_usuario_actual=user, config=NS(supabase_async=NS(table=lambda name: Query())))
        names = {'listar_inventarios_para_analisis', 'obtener_perfil_inventario',
                 'es_usuario_provisional', 'obtener_tienda_provisional'}
        nodes = [node for node in ast.parse(Path('routes/inventario.py').read_text(encoding='utf-8')).body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
        for node in nodes:
            node.decorator_list = []
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'routes/inventario.py', 'exec'), self.env)

    async def fetch(self, **kwargs):
        return await self.env['listar_inventarios_para_analisis'](self.request, **kwargs)

    async def test_pages_are_bounded_stable_and_exclude_drafts(self):
        first = await self.fetch()
        second = await self.fetch(page=2)
        third = await self.fetch(page=3)
        self.assertEqual([len(page['inventarios']) for page in [first, second, third]], [20, 20, 5])
        self.assertEqual([page['hay_mas'] for page in [first, second, third]], [True, True, False])
        self.assertEqual([row['id'] for row in first['inventarios']], list(range(45, 25, -1)))
        self.assertFalse({row['id'] for row in first['inventarios']} & {row['id'] for row in second['inventarios']})
        self.assertEqual([query.bounds for query in self.queries], [(0, 20), (20, 40), (40, 60)])
        self.assertTrue(all('productos' not in query.fields for query in self.queries))

    async def test_filters_apply_before_pagination(self):
        self.request.query_params = QueryParams('tags=Conteo&tags=Ana')
        result = await self.fetch(tienda='CENTRO')
        self.assertEqual(len(result['inventarios']), 20)
        self.assertTrue(all(row['tienda'] == 'CENTRO' for row in result['inventarios']))
        self.assertEqual(len(self.queries), 1)
        self.request.query_params = QueryParams('tags=no-existe')
        self.assertEqual((await self.fetch())['inventarios'], [])

    async def test_exact_day_includes_creation_when_update_is_null(self):
        self.rows[0]['updated_at'] = None
        result = await self.fetch(fecha='2026-11-01')
        self.assertEqual([row['id'] for row in result['inventarios']], [1])
        self.assertEqual((await self.fetch(fecha='2026-11-03'))['inventarios'], [])

    async def test_auth_and_assigned_store_are_enforced(self):
        self.profile.update(tipo_usuario='provisional', tienda='CENTRO')
        result = await self.fetch()
        self.assertTrue(all(row['tienda'] == 'CENTRO' for row in result['inventarios']))
        self.assertIn(('tienda', 'CENTRO'), self.queries[0].filters)
        forbidden = await self.fetch(tienda='SAN DIEGO')
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(len(self.queries), 1)
        self.authenticated = False
        self.assertEqual((await self.fetch()).status_code, 401)
        self.assertEqual(len(self.queries), 1)

    async def test_invalid_filters_do_not_query_and_page_cannot_request_all_rows(self):
        invalid = await self.fetch(fecha='2026-02-31')
        self.assertEqual(invalid.status_code, 400)
        self.request.query_params = QueryParams('&'.join(['tags=a'] * 13))
        self.assertEqual((await self.fetch()).status_code, 400)
        self.assertEqual(self.queries, [])
        self.request.query_params = QueryParams()
        await self.fetch(page=-1)
        self.assertEqual(self.queries[-1].bounds, (0, 20))


if __name__ == '__main__':
    unittest.main()
