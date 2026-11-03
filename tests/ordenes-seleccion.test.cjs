const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/js/ordenes-seleccion.js', 'utf8');
const template = fs.readFileSync('templates/ordenes.html', 'utf8');
const start = template.indexOf('    function filtrarOrdenes()');
const filterSource = template.slice(start, template.indexOf('    async function actualizarFechasAsync', start));

function element(hidden = false) {
    const classes = new Set(hidden ? ['hidden'] : []);
    const events = {};
    return { hidden: false, style: { display: '' }, parentElement: null, textContent: '', innerHTML: '', value: '',
        disabled: false, checked: false, dataset: {},
        classList: {
            contains: value => classes.has(value), add: (...values) => values.forEach(value => classes.add(value)),
            remove: (...values) => values.forEach(value => classes.delete(value)),
            toggle(value, force = !classes.has(value)) { if (force) classes.add(value); else classes.delete(value); }
        },
        addEventListener: (name, fn) => { events[name] = fn; },
        fire(name, event = {}) { return events[name]?.(event); }
    };
}

function setup() {
    const nodes = new Map();
    const get = id => {
        if (!nodes.has(id)) nodes.set(id, element());
        return nodes.get(id);
    };
    ['barra-seleccion', 'modalEliminarOrdenes'].forEach(id => get(id).classList.add('hidden'));
    const groups = Array.from({ length: 2 }, () => ({ ...element(), tagName: 'DETAILS', open: true }));
    const rows = [
        ['1', 'Sol Centro pendiente', '2026-11-01'], ['2', 'Luna Centro recibida', '2026-11-02'],
        ['3', 'Sol San Diego pendiente', '2026-11-01'], ['4', 'Sol San Diego pendiente', '2026-11-02']
    ].map(([id, text, date], index) => {
        const row = element();
        const checkbox = { ...element(), dataset: { id }, value: id };
        row.checkbox = checkbox;
        row.parentElement = groups[index < 2 ? 0 : 1];
        row.textContent = text;
        row.querySelector = selector => selector === '.select-row' ? checkbox : null;
        row.querySelectorAll = () => Array.from({ length: 9 }, (_, cell) => ({
            querySelector: () => ({ value: cell === 4 ? date : '' })
        }));
        return row;
    });
    groups.forEach(group => { group.querySelectorAll = () => rows.filter(row => row.parentElement === group); });
    const ready = [];
    const requests = [], alerts = [], confirmations = [];
    const context = vm.createContext({
        console, AbortController, setTimeout: (callback, delay) => setTimeout(callback, delay === 1200 ? 0 : delay), clearTimeout, Error, TypeError, SyntaxError,
        etiquetasFiltro: [],
        document: {
            getElementById: get,
            addEventListener: (name, callback) => { if (name === 'DOMContentLoaded') ready.push(callback); },
            querySelectorAll: selector => selector === '.row-orden' ? rows : selector === 'details.group' ? groups : []
        },
        mostrarNotificacion: options => alerts.push(options),
        mostrarConfirmacion: async options => { confirmations.push(options); return true; },
        location: { reload() { requests.reloaded = true; } },
        fetch: async (url, options) => {
            requests.push({ url, ids: JSON.parse(options.body).ids });
            return { ok: true, status: 200, json: async () => ({ success: true }) };
        }
    });
    context.window = context;
    vm.runInContext(source + '\n' + filterSource, context);
    ready.forEach(callback => callback());
    get('btn-activar-seleccion').fire('click');
    return { context, rows, groups, get, requests, alerts, confirmations,
        filter(text = '', tags = [], date = '') {
            get('buscador-ordenes').value = text;
            get('filtro-fecha').value = date;
            context.etiquetasFiltro = tags.map(valor => ({ tipo: 'filtro', valor }));
            context.filtrarOrdenes();
        },
        select(id, checked = true) {
            const checkbox = rows.find(row => row.checkbox.value === String(id)).checkbox;
            checkbox.checked = checked; checkbox.fire('change');
        },
        checked: () => rows.filter(row => row.checkbox.checked).map(row => Number(row.checkbox.value))
    };
}

test('seleccionar todo y eliminar usa exclusivamente los IDs del filtro de texto', async () => {
    const app = setup();
    app.filter('sol');
    app.get('btn-seleccionar-todo').fire('click');
    assert.deepEqual(app.checked(), [1, 3, 4]);
    assert.match(app.get('contador-seleccion').textContent, /^3 seleccionados$/);
    await app.context.abrirModalEliminar();
    assert.match(app.confirmations[0].mensaje, /3 orden/);
    assert.deepEqual(app.requests[0].ids, [1, 3, 4]);
    assert.equal(app.requests.reloaded, true);
});

test('cambiar filtros desmarca los registros ocultos y no recupera selecciones anteriores al limpiarlos', async () => {
    const app = setup();
    app.get('btn-seleccionar-todo').fire('click');
    app.filter('centro');
    assert.deepEqual(app.checked(), [1, 2]);
    app.filter('centro', ['sol']);
    assert.deepEqual(app.checked(), [1]);
    app.filter();
    assert.deepEqual(app.checked(), [1]);
    await app.context.abrirModalEliminar();
    assert.deepEqual(app.requests[0].ids, [1]);
});

