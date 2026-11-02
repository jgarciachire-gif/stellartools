"""Avisos de borradores: permisos, tienda impuesta y actualización de estados."""
import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from fastapi.responses import JSONResponse, RedirectResponse


class DraftNotificationsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.rows = [dict(id=i, nombre=f'Documento {i}', tienda=store, estado=status,
                          usuario_creador_id=creator, realizado_por=creator, created_at=f'2026-11-{i:02}')
                     for i, (store, status, creator) in enumerate([
                         ('CENTRO', 'borrador', 'provisional'), ('CENTRO', 'borrador', 'admin'),
                         ('CENTRO', 'borrador', 'normal'), ('GARIBALDI', 'borrador', 'normal'),
                         ('CENTRO', 'completado', 'provisional'), ('CENTRO', 'Borrador', 'another-provisional')], 1)]
        self.queries = []
        self.leak_rows = False
        self.profile = {'tipo_usuario': 'provisional', 'tienda': 'CENTRO'}
        self.request = NS(session={'perfil': self.profile}, query_params={'tienda': 'GARIBALDI'})
        owner = self
        class Query:
            def __init__(self): self.filters = []; self.bounds = (0, 999)
            def select(self, *args): return self
            def eq(self, key, value): self.filters.append(('eq', key, value)); return self
            def ilike(self, key, value): self.filters.append(('ilike', key, value)); return self
            def order(self, *args, **kwargs): return self
            def range(self, start, end): self.bounds = (start, end); return self
            async def execute(self):
                owner.queries.append(self.filters)
                rows = owner.rows[:]
                if not owner.leak_rows:
                    for op, key, value in self.filters:
                        rows = [r for r in rows if (str(r[key]).lower() == value.lower() if op == 'ilike' else r[key] == value)]
                return NS(data=rows[self.bounds[0]:self.bounds[1] + 1])
        async def user(*args): return NS(id='provisional')
        self.env = dict(Request=object, Cookie=lambda value: value, JSONResponse=JSONResponse,
                        obtener_usuario_actual=user, config=NS(supabase_async=NS(table=lambda name: Query())))
        names = {'obtener_perfil_inventario', 'es_usuario_provisional', 'obtener_tienda_provisional',
                 'notificaciones_inventarios_provisionales'}
        nodes = [n for n in ast.parse(Path('routes/inventario.py').read_text(encoding='utf-8')).body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
        for node in nodes: node.decorator_list = []
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'routes/inventario.py', 'exec'), self.env)

    async def fetch(self):
        return await self.env['notificaciones_inventarios_provisionales'](self.request)

    async def test_includes_own_and_all_other_creators_only_in_assigned_store(self):
        response = await self.fetch()
        body = json.loads(response.body)
        self.assertEqual({d['documento_id'] for d in body['notificaciones']}, {1, 2, 3, 6})
        self.assertEqual(body['total'], 4)
        self.assertTrue(all(d['tienda'] == 'CENTRO' for d in body['notificaciones']))
        self.assertFalse(next(d for d in body['notificaciones'] if d['documento_id'] == 1)['creado_por_otro'])
        self.assertTrue(next(d for d in body['notificaciones'] if d['documento_id'] == 2)['creado_por_otro'])
        self.assertIn(('eq', 'tienda', 'CENTRO'), self.queries[0])
        self.assertFalse(any(key == 'usuario_creador_id' for op, key, value in self.queries[0]))
        self.assertEqual(response.headers['cache-control'], 'no-store')

    async def test_completed_document_disappears(self):
        self.rows[0]['estado'] = 'completado'
        body = json.loads((await self.fetch()).body)
        self.assertNotIn(1, [d['documento_id'] for d in body['notificaciones']])
        self.assertEqual(body['total'], 3)

    async def test_response_cannot_contain_other_stores_even_if_database_returns_them(self):
        self.leak_rows = True
        body = json.loads((await self.fetch()).body)
        self.assertEqual({d['documento_id'] for d in body['notificaciones']}, {1, 2, 3, 6})

    async def test_missing_store_or_wrong_role_is_forbidden_without_querying(self):
        for profile in [{'tipo_usuario': 'normal', 'tienda': 'CENTRO'},
                        {'tipo_usuario': 'administrador', 'tienda': 'CENTRO'},
                        {'tipo_usuario': 'provisional', 'tienda': None}, {}]:
            self.request.session['perfil'] = profile
            self.assertEqual((await self.fetch()).status_code, 403)
        self.assertEqual(self.queries, [])

    async def test_unauthenticated_request_is_rejected(self):
        async def nobody(*args): return None
        self.env['obtener_usuario_actual'] = nobody
        self.assertEqual((await self.fetch()).status_code, 401)
        self.assertEqual(self.queries, [])

    async def test_pagination_does_not_truncate_the_draft_count(self):
        self.rows = [dict(self.rows[0], id=i) for i in range(1, 1002)]
        body = json.loads((await self.fetch()).body)
        self.assertEqual(body['total'], 1001)
        self.assertEqual(len(self.queries), 2)

    async def test_middleware_allows_draft_alerts_but_keeps_replenishment_and_dashboard_blocked(self):
        node = next(n for n in ast.parse(Path('main.py').read_text(encoding='utf-8')).body
                    if isinstance(n, ast.AsyncFunctionDef) and n.name == 'autenticacion_y_cache_middleware')
        node.decorator_list = []
        env = dict(Request=object, RedirectResponse=RedirectResponse)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), env)
        seen = []
        async def next_handler(request): seen.append(request.url.path); return JSONResponse({'ok': True})
        request = NS(session={'user': {'id': 'provisional'}, 'perfil': self.profile}, cookies={}, state=NS())
        for path in ['/api/notificaciones/inventarios', '/api/notificaciones/reposicion', '/dashboard']:
            request.url = NS(path=path)
            response = await env['autenticacion_y_cache_middleware'](request, next_handler)
            self.assertEqual(response.status_code, 200 if path.endswith('/inventarios') else 303)
        self.assertEqual(seen, ['/api/notificaciones/inventarios'])


if __name__ == '__main__':
    unittest.main()
