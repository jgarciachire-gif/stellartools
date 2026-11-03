"""Real templates and migrated assets in Edge; all APIs and writes are local mocks."""
import asyncio
import json
import mimetypes
import os
import subprocess
import tempfile
import threading
import time
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace as NS
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen

from jinja2 import Environment, FileSystemLoader, select_autoescape
import websockets

from analisis_navegador import CDP
from test_ordenes_carga import handler
from test_optimizaciones import Query

ROOT = Path(__file__).resolve().parents[1]


async def exercise(port, browser_port, state):
    targets = json.loads(urlopen(f'http://127.0.0.1:{browser_port}/json/list').read())
    target = next(t for t in targets if t['type'] == 'page')
    async with websockets.connect(target['webSocketDebuggerUrl'], max_size=10_000_000) as socket:
        cdp = CDP(socket)
        reader = asyncio.create_task(cdp.listen())
        async def run(code):
            return await cdp.evaluate('(async()=>{' + code + '})()')
        try:
            await cdp.call('Runtime.enable')
            await cdp.call('Page.enable')
            async def navigate(path, ready):
                await cdp.call('Page.navigate', {'url': f'http://127.0.0.1:{port}' + path})
                for _ in range(150):
                    if await cdp.evaluate("document.readyState==='complete' && (" + ready + ')'):
                        return
                    await asyncio.sleep(.1)
                raise AssertionError('No inició: ' + path + ' ' + str(await cdp.evaluate(
                    'JSON.stringify({url:location.href,ready:document.readyState})')) + ' ' + json.dumps(cdp.errors))
            await navigate('/ordenes', "typeof toggleDetalleOC==='function' && !!window.actualizarEstadoSeleccion")
            await run("""window.check=(v,m)=>{if(!v)throw Error(m)};
                window.waitFor=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,50));}throw Error('Espera agotada')};
                for (const elemento of document.querySelectorAll('.ordenes-flex')) {
                    check(getComputedStyle(elemento).display==='none','Panel inicialmente oculto');
                    elemento.classList.remove('hidden');
                    check(getComputedStyle(elemento).display==='flex','Panel abierto conserva flex');
                    elemento.classList.add('hidden');
                    check(getComputedStyle(elemento).display==='none','Panel vuelve a ocultarse');
                }
                check(document.querySelectorAll('.row-orden').length===20,'Página de 20');
                document.querySelector('[data-pagina-ordenes="2"]').click();
                await waitFor(()=>location.search.includes('page=2'));
                check(document.querySelector('.row-orden').dataset.id==='21','Segunda página');
                await toggleDetalleOC('21');
                check(document.querySelector('#detalle-21').innerText.includes('Reintentar'),'Error recuperable');
                document.querySelector('#detalle-21 button').click();
                await waitFor(()=>document.querySelector('#detalle-21').innerText.includes('Producto de prueba'));
                const input=document.getElementById('buscador-ordenes'); input.value='OC-0045'; input.dispatchEvent(new Event('input'));
                await waitFor(()=>document.querySelectorAll('.row-orden').length===1 && document.querySelector('.row-orden').dataset.id==='45');
                await toggleDetalleOC('45'); check(document.querySelector('#detalle-45').innerText.includes('Producto de prueba'),'Detalle bajo demanda');
                await toggleDetalleOC('45'); await toggleDetalleOC('45');
                document.getElementById('btn-activar-seleccion').click(); document.getElementById('btn-seleccionar-todo').click();
                check(document.querySelector('.select-row').checked,'Selección tras búsqueda');
                const eliminar=abrirModalEliminar(); await waitFor(()=>!!document.querySelector('[data-modal-aceptar]'));
                document.querySelector('[data-modal-cancelar]').click(); await eliminar;
                check(document.querySelector('.select-row').checked,'Cancelar conserva selección');
            """)
            assert state['details'] == 3, state
            assert not state['deletes'], state
            print('OK: órdenes, paginación, filtro fuera de página, detalle reutilizado, selección y confirmación', flush=True)
            await navigate('/inventario', "typeof abrirModalNuevoInventario==='function'")
            await run("""abrirModalNuevoInventario();
                if(document.getElementById('modal-nuevo-inventario').classList.contains('hidden')) throw Error('Modal inventario');
                cerrarModalNuevoInventario();
                if(!document.getElementById('modal-nuevo-inventario').classList.contains('hidden')) throw Error('Cerrar inventario');
            """)
            await navigate('/inventario/7', "typeof agregarFilaInventario==='function' && typeof obtenerProductosInventario==='function'")
            await run("""const original=obtenerProductosInventario();
                if(original.length!==1)throw Error('Producto inicial');
                agregarFilaInventario('000002','Producto nuevo',3);
                if(obtenerProductosInventario().length!==2)throw Error('Agregar fila');
                agregarFilaInventario('000002','Duplicado',3);
                if(obtenerProductosInventario().length!==2)throw Error('Duplicados');
                cambiarUbicacionInventario('piso_ventas');
                const cantidad=document.querySelector('.inp-cantidad'); cantidad.value='4'; validarCantidadInventario(cantidad);
                const producto=obtenerProductosInventario()[0];
                if(producto.cantidad_piso_ventas!==4)throw Error('Cantidad piso ventas');
                cambiarUbicacionInventario('almacen');
                if(Number(document.querySelector('.inp-cantidad').value)!==2)throw Error('Cantidad almacén conservada');
                await guardarInventario('borrador');
            """)
            assert state['saved'] and len(state['saved']['productos']) == 2, state
            print('OK: inventario, modales, filas, duplicados, cantidades por ubicación y guardado', flush=True)
            await cdp.call('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            await run("""renderizarProductosMovil();
                if(getComputedStyle(document.getElementById('inventario-documento-header')).display!=='none')throw Error('Header móvil');
            """)
            assert not cdp.errors, json.dumps(cdp.errors, ensure_ascii=False)
            print('OK: vista móvil y ausencia de excepciones JavaScript', flush=True)
        finally:
            reader.cancel()


def main():
    request = Request('https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js', headers={'User-Agent':'Mozilla/5.0'})
    with urlopen(request, timeout=30) as response:
        alpine = response.read()
    env = Environment(loader=FileSystemLoader(ROOT/'templates'), autoescape=select_autoescape())
    env.filters['limpiar_cantidad'] = lambda v: float(str(v or 0).replace(',', ''))
    profile = NS(tipo_usuario='normal', usuario_id='user-1', nombre_comprador='Prueba', tienda='CENTRO')
    rows = [dict(id=i, usuario_id='user-1', numero_orden=f'OC-{i:04}', proveedor='Proveedor',
        proveedores={'nombre':'Proveedor','dias_credito':30}, tienda_destino='CENTRO',
        fecha_envio='2026-10-01', fecha_recepcion=None, monto_total=12) for i in range(1,46)]
    state = {'details':0, 'detail_failure':True, 'deletes':[], 'saved':None}
    def render(template, path, **context):
        context.update(request=NS(url=__import__('starlette.datastructures',fromlist=['URL']).URL('http://localhost'+path),
            state=NS(perfil=profile,user=NS(id='user-1'))), asset_url=lambda n:'/static/'+n, perfil=profile,
            es_provisional=False, es_creador_inventario=True)
        return env.get_template(template).render(**context).replace('https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js','/vendor/alpine').replace(
            'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css','/vendor/fontawesome').encode()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def respond(self, data, mime='application/json', status=200):
            payload = data if isinstance(data,bytes) else json.dumps(data).encode()
            self.send_response(status); self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
        def do_GET(self):
            path=urlparse(self.path).path
            if path=='/vendor/alpine':return self.respond(alpine,'application/javascript')
            if path=='/vendor/fontawesome':return self.respond(b'', 'text/css')
            if path.startswith('/static/'):
                file=(ROOT/path.lstrip('/')).resolve()
                if file.is_relative_to(ROOT/'static') and file.is_file():
                    return self.respond(file.read_bytes(),mimetypes.guess_type(file)[0] or 'application/octet-stream')
                return self.respond({},status=404)
            if path=='/ordenes':
                params={k:v[-1] for k,v in parse_qs(urlparse(self.path).query).items()}
                fn,_=handler('routes/ordenes.py','listar_ordenes', config=NS(supabase_async=Query(rows)),
                    timedelta=timedelta,templates=NS(TemplateResponse=lambda **kw:kw['context']))
                return self.respond(render('ordenes.html',self.path,**asyncio.run(fn(NS(query_params=params)))),'text/html; charset=utf-8')
            if path.endswith('/detalle'):
                state['details']+=1
                if path=='/ordenes/21/detalle' and state['detail_failure']:
                    state['detail_failure']=False
                    return self.respond(dict(mensaje='Fallo simulado'),status=503)
                return self.respond(render('componentes/orden_detalle.html',self.path,o=dict(monto_total=12,
                    detalles_productos=[dict(codigo='000001',descripcion='Producto de prueba',pre=6,emp=1,cantidad=6,precio_unitario=2)])), 'text/html; charset=utf-8')
            if path=='/inventario':
                return self.respond(render('inventario.html',self.path,inventarios=[],pagina_actual=1,total_paginas=1,total_inventarios=0),'text/html; charset=utf-8')
            if path=='/inventario/7':
                return self.respond(render('inventario_nuevo.html',self.path,inventario=dict(id=7,estado='borrador',tienda='CENTRO',nombre='Proveedor',
                    created_at='2026-11-01T12:00:00',updated_at='2026-11-01T12:00:00'),productos=[dict(codigo='000001',descripcion='Producto',cantidad=2,
                    cantidad_almacen=2,cantidad_piso_ventas=0,precio=2)]),'text/html; charset=utf-8')
            if path=='/api/proveedores':return self.respond([dict(id=1,nombre='Proveedor')])
            return self.respond(dict(notificaciones=[],total=0,data=[],productos=[]))
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or '{}')
            if self.path.endswith('/guardar'):state['saved']=data
            if self.path.endswith('eliminar_masivo'):state['deletes'].append(data)
            return self.respond(dict(ok=True,status='ok',success=True))
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    edge=Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe'
    with tempfile.TemporaryDirectory(prefix='optimizaciones-browser-') as temp:
        browser=subprocess.Popen([str(edge),'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
            '--remote-debugging-port=0','--remote-allow-origins=*','--window-size=1440,1000','--user-data-dir='+temp,'about:blank'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            debug=Path(temp)/'DevToolsActivePort'
            browser_port=None
            for _ in range(100):
                try:
                    browser_port=int(debug.read_text().splitlines()[0])
                    break
                except (FileNotFoundError,PermissionError,IndexError,ValueError):
                    pass
                time.sleep(.1)
            if browser_port is None:raise RuntimeError('Edge no publicó su puerto de depuración.')
            asyncio.run(exercise(server.server_port,browser_port,state))
        finally:
            browser.terminate();browser.wait(timeout=15);server.shutdown()


if __name__=='__main__':main()
