const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const template = fs.readFileSync('templates/analisis_pedido.html', 'utf8');
const scripts = [...template.matchAll(/<script src="\{\{ asset_url\('([^']+)'\) \}\}"([^>]*)><\/script>/g)]
    .map(match => ({ path: `static/${match[1]}`, attributes: match[2] }))
    .filter(script => script.path.startsWith('static/js/analisis/'));

function element(value = '') {
    const classes = new Set();
    let currentValue = String(value);
    return { get value() { return currentValue; }, set value(next) { currentValue = String(next); },
        textContent: '', dataset: {}, style: {}, disabled: false, innerHTML: '', children: [],
        classList: { add: (...items) => items.forEach(item => classes.add(item)), remove: (...items) => items.forEach(item => classes.delete(item)), contains: item => classes.has(item) },
        addEventListener() {}, setAttribute() {}, focus() {}, select() {}, remove() {}, click() {},
        appendChild(child) { this.children.push(child); }, removeChild() {},
        querySelectorAll() { return []; }, querySelector() { return null; }, getBoundingClientRect() { return { height: 0 }; }
    };
}

function setup() {
    const nodes = new Map();
    ['filas-tabla-analisis', 'tabla-analisis', 'tot-empaques', 'tot-unidades', 'tot-monto',
        'dias_cobertura', 'porcentaje_crecimiento', 'proveedor_id_analisis', 'buscar_proveedor_analisis', 'modal-exportar-tiendas'].forEach(id => nodes.set(id, element()));
    nodes.get('dias_cobertura').value = '7';
    nodes.get('porcentaje_crecimiento').value = '10';
    nodes.get('proveedor_id_analisis').value = '5';
    nodes.get('buscar_proveedor_analisis').value = 'Proveedor & Uno';
    const rows = [], events = [], requests = [], notices = [], blobs = [], timers = [], tags = [];
    const tbody = nodes.get('filas-tabla-analisis');
    tbody.children = rows;
    tbody.querySelectorAll = () => rows;
    const selectAll = selector => {
        if (selector === '#filas-tabla-analisis tr') return rows;
        if (selector === '#contenedor-etiquetas-exportar .tag-tienda-exportar.activa') return tags;
        if (selector === '#filas-tabla-analisis .inp-codigo') return rows.map(row => row.querySelector('.inp-codigo'));
        if (selector.startsWith('#filas-tabla-analisis .inp-pre')) return rows.flatMap(row => [row.querySelector('.inp-pre'), row.querySelector('.inp-costo')]);
        return [];
    };
    class DownloadURL extends URL {
        static createObjectURL(blob) { blobs.push(blob); return `blob:${blobs.length}`; }
        static revokeObjectURL() {}
    }
    const ctx = vm.createContext({
        console, Blob, URL: DownloadURL, URLSearchParams, AbortController, AbortSignal, Map, Set, Intl, Date,
        setTimeout: callback => { timers.push(callback); return timers.length; }, clearTimeout() {},
        requestAnimationFrame: callback => { timers.push(callback); },
        document: {
            readyState: 'loading', head: element(), body: element(), activeElement: element(),
            getElementById: id => nodes.get(id) || null,
            querySelectorAll: selectAll, querySelector: () => null, createElement: () => element(),
            addEventListener: (name, fn) => events.push({ owner: 'document', name, fn })
        },
        addEventListener: (name, fn) => events.push({ owner: 'window', name, fn }),
        mostrarNotificacion: data => notices.push(data), mostrarAlerta: async data => notices.push(data), mostrarConfirmacion: async () => true,
        fetch: async (url, options = {}) => {
            requests.push({ url, body: options.body ? JSON.parse(options.body) : null });
            return { ok: true, json: async () => ({ status: 'ok', data: [] }) };
        }
    });
    ctx.window = ctx;
    for (const script of scripts) vm.runInContext(fs.readFileSync(script.path, 'utf8'), ctx, { filename: script.path });
    function row(codigo = '000001', pre = '6', emp = '3', inv = '2', costo = '2.5') {
        const fields = Object.fromEntries(Object.entries({ codigo, pre, emp, 'inv-emp': inv, costo, uni: '0', desc: 'Producto & Uno' })
            .map(([name, value]) => [`.inp-${name}`, element(value)]));
        fields['.txt-subtotal'] = element();
        const tr = { dataset: { codigo }, querySelector: selector => fields[selector.split(',')[0]], querySelectorAll: () => Object.values(fields) };
        Object.values(fields).forEach(field => { field.closest = () => tr; });
        rows.push(tr);
        return tr;
    }
    return { ctx, nodes, rows, row, events, requests, notices, blobs, timers, tags };
}

