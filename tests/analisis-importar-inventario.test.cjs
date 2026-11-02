const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/js/analisis/analisis-importar-inventario.js', 'utf8');

function element() {
    const classes = new Set(['hidden']);
    const listeners = {};
    return {
        value: '', textContent: '', innerHTML: '', children: [], dataset: {}, attributes: {}, disabled: false,
        classList: {
            add: value => classes.add(value), remove: value => classes.delete(value),
            contains: value => classes.has(value),
            toggle(value, force) {
                const enabled = force ?? !classes.has(value);
                if (enabled) classes.add(value); else classes.delete(value);
                return enabled;
            }
        },
        setAttribute(name, value) { this.attributes[name] = value; },
        addEventListener(name, callback) { listeners[name] = callback; },
        fire(name, event = {}) { return listeners[name]?.(event); },
        appendChild(child) { this.children.push(child); },
        replaceChildren() { this.children = []; },
        querySelectorAll() { return []; },
        contains(target) { return target === this; },
        focus() { this.focused = true; }, click() { this.clicked = true; }
    };
}

function setup(productDetails = {}, options = {}) {
    const nodes = new Map();
    const get = id => {
        if (!nodes.has(id)) nodes.set(id, element());
        return nodes.get(id);
    };
    const documents = options.documents || [
        { id: '1', nombre: 'Conteo Café', realizado_por: 'Ana', tienda: 'CENTRO', updated_at: '2026-11-01T12:00:00Z' },
        { id: '2', nombre: 'Conteo Arroz', realizado_por: 'Luis', tienda: 'CENTRO', updated_at: '2026-11-02T12:00:00Z' },
        { id: '3', nombre: 'Conteo Café', realizado_por: 'Luis', tienda: 'SAN DIEGO', updated_at: '2026-11-02T12:00:00Z' },
        { id: '4', nombre: 'Conteo externo', realizado_por: 'Ana', tienda: 'OTRA', updated_at: '2026-11-02T12:00:00Z' }
    ];
    const events = {};
    const tableRows = ['A', 'B', 'C'].map(codigo => {
        const code = { value: codigo }, quantity = { value: '0' };
        return { querySelector: selector => selector === '.inp-codigo' ? code : quantity };
    });
    get('inventario-lista-documentos').querySelectorAll = () => {
        return [...get('inventario-lista-documentos').innerHTML.matchAll(/id="inventario-doc-(\d+)"[\s\S]*?data-tienda="([^"]+)"([\s\S]*?)class="peer/g)].map(match => {
            const input = element();
            input.dataset = { id: match[1], tienda: match[2] };
            input.checked = /\bchecked\b/.test(match[3]);
            nodes.set(`inventario-doc-${match[1]}`, input);
            return input;
        });
    };
    let requests = 0;
    const urls = [];
    let now = Date.now();
    class ClockDate extends Date { static now() { return now; } }
    const notifications = [];
    const window = {
        tiendaActivaPestana: 'CENTRO',
        matrizTiendas: { CENTRO: { A: 90, B: 80, C: 70 }, 'SAN DIEGO': { A: 60, B: 50, C: 40 } },
        asegurarEstructuraTienda() {},
        recancularFilaConInventario() { if (this.failOnStore === this.tiendaActivaPestana) throw new Error('Fallo de cálculo'); }
    };
    const guardarEstadoTablaEnMemoria = tienda => {
        window.matrizTiendas[tienda] = Object.fromEntries(tableRows.map(row => [row.querySelector('.inp-codigo').value, Number(row.querySelector('.inp-inv-emp').value)]));
    };
    const cargarEstadoTablaDesdeMemoria = tienda => tableRows.forEach(row => {
        row.querySelector('.inp-inv-emp').value = String(window.matrizTiendas[tienda][row.querySelector('.inp-codigo').value] || 0);
    });
    cargarEstadoTablaDesdeMemoria('CENTRO');
    vm.runInNewContext(source, {
        window, console, Map, Set, Date: ClockDate, URLSearchParams, AbortController, setTimeout, clearTimeout,
        mostrarNotificacion: message => notifications.push(message),
        guardarEstadoTablaEnMemoria, cargarEstadoTablaDesdeMemoria,
        document: {
            getElementById: get, createElement: element,
            querySelectorAll: selector => selector === '.btn-pestana-tienda'
                ? (options.tiendas || ['CENTRO', 'SAN DIEGO']).map(tienda => ({ dataset: { tienda } }))
                : selector === '#filas-tabla-analisis tr' ? tableRows : [],
            addEventListener: (name, callback) => { events[name] = callback; }
        },
        fetch: async (url, fetchOptions) => {
            requests++;
            urls.push(url);
            if (options.fetch) return options.fetch(url, fetchOptions);
            if (url.startsWith('/api/analisis/inventarios?')) {
                const params = new URLSearchParams(url.split('?')[1]);
                const normalize = text => String(text || '').toLowerCase();
                const rows = documents.filter(doc => (!params.get('tienda') || doc.tienda === params.get('tienda'))
                    && (!params.get('fecha') || (doc.updated_at || doc.created_at).slice(0, 10) === params.get('fecha'))
                    && params.getAll('tags').every(tag => normalize([doc.nombre, doc.realizado_por, doc.tienda].join(' ')).includes(normalize(tag))));
                const offset = (Number(params.get('page')) - 1) * 20;
                return { ok: true, json: async () => ({ ok: true, inventarios: rows.slice(offset, offset + 20), hay_mas: rows.length > offset + 20 }) };
            }
            return { ok: true, json: async () => ({ ok: true, productos: productDetails[url.split('/').pop()] || [] }) };
        }
    });
    events.DOMContentLoaded();
    return {
        get, window, events, tableRows, notifications, urls, requests: () => requests,
        flush: () => new Promise(resolve => setImmediate(resolve)),
        advance(ms) { now += ms; },
        select(id, checked = true) { const input = get(`inventario-doc-${id}`); input.checked = checked; input.fire('change'); },
        filterStore(name) { get('inventario-menu-tiendas').children.find(button => button.textContent === name).fire('click'); },
        rows: () => [...get('inventario-lista-documentos').innerHTML.matchAll(/id="inventario-doc-(\d+)"/g)].map(match => match[1]),
        enter(text) {
            get('inventario-buscar-texto').value = text;
            get('inventario-buscar-texto').fire('keydown', { key: 'Enter', preventDefault() {} });
        },
        removeBadge(text) {
            const badge = get('inventario-badges-buscador').children.find(item => item.children[0].textContent === text);
            badge.children[1].fire('click');
        }
    };
}

