"""Build a self-contained SQL check using temporary data and ROLLBACK.

This script does not connect to Supabase. Open its output in the SQL editor.
Usage: python scripts/verificar_listados_sql.py --salida <file.sql>
"""
import argparse
import random
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def quote(text):
    return "'" + text.replace("'", "''") + "'"


def construir_instalacion():
    return '\n'.join([
        'BEGIN;', "SET LOCAL lock_timeout='2s';",
        (ROOT/'scripts/sql/listados-normalizacion.sql').read_text(encoding='utf-8'),
        (ROOT/'scripts/sql/listados-paginados.sql').read_text(encoding='utf-8'),
        'COMMIT;'
    ])


def construir_verificacion():
    normalizacion = (ROOT/'scripts/sql/listados-normalizacion.sql').read_text(encoding='utf-8')
    funciones = (ROOT/'scripts/sql/listados-paginados.sql').read_text(encoding='utf-8')
    fixtures = (ROOT/'scripts/sql/verificar-listados-paginados.sql').read_text(encoding='utf-8')
    corte = fixtures.index('SET LOCAL request.jwt.claim.sub')
    copias = funciones.replace('public.st_listar_ordenes','pg_temp.st_listar_ordenes').replace(
        'public.st_listar_proveedores','pg_temp.st_listar_proveedores').replace(
        'public.ordenes_compra','pg_temp.st_test_ordenes').replace('public.proveedores','pg_temp.st_test_proveedores')
    textos = ['LÁCTEOS', 'Atencio\u0301n', 'Straße', 'Σς', 'ﬃ', 'İ', 'ÁRBOL %_', 'ñ', 'ÆØŁ', 'Ꭰꭰ', '']
    randomizer = random.Random(42)
    montos = [0, 2.675, 2.685, -0.0001, 1.005, 1234.5, 1e20, 1e-20, -1e20, .125, .375]
    montos += [randomizer.uniform(-1e7,1e7) for _ in range(100)]
    comprobaciones = []
    for text in textos:
        expected = ''.join(c for c in unicodedata.normalize('NFD',text) if unicodedata.category(c)!='Mn').casefold()
        comprobaciones.append(f'IF public.st_normalizar_listado({quote(text)}) <> {quote(expected)} THEN RAISE EXCEPTION \'Normalizacion incorrecta\'; END IF;')
    for value in montos:
        expected = format(value,',.2f').replace(',','X').replace('.',',').replace('X','.')
        comprobaciones.append(f'IF public.st_monto_busqueda({value!r}::numeric) <> {quote(expected)} THEN RAISE EXCEPTION \'Formato de monto incorrecto\'; END IF;')
    return '\n'.join([
        'BEGIN;', "SET LOCAL lock_timeout='2s';", normalizacion, funciones,
        'DO $test$ BEGIN', *comprobaciones, 'END $test$;',
        fixtures[:corte], copias, fixtures[corte:], 'ROLLBACK;'
    ])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida',required=True,type=Path)
    parser.add_argument('--tipo', choices=['verificacion','instalacion'], default='verificacion')
    args=parser.parse_args()
    args.salida.write_text(construir_instalacion() if args.tipo=='instalacion' else construir_verificacion(),encoding='utf-8')