test('la plantilla carga una sola vez los archivos del análisis y conserva la secuencia de dependencias', () => {
    const names = scripts.map(script => script.path.split('/').at(-1));
    assert.equal(new Set(names).size, names.length);
    const relocated = ['analisis-core.js', 'analisis-proveedores.js', 'analisis-tabla.js', 'analisis-exportacion.js',
        'analisis-pedidos.js', 'analisis-tiendas.js', 'analisis-sugeridos.js', 'analisis-exportacion-tiendas.js', 'analisis-tendencia-periodos.js', 'analisis-kardex.js', 'analisis-vista.js'];
    assert.deepEqual(names.slice(-relocated.length), relocated);
    assert.equal(scripts.filter(script => script.attributes.includes('defer')).length, 1);
    assert.equal(template.includes('type="module"'), false);
    for (const script of scripts) new vm.Script(fs.readFileSync(script.path, 'utf8'), { filename: script.path });
});

test('los módulos exponen las funciones utilizadas por los controles HTML sin ejecutar consultas al cargar', () => {
    const app = setup();
    const handlers = ['limpiarListaProductos', 'seleccionarProveedorDesdeElemento', 'confirmarProductosProveedor',
        'importarProductosAnalisis', 'ordenarTablaAnalisis', 'guardarPlantillaCompleta', 'cargarUltimoPedidoGuardado',
        'cambiarTiendaPestana', 'calcularSugeridoSedeActual', 'confirmarExportacionSeparada', 'exportarConsolidado',
        'abrirModalExportarSeparado', 'compararDemandaKardexDesdeAnalisis', 'exportarDemandaKardexXML',
        'calcularFila', 'recancularFilaConInventario', 'manejarKeyNav', 'ejecutarAccionConCambios', 'abrirModalImportarInventarios'];
    handlers.forEach(name => assert.equal(typeof app.ctx[name], 'function', name));
    assert.equal(app.requests.length, 0);
    assert.ok(app.events.some(event => event.name === 'DOMContentLoaded'));
});

test('cálculos de unidades, empaques y totales conservan sus resultados', () => {
    const app = setup(); const tr = app.row();
    app.ctx.calcularFila(tr.querySelector('.inp-emp'));
    assert.equal(Number(tr.querySelector('.inp-uni').value), 18);
    assert.equal(app.nodes.get('tot-empaques').textContent, '3');
    assert.equal(app.nodes.get('tot-unidades').textContent, '18');
    assert.match(app.nodes.get('tot-monto').textContent, /45,00/);
    tr.querySelector('.inp-uni').value = '24';
    app.ctx.ajustarPorUnidades(tr.querySelector('.inp-uni'));
    assert.equal(Number(tr.querySelector('.inp-emp').value), 4);
    assert.match(app.nodes.get('tot-monto').textContent, /60,00/);
});

test('cambiar de tienda conserva los valores de cada sede y restaura la tabla', async () => {
    const app = setup(); const tr = app.row();
    app.ctx.calcularFila(tr.querySelector('.inp-emp'));
    app.ctx.matrizTiendas['SAN DIEGO'] = { '000001': { invEmp: 8, emp: 5 } };
    await app.ctx.cambiarTiendaPestana('SAN DIEGO');
    assert.equal(Number(tr.querySelector('.inp-emp').value), 5);
    assert.equal(Number(tr.querySelector('.inp-inv-emp').value), 8);
    assert.equal(app.ctx.matrizTiendas.CENTRO['000001'].emp, 3);
    await app.ctx.cambiarTiendaPestana('CENTRO');
    assert.equal(Number(tr.querySelector('.inp-emp').value), 3);
    assert.equal(Number(tr.querySelector('.inp-inv-emp').value), 2);
    assert.equal(app.requests.filter(request => request.url === '/analisis/cobertura-kardex').length, 1);
});

