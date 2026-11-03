"""Exercise asset/session/cache isolation without config or database access."""
import ast
import gzip
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from starlette.middleware.gzip import GZipMiddleware

from middleware_recursos import SesionesSinRecursosEstaticos


class RecursosTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        Path(self.temp.name, 'app.js').write_text('const example = 1;\n' * 500)
        app = FastAPI()
        app.mount('/static', StaticFiles(directory=self.temp.name))
        tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                    and n.name == 'autenticacion_y_cache_middleware')
        env = dict(app=app, Request=Request, RedirectResponse=RedirectResponse)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), env)

        @app.get('/login')
        async def login(request: Request):
            request.session['user'] = {'id': 'test'}
            return HTMLResponse('login')

        @app.get('/privado')
        async def privado(request: Request):
            return HTMLResponse(request.session['user']['id'] * 1000)

        @app.get('/service-worker.js')
        async def worker():
            return HTMLResponse('worker')

        app.add_middleware(SesionesSinRecursosEstaticos, secret_key='test-only')
        app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_versioned_asset_is_compressed_and_has_no_session_cookie(self):
        self.client.get('/login')
        with self.client.stream('GET', '/static/app.js?v=deploy-abc-123') as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn('immutable', response.headers['cache-control'])
            self.assertNotIn('set-cookie', response.headers)
            self.assertEqual(response.headers['content-encoding'], 'gzip')
            raw = b''.join(response.iter_raw())
        original = Path(self.temp.name, 'app.js').read_bytes()
        self.assertEqual(gzip.decompress(raw), original)
        self.assertLess(len(raw), len(original))

    def test_unversioned_assets_and_worker_revalidate(self):
        response = self.client.get('/static/app.js')
        self.assertIn('must-revalidate', response.headers['cache-control'])
        cached = self.client.get('/static/app.js', headers={'If-None-Match': response.headers['etag']})
        self.assertEqual(cached.status_code, 304)
        self.assertEqual(self.client.get('/service-worker.js').headers['cache-control'], 'no-cache')

    def test_missing_assets_are_not_cached(self):
        response = self.client.get('/static/missing.js?v=abc')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_private_pages_still_require_session_and_are_not_cached(self):
        response = self.client.get('/privado', follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn('set-cookie', self.client.get('/login').headers)
        response = self.client.get('/privado')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers['cache-control'])
        self.assertIn('private', response.headers['cache-control'])
        self.assertEqual(response.text, 'test' * 1000)
