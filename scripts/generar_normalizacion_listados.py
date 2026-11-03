"""Generate the immutable SQL equivalent of NFD / remove Mn / Python casefold.

No extensions, locale-dependent lowercase or database access are required.
Run from the repository root after intentionally updating Unicode tables.
"""
import sys
import unicodedata
from pathlib import Path


def literal(text):
    return "U&'" + ''.join(f'\\{ord(c):04x}' if ord(c) <= 0xffff else f'\\+{ord(c):06x}' for c in text) + "'"


def generate():
    marks = [i for i in range(1, sys.maxunicode + 1) if unicodedata.category(chr(i)) == 'Mn']
    ranges = []
    for point in marks:
        if ranges and point == ranges[-1][1] + 1:
            ranges[-1][1] = point
        else:
            ranges.append([point, point])
    pattern = '[' + ''.join(chr(a) + ('-' + chr(b) if a != b else '') for a, b in ranges) + ']'
    simple, multiple = [], []
    for point in range(1, sys.maxunicode + 1):
        char = chr(point)
        folded = char.casefold()
        if char != folded:
            (simple if len(folded) == 1 else multiple).append((char, folded))
    cases = '\n'.join(f'            WHEN {literal(a)} THEN {literal(b)}' for a, b in multiple)
    return f'''-- Generated with Unicode {unicodedata.unidata_version}; source: generar_normalizacion_listados.py.
CREATE OR REPLACE FUNCTION public.st_normalizar_listado(p_texto text)
RETURNS text LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE SECURITY INVOKER
SET search_path = '' AS $fn$
DECLARE v_texto text;
BEGIN
    v_texto := regexp_replace(normalize(coalesce(p_texto, ''), NFD), {literal(pattern)}, '', 'g');
    -- Spanish accents decompose to ASCII, so ordinary names use this fast path.
    IF v_texto !~ U&'[^\\0001-\\007f]' THEN
        RETURN lower(v_texto COLLATE "C");
    END IF;
    v_texto := translate(v_texto, {literal(''.join(a for a, _ in simple))}, {literal(''.join(b for _, b in simple))});
    IF v_texto ~ {literal('[' + ''.join(a for a, _ in multiple) + ']')} THEN
        SELECT string_agg(CASE c
{cases}
            ELSE c END, '' ORDER BY posicion)
        INTO v_texto FROM regexp_split_to_table(v_texto, '') WITH ORDINALITY AS partes(c, posicion);
    END IF;
    RETURN v_texto;
END $fn$;
'''


if __name__ == '__main__':
    Path('scripts/sql/listados-normalizacion.sql').write_text(generate(), encoding='utf-8')
