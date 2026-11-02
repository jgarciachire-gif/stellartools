const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('static/js/componentes/notificaciones-header.js', 'utf8');

function setup(storage = new Map(), usuarioId = 'user-a', descartadasStorage = new Map()) {
    const requests = [];
    let now = 1000;
    const listeners = new Map();
    const timers = new Map();
    const document = {visibilityState: 'visible',
        addEventListener: (name, fn) => listeners.set(name, fn),
        removeEventListener: name => listeners.delete(name)};
    const window = {
        sessionStorage: {getItem: key => storage.get(key) || null,
            setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
        localStorage: {getItem: key => descartadasStorage.get(key) || null,
            setItem: (key, value) => descartadasStorage.set(key, value)},
        setInterval: fn => { timers.set(1, fn); return 1; }, clearInterval: id => timers.delete(id)
    };
    vm.runInNewContext(source, {window, document, URL, Date: {now: () => now},
        fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject}))});
    return {state: window.notificacionesHeader(usuarioId), requests, storage, descartadasStorage, document, timers, listeners,
        advance(ms) { now += ms; },
        respond(index, body = {notificaciones: [], total: 0}, status = 200) {
            requests[index].resolve({ok: status === 200, status, json: async () => body});
        }};
}

test('carga el conteo al iniciar sin abrir el menú y reutiliza los datos durante un minuto', async () => {
    const view = setup();
    assert.equal(view.requests.length, 0);
    view.state.init();
    assert.equal(view.state.abierto, false);
    assert.equal(view.state.cargando, true);
    assert.equal(view.requests.length, 1);
    view.respond(0, {notificaciones: [{proveedor: 'Proveedor A', version_estado: 'a1', tiendas: []}, {proveedor: 'Proveedor B', version_estado: 'b1', tiendas: []}], total: 2});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(view.state.cargando, false);
    assert.equal(view.state.total, 2);
    view.state.alternar(); view.state.alternar();
    assert.equal(view.requests.length, 1);
    assert.equal(view.requests[0].options.cache, 'no-store');
    assert.equal(view.requests[0].options.credentials, 'same-origin');
});

test('el conteo se restaura inmediatamente al navegar y disminuye tras actualizar estados', async () => {
    const first = setup();
    const loaded = first.state.cargar();
    first.respond(0, {notificaciones: [{proveedor: 'Proveedor A', version_estado: 'a1', tiendas: []}, {proveedor: 'Proveedor B', version_estado: 'b1', tiendas: []}], total: 2});
    await loaded;
    const nextPage = setup(first.storage);
    nextPage.state.init();
    assert.equal(nextPage.state.total, 2);
    assert.equal(nextPage.requests.length, 0);
    nextPage.advance(60001);
    nextPage.timers.get(1)();
    nextPage.respond(0, {notificaciones: [], total: 0});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(nextPage.state.total, 0);
    assert.equal(nextPage.state.notificaciones.length, 0);
    assert.equal(JSON.parse([...nextPage.storage.values()][0]).total, 0);
});

test('la caché pertenece al usuario y no se comparte con otra sesión de usuario', async () => {
    const first = setup();
    const loaded = first.state.cargar();
    first.respond(0, {notificaciones: [{proveedor: 'Privado', version_estado: 'p1', tiendas: []}], total: 1});
    await loaded;
    const another = setup(first.storage, 'user-b');
    another.state.init();
    assert.equal(another.state.total, 0);
    assert.equal(another.state.notificaciones.length, 0);
    assert.equal(another.requests.length, 1);
    another.respond(0);
    await new Promise(resolve => setImmediate(resolve));
});

test('recalcula por proveedor los conteos de tienda guardados anteriormente en caché', () => {
    const storage = new Map([['stellartools:notificaciones:reposicion:user-a', JSON.stringify({
        notificaciones: [{proveedor: 'Proveedor A', version_estado: 'a1', tiendas: [{tienda: 'CENTRO'}, {tienda: 'GARIBALDI'}]}],
        total: 2, ultimaCarga: 1000
    })]]);
    const view = setup(storage);
    view.state.init();
    assert.equal(view.state.total, 1);
    assert.equal(view.requests.length, 0);
});

test('no consulta en segundo plano y actualiza al regresar a la pestaña', async () => {
    const view = setup();
    view.state.init(); view.respond(0);
    await new Promise(resolve => setImmediate(resolve));
    view.document.visibilityState = 'hidden';
    view.advance(60001); view.timers.get(1)();
    assert.equal(view.requests.length, 1);
    view.document.visibilityState = 'visible';
    view.listeners.get('visibilitychange')();
    assert.equal(view.requests.length, 2);
    view.respond(1);
    await new Promise(resolve => setImmediate(resolve));
    view.state.destroy();
    assert.equal(view.timers.size, 0);
    assert.equal(view.listeners.size, 0);
});

test('evita solicitudes simultáneas y permite actualizar al vencer la caché', async () => {
    const view = setup();
    const first = view.state.cargar();
    await view.state.cargar();
    assert.equal(view.requests.length, 1);
    view.respond(0); await first;
    view.advance(60001);
    const next = view.state.cargar();
    assert.equal(view.requests.length, 2);
    view.respond(1); await next;
});

test('actualizar manualmente omite la caché y los errores permiten reintentar', async () => {
    const view = setup();
    const first = view.state.cargar(); view.respond(0); await first;
    const forced = view.state.cargar(true);
    view.respond(1, {}, 500); await forced;
    assert.ok(view.state.error);
    assert.equal(view.state.cargando, false);
    const retry = view.state.cargar(true);
    view.respond(2); await retry;
    assert.equal(view.state.error, '');
});

