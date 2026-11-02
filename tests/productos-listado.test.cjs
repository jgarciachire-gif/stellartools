const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/productos-listado.js', 'utf8');
const searchSource = fs.readFileSync('templates/productos.html', 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];

function setupSearch() {
    const handlers = {};
    const ready = [];
    const calls = [];
    const timers = [];
    const input = { value: '', addEventListener(name, fn) { handlers[name] = fn; } };
    const fields = { busqueda_productos: input, form_ficha_q: {}, form_ficha_tags: {} };
    const ctx = vm.createContext({
        URL, URLSearchParams,
        window: { location: { href: 'http://test/productos', search: '' } },
        document: {
            getElementById: id => fields[id],
            addEventListener(name, fn) { if (name === 'DOMContentLoaded') ready.push(fn); }
        },
        cargarListadoProductos: url => calls.push(url),
        setTimeout: fn => timers.push(fn), clearTimeout() {}
    });
    vm.runInContext(searchSource, ctx);
    ctx.renderizarEtiquetasProds = () => {};
    ready.forEach(fn => fn());
    return {ctx, input, handlers, calls, timers};
}

test('escribir no consulta; Enter crea el badge y envía una sola búsqueda', () => {
    const {input, handlers, calls, timers} = setupSearch();
    input.value = 'pan';
    handlers.input?.({});
    timers.forEach(fn => fn());
    assert.equal(calls.length, 0);
    handlers.keydown({key: 'Enter', preventDefault() {}});
    assert.equal(calls.length, 1);
    assert.equal(calls[0].searchParams.get('tags'), 'pan');
    assert.equal(calls[0].searchParams.has('q'), false);
    assert.equal(input.value, '');
});

test('Enter vacío o un badge repetido no genera más consultas', () => {
    const {input, handlers, calls} = setupSearch();
    handlers.keydown({key: 'Enter', preventDefault() {}});
    assert.equal(calls.length, 0);
    input.value = 'pan';
    handlers.keydown({key: 'Enter', preventDefault() {}});
    input.value = 'PAN';
    handlers.keydown({key: 'Enter', preventDefault() {}});
    assert.equal(calls.length, 1);
});

test('eliminar un badge actualiza la búsqueda e ignora el texto sin confirmar', () => {
    const {ctx, input, handlers, calls} = setupSearch();
    input.value = 'pan';
    handlers.keydown({key: 'Enter', preventDefault() {}});
    input.value = 'sin confirmar';
    ctx.removerEtiquetaProd(0);
    assert.equal(calls.length, 2);
    assert.equal(calls[1].searchParams.get('tags'), '');
    assert.equal(calls[1].searchParams.has('q'), false);
    assert.equal(input.value, 'sin confirmar');
});

function setup() {
    const elements = new Map();
    const requests = [];
    const history = [];
    const get = id => {
        if (!elements.has(id)) elements.set(id, {
            innerHTML: '', textContent: '', attributes: {}, open: false,
            setAttribute(name, value) { this.attributes[name] = value; },
            removeAttribute(name) { delete this.attributes[name]; },
            showModal() { this.open = true; }, close() { this.open = false; },
            focus() {}, querySelector(selector) { return selector === '[role="status"]' ? get('message') : get('close-button'); }
        });
        return elements.get(id);
    };
    const ctx = vm.createContext({
        AbortController, URL, console, clearTimeout,
        document: { getElementById: get, addEventListener() {}, body: { appendChild() {} } },
        window: {
            location: { href: 'http://test/productos?q=pan&page=2&sort=precio&dir=desc', origin: 'http://test', assign() {} },
            history: { replaceState(...args) { history.push(args[2]); }, pushState(...args) { history.push(args[2]); } },
            addEventListener() {}
        },
        fetch: (url, options) => new Promise(resolve => requests.push({url, options, resolve})),
        DOMParser: class {
            parseFromString(html) {
                return { getElementById(id) {
                    if (id === 'lista-productos') return { innerHTML: html };
                    if (id === 'contenido-ficha-producto') return {
                        innerHTML: html, querySelector() { return html === 'missing' ? null : {}; }
                    };
                } };
            }
        }
    });
    vm.runInContext(source, ctx);
    function respond(index, html, ok = true) {
        const request = requests[index];
        request.resolve({ ok, url: String(request.url), text: async () => html });
    }
    return {ctx, get, requests, history, respond};
}

