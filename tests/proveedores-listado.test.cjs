const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/proveedores-listado.js', 'utf8');
const loadingMarkup = fs.readFileSync('templates/proveedores.html', 'utf8')
    .match(/<template id="plantilla-carga-ficha-proveedor">([\s\S]*?)<\/template>/)[1];
const searchSource = fs.readFileSync('templates/proveedores.html', 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];

function setupSearch() {
    const handlers = {};
    const ready = [];
    const calls = [];
    const timers = [];
    const input = { value: '', addEventListener(name, fn) { handlers[name] = fn; } };
    const fields = { busqueda_proveedores: input, form_ficha_q: {}, form_ficha_tags: {},
        'datos-etiquetas-proveedores': {textContent: '[]'} };
    const ctx = vm.createContext({
        URL, URLSearchParams,
        window: { location: { href: 'http://test/proveedores', search: '' } },
        document: {
            getElementById: id => fields[id],
            addEventListener(name, fn) { if (name === 'DOMContentLoaded') ready.push(fn); }
        },
        cargarListadoProveedores: url => calls.push(url),
        setTimeout: fn => timers.push(fn), clearTimeout() {}
    });
    vm.runInContext(searchSource, ctx);
    ctx.renderizarEtiquetas = () => {};
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
    ctx.removerEtiqueta(0);
    assert.equal(calls.length, 2);
    assert.equal(calls[1].searchParams.get('tags'), '');
    assert.equal(calls[1].searchParams.has('q'), false);
    assert.equal(input.value, 'sin confirmar');
});

test('cancelar edición restaura las categorías y deshabilita los campos de la ficha', () => {
    const {ctx} = setupSearch();
    function node(hidden = false) {
        const classes = new Set(hidden ? ['hidden'] : []);
        return {classList: {add: value => classes.add(value), remove: value => classes.delete(value),
            contains: value => classes.has(value)}};
    }
    const badges = {innerHTML: '<span>Categoría original</span>'};
    const inputs = [{disabled: true}];
    const removeButton = node(true);
    const form = {
        querySelector: () => badges,
        querySelectorAll: selector => selector.startsWith('input') ? inputs : [removeButton],
        reset() { this.wasReset = true; }
    };
    const elements = {'form-proveedor-ficha': form, modo_vista: node(), modo_edicion: node(true),
        'control-agregar-badge': node(true)};
    ctx.document.getElementById = id => elements[id];
    ctx.habilitarEdicion();
    assert.equal(inputs[0].disabled, false);
    badges.innerHTML = '<span>Categoría modificada</span>';
    ctx.cancelarEdicion();
    assert.equal(badges.innerHTML, '<span>Categoría original</span>');
    assert.equal(inputs[0].disabled, true);
    assert.equal(elements.modo_edicion.classList.contains('hidden'), true);
    assert.equal(removeButton.classList.contains('hidden'), true);
    assert.equal(form.wasReset, true);
});

test('no agrega categorías duplicadas aunque cambien las mayúsculas o acentos', () => {
    const {ctx} = setupSearch();
    const input = {value: 'LACTEOS'};
    const container = {querySelectorAll: () => [{textContent: 'Lácteos'}]};
    const suggestions = {classList: {add() {}}};
    const section = {querySelector: selector => selector === '.input-badge' ? input
        : selector === '.contenedor-badges' ? container : suggestions};
    ctx.agregarBadgeFicha({closest: () => section});
    assert.equal(input.value, '');
});