test('escribir no consulta; Enter busca con criterios acumulados y reutiliza filtros anteriores', async () => {
    const app = setup();
    await app.window.abrirModalImportarInventarios();
    assert.deepEqual(app.rows(), ['2', '1', '3']);
    app.get('inventario-buscar-texto').value = 'cafe';
    app.get('inventario-buscar-texto').fire('input');
    assert.deepEqual(app.rows(), ['2', '1', '3']);
    app.enter('caf\u00e9');
    await app.flush();
    assert.deepEqual(app.rows(), ['3', '1']);
    app.enter('Luis');
    await app.flush();
    assert.deepEqual(app.rows(), ['3']);
    app.removeBadge('Luis');
    await app.flush();
    assert.deepEqual(app.rows(), ['3', '1']);
    app.removeBadge('caf\u00e9');
    await app.flush();
    assert.deepEqual(app.rows(), ['2', '1', '3']);
    assert.equal(app.requests(), 3);
});

test('selector de tiendas muestra las tiendas disponibles y permite quitar el filtro', async () => {
    const app = setup();
    await app.window.abrirModalImportarInventarios();
    assert.equal(app.get('inventario-menu-tiendas').children.length, 3);
    assert.deepEqual(app.rows(), ['2', '1', '3']);
    const button = app.get('inventario-menu-tiendas').children.find(item => item.textContent === 'SAN DIEGO');
    app.get('inventario-btn-tiendas').fire('click');
    assert.equal(app.get('inventario-btn-tiendas').attributes['aria-expanded'], 'true');
    button.fire('click');
    await app.flush();
    assert.deepEqual(app.rows(), ['3']);
    assert.equal(app.get('inventario-btn-tiendas').attributes['aria-expanded'], 'false');
    app.removeBadge('SAN DIEGO');
    await app.flush();
    assert.deepEqual(app.rows(), ['2', '1', '3']);
    app.filterStore('CENTRO');
    await app.flush();
    assert.deepEqual(app.rows(), ['2', '1']);
});

test('calendario filtra un día exacto y su badge permite quitar la fecha', async () => {
    const app = setup();
    await app.window.abrirModalImportarInventarios();
    let opened = false;
    app.get('inventario-fecha').showPicker = () => { opened = true; };
    app.get('inventario-btn-fecha').fire('click');
    assert.equal(opened, true);
    app.get('inventario-fecha').value = '2026-11-01';
    app.get('inventario-fecha').fire('change');
    await app.flush();
    assert.deepEqual(app.rows(), ['1']);
    app.removeBadge('01/11/2026');
    await app.flush();
    assert.equal(app.get('inventario-fecha').value, '');
    assert.deepEqual(app.rows(), ['2', '1', '3']);
    app.get('inventario-fecha').showPicker = () => { throw new Error('unsupported'); };
    app.get('inventario-btn-fecha').fire('click');
    assert.equal(app.get('inventario-fecha').clicked, true);
});