test('fecha y badges limitan el alcance de seleccionar todo y desmarcar todo', async () => {
    const app = setup();
    app.filter('', [], '2026-11-02');
    app.get('btn-seleccionar-todo').fire('click');
    assert.deepEqual(app.checked(), [2, 4]);
    app.get('btn-seleccionar-todo').fire('click');
    assert.deepEqual(app.checked(), []);
    app.filter('', ['pendiente'], '2026-11-02');
    app.get('btn-seleccionar-todo').fire('click');
    await app.context.abrirModalEliminar();
    assert.deepEqual(app.requests[0].ids, [4]);
});

test('un filtro sin resultados desactiva la selección y nunca permite eliminar', async () => {
    const app = setup();
    app.filter('inexistente');
    app.get('btn-seleccionar-todo').fire('click');
    assert.equal(app.get('btn-seleccionar-todo').disabled, true);
    assert.equal(app.get('btnEliminarMasivo').disabled, true);
    await app.context.abrirModalEliminar();
    assert.equal(app.alerts.length, 1);
    assert.equal(app.requests.length, 0);
});

test('los grupos ocultos o colapsados no se seleccionan y pierden sus selecciones', () => {
    const app = setup();
    app.get('btn-seleccionar-todo').fire('click');
    app.groups[1].open = false;
    app.groups[1].fire('toggle');
    assert.deepEqual(app.checked(), [1, 2]);
    app.get('btn-seleccionar-todo').fire('click');
    app.get('btn-seleccionar-todo').fire('click');
    assert.deepEqual(app.checked(), [1, 2]);
    app.groups[0].style.display = 'none';
    app.context.actualizarEstadoSeleccion();
    assert.deepEqual(app.checked(), []);
});

test('si cambia el filtro o la selección después de abrir el modal, exige confirmar nuevamente', async () => {
    for (const change of ['filter', 'selection']) {
        const app = setup();
        let accept;
        app.context.mostrarConfirmacion = () => new Promise(resolve => { accept = resolve; });
        app.select(1);
        const deletion = app.context.abrirModalEliminar();
        if (change === 'filter') app.filter('luna'); else app.select(2);
        accept(true);
        await deletion;
        assert.equal(app.requests.length, 0);
        assert.match(app.alerts[0].mensaje, /cambiaron/);
        app.context.mostrarConfirmacion = async () => true;
        if (change === 'filter') app.select(2);
        await app.context.abrirModalEliminar();
        assert.deepEqual(app.requests[0].ids, change === 'filter' ? [2] : [1, 2]);
    }
});

test('durante la eliminación congela los IDs confirmados e impide el doble envío', async () => {
    const app = setup();
    let finish;
    app.context.fetch = async (_url, options) => {
        app.requests.push(JSON.parse(options.body).ids);
        return new Promise(resolve => { finish = resolve; });
    };
    app.select(1);
    const deletion = app.context.abrirModalEliminar();
    await new Promise(resolve => setImmediate(resolve));
    app.select(2);
    await app.context.abrirModalEliminar();
    assert.equal(app.get('btnEliminarMasivo').disabled, true);
    assert.deepEqual(app.requests, [[1]]);
    finish({ ok: true, status: 200, json: async () => ({ success: true }) });
    await deletion;
});

test('errores generan notificaciones y liberan controles sin cambiar la selección', async () => {
    const app = setup();
    app.context.fetch = async (_url, options) => {
        app.requests.push(JSON.parse(options.body).ids);
        return { ok: false, status: 500, json: async () => ({ success: false, message: 'No se pudo eliminar' }) };
    };
    app.filter('centro'); app.select(1);
    await app.context.abrirModalEliminar();
    assert.deepEqual(app.requests, [[1]]);
    assert.equal(app.get('btnEliminarMasivo').disabled, false);
    assert.equal(app.alerts[0].tipo, 'error');
    assert.match(app.alerts[0].mensaje, /No se pudo eliminar/);
    assert.deepEqual(app.checked(), [1]);
});

test('cancelar la confirmación conserva la selección y cancelar el modo la limpia', async () => {
    const app = setup();
    app.context.mostrarConfirmacion = async () => false;
    app.select(1); await app.context.abrirModalEliminar();
    assert.equal(app.requests.length, 0);
    assert.deepEqual(app.checked(), [1]);
    assert.equal(app.get('contador-seleccion').textContent, '1 seleccionado');
    app.get('btn-cancelar-seleccion').fire('click');
    assert.deepEqual(app.checked(), []);
    assert.equal(app.get('btnEliminarMasivo').disabled, true);
});

test('guardar fechas comunica éxito o error mediante notificaciones', async () => {
    const dateStart = template.indexOf('    async function actualizarFechasAsync');
    const dateSource = template.slice(dateStart, template.indexOf("    document.addEventListener('DOMContentLoaded'", dateStart));
    for (const outcome of ['success', 'server', 'network']) {
        const app = setup();
        const row = app.rows[0], original = row.querySelector;
        row.querySelector = selector => selector === '.badge-estatus' ? element()
            : selector.startsWith('input[name=') ? { value: '2026-11-02' } : original(selector);
        app.context.document.querySelector = () => row;
        app.context.FormData = class { append() {} };
        app.context.fetch = async () => {
            if (outcome === 'network') throw new Error('Sin conexión');
            return { ok: outcome === 'success', json: async () => ({ status: outcome === 'success' ? 'ok' : 'error', estatus: 'Enviada' }) };
        };
        app.context.console = { error() {} };
        vm.runInContext(dateSource, app.context);
        await app.context.actualizarFechasAsync(1);
        assert.equal(app.alerts.at(-1).tipo, outcome === 'success' ? 'success' : 'error');
    }
});
