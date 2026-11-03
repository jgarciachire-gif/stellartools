const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/componentes/modal.js', 'utf8');

function setup() {
    const listeners = new Set();
    const nodes = [], timers = new Map();
    let timer = 0;
    function element() {
        const events = {};
        const children = {};
        return {
            innerHTML: '', className: '', classList: { add() {}, remove() {} },
            addEventListener(name, callback) { events[name] = callback; },
            fire(name, event = {}) { events[name]?.(event); },
            querySelector(selector) { return children[selector] ||= element(); },
            remove() {}, focus() {}
        };
    }
    const window = {};
    vm.runInNewContext(source, {
        window,
        document: {
            createElement: element, body: { appendChild: node => nodes.push(node) },
            addEventListener: (name, callback) => { if (name === 'keydown') listeners.add(callback); },
            removeEventListener: (name, callback) => { if (name === 'keydown') listeners.delete(callback); }
        },
        setTimeout: (callback, delay) => { timers.set(++timer, { callback, delay }); return timer; },
        clearTimeout: id => timers.delete(id),
        requestAnimationFrame: callback => callback()
    });
    return { window, nodes, listeners, timers, escape() { [...listeners].forEach(callback => callback({ key: 'Escape' })); } };
}

test('reemplazar una confirmación resuelve la anterior y espera la decisión del modal nuevo', async () => {
    const app = setup();
    const first = app.window.mostrarConfirmacion({ titulo: 'Primera' });
    const second = app.window.mostrarConfirmacion({ titulo: 'Segunda' });
    assert.equal(await first, false);
    assert.equal(app.listeners.size, 1);
    app.nodes.at(-1).querySelector('[data-modal-aceptar]').fire('click');
    assert.equal(await second, true);
    assert.equal(app.listeners.size, 0);
});

test('cerrar con botón limpia Escape y el foco pendiente antes de abrir otra confirmación', async () => {
    const app = setup();
    const first = app.window.mostrarConfirmacion();
    app.nodes.at(-1).querySelector('[data-modal-cancelar]').fire('click');
    assert.equal(await first, false);
    assert.equal(app.listeners.size, 0);
    assert.equal([...app.timers.values()].some(timer => timer.delay === 50), false);
    const second = app.window.mostrarConfirmacion();
    app.escape();
    assert.equal(await second, false);
    assert.equal(app.listeners.size, 0);
});

test('las notificaciones informan sin aceptar ni cancelar una confirmación abierta', async () => {
    const app = setup();
    const confirmation = app.window.mostrarConfirmacion();
    const modal = app.nodes[0];
    app.window.mostrarNotificacion({ tipo: 'error', mensaje: 'Error recuperable' });
    assert.equal(app.listeners.size, 1);
    modal.querySelector('[data-modal-cancelar]').fire('click');
    assert.equal(await confirmation, false);
    assert.equal(app.listeners.size, 0);
});

test('reemplazar una alerta por confirmación no acepta la acción y escapa el texto', async () => {
    const app = setup();
    const alert = app.window.mostrarAlerta({ mensaje: '<script>inseguro</script>' });
    assert.match(app.nodes.at(-1).innerHTML, /&lt;script&gt;/);
    const confirmation = app.window.mostrarConfirmacion();
    assert.equal(await alert, false);
    app.window.cerrarModalGlobal();
    assert.equal(await confirmation, false);
});
