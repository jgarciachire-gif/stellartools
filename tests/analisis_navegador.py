"""Prueba de integración en Edge con HTML real y API local simulada.

Ejecutar: python tests/analisis_navegador.py
Requiere Microsoft Edge, Jinja2 y websockets. No importa config ni accede a la BD.
"""
import asyncio
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace as NS
from urllib.parse import urlparse
from urllib.request import urlopen, Request

from jinja2 import Environment, FileSystemLoader, select_autoescape
import websockets

ROOT = Path(__file__).resolve().parents[1]
STORES = ['CENTRO', 'NAGUANAGUA', 'ISABELICA', 'CIUDAD ALIANZA', 'GARIBALDI', 'SAN DIEGO']
PRODUCTS = [dict(codigo='000001', codigo_st='000001', descripcion='Producto & Uno', unidad_manejo=6, precio=2.5),
            dict(codigo='000002', codigo_st='000002', descripcion='Producto Dos', unidad_manejo=4, precio=3)]


class CDP:
    def __init__(self, socket):
        self.socket, self.next_id, self.pending, self.errors = socket, 0, {}, []

    async def listen(self):
        async for message in self.socket:
            event = json.loads(message)
            if 'id' in event:
                future = self.pending.pop(event['id'])
                if not future.done():
                    future.set_result(event)
            elif event.get('method') == 'Runtime.exceptionThrown':
                self.errors.append(event['params']['exceptionDetails'])

    async def call(self, method, params=None):
        self.next_id += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[self.next_id] = future
        await self.socket.send(json.dumps(dict(id=self.next_id, method=method, params=params or {})))
        response = await asyncio.wait_for(future, 45)
        if 'error' in response:
            raise AssertionError(response['error'])
        return response.get('result', {})

    async def evaluate(self, expression):
        result = await self.call('Runtime.evaluate', dict(expression=expression, awaitPromise=True, returnByValue=True, userGesture=True))
        if result.get('exceptionDetails'):
            raise AssertionError(result['exceptionDetails'])
        return result.get('result', {}).get('value')