test('una sesión vencida elimina los avisos anteriores', async () => {
    const view = setup();
    view.state.notificaciones = [{proveedor: 'Anterior'}]; view.state.total = 1;
    const pending = view.state.cargar();
    view.respond(0, {}, 401); await pending;
    assert.equal(view.state.notificaciones.length, 0);
    assert.equal(view.state.total, 0);
    assert.match(view.state.error, /sesión/);
    assert.equal(view.state.cargando, false);
});

test('una respuesta inválida no se guarda en caché', async () => {
    const view = setup();
    const pending = view.state.cargar();
    view.respond(0, {notificaciones: 'invalid', total: -1}); await pending;
    assert.ok(view.state.error);
    assert.equal(view.state.ultimaCarga, null);
    assert.equal(view.state.cargando, false);
});

test('descartar un proveedor reduce el conteo y se conserva al cambiar de página', async () => {
    const view = setup();
    const avisos = [{proveedor: 'Proveedor A', version_estado: 'a1', tiendas: []},
        {proveedor: 'Proveedor B', version_estado: 'b1', tiendas: []}];
    const loaded = view.state.cargar(); view.respond(0, {notificaciones: avisos, total: 2}); await loaded;
    view.state.descartar(view.state.notificaciones[0]);
    assert.equal(view.state.total, 1);
    assert.equal(view.state.notificaciones[0].proveedor, 'Proveedor B');
    const nextPage = setup(view.storage, 'user-a', view.descartadasStorage);
    nextPage.state.init();
    assert.equal(nextPage.state.total, 1);
    assert.equal(nextPage.requests.length, 0);
    assert.equal(JSON.parse([...view.storage.values()][0]).notificaciones.length, 2);
});

test('descartar mantiene abierta la lista y mueve el foco antes de retirar el botón', async () => {
    const view = setup();
    const aviso = {proveedor: 'Proveedor A', version_estado: 'a1', tiendas: []};
    const loaded = view.state.cargar();
    view.respond(0, {notificaciones: [aviso], total: 1}); await loaded;
    view.state.abierto = true;
    let focused = false;
    view.state.$refs = {campana: {focus(options) {
        assert.equal(view.state.notificaciones.length, 1);
        assert.equal(options.preventScroll, true);
        focused = true;
    }}};
    view.state.descartar(aviso);
    assert.equal(focused, true);
    assert.equal(view.state.abierto, true);
    assert.equal(view.state.total, 0);
    assert.equal(view.state.notificaciones.length, 0);
    const markup = fs.readFileSync('templates/componentes/notificaciones_header.html', 'utf8');
    assert.match(markup, /@click\.stop="descartar\(aviso\)"/);
    assert.doesNotMatch(markup, /@focusout=/);
    assert.match(markup, /@click\.outside="abierto = false"/);
    assert.match(markup, /@keydown\.escape\.prevent\.stop=/);
});

test('la alerta permanece descartada con el mismo estado y reaparece cuando cambia', async () => {
    const view = setup();
    const aviso = {proveedor: 'Proveedor A', version_estado: 'a1', tiendas: [{dias_inventario: 'Quedan 2d'}]};
    const loaded = view.state.cargar(); view.respond(0, {notificaciones: [aviso], total: 1}); await loaded;
    view.state.descartar(view.state.notificaciones[0]);
    const unchanged = view.state.cargar(true);
    view.respond(1, {notificaciones: [{...aviso, tiendas: [{dias_inventario: 'Queda 1d'}]}], total: 1}); await unchanged;
    assert.equal(view.state.total, 0);
    const changed = view.state.cargar(true);
    view.respond(2, {notificaciones: [{...aviso, version_estado: 'a2'}], total: 1}); await changed;
    assert.equal(view.state.total, 1);
    assert.equal(view.state.descartadas.length, 0);
});

test('salir de alerta libera el descarte para una alerta posterior', async () => {
    const view = setup();
    const aviso = {proveedor: 'Proveedor A', version_estado: 'a1', tiendas: []};
    const loaded = view.state.cargar(); view.respond(0, {notificaciones: [aviso], total: 1}); await loaded;
    view.state.descartar(view.state.notificaciones[0]);
    const healthy = view.state.cargar(true); view.respond(1); await healthy;
    assert.equal(view.state.descartadas.length, 0);
    const renewed = view.state.cargar(true);
    view.respond(2, {notificaciones: [aviso], total: 1}); await renewed;
    assert.equal(view.state.total, 1);
});

test('los descartes no se comparten entre usuarios', async () => {
    const view = setup();
    const aviso = {proveedor: 'Proveedor A', version_estado: 'a1', tiendas: []};
    const loaded = view.state.cargar(); view.respond(0, {notificaciones: [aviso], total: 1}); await loaded;
    view.state.descartar(view.state.notificaciones[0]);
    const other = setup(new Map(), 'user-b', view.descartadasStorage);
    other.state.init();
    other.respond(0, {notificaciones: [aviso], total: 1});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(other.state.total, 1);
});

test('la caché anterior sin versión se actualiza antes de permitir descartes', async () => {
    const storage = new Map([['stellartools:notificaciones:reposicion:user-a', JSON.stringify({
        notificaciones: [{proveedor: 'Anterior', tiendas: []}], total: 1, ultimaCarga: 1000
    })]]);
    const view = setup(storage);
    view.state.init();
    assert.equal(view.requests.length, 1);
    view.state.descartar(view.state.notificaciones[0]);
    assert.equal(view.state.total, 1);
    view.respond(0, {notificaciones: [{proveedor: 'Anterior', version_estado: 'v1', tiendas: []}], total: 1});
    await new Promise(resolve => setImmediate(resolve));
    view.state.descartar(view.state.notificaciones[0]);
    assert.equal(view.state.total, 0);
});
