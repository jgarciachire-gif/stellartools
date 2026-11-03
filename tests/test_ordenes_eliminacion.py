"""Comprueba el alcance de la eliminación sin acceder a datos reales."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from fastapi.responses import JSONResponse


class OrderDeletionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.rows = [dict(id=1, usuario_id='actual'), dict(id=2, usuario_id='actual'),
                     dict(id=3, usuario_id='otro'), dict(id=4, usuario_id='actual')]
        self.authenticated = True
        self.calls = []
        owner = self

        class Query:
            def __init__(self):
                self.ids = []
                self.user_id = None

            def delete(self):
                return self

            def in_(self, column, ids):
                assert column == 'id'
                self.ids = ids
                return self

            def eq(self, column, value):
                assert column == 'usuario_id'
                self.user_id = value
                return self

            async def execute(self):
                owner.calls.append((self.ids, self.user_id))
                owner.rows[:] = [row for row in owner.rows if not (row['id'] in self.ids and row['usuario_id'] == self.user_id)]
                return NS(data=[])

        async def user(*args):
            return NS(id='actual') if owner.authenticated else None

        env = dict(Request=object, Cookie=lambda default: default, JSONResponse=JSONResponse,
                   obtener_usuario_actual=user, config=NS(supabase_async=NS(table=lambda name: Query())))
        node = next(node for node in ast.parse(Path('routes/ordenes.py').read_text(encoding='utf-8')).body
                    if isinstance(node, ast.AsyncFunctionDef) and node.name == 'eliminar_ordenes_masivo')
        node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'routes/ordenes.py', 'exec'), env)
        self.handler = env['eliminar_ordenes_masivo']

    async def delete(self, ids):
        async def body():
            return {'ids': ids}
        return await self.handler(NS(json=body))

    async def test_deletes_only_requested_orders_belonging_to_current_user(self):
        response = await self.delete([1, 3])
        self.assertTrue(response['success'])
        self.assertEqual([row['id'] for row in self.rows], [2, 3, 4])
        self.assertEqual(self.calls, [([1, 3], 'actual')])

    async def test_no_session_does_not_delete(self):
        self.authenticated = False
        response = await self.delete([1, 2, 4])
        self.assertEqual(response.status_code, 401)
        self.assertEqual(len(self.rows), 4)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
