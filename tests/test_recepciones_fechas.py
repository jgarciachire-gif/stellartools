"""Lectura de fechas de reportes XML sin conexión a la base de datos."""
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace as NS

from test_ordenes_carga import handler, Upload


class RecepcionesFechasTests(unittest.IsolatedAsyncioTestCase):
    async def procesar(self, fecha):
        class Query:
            def __init__(self, db):
                self.db, self.values, self.start = db, None, 0
                self.filters = []

            def select(self, *args):
                return self

            def order(self, *args):
                return self

            def range(self, start, end):
                self.start = start
                return self

            def eq(self, field, value):
                self.filters.append((field, value))
                return self

            def is_(self, field, value):
                return self.eq(field, None)

            def update(self, values):
                self.values = values
                return self

            async def execute(self):
                if self.values is not None:
                    self.db.writes.append((self.values, self.filters))
                    return NS(data=[dict(id=1, **self.values)])
                return NS(data=[] if self.start else [dict(
                    id=1, numero_orden='000011770', usuario_id='user-1',
                    fecha_recepcion=None, estatus='Enviada',
                    tienda_destino='Garibaldi', proveedores={'nombre': 'Proveedor'}
                )])

        class Database:
            def __init__(self):
                self.writes = []

            def table(self, name):
                return Query(self)

        db = Database()
        process, _ = handler('routes/escanear.py', 'procesar_recepciones_xml',
                             config=NS(supabase_async=db), ET=ET)
        xml = ('<datos><registro><Nro_OrdenDeCompra>11770</Nro_OrdenDeCompra>'
               f'<FechaREC>{fecha}</FechaREC></registro></datos>').encode('utf-8')
        response = await process(NS(), [Upload('REC GARIBALDI.xml', xml)])
        return response.content, db.writes

    async def test_fecha_del_reporte_con_hora_espanola(self):
        for fecha in ['2/11/2026 2:02:02 p.\u00a0m.',
                      '2/11/2026 2:02:02 p.\u202fm.',
                      '2/11/2026 2:02:02 P. M.',
                      '2/11/2026 12:02:02 a. m.',
                      '2/11/2026 12:02:02 p. m.',
                      '2/11/2026 14:02:02']:
            with self.subTest(fecha=fecha):
                result, writes = await self.procesar(fecha)
                self.assertEqual(len(result['procesados']), 1, result)
                self.assertEqual(writes[0][0], {
                    'fecha_recepcion': '2026-11-02', 'estatus': 'Despacho Recibido'})
                self.assertIn(('usuario_id', 'user-1'), writes[0][1])
                self.assertIn(('fecha_recepcion', None), writes[0][1])

    async def test_formatos_anteriores_se_conservan(self):
        for fecha in ['02/11/2026', '02/11/26', '02-11-2026',
                      '2026-11-02', '2026-11-02T14:02:02Z']:
            with self.subTest(fecha=fecha):
                result, writes = await self.procesar(fecha)
                self.assertEqual(len(result['procesados']), 1, result)
                self.assertEqual(writes[0][0]['fecha_recepcion'], '2026-11-02')

    async def test_fechas_y_horas_invalidas_no_se_guardan(self):
        for fecha in ['31/11/2026 2:02:02 p. m.', '2/11/2026 13:02:02 p. m.',
                      '2/11/2026 2:70:02 p. m.', '2/11/2026 25:02:02', '']:
            with self.subTest(fecha=fecha):
                result, writes = await self.procesar(fecha)
                self.assertEqual(writes, [])
                self.assertEqual(result['detalles'][0]['estado'], 'Registro inválido')


if __name__ == '__main__':
    unittest.main()