test('fechas escritas se confirman con Enter; duplicados y composición no agregan badges', async () => {
    const app = setup();
    await app.window.abrirModalImportarInventarios();
    app.enter('2/11/26');
    await app.flush();
    assert.deepEqual(app.rows(), ['2', '3']);
    assert.equal(app.get('inventario-fecha').value, '2026-11-02');
    app.enter('arroz'); app.enter('ARROZ');
    await app.flush();
    assert.equal(app.get('inventario-badges-buscador').children.length, 2);
    app.get('inventario-buscar-texto').value = 'Luis';
    app.get('inventario-buscar-texto').fire('keydown', { key: 'Enter', isComposing: true });
    assert.equal(app.get('inventario-badges-buscador').children.length, 2);
    app.get('inventario-buscar-texto').value = '';
    app.get('inventario-buscar-texto').fire('keydown', { key: 'Backspace' });
    await app.flush();
    assert.equal(app.get('inventario-badges-buscador').children.length, 1);
});

test('limpiar y reabrir restablecen filtros y selección sin limitar a la tienda activa', async () => {
    const app = setup();
    await app.window.abrirModalImportarInventarios();
    app.enter('caf\u00e9'); app.enter('1/11/2026');
    await app.flush();
    app.get('inventario-limpiar-buscador').fire('click');
    await app.flush();
    assert.deepEqual(app.rows(), ['2', '1', '3']);
    assert.equal(app.get('inventario-fecha').value, '');
    assert.equal(app.get('inventario-badges-buscador').children.length, 0);
    app.window.cerrarModalImportarInventarios();
    app.window.tiendaActivaPestana = 'SAN DIEGO';
    await app.window.abrirModalImportarInventarios();
    assert.deepEqual(app.rows(), ['2', '1', '3']);
    assert.equal(app.get('inventario-badges-buscador').children.length, 0);
    assert.equal(app.get('btn-previsualizar-importacion-inventario').disabled, true);
});

test('seleccionar otro documento de la misma tienda reemplaza el anterior y conserva otras tiendas', async () => {
    const app = setup();
    await app.window.abrirModalImportarInventarios();
    app.filterStore('CENTRO');
    await app.flush();
    app.select('1'); app.select('2');
    assert.equal(app.get('inventario-doc-1').checked, false);
    assert.equal(app.get('inventario-doc-2').checked, true);
    assert.match(app.get('inventario-resumen-seleccion').textContent, /^1 documento/);
    app.filterStore('SAN DIEGO');
    await app.flush();
    app.select('3');
    assert.match(app.get('inventario-resumen-seleccion').textContent, /^2 documento/);
    app.select('3', false);
    assert.match(app.get('inventario-resumen-seleccion').textContent, /^1 documento/);
    app.filterStore('CENTRO');
    await app.flush();
    assert.equal(app.get('inventario-doc-1').checked, false);
    assert.equal(app.get('inventario-doc-2').checked, true);
});

test('seleccionar y desmarcar visibles respeta el filtro y no borra otras selecciones', async () => {
    const app = setup();
    await app.window.abrirModalImportarInventarios();
    app.select('3');
    app.filterStore('CENTRO');
    await app.flush();
    app.window.seleccionarInventariosVisibles();
    assert.match(app.get('inventario-resumen-seleccion').textContent, /^2 documento/);
    assert.equal(app.get('inventario-doc-2').checked, true);
    assert.equal(app.get('inventario-doc-1').checked, false);
    app.window.seleccionarInventariosVisibles();
    assert.match(app.get('inventario-resumen-seleccion').textContent, /^1 documento/);
    app.window.limpiarSeleccionInventarios();
    assert.equal(app.get('btn-previsualizar-importacion-inventario').disabled, true);
});

