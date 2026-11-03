/* Tendencia calculada únicamente con los resultados de la comparación actual. */
(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const boton = $('btn-tendencia-periodos');
    const panel = $('kardex-tendencia-contenedor');
    const selector = $('kardex-tendencia-producto');
    const grafico = $('kardex-tendencia-grafico');
    let datos = null;

    const modal = document.createElement('dialog');
    modal.id = 'modal-tendencia-periodos';
    modal.setAttribute('aria-labelledby', 'titulo-tendencia-periodos');
    modal.className =
        'fixed inset-0 m-auto max-h-[90vh] w-[96vw] max-w-7xl ' +
        'overflow-hidden rounded-2xl bg-white p-0 shadow-2xl backdrop:bg-black/50';

    const cerrar = document.createElement('button');
    cerrar.type = 'button';
    cerrar.textContent = 'Cerrar';
    cerrar.className =
        'absolute right-4 top-3 rounded-lg border border-slate-300 ' +
        'bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100';

    panel.insertBefore(cerrar, panel.firstChild);
    panel.classList.remove('hidden');
    panel.classList.add('relative', 'pt-4', 'pr-24');

    grafico.style.maxHeight = '65vh';
    grafico.style.overflow = 'auto';

    modal.append(panel);
    document.body.append(modal);

    boton.setAttribute('aria-haspopup', 'dialog');
    boton.setAttribute('aria-controls', modal.id);
    cerrar.addEventListener('click', () => modal.close());
    modal.addEventListener('close', () => {
        boton.setAttribute('aria-expanded', 'false');
        if (!boton.disabled) boton.focus();
    });
    const numero = valor => Number(valor).toLocaleString('es-VE', { maximumFractionDigits: 2 });

    function nodo(nombre, atributos = {}, texto) {
        const elemento = document.createElementNS('http://www.w3.org/2000/svg', nombre);
        Object.entries(atributos).forEach(([clave, valor]) => elemento.setAttribute(clave, String(valor)));
        if (texto !== undefined) elemento.textContent = texto;
        return elemento;
    }
    function dibujar() {
        if (!datos) return;

        const productos = selector.value
            ? datos.productos.filter(producto => producto.codigo === selector.value)
            : datos.productos;

        const colores = ['#2563eb', '#7c3aed', '#0f766e'];
        const izquierda = 270;
        const ancho = 1080;
        const anchoBarras = 700;
        const inicioFilas = 58;
        const altoBarra = 20;
        const altoFila = datos.periodos.length * altoBarra + 18;
        const finFilas = inicioFilas + productos.length * altoFila;

        // Una sola escala para todos los productos visibles.
        let maximo = 1;
        productos.forEach(producto => {
            producto.ventas.forEach(venta => {
                maximo = Math.max(maximo, venta);
            });
        });

        const svg = nodo('svg', {
            viewBox: `0 0 ${ancho} ${finFilas + 16}`,
            role: 'img',
            'aria-labelledby': 'titulo-barras-tendencia',
            style: 'display:block;width:100%;min-width:850px;height:auto'
        });

        svg.append(nodo('title', {
            id: 'titulo-barras-tendencia'
        }, 'Unidades vendidas por producto y período'));

        // Dibuja la escala horizontal.
        for (let i = 0; i <= 4; i++) {
            const x = izquierda + anchoBarras * i / 4;

            svg.append(nodo('line', {
                x1: x, x2: x, y1: 46, y2: finFilas,
                stroke: '#e2e8f0'
            }));

            svg.append(nodo('text', {
                x, y: 38, 'text-anchor': 'middle',
                fill: '#475569', 'font-size': 12
            }, numero(maximo * i / 4)));
        }

        svg.append(nodo('text', {
            x: izquierda, y: 16, fill: '#475569', 'font-size': 12
        }, 'Unidades vendidas'));

        productos.forEach((producto, fila) => {
            const y = inicioFilas + fila * altoFila;
            const descripcion = producto.descripcion || '';
            const nombre = descripcion.length > 34
                ? `${descripcion.slice(0, 33)}…`
                : descripcion;

            const etiqueta = nodo('text', {
                x: izquierda - 12, y: y + 11, 'text-anchor': 'end',
                fill: '#334155', 'font-size': 12
            }, producto.codigo);

            etiqueta.append(nodo('tspan', {
                x: izquierda - 12, dy: 15, fill: '#64748b'
            }, nombre));
            etiqueta.append(nodo('title', {}, `${producto.codigo} · ${descripcion}`));
            svg.append(etiqueta);

            datos.periodos.forEach((periodo, indice) => {
                // Usa el índice original aunque los períodos se ordenen por fecha.
                const unidades = producto.ventas[periodo.indice];
                const anchoBarra = unidades / maximo * anchoBarras;
                const yBarra = y + indice * altoBarra;

                const grupo = nodo('g');
                const ritmo = Number.isFinite(periodo.dias) && periodo.dias > 0
                    ? ` · ${numero(unidades / periodo.dias)} u/día`
                    : '';

                grupo.append(nodo('title', {},
                    `${producto.codigo} · ${periodo.nombre} · ${periodo.intervalo} · ${numero(unidades)} unidades${ritmo}`
                ));

                grupo.append(nodo('rect', {
                    x: izquierda, y: yBarra,
                    width: anchoBarra, height: 15, rx: 3,
                    fill: colores[indice % colores.length]
                }));

                grupo.append(nodo('text', {
                    x: izquierda + anchoBarra + 6, y: yBarra + 12,
                    fill: '#334155', 'font-size': 12
                }, numero(unidades)));

                svg.append(grupo);
            });
        });

        // La leyenda queda encima del área que se desplaza.
        const leyenda = document.createElement('div');
        leyenda.className =
            'sticky top-0 flex flex-wrap gap-x-5 gap-y-2 border-b ' +
            'border-slate-200 bg-white px-3 py-2 text-xs text-slate-700';

        datos.periodos.forEach((periodo, indice) => {
            const item = document.createElement('span');
            item.className = 'inline-flex items-center gap-2';

            const muestra = document.createElement('span');
            muestra.className = 'inline-block h-3 w-3 rounded-sm';
            muestra.style.backgroundColor = colores[indice % colores.length];

            item.append(muestra, `${periodo.nombre} · ${periodo.intervalo}`);
            leyenda.append(item);
        });

        grafico.replaceChildren(leyenda, svg);
        grafico.scrollTop = 0;

        $('kardex-tendencia-contexto').textContent =
            `${datos.sede} · ${productos.length} de ${datos.productos.length} productos`;
    }

    function limpiar() {
        datos = null;
        if (!boton || !panel) return;
        boton.disabled = true;
        boton.title = 'Compara al menos dos períodos para ver la tendencia';
        boton.setAttribute('aria-expanded', 'false');
        boton.querySelector('span').textContent = 'Ver tendencia';
        if (modal.open) modal.close();
        grafico.replaceChildren();
        selector.replaceChildren();
    }

    window.tendenciaPeriodosKardex = {
        limpiar,
        actualizar(consulta) {
            limpiar();
            if (!boton || consulta.periodos.length < 2) return;
            datos = {
                sede: consulta.sede,
                periodos: consulta.periodos.map((periodo, indice) => ({ ...periodo, indice }))
                    .sort((a, b) => a.inicio.localeCompare(b.inicio)),
                productos: consulta.productos.map(producto => ({ ...producto, ventas: [...producto.ventas] }))
            };

            const total = document.createElement('option');
            total.value = '';
            total.textContent = 'Todos los productos';
            selector.append(total);
            datos.productos.forEach(producto => {
                const opcion = document.createElement('option');
                opcion.value = producto.codigo;
                opcion.textContent = producto.codigo + ' · ' + producto.descripcion;
                selector.append(opcion);
            });
            selector.value = '';
            boton.disabled = false;
            boton.title = 'Ver unidades vendidas por producto y período';
        }
    };
    boton?.addEventListener('click', () => {
        if (!datos || boton.disabled || modal.open) return;

        dibujar();
        modal.showModal();
        boton.setAttribute('aria-expanded', 'true');
        cerrar.focus();
    });
    selector?.addEventListener('change', dibujar);
})();
