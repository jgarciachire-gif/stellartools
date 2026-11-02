"""Comparte las reglas del dashboard y verifica el aislamiento por usuario."""
import ast
import hashlib
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

from fastapi.responses import JSONResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape


class NotificationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.today = date(2026, 11, 2)
        self.rows = []
        self.queries = []
        owner = self

        class Query:
            def __init__(self):
                self.user = None
                self.bounds = (0, 999)
            def select(self, *args): return self
            def eq(self, column, value):
                assert column == 'usuario_id'
                self.user = value
                return self
            def order(self, *args, **kwargs): return self
            def range(self, start, end):
                self.bounds = (start, end)
                return self
            async def execute(self):
                owner.queries.append((self.user, self.bounds))
                rows = sorted((r for r in owner.rows if r['usuario_id'] == self.user), key=lambda r: r['id'])
                return NS(data=rows[self.bounds[0]:self.bounds[1] + 1])

        async def user(*args): return NS(id='current-user')
        self.env = dict(datetime=datetime, timedelta=timedelta, timezone=timezone, hashlib=hashlib, json=json,
                        JSONResponse=JSONResponse, RedirectResponse=RedirectResponse,
                        Request=object, Cookie=lambda value: value,
                        obtener_usuario_actual=user,
                        config=NS(supabase_async=NS(table=lambda name: Query())),
                        templates=NS(TemplateResponse=lambda **kwargs: kwargs))
        names = {'construir_desglose_reposicion', 'construir_notificaciones_reposicion',
                 'obtener_desglose_reposicion', 'notificaciones_reposicion', 'dashboard'}
        nodes = [n for n in ast.parse(Path('routes/dashboard.py').read_text(encoding='utf-8')).body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
        for node in nodes: node.decorator_list = []
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'routes/dashboard.py', 'exec'), self.env)

    def order(self, identifier=1, remaining=1, supplier='Proveedor A', store='CENTRO', groups=('Víveres',)):
        return dict(id=identifier, usuario_id='current-user', proveedor=supplier,
                    proveedores={'nombre': supplier}, tienda_destino=store,
                    numero_orden=f'OC-{identifier}', dias_inventario=15,
                    fecha_recepcion=(self.today - timedelta(days=15 - remaining)).isoformat(),
                    detalles_productos=[{'grupo': group} for group in groups])

    def breakdown(self, rows):
        return self.env['construir_desglose_reposicion'](rows, hoy=self.today)

    def notifications(self, rows):
        return self.env['construir_notificaciones_reposicion'](self.breakdown(rows))

    async def test_inventory_thresholds_match_dashboard(self):
        rows = [self.order(i + 1, remaining=remaining, store=f'Tienda {remaining}')
                for i, remaining in enumerate([-1, 0, 1, 2, 3])]
        breakdown = self.breakdown(rows)['Proveedor A']['Víveres']
        self.assertEqual(breakdown['Tienda 0']['estatus_inv'], 'Reponer inventario')
        self.assertEqual(breakdown['Tienda 2']['estatus_inv'], 'Próximo a Agotar')
        self.assertEqual(breakdown['Tienda 3']['estatus_inv'], 'Stock OK')
        alerts = self.notifications(rows)[0]['tiendas']
        self.assertEqual(len(alerts), 4)
        for alert in alerts:
            self.assertEqual(alert['dias_inventario'], breakdown[alert['tienda']]['dias_inventario'])

    async def test_pending_stock_ok_and_invalid_dates_are_excluded(self):
        pending = self.order(1, store='Pendiente'); pending['fecha_recepcion'] = None
        invalid = self.order(2, store='Inválida'); invalid['fecha_recepcion'] = 'bad-date'
        self.assertEqual(self.notifications([pending, invalid, self.order(3, remaining=5)]), [])

    async def test_latest_received_order_sets_the_current_inventory(self):
        expired = self.order(1, remaining=-2)
        replenished = self.order(2, remaining=10)
        self.assertEqual(self.notifications([expired, replenished]), [])
        sent = self.order(3); sent['fecha_recepcion'] = None
        self.assertEqual(len(self.notifications([expired, sent])), 1)

    async def test_same_store_and_status_are_not_duplicated_across_groups(self):
        alert = self.notifications([self.order(groups=('Víveres', 'Lácteos'))])[0]
        self.assertEqual(len(alert['tiendas']), 1)
        self.assertEqual(set(alert['tiendas'][0]['grupos']), {'Víveres', 'Lácteos'})

    async def test_conflicting_group_states_remain_distinguishable(self):
        alerts = self.notifications([self.order(1, remaining=-2, groups=('Víveres',)),
                                    self.order(2, remaining=2, groups=('Lácteos',))])[0]['tiendas']
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0]['estatus'], 'Reponer inventario')
        self.assertTrue(all(alert['mostrar_grupos'] for alert in alerts))

    async def test_zero_days_and_empty_supplier_name_are_handled(self):
        order = self.order(remaining=15)
        order['dias_inventario'] = 0
        order['proveedores'] = [{'nombre': ''}]
        self.assertEqual(self.notifications([order])[0]['proveedor'], 'Proveedor A')
        self.assertEqual(self.notifications([order])[0]['tiendas'][0]['estatus'], 'Reponer inventario')

    async def test_query_reads_only_current_user_and_all_pages(self):
        self.rows = [self.order(i, remaining=-1000) for i in range(1, 1002)]
        other = self.order(2000, supplier='Privado'); other['usuario_id'] = 'another-user'
        self.rows.append(other)
        result = await self.env['obtener_desglose_reposicion']('current-user')
        self.assertNotIn('Privado', result)
        self.assertEqual(self.queries, [('current-user', (0, 999)), ('current-user', (1000, 1999))])

    async def test_endpoint_requires_session_and_disables_http_caching(self):
        async def no_user(*args): return None
        self.env['obtener_usuario_actual'] = no_user
        response = await self.env['notificaciones_reposicion']()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(self.queries, [])

    async def test_endpoint_and_dashboard_use_same_breakdown(self):
        breakdown = self.breakdown([self.order(remaining=-1), self.order(2, supplier='Proveedor B', remaining=2),
                                    self.order(3, store='GARIBALDI', remaining=1)])
        async def shared(user_id):
            self.assertEqual(user_id, 'current-user')
            return breakdown
        self.env['obtener_desglose_reposicion'] = shared
        dashboard = await self.env['dashboard'](request=object())
        response = await self.env['notificaciones_reposicion']()
        body = json.loads(response.body)
        self.assertIs(dashboard['context']['proveedores_desglose'], breakdown)
        self.assertEqual(body['notificaciones'], self.env['construir_notificaciones_reposicion'](breakdown))
        self.assertEqual(body['total'], 2)

    async def test_header_chooses_notification_type_by_role(self):
        env = Environment(loader=FileSystemLoader('templates'), autoescape=select_autoescape())
        env.globals['asset_url'] = lambda path: '/static/' + path
        request = NS(state=NS(perfil=None))
        html = env.get_template('base.html').render(request=request)
        self.assertIn('id="panel-notificaciones-header"', html)
        self.assertLess(html.index('id="panel-notificaciones-header"'), html.index('</header>'))
        self.assertLess(html.index('notificaciones-header.js'), html.index('alpinejs'))
        request.state.perfil = NS(tipo_usuario='provisional', nombre_comprador='Inventario', tienda='CENTRO')
        restricted = env.get_template('base.html').render(request=request)
        self.assertIn('id="panel-notificaciones-header"', restricted)
        self.assertIn('data-tipo-notificaciones="inventarios"', restricted)
        self.assertIn('data-tienda-notificaciones="CENTRO"', restricted)
        self.assertIn('data-tipo-notificaciones="reposicion"', html)

    async def test_version_changes_with_status_but_not_with_daily_countdown(self):
        order = self.order(remaining=2)
        build = self.env['construir_desglose_reposicion']
        alerts = self.env['construir_notificaciones_reposicion']
        today = alerts(build([order], hoy=self.today))[0]['version_estado']
        tomorrow = alerts(build([order], hoy=self.today + timedelta(days=1)))[0]['version_estado']
        expired = alerts(build([order], hoy=self.today + timedelta(days=2)))[0]['version_estado']
        self.assertEqual(today, tomorrow)
        self.assertNotEqual(today, expired)

    async def test_new_received_order_renews_alert_even_if_healthy_interval_was_not_observed(self):
        previous = self.notifications([self.order(1, remaining=-2)])[0]['version_estado']
        new_cycle = self.notifications([self.order(2, remaining=-2)])[0]['version_estado']
        self.assertNotEqual(previous, new_cycle)


if __name__ == '__main__':
    unittest.main()