test('sugeridos mantiene cobertura, crecimiento, descuento de inventario y redondeo por presentación', async () => {
    const app = setup(); const tr = app.row();
    app.ctx.fetch = async () => ({ ok: true, json: async () => ({
        fecha_referencia: app.ctx.fechaCaracasSugeridos(),
        data: ['CENTRO', 'NAGUANAGUA', 'ISABELICA', 'CIUDAD ALIANZA', 'GARIBALDI', 'SAN DIEGO']
            .map(sede => ({ sede, codigo: '000001', demanda_diaria: 4 }))
    }) });
    await app.ctx.calcularSugeridoSedeActual();
    // ceil((4 * 7 * 1.10 - 2 * 6) / 6) = 4 empaques.
    assert.equal(Number(tr.querySelector('.inp-emp').value), 4);
    assert.equal(Number(tr.querySelector('.inp-uni').value), 24);
    assert.equal(app.ctx.matrizTiendas['SAN DIEGO']['000001'].emp, 6);
    assert.equal(app.nodes.get('dias_cobertura').disabled, false);
});

test('guardar el pedido conserva la estructura enviada al servidor y excluye códigos ausentes de la tabla', async () => {
    const app = setup(); app.row();
    app.ctx.matrizTiendas['SAN DIEGO'] = { '000001': { invEmp: 1, emp: 4 }, '999999': { invEmp: 9, emp: 9 } };
    await app.ctx.guardarPlantillaCompleta();
    const request = app.requests.find(request => request.url === '/analisis/guardar-pedido');
    assert.equal(request.body.proveedor_id, 5);
    assert.equal(request.body.dias_cobertura, 7);
    assert.deepEqual(JSON.parse(JSON.stringify(request.body.detalles)).sort((a, b) => a.sede.localeCompare(b.sede)), [
        { sede: 'CENTRO', codigo: '000001', sugerido: 2, pedido_final: 3 },
        { sede: 'SAN DIEGO', codigo: '000001', sugerido: 1, pedido_final: 4 }
    ]);
});

test('exportar XML y TXT conserva cantidades, escape XML y saltos CRLF', async () => {
    const app = setup(); const tr = app.row();
    app.ctx.calcularFila(tr.querySelector('.inp-emp'));
    app.ctx.matrizTiendas['SAN DIEGO'] = { '000001': { emp: 4, uni: 24 } };
    await app.ctx.exportarConsolidado();
    const xml = await app.blobs[0].text();
    assert.match(xml, /<emp>7<\/emp>/);
    assert.match(xml, /Producto &amp; Uno/);
    assert.match(xml, /proveedor="Proveedor &amp; Uno"/);
    app.tags.push({ dataset: { tienda: 'CENTRO' } }, { dataset: { tienda: 'SAN DIEGO' } });
    await app.ctx.confirmarExportacionSeparada();
    while (app.timers.length) app.timers.shift()();
    assert.equal(await app.blobs[1].text(), '000001|18|\r\n');
    assert.equal(await app.blobs[2].text(), '000001|24|\r\n');
});

test('cambios pendientes en PRE y costo siguen detectándose y pueden marcarse como guardados', () => {
    const app = setup(); const tr = app.row();
    tr.querySelector('.inp-pre').dataset.original = '6';
    tr.querySelector('.inp-costo').dataset.original = '2.5';
    assert.equal(app.ctx.obtenerProductosModificados().length, 0);
    tr.querySelector('.inp-costo').value = '3';
    assert.equal(app.ctx.obtenerProductosModificados().length, 1);
    app.ctx.marcarCambiosComoGuardados();
    assert.equal(app.ctx.obtenerProductosModificados().length, 0);
});
