/* Tendencia calculada únicamente con los resultados de la comparación actual. */
(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const boton = $('btn-tendencia-periodos');
    const panel = $('kardex-tendencia-contenedor');
    const selector = $('kardex-tendencia-producto');
    const grafico = $('kardex-tendencia-grafico');
    let datos = null, animar = actualizar => actualizar();
    const numero = valor => Number(valor).toLocaleString('es-VE', { maximumFractionDigits: 2 });

    function serie(codigo = '') {
        if (!datos) return [];
        return datos.periodos.map(periodo => ({
            ...periodo,
            unidades: datos.productos.reduce((total, producto) => total +
                (!codigo || producto.codigo === codigo ? producto.ventas[periodo.indice] : 0), 0)
        }));
    }
    function nodo(nombre, atributos = {}, texto) {
        const elemento = document.createElementNS('http://www.w3.org/2000/svg', nombre);
        Object.entries(atributos).forEach(([clave, valor]) => elemento.setAttribute(clave, String(valor)));
        if (texto !== undefined) elemento.textContent = texto;
        return elemento;
    }
    function dibujar() {
        if (!datos) return;
        const puntos = serie(selector.value);
        const titulo = selector.selectedOptions[0]?.textContent || 'Total de productos consultados';
        const svg = nodo('svg', { viewBox: '0 0 760 300', role: 'img', 'aria-labelledby': 'tendencia-svg-titulo tendencia-svg-descripcion',
            style: 'width:100%;min-width:520px;height:auto;display:block;font-family:inherit' });
        svg.append(nodo('title', { id: 'tendencia-svg-titulo' }, 'Unidades vendidas: ' + titulo));
        svg.append(nodo('desc', { id: 'tendencia-svg-descripcion' }, puntos.map(p => `${p.nombre}: ${numero(p.unidades)} unidades, ${p.intervalo}`).join('. ')));
        const maximo = Math.max(1, ...puntos.map(p => p.unidades));
        const margen = Math.max(72, numero(maximo).length * 7 + 18);
        const x = i => margen + i * (660 - margen) / Math.max(1, puntos.length - 1);
        const y = valor => 226 - (valor / maximo) * 176;
        for (let i = 0; i <= 4; i++) {
            const valor = maximo * i / 4;
            svg.append(nodo('line', { x1: margen, x2: 660, y1: y(valor), y2: y(valor), stroke: '#e2e8f0' }));
            svg.append(nodo('text', { x: margen - 12, y: y(valor) + 4, 'text-anchor': 'end', fill: '#64748b', 'font-size': 12 }, numero(valor)));
        }
        svg.append(nodo('text', { x: margen, y: 22, fill: '#64748b', 'font-size': 12 }, 'Unidades vendidas'));
        svg.append(nodo('polyline', { points: puntos.map((p, i) => `${x(i)},${y(p.unidades)}`).join(' '),
            fill: 'none', stroke: '#7c3aed', 'stroke-width': 3, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
        puntos.forEach((punto, i) => {
            const circulo = nodo('circle', { cx: x(i), cy: y(punto.unidades), r: 5, fill: '#7c3aed', stroke: '#ffffff', 'stroke-width': 2 });
            circulo.append(nodo('title', {}, `${punto.nombre}: ${numero(punto.unidades)} unidades · ${punto.intervalo}`));
            svg.append(circulo);
            svg.append(nodo('text', { x: x(i), y: y(punto.unidades) - 14, 'text-anchor': 'middle', fill: '#5b21b6', 'font-size': 13, 'font-weight': 600 }, numero(punto.unidades)));
            svg.append(nodo('text', { x: x(i), y: 254, 'text-anchor': 'middle', fill: '#334155', 'font-size': 12 }, punto.nombre));
            svg.append(nodo('text', { x: x(i), y: 274, 'text-anchor': 'middle', fill: '#64748b', 'font-size': 11 }, punto.intervalo));
        });
        grafico.replaceChildren(svg);
        $('kardex-tendencia-contexto').textContent = datos.sede + ' · ' + titulo;
    }
    function limpiar() {
        datos = null;
        if (!boton || !panel) return;
        boton.disabled = true;
        boton.title = 'Compara al menos dos períodos para ver la tendencia';
        boton.setAttribute('aria-expanded', 'false');
        boton.querySelector('span').textContent = 'Ver tendencia';
        panel.classList.add('hidden');
        grafico.replaceChildren();
        selector.replaceChildren();
    }
    window.tendenciaPeriodosKardex = {
        limpiar,
        actualizar(consulta, transicion) {
            limpiar();
            if (!boton || consulta.periodos.length < 2) return;
            datos = {
                sede: consulta.sede,
                periodos: consulta.periodos.map((periodo, indice) => ({ ...periodo, indice }))
                    .sort((a, b) => a.inicio.localeCompare(b.inicio)),
                productos: consulta.productos.map(producto => ({ ...producto, ventas: [...producto.ventas] }))
            };
            animar = transicion || (actualizar => actualizar());
            const total = document.createElement('option');
            total.value = '';
            total.textContent = 'Total de productos consultados';
            selector.append(total);
            datos.productos.forEach(producto => {
                const opcion = document.createElement('option');
                opcion.value = producto.codigo;
                opcion.textContent = producto.codigo + ' · ' + producto.descripcion;
                selector.append(opcion);
            });
            boton.disabled = false;
            boton.title = 'Ver unidades vendidas por mes consultado';
        }
    };
    boton?.addEventListener('click', () => {
        if (!datos || boton.disabled) return;
        animar(() => {
            const mostrar = panel.classList.contains('hidden');
            if (mostrar) dibujar();
            panel.classList.toggle('hidden', !mostrar);
            boton.setAttribute('aria-expanded', String(mostrar));
            boton.querySelector('span').textContent = mostrar ? 'Ocultar tendencia' : 'Ver tendencia';
        });
    });
    selector?.addEventListener('change', dibujar);
})();
