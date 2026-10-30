// node --test tests/ordenes-carga.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/ordenes-carga.js', 'utf8');

function element() {
    const classes = new Set(['hidden']);
    return { classList: { add: (...v) => v.forEach(x => classes.add(x)), remove: (...v) => v.forEach(x => classes.delete(x)), contains: x => classes.has(x) },
        dataset: {}, style: {}, disabled: false, hidden: true, textContent: '', value: '', files: [],
        setAttribute() {}, focus() {}, addEventListener() {}, replaceChildren() {} };
}

function setup() {
    const elements = new Map();
    const forms = [];
    const requests = [];
    const events = {};
    const get = id => {
        if (!elements.has(id)) elements.set(id, element());
        return elements.get(id);
    };
    const ctx = vm.createContext({ console, Error, TypeError, AbortController, setTimeout, clearTimeout,
        document: { getElementById: get, querySelectorAll: () => forms, createElement: () => element() },
        window: { confirm: () => true, addEventListener: (name, fn) => { events[name] = fn; }, location: { reload() {} } },
        FormData: class {
            constructor(form) { this.values = form ? Object.fromEntries(form.inputs.map(i => [i.name, i.value])) : {}; }
            append(name, value) { (this.values[name] ||= []).push(value); }
        },
        XMLHttpRequest: class {
            constructor() { this.upload = {}; requests.push(this); }
            open() {} setRequestHeader() {} send(data) { this.data = data; }
            abort() { this.onabort(); this.onloadend(); }
        },
        fetch: async () => ({ ok: true, status: 200, json: async () => ({ status: 'ok' }) })
    });
    vm.runInContext(source, ctx);
    function form(number = '1') {
        const f = element();
        f.dataset.estado = 'pendiente';
        f.inputs = Object.entries({ numero_orden: number, proveedor: 'Proveedor', tienda_destino: 'Tienda', monto_total: '1', fecha_emision: '2026-10-30', dias_inventario: '15', productos_json: '[]' }).map(([name, value]) => ({ name, value, disabled: false }));
        f.elements = { namedItem: name => f.inputs.find(i => i.name === name) };
        f.btn = element(); f.message = element();
        f.querySelector = selector => selector === '.mensaje-orden' ? f.message : f.btn;
        f.querySelectorAll = () => f.inputs;
        f.reportValidity = () => true;
        forms.push(f);
        return f;
    }
    get('contenedor-tarjetas-oc').replaceChildren = () => { forms.length = 0; };
    return { ctx, forms, form, get, requests, events };
}
const event = { preventDefault() {} };
const file = (name = 'order.pdf', size = 100) => ({ name, size, lastModified: 1 });

test('escapa los datos del PDF para texto y atributos HTML', () => {
    const { ctx } = setup();
    assert.equal(vm.runInContext('ocEscapar', ctx)('<img src=x onerror="x">&\''), '&lt;img src=x onerror=&quot;x&quot;&gt;&amp;&#39;');
});

test('la revisión no interpreta los nombres, proveedores ni productos como HTML', () => {
    const { ctx, get } = setup();
    const cards = [];
    get('contenedor-tarjetas-oc').appendChild = card => cards.push(card);
    ctx.activarEventosFormulariosModal = () => {};
    ctx.ocActualizarResumen = () => {};
    const malicious = '\"><img src=x onerror="alert(1)">&';
    ctx.renderizarTablaDetalleOC([{ nombre_archivo: malicious, proveedor: malicious, productos: [{ codigo: malicious, descripcion: malicious }] }]);
    assert.equal(cards.length, 1);
    assert.equal(cards[0].innerHTML.includes('<img'), false);
    assert.equal(cards[0].innerHTML.includes('&lt;img'), true);
    assert.equal(cards[0].innerHTML.includes('name="productos_json"'), true);
});

test('rechaza vacíos, extensiones incorrectas, exceso de tamaño/cantidad y repetidos antes de subir', () => {
    for (const files of [[], [file('x.txt')], [file('x.pdf', 0)], [file('x.pdf', 4194305)], Array.from({ length: 21 }, () => file()), [file(), file()]]) {
        const { ctx, get, requests } = setup();
        get('input-pdf-modal').files = files;
        ctx.validarYProcesarPDFModal(event);
        assert.equal(requests.length, 0);
        assert.equal(get('mensaje-carga-pdf').hidden, false);
    }
});

test('extracción parcial abre revisión, bloquea doble envío y restablece controles', () => {
    const { ctx, get, requests } = setup();
    get('input-pdf-modal').files = [file()];
    let result;
    ctx.renderizarTablaDetalleOC = (orders, data) => { result = data; };
    ctx.validarYProcesarPDFModal(event);
    ctx.validarYProcesarPDFModal(event);
    assert.equal(requests.length, 1);
    assert.equal(get('input-pdf-modal').disabled, true);
    const xhr = requests[0];
    xhr.status = 200;
    xhr.responseText = JSON.stringify({ success: true, ordenes: [{}], errores: [{ archivo: 'bad.pdf', mensaje: 'bad' }] });
    xhr.onload(); xhr.onloadend();
    assert.equal(result.errores.length, 1);
    assert.equal(get('modal-detalle-extraido-oc').classList.contains('hidden'), false);
    assert.equal(get('input-pdf-modal').disabled, false);
});