test('actualiza la tabla y conserva filtros, página y orden en la URL', async () => {
    const {ctx, get, history, respond} = setup();
    const url = 'http://test/productos?q=pan&page=3&sort=precio&dir=desc';
    const pending = ctx.cargarListadoProductos(url, 'push');
    assert.equal(get('lista-productos').attributes['aria-busy'], 'true');
    assert.equal(get('cargando-listado-productos').hidden, false);
    respond(0, 'page-3');
    await pending;
    assert.equal(get('lista-productos').innerHTML, 'page-3');
    assert.equal(String(history[0]), url);
    assert.equal(get('lista-productos').attributes['aria-busy'], undefined);
    assert.equal(get('cargando-listado-productos').hidden, true);
});

test('una consulta cancelada no oculta el indicador de la búsqueda vigente', async () => {
    const {ctx, get, respond} = setup();
    const old = ctx.cargarListadoProductos('http://test/productos?q=old');
    const latest = ctx.cargarListadoProductos('http://test/productos?q=latest');
    respond(0, 'old'); await old;
    assert.equal(get('cargando-listado-productos').hidden, false);
    respond(1, 'latest'); await latest;
    assert.equal(get('cargando-listado-productos').hidden, true);
});

test('el error oculta el indicador y conserva la lista anterior', async () => {
    const {ctx, get, respond} = setup();
    get('lista-productos').innerHTML = 'previous';
    const pending = ctx.cargarListadoProductos('http://test/productos');
    respond(0, '', false); await pending;
    assert.equal(get('cargando-listado-productos').hidden, true);
    assert.equal(get('lista-productos').innerHTML, 'previous');
    assert.ok(get('estado-listado-productos').textContent);
});

test('una búsqueda anterior no reemplaza los resultados más recientes', async () => {
    const {ctx, get, requests, respond} = setup();
    const old = ctx.cargarListadoProductos('http://test/productos?q=old');
    const latest = ctx.cargarListadoProductos('http://test/productos?q=latest');
    assert.equal(requests[0].options.signal.aborted, true);
    respond(1, 'latest'); await latest;
    respond(0, 'old'); await old;
    assert.equal(get('lista-productos').innerHTML, 'latest');
});

test('abre la ficha inmediatamente y la carga sin reemplazar la tabla', async () => {
    const {ctx, get, respond} = setup();
    get('lista-productos').innerHTML = 'current-page';
    const pending = ctx.abrirFichaProducto('http://test/productos?select=1');
    assert.equal(get('modal-ficha-producto').open, true);
    assert.match(get('contenido-ficha-producto').innerHTML, /Cargando ficha/);
    respond(0, 'product-1'); await pending;
    assert.equal(get('contenido-ficha-producto').innerHTML, 'product-1');
    assert.equal(get('lista-productos').innerHTML, 'current-page');
    assert.equal(get('contenido-ficha-producto').attributes['aria-busy'], undefined);
});

test('cerrar la ficha cancela la carga y evita reabrirla con la respuesta', async () => {
    const {ctx, get, requests, respond} = setup();
    const pending = ctx.abrirFichaProducto('http://test/productos?select=1');
    ctx.cerrarFichaProducto();
    ctx.alCerrarFichaProducto();
    assert.equal(requests[0].options.signal.aborted, true);
    respond(0, 'product-1'); await pending;
    assert.equal(get('modal-ficha-producto').open, false);
    assert.notEqual(get('contenido-ficha-producto').innerHTML, 'product-1');
});

test('un producto eliminado muestra un error y permite cerrar el modal', async () => {
    const {ctx, get, respond} = setup();
    const pending = ctx.abrirFichaProducto('http://test/productos?select=1');
    respond(0, 'missing'); await pending;
    assert.equal(get('message').textContent, 'El producto ya no está disponible.');
    assert.equal(get('modal-ficha-producto').open, true);
    ctx.cerrarFichaProducto();
    assert.equal(get('modal-ficha-producto').open, false);
});
