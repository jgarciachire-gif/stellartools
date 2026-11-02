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
        window: { confirm: () => { assert.fail('Usar el modal reutilizable'); }, mostrarConfirmacion: async () => true,
            addEventListener: (name, fn) => { events[name] = fn; }, location: { reload() {} } },
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
        f.btn = element(); f.message = element(); f.omitir = element();
        f.elements.namedItem('productos_json').value = JSON.stringify([{ codigo: 'A', cantidad: 2 }]);
        f.productInputs = { pre: { valueAsNumber: 1 }, emp: { valueAsNumber: 2 }, precio: { valueAsNumber: 3 } };
        f.row = { dataset: { productoIndice: '0' }, querySelector: selector => f.productInputs[selector.match(/"(\w+)"/)[1]] };
        f.querySelector = selector => selector === '.mensaje-orden' ? f.message : selector === '.btn-omitir-orden' ? f.omitir : f.btn;
        f.querySelectorAll = selector => selector === '[data-producto-indice]' ? [f.row] : [...f.inputs, ...Object.values(f.productInputs)];
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
    assert.equal(f.dataset.estado, 'error');
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
    ctx.window.mostrarConfirmacion = async () => false;
    await ctx.cerrarModalDetalleOC(); assert.equal(forms.length, 2);
    ctx.window.mostrarConfirmacion = async () => true;
    let reload = 0;
    ctx.window.location.reload = () => { reload++; };
    await ctx.cerrarModalDetalleOC(); assert.equal(forms.length, 0); assert.equal(reload, 1);
    let prevented = false;
    events.beforeunload({ preventDefault() { prevented = true; } });
    assert.equal(prevented, false);
});

test('permite omitir una orden con error y volver a incluirla sin perder correcciones', async () => {
    const { ctx, form, get } = setup();
    const bad = form('1'), good = form('2');
    bad.productInputs.pre.valueAsNumber = 0;
    ctx.activarEventosFormulariosModal();
    await get('btn-guardar-todo-modal').onclick();
    assert.equal(bad.dataset.estado, 'error');
    assert.equal(good.dataset.estado, 'guardada');
    bad.omitir.onclick();
    assert.equal(bad.dataset.estado, 'omitida');
    assert.equal(get('btn-guardar-todo-modal').disabled, true);
    assert.equal(await ctx.guardarOrdenModal(bad), false);
    bad.omitir.onclick();
    bad.productInputs.pre.valueAsNumber = 4;
    assert.equal(await ctx.guardarOrdenModal(bad), true);
    const product = JSON.parse(bad.elements.namedItem('productos_json').value)[0];
    assert.equal(product.cantidad, 8);
    assert.equal(product.subtotal, 24);
});

test('detener o cerrar durante un guardado cancela la espera y no envía las siguientes órdenes', async () => {
    for (const close of [false, true]) {
        const { ctx, form, get, forms, events } = setup();
        const one = form('1'), two = form('2');
        let calls = 0, reloads = 0;
        ctx.window.location.reload = () => reloads++;
        ctx.fetch = (_url, options) => new Promise((_resolve, reject) => {
            calls++;
            options.signal.addEventListener('abort', () => {
                const error = new Error('Aborted'); error.name = 'AbortError'; reject(error);
            });
        });
        ctx.activarEventosFormulariosModal();
        const pending = get('btn-guardar-todo-modal').onclick();
        assert.equal(get('btn-detener-guardado-oc').hidden, false);
        if (close) await ctx.cerrarModalDetalleOC(); else await ctx.detenerGuardadoOC();
        await pending;
        assert.equal(calls, 1);
        assert.equal(one.dataset.estado, 'error');
        assert.equal(two.dataset.estado, 'pendiente');
        assert.equal(one.inputs.every(i => !i.disabled), true);
        assert.equal(get('btn-detener-guardado-oc').hidden, true);
        assert.match(one.message.textContent, /diario/);
        if (close) {
            assert.equal(forms.length, 0);
            assert.equal(reloads, 1);
            events.beforeunload({ preventDefault() { assert.fail('No debe bloquear la salida'); } });
        } else assert.equal(get('btn-guardar-todo-modal').disabled, false);
    }
});

test('un fallo al iniciar la petición o preparar la revisión restablece la carga', () => {
    for (const stage of ['open', 'render', 'null']) {
        const { ctx, get, requests } = setup();
        get('input-pdf-modal').files = [file()];
        if (stage === 'open') ctx.XMLHttpRequest.prototype.open = () => { throw new Error('connection'); };
        ctx.validarYProcesarPDFModal(event);
        if (stage !== 'open') {
            ctx.renderizarTablaDetalleOC = () => { throw new Error('invalid details'); };
            requests[0].status = 200;
            requests[0].responseText = stage === 'null' ? 'null' : JSON.stringify({ success: true, ordenes: [{}] });
            requests[0].onload(); requests[0].onloadend();
        }
        assert.equal(get('input-pdf-modal').disabled, false);
        assert.equal(get('btn-procesar-pdf-modal').disabled, false);
        assert.equal(get('mensaje-carga-pdf').hidden, false);
    }
});