test('errores de extracción, respuesta inválida, timeout, red y cancelación permiten reintentar', () => {
    for (const outcome of ['empty', 'invalid', 'session', 'timeout', 'network', 'abort']) {
        const { ctx, get, requests } = setup();
        get('input-pdf-modal').files = [file()];
        ctx.validarYProcesarPDFModal(event);
        const xhr = requests[0];
        if (outcome === 'empty') {
            xhr.status = 422; xhr.responseText = JSON.stringify({ success: false, errores: [{ archivo: 'a.pdf', mensaje: 'No products' }] }); xhr.onload();
        } else if (outcome === 'invalid' || outcome === 'session') {
            xhr.responseText = '<html>'; xhr.responseURL = outcome === 'session' ? '/login' : '/error'; xhr.onload();
        } else if (outcome === 'timeout') xhr.ontimeout();
        else if (outcome === 'network') xhr.onerror();
        else xhr.onabort();
        xhr.onloadend();
        assert.equal(get('btn-procesar-pdf-modal').disabled, false);
        assert.ok(get('mensaje-carga-pdf').textContent);
        assert.equal(get('modal-detalle-extraido-oc').classList.contains('hidden'), true);
    }
});

test('formulario inválido no realiza ninguna escritura', async () => {
    const { ctx, form } = setup();
    const f = form(); f.reportValidity = () => false;
    ctx.fetch = () => { throw new Error('Must not request'); };
    assert.equal(await ctx.guardarOrdenModal(f), false);
    assert.equal(f.dataset.estado, 'pendiente');
});

test('doble clic guarda una sola vez y congela los datos durante el guardado', async () => {
    const { ctx, form } = setup();
    const f = form(); let finish; let calls = 0;
    ctx.fetch = () => { calls++; return new Promise(resolve => { finish = resolve; }); };
    const pending = ctx.guardarOrdenModal(f);
    assert.equal(f.inputs.every(i => i.disabled), true);
    assert.equal(await ctx.guardarOrdenModal(f), false);
    finish({ ok: true, status: 200, json: async () => ({ status: 'ok' }) });
    assert.equal(await pending, true);
    assert.equal(calls, 1);
    assert.equal(f.dataset.estado, 'guardada');
    assert.equal(await ctx.guardarOrdenModal(f), false);
});

test('duplicados, datos inválidos, sesión, errores del servidor y de red conservan la revisión', async () => {
    for (const status of [409, 422, 401, 429, 500, 'network', 'timeout', 'html']) {
        const { ctx, form } = setup(); const f = form();
        ctx.fetch = async () => {
            if (status === 'network') throw new TypeError('Failed to fetch');
            if (status === 'timeout') { const e = new Error('timeout'); e.name = 'AbortError'; throw e; }
            return { ok: false, status: typeof status === 'number' ? status : 200, json: async () => {
                if (status === 'html') throw new Error('Invalid JSON');
                return { status: 'error', mensaje: 'Error recuperable' };
            } };
        };
        assert.equal(await ctx.guardarOrdenModal(f), false);
        assert.equal(f.dataset.estado, status === 409 ? 'duplicada' : 'error');
        assert.equal(f.inputs.every(i => !i.disabled), true);
        assert.equal(f.btn.disabled, false);
        assert.ok(f.message.textContent);
    }
});

test('guardar pendientes conserva éxitos y omite duplicados al reintentar', async () => {
    const { ctx, form, get } = setup();
    const one = form('1'), two = form('2'), three = form('3');
    const statuses = [200, 409, 422, 200]; let calls = 0;
    ctx.fetch = async () => { const status = statuses[calls++]; return { ok: status === 200, status, json: async () => ({ status: status === 200 ? 'ok' : 'error' }) }; };
    ctx.activarEventosFormulariosModal();
    await get('btn-guardar-todo-modal').onclick();
    assert.deepEqual([one.dataset.estado, two.dataset.estado, three.dataset.estado], ['guardada', 'duplicada', 'error']);
    await get('btn-guardar-todo-modal').onclick();
    assert.equal(calls, 4);
    assert.equal(three.dataset.estado, 'guardada');
});

test('el lote se detiene al vencer la sesión y conserva las siguientes pendientes', async () => {
    const { ctx, form, get } = setup(); const one = form('1'), two = form('2');
    let calls = 0;
    ctx.fetch = async () => { calls++; return { ok: false, status: 401, json: async () => ({}) }; };
    ctx.activarEventosFormulariosModal();
    await get('btn-guardar-todo-modal').onclick();
    assert.equal(calls, 1);
    assert.equal(one.dataset.estado, 'error');
    assert.equal(two.dataset.estado, 'pendiente');
});

test('la misma orden dentro del lote no vuelve a enviarse', async () => {
    const { ctx, form } = setup(); const one = form(), two = form(); let calls = 0;
    ctx.fetch = async () => { calls++; return { ok: true, status: 200, json: async () => ({ status: 'ok' }) }; };
    await ctx.guardarOrdenModal(one);
    await ctx.guardarOrdenModal(two);
    assert.equal(calls, 1);
    assert.equal(two.dataset.estado, 'duplicada');
});

test('cerrar requiere confirmar pendientes y no provoca una segunda advertencia al recargar', async () => {
    const { ctx, form, forms, events } = setup(); const one = form('1'); form('2');
    await ctx.guardarOrdenModal(one);
    ctx.window.confirm = () => false;
    ctx.cerrarModalDetalleOC(); assert.equal(forms.length, 2);
    ctx.window.confirm = () => true;
    let reload = 0;
    ctx.window.location.reload = () => { reload++; };
    ctx.cerrarModalDetalleOC(); assert.equal(forms.length, 0); assert.equal(reload, 1);
    let prevented = false;
    events.beforeunload({ preventDefault() { prevented = true; } });
    assert.equal(prevented, false);
});
