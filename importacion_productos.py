"""Lee columnas de productos por su encabezado y conserva los campos ausentes."""
import csv
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import BadZipFile


ALIAS_COLUMNAS = {
    'codigo': ('codigo', 'cod', 'codigo del producto', 'codigo de producto', 'codigo producto', 'codigo st'),
    'codigo_ean': ('codigo ean', 'ean', 'codigo de barras', 'codigobarras'),
    'descripcion': ('descripcion', 'descripcion del producto', 'descripcion producto', 'nombre producto', 'nombre del producto'),
    'unidad_manejo': ('unidad manejo', 'unidad de manejo', 'um', 'unidad de empaque', 'unidad empaque', 'unidades por empaque', 'pre'),
    'costo': ('costo', 'costo actual', 'costo unitario', 'precio', 'precio actual', 'precio unitario'),
    'marca': ('marca',),
    'departamento': ('departamento',),
    'grupo': ('grupo',),
    'subgrupo': ('subgrupo',),
    'proveedor': ('proveedor', 'nombre proveedor', 'nombre del proveedor', 'proveedor id', 'id proveedor'),
}


def normalizar_encabezado_producto(valor):
    texto = unicodedata.normalize('NFKD', str(valor).rsplit('}', 1)[-1]).casefold()
    return re.sub(r'[^a-z0-9]', '', texto)


CAMPOS_POR_ALIAS = {
    normalizar_encabezado_producto(alias): campo
    for campo, alias_campo in ALIAS_COLUMNAS.items()
    for alias in alias_campo
}


def mapear_columnas_producto(columnas):
    """Devuelve la posición de cada campo reconocido y rechaza ambigüedades."""
    posiciones = {}
    for indice, columna in enumerate(columnas):
        campo = CAMPOS_POR_ALIAS.get(normalizar_encabezado_producto(columna))
        if campo is None:
            continue
        if campo in posiciones:
            raise ValueError(f'Hay dos columnas para el mismo campo: {campo}. Conserva una sola.')
        posiciones[campo] = indice
    if 'codigo' not in posiciones:
        raise ValueError('Falta la columna código. Puedes usar Código, CodigoDelProducto o Codigo ST.')
    if len(posiciones) < 2:
        raise ValueError('Incluye al menos una columna de datos reconocida además del código, como descripción, UM o costo.')
    return posiciones


def leer_filas_productos(contenido, nombre):
    nombre = nombre.lower()
    if nombre.endswith('.xml'):
        try:
            root = ET.fromstring(contenido)
        except ET.ParseError as error:
            raise ValueError('No se pudo leer el XML. Comprueba que el archivo sea válido.') from error
        elementos = [item for item in root.iter() if normalizar_encabezado_producto(item.tag) == 'producto']
        if not elementos:
            elementos = list(root)
        columnas = list(dict.fromkeys(campo.tag for item in elementos for campo in item))
        posiciones = mapear_columnas_producto(columnas)
        filas = []
        for item in elementos:
            valores = {}
            for campo in item:
                if campo.tag in valores:
                    raise ValueError(f'El XML repite el campo {campo.tag} dentro de un producto.')
                valores[campo.tag] = campo.text or ''
            filas.append({campo: valores.get(columnas[indice], '') for campo, indice in posiciones.items()})
        return filas

    if not nombre.endswith(('.csv', '.xlsx')):
        raise ValueError('El archivo debe ser CSV, XLSX o XML.')

    import pandas as pd

    try:
        if nombre.endswith('.csv'):
            try:
                texto = contenido.decode('utf-8-sig')
            except UnicodeDecodeError:
                texto = contenido.decode('latin1')
            cabecera = next((linea for linea in texto.splitlines() if linea.strip()), '')
            try:
                separador = csv.Sniffer().sniff(cabecera, delimiters=',;\t|').delimiter
            except csv.Error:
                separador = ','
            tabla = pd.read_csv(
                io.StringIO(texto), sep=separador, header=None, dtype=str, keep_default_na=False,
            )
        else:
            tabla = pd.read_excel(io.BytesIO(contenido), header=None, dtype=str, keep_default_na=False)
    except (ValueError, UnicodeError, BadZipFile, OSError) as error:
        raise ValueError('No se pudo leer la tabla. Revisa el formato y los separadores del archivo.') from error

    if tabla.empty:
        raise ValueError('El archivo no contiene encabezados ni productos.')
    posiciones = mapear_columnas_producto(tabla.iloc[0].tolist())
    return [
        {campo: fila.iloc[indice] for campo, indice in posiciones.items()}
        for _, fila in tabla.iloc[1:].iterrows()
    ]