test('importa solo el documento elegido por tienda, incluso si el usuario elige uno anterior', async () => {
    const app = setup({
        '1': [{ codigo: 'A', cantidad: 3 }, { codigo: 'B', cantidad: 5 }],
        '2': [{ codigo: 'A', cantidad: 8 }, { codigo: 'X', cantidad: 9 }],
        '3': [{ codigo: 'B', cantidad: 12 }]
    });
    await app.window.abrirModalImportarInventarios();
    app.select('2'); app.select('1'); app.select('3');
    await app.window.previsualizarImportacionInventarios();
    assert.equal(app.get('btn-confirmar-importacion-inventario').disabled, false);
    assert.match(app.get('inventario-vista-previa').innerHTML, /CENTRO — Conteo Café/);
    assert.equal(app.get('inventario-vista-previa').innerHTML.includes('Conteo Arroz'), false);
    assert.equal(app.window.matrizTiendas.CENTRO.A, 90);
    await app.window.confirmarImportacionInventarios();
    assert.deepEqual(app.window.matrizTiendas.CENTRO, { A: 3, B: 5, C: 0 });
    assert.deepEqual(app.window.matrizTiendas['SAN DIEGO'], { A: 0, B: 12, C: 0 });
    assert.equal(app.window.tiendaActivaPestana, 'CENTRO');
    assert.deepEqual(app.tableRows.map(row => row.querySelector('.inp-inv-emp').value), ['3', '5', '0']);
});

test('una tienda sin coincidencias impide confirmar la importación de toda la selección', async () => {
    const app = setup({ '1': [{ codigo: 'A', cantidad: 3 }], '3': [{ codigo: 'X', cantidad: 12 }] });
    await app.window.abrirModalImportarInventarios();
    app.select('1'); app.select('3');
    await app.window.previsualizarImportacionInventarios();
    assert.equal(app.get('btn-confirmar-importacion-inventario').disabled, true);
    assert.equal(app.window.matrizTiendas.CENTRO.A, 90);
});

test('un fallo al aplicar inventarios revierte todas las tiendas y restaura la tienda visible', async () => {
    const app = setup({ '1': [{ codigo: 'A', cantidad: 3 }], '3': [{ codigo: 'B', cantidad: 12 }] });
    await app.window.abrirModalImportarInventarios();
    app.select('1'); app.select('3');
    await app.window.previsualizarImportacionInventarios();
    const before = JSON.stringify(app.window.matrizTiendas);
    app.window.failOnStore = 'CENTRO';
    await app.window.confirmarImportacionInventarios();
    assert.equal(JSON.stringify(app.window.matrizTiendas), before);
    assert.equal(app.window.tiendaActivaPestana, 'CENTRO');
    assert.deepEqual(app.tableRows.map(row => row.querySelector('.inp-inv-emp').value), ['90', '80', '70']);
    assert.equal(app.notifications.at(-1).tipo, 'error');
});

test('carga 20 por página, conserva selecciones entre páginas y reutiliza páginas durante un minuto', async () => {
    const documents = Array.from({ length: 45 }, (_, index) => ({
        id: String(index + 1), nombre: `Conteo ${index + 1}`, tienda: index < 20 ? 'CENTRO' : 'SAN DIEGO',
        updated_at: '2026-11-02T12:00:00Z'
    }));
    const app = setup({}, { documents });
    await app.window.abrirModalImportarInventarios();
    assert.equal(app.rows().length, 20);
    assert.equal(app.requests(), 1);
    app.select('1');
    app.get('inventario-pagina-siguiente').fire('click'); await app.flush();
    assert.equal(app.rows().length, 20);
    app.select('21');
    assert.match(app.get('inventario-resumen-seleccion').textContent, /^2 documento/);
    await app.window.previsualizarImportacionInventarios();
    assert.equal(app.urls.includes('/api/analisis/inventarios/1'), true);
    assert.equal(app.urls.includes('/api/analisis/inventarios/21'), true);
    app.get('inventario-pagina-anterior').fire('click'); await app.flush();
    assert.equal(app.get('inventario-doc-1').checked, true);
    const requests = app.requests();
    app.window.cerrarModalImportarInventarios();
    await app.window.abrirModalImportarInventarios();
    assert.equal(app.requests(), requests);
    app.advance(60001);
    await app.window.abrirModalImportarInventarios();
    assert.equal(app.requests(), requests + 1);
    app.get('inventario-actualizar-listado').fire('click'); await app.flush();
    assert.equal(app.requests(), requests + 2);
});

test('dos aperturas simultáneas comparten la misma solicitud', async () => {
    let finish;
    const app = setup({}, { fetch: () => new Promise(resolve => { finish = resolve; }) });
    const first = app.window.abrirModalImportarInventarios();
    const second = app.window.abrirModalImportarInventarios();
    assert.equal(app.requests(), 1);
    finish({ ok: true, json: async () => ({ ok: true, inventarios: [], hay_mas: false }) });
    await Promise.all([first, second]);
    assert.equal(app.get('inventario-pagina-siguiente').disabled, true);
});