function setupXML() {
    const env = setup();
    const template = fs.readFileSync('templates/ordenes.html', 'utf8');
    const start = template.indexOf('    const estadoCargaXML =');
    const end = template.indexOf('    function renderizarResumenXML(', start);
    vm.runInContext(template.slice(start, end), env.ctx);
    const cancel = element();
    env.get('modal-cargar-xml').querySelectorAll = selector => {
        const inputs = [env.get('input-xml-modal'), env.get('btn-procesar-xml-modal')];
        return selector.includes('button[type="submit"]') ? inputs : [...inputs, cancel];
    };
    env.get('input-xml-modal').files = [file('a.xml')];
    env.ctx.renderizarResumenXML = result => { env.result = result; };
    env.cancel = cancel;
    return env;
}

test('cancelar extracción espera al modal reutilizable y rechazar conserva la carga', async () => {
    const { ctx, get, requests } = setup();
    get('input-pdf-modal').files = [file()];
    ctx.validarYProcesarPDFModal(event);
    let accept;
    const confirmations = [];
    ctx.window.mostrarConfirmacion = options => {
        confirmations.push(options);
        return new Promise(resolve => { accept = resolve; });
    };
    const pending = ctx.cerrarModalCargarOC();
    await ctx.cerrarModalCargarOC();
    assert.equal(confirmations.length, 1);
    assert.equal(get('input-pdf-modal').disabled, true);
    assert.equal(confirmations[0].textoAceptar, 'Cancelar extracción');
    accept(false); await pending;
    assert.equal(get('input-pdf-modal').disabled, true);
    const confirmed = ctx.cerrarModalCargarOC();
    accept(true); await confirmed;
    assert.equal(get('input-pdf-modal').disabled, false);
    assert.equal(requests.length, 1);
});

test('si la extracción termina mientras se confirma, se conserva la revisión nueva', async () => {
    const { ctx, get, requests } = setup();
    get('input-pdf-modal').files = [file()];
    ctx.renderizarTablaDetalleOC = () => {};
    ctx.validarYProcesarPDFModal(event);
    let accept;
    ctx.window.mostrarConfirmacion = () => new Promise(resolve => { accept = resolve; });
    const closing = ctx.cerrarModalCargarOC();
    requests[0].status = 200;
    requests[0].responseText = JSON.stringify({ success: true, ordenes: [{}] });
    requests[0].onload(); requests[0].onloadend();
    accept(true); await closing;
    assert.equal(get('modal-detalle-extraido-oc').classList.contains('hidden'), false);
});

test('rechazar el modal de interrupción XML deja el procesamiento activo', async () => {
    const env = setupXML();
    env.ctx.procesarXMLModal(event);
    let accept, count = 0;
    env.ctx.window.mostrarConfirmacion = () => { count++; return new Promise(resolve => { accept = resolve; }); };
    const closing = env.ctx.cerrarModalCargarXML();
    await env.ctx.cerrarModalCargarXML();
    assert.equal(count, 1);
    accept(false); await closing;
    assert.equal(env.get('input-xml-modal').disabled, true);
    assert.equal(env.result, undefined);
    env.requests[0].onloadend();
});

test('XML mantiene Cancelar disponible, informa cambios inciertos y permite salir', async () => {
    const env = setupXML();
    env.ctx.procesarXMLModal(event);
    assert.equal(env.cancel.disabled, false);
    assert.equal(env.get('input-xml-modal').disabled, true);
    await env.ctx.cerrarModalCargarXML();
    assert.equal(env.result.incierto, true);
    assert.match(env.result.detalles[0].motivo, /diario/);
    assert.equal(env.get('input-xml-modal').disabled, false);
    assert.equal(env.get('modal-cargar-xml').classList.contains('hidden'), true);
    assert.equal(env.get('modal-detalle-xml-oc').classList.contains('hidden'), false);
});

test('XML recupera controles ante fallos de inicio, red, timeout y respuestas inválidas', () => {
    for (const stage of ['open', 'network', 'timeout', 'null']) {
        const env = setupXML();
        if (stage === 'open') env.ctx.XMLHttpRequest.prototype.open = () => { throw new Error('connection'); };
        env.ctx.procesarXMLModal(event);
        if (stage !== 'open') {
            const xhr = env.requests[0];
            if (stage === 'network') xhr.onerror();
            else if (stage === 'timeout') xhr.ontimeout();
            else { xhr.status = 200; xhr.responseText = 'null'; xhr.onload(); }
            xhr.onloadend();
            assert.equal(env.result.incierto, true);
        }
        assert.equal(env.get('input-xml-modal').disabled, false);
        assert.equal(env.get('btn-procesar-xml-modal').disabled, false);
        assert.equal(env.cancel.disabled, false);
    }
});
