const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { setTimeout: pause } = require('node:timers/promises');

function setup() {
    const nodes = new Map(), requests = [], notices = [], events = [];
    const node = id => {
        if (!nodes.has(id)) nodes.set(id, { value: '', attrs: {},
            setAttribute(key, value) { this.attrs[key] = value; },
            before(element) { nodes.set(element.id, element); },
            querySelectorAll() { return []; },
            replaceWith(element) { nodes.set(id, element); }
        });
        return nodes.get(id);
    };
    node('ordenes-resultados').label = 'inicial';
    const context = vm.createContext({
        URL, AbortController, Event, console, etiquetasFiltro: [],
        location: { href: 'http://test/ordenes' },
        history: { replaceState() {} },
        document: {
            getElementById: node, createElement: () => ({}),
            addEventListener() {}, dispatchEvent: event => events.push(event.type), querySelectorAll: () => [],
        },
        setTimeout: (fn, ms) => setTimeout(fn, ms < 20000 ? 0 : ms), clearTimeout,
        mostrarNotificacion: value => notices.push(value),
        fetch: (url, options) => new Promise(resolve => requests.push({ url, options, resolve })),
        DOMParser: class { parseFromString(label) {
            return { getElementById: () => ({ ...node('ordenes-resultados'), label }) };
        } },
    });
    context.window = context;
    vm.runInContext(fs.readFileSync('static/js/ordenes-listado.js', 'utf8'), context);
    const response = label => ({ ok: true, redirected: false, text: async () => label });
    return { context, node, requests, notices, events, response };
}

test('new search cancels the previous request and ignores a late response', async () => {
    const app = setup();
    app.node('buscador-ordenes').value = 'anterior';
    app.context.consultarListadoOrdenes(); await pause(15);
    app.node('buscador-ordenes').value = 'actual';
    app.context.consultarListadoOrdenes(); await pause(15);
    assert.equal(app.requests[0].options.signal.aborted, true);
    assert.equal(app.requests[1].url.searchParams.get('q'), 'actual');
    app.requests[1].resolve(app.response('actual')); await pause(15);
    app.requests[0].resolve(app.response('anterior')); await pause(15);
    assert.equal(app.node('ordenes-resultados').label, 'actual');
    assert.equal(app.node('ordenes-cargando').hidden, true);
    assert.deepEqual(app.events, ['ordenes:listado']);
});

test('errors preserve the list and the next request can recover', async () => {
    const app = setup();
    app.context.consultarListadoOrdenes(); await pause(15);
    app.requests[0].resolve({ ok: false }); await pause(15);
    assert.equal(app.node('ordenes-resultados').label, 'inicial');
    assert.equal(app.node('ordenes-cargando').hidden, true);
    assert.equal(app.notices.length, 1);
    app.context.consultarListadoOrdenes(); await pause(15);
    app.requests[1].resolve(app.response('recuperada')); await pause(15);
    assert.equal(app.node('ordenes-resultados').label, 'recuperada');
});