test('eliminar la última categoría restaura el mensaje vacío', () => {
    const {ctx} = setupSearch();
    const container = {querySelector: () => null, innerHTML: ''};
    let removed = false;
    ctx.eliminarBadgeFicha({closest: selector => selector === '.contenedor-badges' ? container
        : {remove() { removed = true; }}});
    assert.equal(removed, true);
    assert.match(container.innerHTML, /Sin categorías asignadas/);
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
    get('plantilla-carga-ficha-proveedor').innerHTML = loadingMarkup;
    const ctx = vm.createContext({
        AbortController, URL, console, clearTimeout,
        document: { getElementById: get, addEventListener() {}, body: { appendChild() {} } },
        window: {
            location: { href: 'http://test/proveedores?q=pan&page=2&sort=precio&dir=desc', origin: 'http://test', assign() {} },
            history: { replaceState(...args) { history.push(args[2]); }, pushState(...args) { history.push(args[2]); } },
            addEventListener() {}
        },
        fetch: (url, options) => new Promise(resolve => requests.push({url, options, resolve})),
        DOMParser: class {
            parseFromString(html) {
                return { getElementById(id) {
                    if (id === 'lista-proveedores') return { innerHTML: html };
                    if (id === 'contenido-ficha-proveedor') return {
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
    const url = 'http://test/proveedores?q=pan&page=3&sort=precio&dir=desc';
    const pending = ctx.cargarListadoProveedores(url, 'push');
    assert.equal(get('lista-proveedores').attributes['aria-busy'], 'true');
    assert.equal(get('cargando-listado-proveedores').hidden, false);
    respond(0, 'page-3');
    await pending;
    assert.equal(get('lista-proveedores').innerHTML, 'page-3');
    assert.equal(String(history[0]), url);
    assert.equal(get('lista-proveedores').attributes['aria-busy'], undefined);
    assert.equal(get('cargando-listado-proveedores').hidden, true);
});

test('una consulta cancelada no oculta el indicador de la búsqueda vigente', async () => {
    const {ctx, get, respond} = setup();
    const old = ctx.cargarListadoProveedores('http://test/proveedores?q=old');
    const latest = ctx.cargarListadoProveedores('http://test/proveedores?q=latest');
    respond(0, 'old'); await old;
    assert.equal(get('cargando-listado-proveedores').hidden, false);
    respond(1, 'latest'); await latest;
    assert.equal(get('cargando-listado-proveedores').hidden, true);
});

test('el error oculta el indicador y conserva la lista anterior', async () => {
    const {ctx, get, respond} = setup();
    get('lista-proveedores').innerHTML = 'previous';
    const pending = ctx.cargarListadoProveedores('http://test/proveedores');
    respond(0, '', false); await pending;
    assert.equal(get('cargando-listado-proveedores').hidden, true);
    assert.equal(get('lista-proveedores').innerHTML, 'previous');
    assert.ok(get('estado-listado-proveedores').textContent);
});

test('una búsqueda anterior no reemplaza los resultados más recientes', async () => {
    const {ctx, get, requests, respond} = setup();
    const old = ctx.cargarListadoProveedores('http://test/proveedores?q=old');
    const latest = ctx.cargarListadoProveedores('http://test/proveedores?q=latest');
    assert.equal(requests[0].options.signal.aborted, true);
    respond(1, 'latest'); await latest;
    respond(0, 'old'); await old;
    assert.equal(get('lista-proveedores').innerHTML, 'latest');
});

test('abre la ficha inmediatamente y la carga sin reemplazar la tabla', async () => {
    const {ctx, get, respond} = setup();
    get('lista-proveedores').innerHTML = 'current-page';
    const pending = ctx.abrirFichaProveedor('http://test/proveedores?select=1');
    assert.equal(get('modal-ficha-proveedor').open, true);
    assert.match(get('contenido-ficha-proveedor').innerHTML, /Cargando ficha/);
    assert.match(get('contenido-ficha-proveedor').innerHTML, /Ficha de Proveedor/);
    assert.match(get('contenido-ficha-proveedor').innerHTML, /animate-pulse/);
    assert.equal(get('contenido-ficha-proveedor').attributes['aria-busy'], 'true');
    respond(0, 'product-1'); await pending;
    assert.equal(get('contenido-ficha-proveedor').innerHTML, 'product-1');
    assert.equal(get('lista-proveedores').innerHTML, 'current-page');
    assert.equal(get('contenido-ficha-proveedor').attributes['aria-busy'], undefined);
});

test('cerrar la ficha cancela la carga y evita reabrirla con la respuesta', async () => {
    const {ctx, get, requests, respond} = setup();
    const pending = ctx.abrirFichaProveedor('http://test/proveedores?select=1');
    ctx.cerrarFichaProveedor();
    ctx.alCerrarFichaProveedor();
    assert.equal(requests[0].options.signal.aborted, true);
    respond(0, 'product-1'); await pending;
    assert.equal(get('modal-ficha-proveedor').open, false);
    assert.notEqual(get('contenido-ficha-proveedor').innerHTML, 'product-1');
});

test('un proveedor eliminado muestra un error y permite cerrar el modal', async () => {
    const {ctx, get, respond} = setup();
    const pending = ctx.abrirFichaProveedor('http://test/proveedores?select=1');
    respond(0, 'missing'); await pending;
    assert.equal(get('message').textContent, 'El proveedor ya no está disponible.');
    assert.equal(get('modal-ficha-proveedor').open, true);
    ctx.cerrarFichaProveedor();
    assert.equal(get('modal-ficha-proveedor').open, false);
});
