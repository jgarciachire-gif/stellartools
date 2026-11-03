"""Inventory local resource sizes without importing the app or accessing the DB.

Run: python scripts/auditar_recursos.py
Sizes are source bytes, not rendered HTML sizes or production load timings.
"""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inventory(directory, suffixes):
    result = []
    for file in (ROOT / directory).rglob('*'):
        if file.is_file() and file.suffix in suffixes:
            raw = file.read_bytes()
            result.append({
                'archivo': file.relative_to(ROOT).as_posix(),
                'bytes': len(raw),
                'gzip5_bytes': len(gzip.compress(raw, compresslevel=5, mtime=0)),
            })
    return sorted(result, key=lambda item: item['bytes'], reverse=True)


if __name__ == '__main__':
    print(json.dumps({
        'nota': 'Tamaños de fuentes locales; no representan latencia ni HTML renderizado.',
        'plantillas': inventory('templates', {'.html'}),
        'recursos': inventory('static', {'.js', '.css', '.json', '.jpg', '.svg'}),
    }, indent=2, ensure_ascii=False))