test('al cambiar filtro cancela la consulta anterior y una respuesta tardía no reemplaza los resultados', async () => {
    const pending = [];
    const app = setup({}, { fetch: (url, options) => new Promise(resolve => pending.push({ url, options, resolve })) });
    const first = app.window.abrirModalImportarInventarios();
    app.filterStore('SAN DIEGO');
    assert.equal(pending[0].options.signal.aborted, true);
    pending[1].resolve({ ok: true, json: async () => ({ ok: true, inventarios: [
        { id: '3', tienda: 'SAN DIEGO', nombre: 'Actual', updated_at: '2026-11-02' }
    ] }) });
    await app.flush();
    pending[0].resolve({ ok: true, json: async () => ({ ok: true, inventarios: [
        { id: '1', tienda: 'CENTRO', nombre: 'Anterior', updated_at: '2026-11-01' }
    ] }) });
    await first;
    assert.deepEqual(app.rows(), ['3']);
});

test('un error de carga no se conserva en caché y permite reintentar', async () => {
    let fail = true;
    const app = setup({}, { fetch: async () => {
        if (fail) throw new Error('Sin conexión');
        return { ok: true, json: async () => ({ ok: true, inventarios: [] }) };
    } });
    await app.window.abrirModalImportarInventarios();
    assert.match(app.get('inventario-lista-documentos').innerHTML, /Sin conexión/);
    fail = false;
    app.get('inventario-actualizar-listado').fire('click'); await app.flush();
    assert.equal(app.requests(), 2);
    assert.match(app.get('inventario-lista-documentos').innerHTML, /No hay inventarios/);
});

test('doble clic en revisar importa una sola lectura de detalle por documento', async () => {
    const app = setup({ '1': [{ codigo: 'A', cantidad: 1 }] });
    await app.window.abrirModalImportarInventarios();
    app.select('1');
    await Promise.all([app.window.previsualizarImportacionInventarios(), app.window.previsualizarImportacionInventarios()]);
    assert.equal(app.urls.filter(url => url === '/api/analisis/inventarios/1').length, 1);
});

test('revisar varias tiendas limita las lecturas de detalle a dos simultáneas', async () => {
    const tiendas = ['CENTRO', 'SAN DIEGO', 'NAGUANAGUA'];
    const documentos = tiendas.map((tienda, index) => ({ id: String(index + 1), tienda, nombre: tienda, updated_at: '2026-11-02' }));
    const pending = [];
    let active = 0, maximum = 0;
    const app = setup({}, { tiendas, fetch: async url => {
        if (url.includes('?')) return { ok: true, json: async () => ({ ok: true, inventarios: documentos }) };
        active++; maximum = Math.max(maximum, active);
        return new Promise(resolve => pending.push(() => {
            active--;
            resolve({ ok: true, json: async () => ({ ok: true, productos: [{ codigo: 'A', cantidad: 1 }] }) });
        }));
    } });
    await app.window.abrirModalImportarInventarios();
    app.select('1'); app.select('2'); app.select('3');
    const preview = app.window.previsualizarImportacionInventarios();
    assert.equal(pending.length, 2);
    pending[0](); pending[1](); await app.flush();
    assert.equal(pending.length, 3);
    pending[2](); await preview;
    assert.equal(maximum, 2);
});

test('cerrar durante la lectura del detalle cancela solicitudes y evita abrir la confirmación después', async () => {
    let finish, signal;
    const app = setup({}, { fetch: async (url, options) => {
        if (url.includes('?')) return { ok: true, json: async () => ({ ok: true, inventarios: [
            { id: '1', tienda: 'CENTRO', nombre: 'Conteo', updated_at: '2026-11-02' }
        ] }) };
        signal = options.signal;
        return new Promise(resolve => { finish = resolve; });
    } });
    await app.window.abrirModalImportarInventarios();
    app.select('1');
    const preview = app.window.previsualizarImportacionInventarios();
    app.window.cerrarModalImportarInventarios();
    assert.equal(signal.aborted, true);
    finish({ ok: true, json: async () => ({ ok: true, productos: [{ codigo: 'A', cantidad: 1 }] }) });
    await preview;
    assert.equal(app.get('modal-confirmar-importacion-inventario').classList.contains('hidden'), true);
    await app.window.abrirModalImportarInventarios();
    assert.match(app.get('btn-previsualizar-importacion-inventario').innerHTML, /Revisar importación/);
});
