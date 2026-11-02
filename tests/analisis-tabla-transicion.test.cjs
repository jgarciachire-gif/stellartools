const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/analisis/analisis-tabla-transicion.js', 'utf8');

function setup(reducedMotion = false) {
    let naturalHeight = 120;
    let observeResize;
    const frames = [];
    const animations = [];
    const contentAnimations = [];
    const container = {
        style: {height: '', overflowY: ''},
        getBoundingClientRect() {
            const active = animations.at(-1);
            const height = active && !active.cancelled ? active.visibleHeight
                : this.style.height ? parseFloat(this.style.height) : naturalHeight;
            return {height};
        },
        animate(keyframes, options) {
            const animation = {keyframes, options, visibleHeight: parseFloat(keyframes[0].height),
                cancel() { this.cancelled = true; }};
            animations.push(animation);
            return animation;
        }
    };
    const table = {};
    const rows = {animate(keyframes, options) {
        const animation = {keyframes, options, cancel() { this.cancelled = true; }};
        contentAnimations.push(animation);
        return animation;
    }};
    vm.runInNewContext(source, {
        document: {readyState: 'complete', getElementById: id => ({
            'contenedor-tabla-productos-analisis': container, 'tabla-analisis': table,
            'filas-tabla-analisis': rows
        })[id]},
        window: {matchMedia: () => ({matches: reducedMotion})},
        ResizeObserver: class {
            constructor(callback) { observeResize = callback; }
            observe(element) { assert.equal(element, table); }
        },
        requestAnimationFrame: callback => frames.push(callback)
    });
    observeResize();
    return {container, animations, contentAnimations,
        resize(height) { naturalHeight = height; observeResize(); },
        flush() { while (frames.length) frames.shift()(); }};
}

test('no anima la carga inicial y expande al agregar una fila entre fotogramas', () => {
    const view = setup();
    assert.equal(view.animations.length, 0);
    view.resize(155);
    assert.equal(view.container.style.height, '120px');
    assert.equal(view.animations.length, 0);
    view.flush();
    const animation = view.animations[0];
    assert.equal(animation.keyframes[0].height, '120px');
    assert.equal(animation.keyframes[1].height, '155px');
    assert.equal(animation.options.easing, 'cubic-bezier(0.4, 0, 0.15, 1)');
    animation.onfinish();
    assert.equal(view.container.style.height, '');
    assert.equal(view.container.style.overflowY, '');
});

test('una importación de muchas filas produce una sola transición y aparición', () => {
    const view = setup();
    view.resize(2400);
    view.flush();
    assert.equal(view.animations.length, 1);
    assert.equal(view.contentAnimations.length, 1);
    assert.equal(view.animations[0].keyframes[1].height, '2400px');
    assert.equal(view.animations[0].options.duration, 1000);
});

test('agregar filas durante la transición continúa desde la altura visible', () => {
    const view = setup();
    view.resize(300); view.flush();
    const previous = view.animations[0];
    previous.visibleHeight = 200;
    view.resize(500); view.flush();
    assert.equal(previous.cancelled, true);
    assert.equal(view.animations[1].keyframes[0].height, '200px');
    previous.onfinish();
    assert.equal(view.container.style.height, '200px');
    view.animations[1].onfinish();
    assert.equal(view.container.style.height, '');
});

test('la contracción con movimiento reducido usa una transición breve', () => {
    const view = setup(true);
    view.resize(80); view.flush();
    assert.equal(view.animations[0].keyframes[1].height, '80px');
    assert.equal(view.animations[0].options.duration, 180);
    assert.equal(view.contentAnimations[0].options.duration, 180);
});