async def exercise(port, browser_port, state):
    targets = json.loads(urlopen(f'http://127.0.0.1:{browser_port}/json/list').read())
    target = next(target for target in targets if target['type'] == 'page')
    async with websockets.connect(target['webSocketDebuggerUrl'], max_size=10_000_000) as socket:
        cdp = CDP(socket)
        reader = asyncio.create_task(cdp.listen())
        try:
            await cdp.call('Runtime.enable')
            await cdp.call('Page.enable')
            await cdp.call('Page.navigate', dict(url=f'http://127.0.0.1:{port}/'))
            for _ in range(100):
                if await cdp.evaluate("document.readyState === 'complete' && typeof compararDemandaKardexDesdeAnalisis === 'function' && !!window.Alpine"):
                    break
                await asyncio.sleep(.2)
            else:
                raise AssertionError('La página no terminó de iniciar')
            await cdp.evaluate(r"""window.check = (condition, message) => { if (!condition) throw Error(message); };
                window.waitFor = async predicate => { for(let i=0;i<100;i++){if(predicate())return; await new Promise(r=>setTimeout(r,30));} throw Error('Espera agotada'); };
                window.rows = () => [...document.querySelectorAll('#filas-tabla-analisis tr')];
                check(rows().length===1, 'Fila inicial');
                check(document.getElementById('modal-productos-proveedor').parentElement===document.body, 'Modal fuera del main');
                'inicio correcto';""")
            print('OK: inicio, dependencias y ubicación de modales', flush=True)
            await cdp.evaluate(r"""(async()=>{
                const pending=seleccionarProveedorAnalisis(5,'Proveedor de prueba');
                check(!document.getElementById('modal-productos-proveedor').classList.contains('hidden'), 'Apertura inmediata');
                await pending;
                check(!document.getElementById('btn_importar_productos').disabled,'Clasificación cargada');
                await confirmarProductosProveedor();
                check(rows().length===2,'Importación de productos');
                await importarProductosAnalisis();
                check(rows().length===2,'Sin duplicados');
                const tr=rows()[0]; tr.querySelector('.inp-pre').value=6; tr.querySelector('.inp-emp').value=3;
                tr.querySelector('.inp-inv-emp').value=2; tr.querySelector('.inp-costo').value=2.5;
                calcularFila(tr.querySelector('.inp-emp'));
                check(+tr.querySelector('.inp-uni').value===18,'Unidades');
                check(document.getElementById('tot-monto').textContent.includes('45,00'),'Total');
                matrizTiendas['SAN DIEGO']={'000001':{invEmp:8,emp:5}};
                await cambiarTiendaPestana('SAN DIEGO');
                check(+rows()[0].querySelector('.inp-emp').value===5,'Otra tienda');
                await cambiarTiendaPestana('CENTRO');
                check(+rows()[0].querySelector('.inp-emp').value===3,'Restauración');
                document.getElementById('dias_cobertura').value=7;
                document.getElementById('porcentaje_crecimiento').value=10;
                await calcularSugeridoSedeActual();
                check(+rows()[0].querySelector('.inp-emp').value===4,'Sugerido');
                await guardarPlantillaCompleta(); await cargarUltimoPedidoGuardado();
                check(rows().length===2 && +rows()[0].querySelector('.inp-emp').value===4,'Pedido restaurado');
                return true;
            })()""")
            assert state.get('saved', {}).get('detalles'), 'El pedido no llegó a la API simulada'
            print('OK: proveedor, productos, cálculos, tiendas, sugeridos y guardado/restauración', flush=True)
            await cdp.evaluate(r"""(async()=>{
                window.exportBlobs=[]; window.exportNames=[];
                URL.createObjectURL=blob=>{exportBlobs.push(blob);return 'blob:prueba';}; URL.revokeObjectURL=()=>{};
                HTMLAnchorElement.prototype.click=function(){exportNames.push(this.download);};
                window.stage='XML'; await exportarConsolidado();
                check((await exportBlobs[0].text()).includes('<consolidado'),'Exportación XML');
                abrirModalExportarSeparado();
                document.querySelectorAll('.tag-tienda-exportar').forEach(tag=>{
                    if(tag.dataset.tienda!=='CENTRO') toggleTiendaExportar(tag.dataset.tienda,tag);
                });
                window.stage='TXT'; await confirmarExportacionSeparada();
                await waitFor(()=>exportBlobs.length>=2);
                check((await exportBlobs[1].text()).includes('000001|24|\r\n'),'Exportación TXT');
                window.stage='Inventarios'; await abrirModalImportarInventarios();
                const input=document.getElementById('inventario-buscar-texto'); input.value='Centro';
                input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
                await waitFor(()=>document.getElementById('inventario-doc-11'));
                document.getElementById('inventario-doc-11').click();
                window.stage='Revisión inventarios'; await previsualizarImportacionInventarios();
                window.stage='Aplicación inventarios'; await confirmarImportacionInventarios();
                check(matrizTiendas.CENTRO['000001'].invEmp===9,'Inventario importado');
                window.stage='Comparación'; await compararDemandaKardexDesdeAnalisis([{anio:2026,mes:10,inicio:'2026-10-01',fin:'2026-10-07',dias:7}]);
                check(document.getElementById('kardex-comparacion-resultados').rows.length===2,'Comparación Kardex');
                check(document.getElementById('kardex-comparacion-mensaje').classList.contains('hidden'),'Comparación sin errores');
                window.stage='Cancelar limpieza'; const pending=limpiarListaProductos();
                await waitFor(()=>document.querySelector('[data-modal-cancelar]'));
                document.querySelector('[data-modal-cancelar]').click(); await pending;
                check(rows().length===2,'Cancelar conserva productos');
                await new Promise(r=>setTimeout(r,200));
                window.stage='Confirmar limpieza'; const clean=limpiarListaProductos();
                document.querySelector('[data-modal-aceptar]').click(); await clean;
                check(rows().length===0,'Limpiar confirmado');
                agregarFilaAnalisis(); check(rows().length===1,'Agregar fila manual');
                return true;
            })()""")
            print('OK: XML/TXT, importador de inventarios, comparación, confirmaciones y filas manuales', flush=True)
            assert not cdp.errors, json.dumps(cdp.errors, ensure_ascii=False)
            print('OK: sin excepciones JavaScript en navegador', flush=True)
        except Exception:
            print('DIAGNÓSTICO:', await cdp.evaluate("JSON.stringify({stage:window.stage,modal:[...document.querySelectorAll('[data-modal-aceptar]')].map(x=>x.parentElement.parentElement.innerText),errors:document.querySelector('#kardex-comparacion-mensaje')?.textContent})"), flush=True)
            raise
        finally:
            reader.cancel()


