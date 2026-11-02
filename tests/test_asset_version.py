"""Verifica que una edición no reutilice la URL cacheada del recurso anterior."""
import ast
import os
import tempfile
import unittest
from pathlib import Path


class AssetVersionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'static').mkdir()
        env = {'os': os, '__file__': str(self.root / 'config.py'), 'ASSET_VERSION': 'release'}
        node = next(n for n in ast.parse(Path('config.py').read_text(encoding='utf-8')).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'asset_url')
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'config.py', 'exec'), env)
        self.asset_url = env['asset_url']

    def test_unchanged_file_keeps_url_and_edited_file_gets_new_url(self):
        asset = self.root / 'static' / 'header.js'
        asset.write_text('old', encoding='utf-8')
        previous = self.asset_url('header.js')
        self.assertEqual(self.asset_url('header.js'), previous)
        asset.write_text('new notification behavior', encoding='utf-8')
        self.assertNotEqual(self.asset_url('header.js'), previous)
        self.assertTrue(self.asset_url('header.js').startswith('/static/header.js?v=release-'))

    def test_other_file_changes_do_not_invalidate_unchanged_assets(self):
        asset = self.root / 'static' / 'header.js'
        asset.write_text('same', encoding='utf-8')
        previous = self.asset_url('header.js')
        (self.root / 'static' / 'other.js').write_text('changed', encoding='utf-8')
        self.assertEqual(self.asset_url('header.js'), previous)

    def test_missing_asset_retains_deployment_version(self):
        self.assertEqual(self.asset_url('/missing.js'), '/static/missing.js?v=release')


if __name__ == '__main__':
    unittest.main()
