"""Guard Vercel's dependency manifest against an empty or incomplete install."""
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ConfiguracionDespliegueTests(unittest.TestCase):
    def test_vercel_installs_all_runtime_dependencies(self):
        manifest = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
        requirements = {
            line.strip() for line in (ROOT / 'requirements.txt').read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')
        }
        self.assertEqual(set(manifest['project']['dependencies']), requirements)
        self.assertIn('fastapi', manifest['project']['dependencies'])
        self.assertEqual(manifest['project']['requires-python'], '>=3.12,<3.13')
        self.assertFalse(manifest['tool']['uv']['package'])