def main():
    vendors = {}
    for name, url in [('tailwind', 'https://cdn.tailwindcss.com'), ('alpine', 'https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js')]:
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(request, timeout=30) as response:
            vendors[name] = response.read()
    vendors['supabase'] = b'window.supabase={createClient:()=>({})};'
    env = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=select_autoescape())
    profile = NS(tipo_usuario='normal', nombre_comprador='Prueba', usuario_id='prueba')
    html = env.get_template('analisis_pedido.html').render(
        request=NS(state=NS(perfil=profile, user=NS(id='prueba'))), user=NS(id='prueba'),
        active_app='Análisis de Pedido', proveedores=[dict(id=5, nombre='Proveedor de prueba')],
        asset_url=lambda name: '/static/' + name)
    for url, path in [('https://cdn.tailwindcss.com', '/vendor/tailwind'), ('https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js', '/vendor/alpine'),
                      ('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2', '/vendor/supabase')]:
        html = html.replace(url, path)
    state = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, data, mime='application/json'):
            payload = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/':
                return self.respond(html.encode(), 'text/html; charset=utf-8')
            if path.startswith('/vendor/'):
                return self.respond(vendors[path.split('/')[-1]], 'application/javascript')
            if path.startswith('/static/'):
                file = (ROOT / path.lstrip('/')).resolve()
                if file.is_relative_to(ROOT / 'static') and file.is_file():
                    return self.respond(file.read_bytes(), mimetypes.guess_type(file)[0] or 'application/octet-stream')
                return self.send_error(404)
            if path == '/api/clasificacion':
                return self.respond([dict(departamento='ALIMENTOS', grupo='GENERAL', subgrupo='BASICOS', marca='MARCA')])
            if path == '/api/proveedores/5':
                return self.respond(dict(nombre='Proveedor de prueba', contacto='Contacto', telefono='123', etiquetas='Prueba'))
            if path == '/api/productos/importar-analisis':
                return self.respond(PRODUCTS)
            if path.startswith('/api/notificaciones/'):
                return self.respond(dict(notificaciones=[], total=0))
            if path == '/api/analisis/inventarios':
                return self.respond(dict(ok=True, inventarios=[dict(id=11, nombre='Inventario Centro', tienda='CENTRO', updated_at='2026-11-01')], hay_mas=False))
            if path.startswith('/api/analisis/inventarios/'):
                return self.respond(dict(ok=True, productos=[dict(codigo='000001', cantidad=9), dict(codigo='000002', cantidad=2)]))
            if path == '/analisis/ultimo-pedido':
                return self.respond(dict(encontrado=True, analisis=dict(proveedor_id=5, dias_cobertura=7),
                                         proveedor=dict(nombre='Proveedor de prueba'), productos=PRODUCTS, detalles=state['saved']['detalles']))
            if path == '/analisis/cobertura-kardex':
                return self.respond(dict(status='ok', data=[dict(sede=sede, fecha_minima='2026-10-01', fecha_maxima='2026-10-31') for sede in STORES]))
            if path == '/analisis/meses-kardex':
                return self.respond(dict(status='ok', data=[dict(anio=2026, mes=10, fecha_minima='2026-10-01', fecha_maxima='2026-10-31')]))
            if path == '/analisis/demanda-kardex':
                return self.respond(dict(data=[dict(sede=sede, codigo=product['codigo'], unidades_vendidas=28, dias_con_ventas=7) for sede in STORES for product in PRODUCTS]))
            self.send_error(404)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            if self.path == '/analisis/guardar-pedido':
                state['saved'] = payload
                return self.respond(dict(ok=True))
            if self.path == '/analisis/sugeridos-tooltip-lote':
                today = datetime.now(timezone(timedelta(hours=-4))).strftime('%Y-%m-%d')
                return self.respond(dict(fecha_referencia=today, data=[dict(sede=sede, codigo=code, demanda_diaria=4) for sede in STORES for code in payload['codigos']]))
            self.send_error(404)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    edge = Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe'
    with tempfile.TemporaryDirectory(prefix='analisis-browser-') as temp:
        browser = subprocess.Popen([str(edge), '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
                                    '--remote-debugging-port=0', '--remote-allow-origins=*', '--window-size=1440,1000',
                                    '--user-data-dir=' + temp, 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            debug = Path(temp) / 'DevToolsActivePort'
            for _ in range(100):
                if debug.exists():
                    break
                time.sleep(.1)
            browser_port = int(debug.read_text().splitlines()[0])
            asyncio.run(exercise(server.server_port, browser_port, state))
        finally:
            browser.terminate()
            browser.wait(timeout=15)
            server.shutdown()


if __name__ == '__main__':
    main()
