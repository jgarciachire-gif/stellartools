const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function setup() {
    function element(tag = 'div') {
        const classes = new Set(['hidden']);
        return { tag, children: [], attrs: {}, value: '', textContent: '', events: {}, disabled: true,
            classList: { contains: c => classes.has(c), add: c => classes.add(c),
                toggle(c, force) { const add = force === undefined ? !classes.has(c) : force; if (add) classes.add(c); else classes.delete(c); } },
            setAttribute(k, v) { this.attrs[k] = String(v); },
            append(...nodes) { this.children.push(...nodes); },
            replaceChildren(...nodes) { this.children = nodes; },
            addEventListener(k, v) { this.events[k] = v; },
            querySelector() { return this.label ||= element('span'); },
            get selectedOptions() { return this.children.filter(c => c.value === this.value); }
        };
    }
    const nodes = new Map(['btn-tendencia-periodos', 'kardex-tendencia-contenedor', 'kardex-tendencia-producto',
        'kardex-tendencia-grafico', 'kardex-tendencia-contexto'].map(id => [id, element()]));
    const ctx = vm.createContext({ document: { getElementById: id => nodes.get(id),
        createElement: element, createElementNS: (_, tag) => element(tag) },
        fetch() { throw Error('El gráfico no debe consultar la base de datos'); } });
    ctx.window = ctx;
    vm.runInContext(fs.readFileSync('static/js/analisis/analisis-tendencia-periodos.js', 'utf8'), ctx);
    const description = () => nodes.get('kardex-tendencia-grafico').children[0].children.find(n => n.tag === 'desc').textContent;
    return { nodes, api: ctx.tendenciaPeriodosKardex, description };
}
const consulta = () => ({ sede: 'CENTRO', periodos: [
    { inicio: '2026-11-01', nombre: 'Noviembre 2026', intervalo: '01/11 a 07/11' },
    { inicio: '2026-10-01', nombre: 'Octubre 2026', intervalo: '01/10 a 07/10' }
], productos: [{ codigo: '000001', descripcion: '<Producto>', ventas: [30, 10] },
    { codigo: '000002', descripcion: 'Otro producto', ventas: [0, 5] }] });

test('grafica totales en orden cronológico y permite consultar un producto sin nuevas peticiones', () => {
    const { nodes, api, description } = setup();
    api.actualizar(consulta());
    const button = nodes.get('btn-tendencia-periodos');
    assert.equal(button.disabled, false);
    button.events.click();
    assert.match(description(), /Octubre 2026: 15 unidades.*Noviembre 2026: 30 unidades/);
    assert.equal(button.attrs['aria-expanded'], 'true');
    const select = nodes.get('kardex-tendencia-producto');
    select.value = '000002'; select.events.change();
    assert.match(description(), /Octubre 2026: 5 unidades.*Noviembre 2026: 0 unidades/);
    button.events.click();
    assert.equal(button.attrs['aria-expanded'], 'false');
});

test('renovar o limpiar la consulta elimina el gráfico anterior; un período no habilita tendencia', () => {
    const { nodes, api } = setup();
    api.actualizar(consulta()); nodes.get('btn-tendencia-periodos').events.click();
    api.actualizar({ ...consulta(), periodos: consulta().periodos.slice(0, 1) });
    assert.equal(nodes.get('btn-tendencia-periodos').disabled, true);
    assert.equal(nodes.get('kardex-tendencia-grafico').children.length, 0);
    assert.equal(nodes.get('kardex-tendencia-contenedor').classList.contains('hidden'), true);
});

test('las ventas en cero dibujan valores finitos y los nombres se insertan como texto', () => {
    const { nodes, api, description } = setup();
    const data = consulta(); data.productos[0].ventas = [0, 0]; data.productos[1].ventas = [0, 0];
    api.actualizar(data); nodes.get('btn-tendencia-periodos').events.click();
    assert.match(description(), /Octubre 2026: 0 unidades.*Noviembre 2026: 0 unidades/);
    const line = nodes.get('kardex-tendencia-grafico').children[0].children.find(n => n.tag === 'polyline');
    assert.doesNotMatch(line.attrs.points, /NaN|Infinity/);
    assert.equal(nodes.get('kardex-tendencia-producto').children[1].textContent, '000001 · <Producto>');
});
