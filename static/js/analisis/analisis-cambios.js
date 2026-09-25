/**
 * Gestión de cambios pendientes de productos.
 *
 * Responsabilidades:
 * - Detectar cambios en PRE y Costo.
 * - Mostrar el detalle de cambios.
 * - Guardar cambios antes de ejecutar acciones.
 * - Confirmar navegación cuando existen cambios.
 * - Gestionar el tooltip de cambios.
 */

(function () {
    'use strict';


    // ============================================================
    // UTILIDADES LOCALES
    // ============================================================

    function escaparHTML(valor) {
        return String(valor ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }


    function formatearValorPre(valor) {
        return Number(valor).toLocaleString(
            'es-VE',
            {
                maximumFractionDigits: 2
            }
        );
    }


    function formatearValorCosto(valor) {
        return `$ ${Number(valor).toLocaleString(
            'es-VE',
            {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }
        )}`;
    }


    // ============================================================
    // DETECCIÓN DE CAMBIOS
    // ============================================================

    function obtenerProductosModificados() {

        const modificados = [];

        document.querySelectorAll(
            '#filas-tabla-analisis tr'
        ).forEach(tr => {

            const inpCod =
                tr.querySelector('.inp-codigo');

            const inpPre =
                tr.querySelector('.inp-pre');

            const inpCosto =
                tr.querySelector('.inp-costo');

            if (
                !inpCod
                || !inpCod.value.trim()
                || !inpPre
                || !inpCosto
            ) {
                return;
            }

            const originalPre =
                parseFloat(inpPre.dataset.original);

            const originalCosto =
                parseFloat(inpCosto.dataset.original);

            const nuevoPre =
                parseFloat(inpPre.value);

            const nuevoCosto =
                parseFloat(inpCosto.value);

            if (
                Number.isNaN(originalPre)
                || Number.isNaN(originalCosto)
                || Number.isNaN(nuevoPre)
                || Number.isNaN(nuevoCosto)
            ) {
                return;
            }

            if (
                originalPre !== nuevoPre
                || originalCosto !== nuevoCosto
            ) {
                modificados.push({
                    codigo:
                        normalizarCodigoAnalisis(
                            inpCod.value
                        ),

                    unidad_manejo:
                        nuevoPre,

                    precio:
                        nuevoCosto
                });
            }
        });

        return modificados;
    }


    function obtenerDetalleCambiosProductos() {

        const cambios = [];

        document.querySelectorAll(
            '#filas-tabla-analisis tr'
        ).forEach(tr => {

            const inpCod =
                tr.querySelector('.inp-codigo');

            const inpDesc =
                tr.querySelector('.inp-desc');

            const inpPre =
                tr.querySelector('.inp-pre');

            const inpCosto =
                tr.querySelector('.inp-costo');

            if (
                !inpCod
                || !inpCod.value.trim()
                || !inpPre
                || !inpCosto
            ) {
                return;
            }

            const originalPre =
                parseFloat(inpPre.dataset.original);

            const originalCosto =
                parseFloat(inpCosto.dataset.original);

            const nuevoPre =
                parseFloat(inpPre.value);

            const nuevoCosto =
                parseFloat(inpCosto.value);

            if (
                Number.isNaN(originalPre)
                || Number.isNaN(originalCosto)
                || Number.isNaN(nuevoPre)
                || Number.isNaN(nuevoCosto)
            ) {
                return;
            }

            const cambioPre =
                originalPre !== nuevoPre;

            const cambioCosto =
                originalCosto !== nuevoCosto;

            if (!cambioPre && !cambioCosto) {
                return;
            }

            cambios.push({
                codigo:
                    normalizarCodigoAnalisis(
                        inpCod.value
                    ),

                descripcion:
                    inpDesc?.value || '',

                originalPre,
                nuevoPre,
                cambioPre,

                originalCosto,
                nuevoCosto,
                cambioCosto
            });
        });

        return cambios;
    }


    // ============================================================
    // RENDER DEL MODAL DE CAMBIOS
    // ============================================================

    function renderizarCambiosProductos() {

        const tbody =
            document.getElementById(
                'lista-cambios-productos'
            );

        if (!tbody) {
            return;
        }

        const cambios =
            obtenerDetalleCambiosProductos();

        tbody.innerHTML = '';

        cambios.forEach(cambio => {

            const tr =
                document.createElement('tr');

            tr.className =
                'hover:bg-slate-50 transition';

            let htmlPre = '';

            if (cambio.cambioPre) {

                htmlPre = `
                    <span class="text-slate-400 line-through mr-1">
                        ${formatearValorPre(cambio.originalPre)}
                    </span>

                    <span class="text-emerald-600">
                        ${formatearValorPre(cambio.nuevoPre)}
                    </span>
                `;

            } else {

                htmlPre = `
                    <span class="text-slate-700">
                        ${formatearValorPre(cambio.nuevoPre)}
                    </span>
                `;
            }


            let htmlCosto = '';

            if (cambio.cambioCosto) {

                htmlCosto = `
                    <span class="text-slate-400 line-through mr-1">
                        ${formatearValorCosto(cambio.originalCosto)}
                    </span>

                    <span class="text-emerald-600">
                        ${formatearValorCosto(cambio.nuevoCosto)}
                    </span>
                `;

            } else {

                htmlCosto = `
                    <span class="text-slate-700">
                        ${formatearValorCosto(cambio.nuevoCosto)}
                    </span>
                `;
            }


            tr.innerHTML = `
                <td class="px-4 py-3 font-semibold text-slate-700">
                    ${escaparHTML(cambio.codigo)}
                </td>

                <td class="px-4 py-3 text-slate-600">
                    ${escaparHTML(cambio.descripcion)}
                </td>

                <td
                    class="px-4 py-3 text-center font-semibold cursor-help"
                    data-tooltip-pre="true"
                    title="">

                    ${htmlPre}
                </td>

                <td
                    class="px-4 py-3 text-right font-semibold cursor-help">

                    ${htmlCosto}
                </td>
            `;


            const celdaPre =
                tr.children[2];

            const celdaCosto =
                tr.children[3];


            if (cambio.cambioPre) {

                celdaPre.title =
                    `Antes: ${formatearValorPre(cambio.originalPre)}\n`
                    + `Ahora: ${formatearValorPre(cambio.nuevoPre)}`;

            } else {

                celdaPre.removeAttribute('title');
            }


            if (cambio.cambioCosto) {

                celdaCosto.title =
                    `Antes: ${formatearValorCosto(cambio.originalCosto)}\n`
                    + `Ahora: ${formatearValorCosto(cambio.nuevoCosto)}`;

            } else {

                celdaCosto.removeAttribute('title');
            }


            tbody.appendChild(tr);
        });
    }


    // ============================================================
    // ESTADO DE CAMBIOS
    // ============================================================

    function marcarCambiosComoGuardados() {

        document.querySelectorAll(
            '#filas-tabla-analisis tr'
        ).forEach(tr => {

            const inpPre =
                tr.querySelector('.inp-pre');

            const inpCosto =
                tr.querySelector('.inp-costo');

            if (inpPre) {
                inpPre.dataset.original =
                    inpPre.value;
            }

            if (inpCosto) {
                inpCosto.dataset.original =
                    inpCosto.value;
            }
        });

        ocultarTooltipCambioProducto();
    }


    function limpiarEstadoCambiosProductos() {

        document.querySelectorAll(
            '#filas-tabla-analisis .inp-pre, #filas-tabla-analisis .inp-costo'
        ).forEach(input => {

            delete input.dataset.original;
        });

        ocultarTooltipCambioProducto();
    }


    // ============================================================
    // TOOLTIP DE CAMBIOS
    // ============================================================

    let tooltipCambioProducto = null;


    function posicionarTooltipCambioProducto(x, y) {

        if (!tooltipCambioProducto) {
            return;
        }

        const margen = 12;

        let left = x + margen;
        let top = y + margen;

        const rect =
            tooltipCambioProducto.getBoundingClientRect();

        if (
            left + rect.width
            > window.innerWidth - margen
        ) {
            left =
                x - rect.width - margen;
        }

        if (
            top + rect.height
            > window.innerHeight - margen
        ) {
            top =
                y - rect.height - margen;
        }

        tooltipCambioProducto.style.left =
            `${Math.max(margen, left)}px`;

        tooltipCambioProducto.style.top =
            `${Math.max(margen, top)}px`;
    }


    function ocultarTooltipCambioProducto() {

        if (tooltipCambioProducto) {

            tooltipCambioProducto.classList.add(
                'hidden'
            );
        }
    }


    function mostrarTooltipCambioProducto(
        input,
        tipo,
        evento
    ) {

        if (!input.dataset.original) {
            return;
        }

        const original =
            parseFloat(input.dataset.original);

        const actual =
            parseFloat(input.value);

        if (
            Number.isNaN(original)
            || Number.isNaN(actual)
            || original === actual
        ) {
            ocultarTooltipCambioProducto();
            return;
        }

        if (!tooltipCambioProducto) {

            tooltipCambioProducto =
                document.createElement('div');

            tooltipCambioProducto.className =
                'fixed z-[10001] hidden '
                + 'bg-slate-900 text-white '
                + 'text-xs rounded-lg shadow-xl '
                + 'px-3 py-2 pointer-events-none';

            document.body.appendChild(
                tooltipCambioProducto
            );
        }


        let contenido = '';

        if (tipo === 'pre') {

            contenido = `
                <div>
                    Antes:
                    <span class="text-slate-300">
                        ${formatearValorPre(original)}
                    </span>
                </div>

                <div>
                    Ahora:
                    <span class="text-emerald-300 font-semibold">
                        ${formatearValorPre(actual)}
                    </span>
                </div>
            `;

        } else {

            contenido = `
                <div>
                    Antes:
                    <span class="text-slate-300">
                        ${formatearValorCosto(original)}
                    </span>
                </div>

                <div>
                    Ahora:
                    <span class="text-emerald-300 font-semibold">
                        ${formatearValorCosto(actual)}
                    </span>
                </div>
            `;
        }


        tooltipCambioProducto.innerHTML =
            contenido;

        tooltipCambioProducto.classList.remove(
            'hidden'
        );

        posicionarTooltipCambioProducto(
            evento.clientX,
            evento.clientY
        );
    }


    // Eventos delegados.
    document.addEventListener(
        'mouseover',
        e => {

            const input =
                e.target.closest(
                    '#filas-tabla-analisis .inp-pre, #filas-tabla-analisis .inp-costo'
                );

            if (!input) {
                return;
            }

            const tipo =
                input.classList.contains('inp-pre')
                    ? 'pre'
                    : 'costo';

            mostrarTooltipCambioProducto(
                input,
                tipo,
                e
            );
        }
    );


    document.addEventListener(
        'mousemove',
        e => {

            if (
                tooltipCambioProducto
                && !tooltipCambioProducto.classList.contains(
                    'hidden'
                )
            ) {
                posicionarTooltipCambioProducto(
                    e.clientX,
                    e.clientY
                );
            }
        }
    );


    document.addEventListener(
        'mouseout',
        e => {

            const input =
                e.target.closest(
                    '#filas-tabla-analisis .inp-pre, #filas-tabla-analisis .inp-costo'
                );

            if (input) {
                ocultarTooltipCambioProducto();
            }
        }
    );


    // ============================================================
    // FLUJO DE ACCIONES CON CAMBIOS PENDIENTES
    // ============================================================

    let accionPendienteCambios = null;


    function cerrarModalCambiosProductos() {

        const modal =
            document.getElementById(
                'modal-cambios-productos'
            );

        if (modal) {
            modal.classList.add('hidden');
        }

        accionPendienteCambios = null;
    }


    async function resolverCambiosProductos(
        guardarCambios
    ) {

        const pendiente =
            accionPendienteCambios;

        if (!pendiente) {
            return;
        }

        const modal =
            document.getElementById(
                'modal-cambios-productos'
            );

        if (modal) {
            modal.classList.add('hidden');
        }

        accionPendienteCambios = null;


        if (guardarCambios) {

            const modificados =
                obtenerProductosModificados();

            const guardadoCorrectamente =
                await guardarDatosModificados(
                    modificados
                );

            if (!guardadoCorrectamente) {
                return;
            }
        }


        if (!guardarCambios) {

            if (
                !pendiente.conservarCambiosSiNoGuarda
            ) {
                limpiarEstadoCambiosProductos();
            }
        }


        await pendiente.accion();
    }


    function ejecutarAccionConCambios(
        accion,
        conservarCambiosSiNoGuarda = true
    ) {

        const modificados =
            obtenerProductosModificados();

        if (modificados.length === 0) {
            return accion();
        }

        accionPendienteCambios = {
            accion,
            conservarCambiosSiNoGuarda
        };

        renderizarCambiosProductos();

        const modal =
            document.getElementById(
                'modal-cambios-productos'
            );

        if (modal) {
            modal.classList.remove('hidden');
        }
    }


    // ============================================================
    // GUARDAR CAMBIOS DE PRODUCTOS
    // ============================================================

    async function guardarDatosModificados(
        modificados
    ) {

        if (
            !Array.isArray(modificados)
            || modificados.length === 0
        ) {
            return true;
        }

        try {

            console.log(
                'Enviando cambios de productos:',
                JSON.stringify(modificados)
            );

            const response =
                await fetch(
                    '/api/productos/actualizar-analisis',
                    {
                        method: 'POST',

                        headers: {
                            'Content-Type':
                                'application/json'
                        },

                        body:
                            JSON.stringify(
                                modificados
                            )
                    }
                );


            const resultado =
                await response.json().catch(
                    () => ({})
                );


            if (!response.ok) {

                console.error(
                    'Error al actualizar productos:',
                    resultado
                );

                mostrarNotificacion({
                    tipo: 'error',

                    mensaje:
                        resultado.detail
                        || 'Error al guardar los cambios en la base de datos.'
                });

                return false;
            }


            marcarCambiosComoGuardados();

            console.log(
                'Datos de productos actualizados correctamente.'
            );

            return true;

        } catch (error) {

            console.error(
                'Error de conexión al actualizar productos:',
                error
            );

            mostrarNotificacion({
                tipo: 'error',

                mensaje:
                    'No se pudieron guardar los cambios de los productos.'
            });

            return false;
        }
    }


    // ============================================================
    // ESCAPE PARA EL MODAL
    // ============================================================

    document.addEventListener(
        'keydown',
        e => {

            const modal =
                document.getElementById(
                    'modal-cambios-productos'
                );

            if (
                e.key === 'Escape'
                && modal
                && !modal.classList.contains('hidden')
            ) {
                e.preventDefault();

                cerrarModalCambiosProductos();
            }
        }
    );


    // ============================================================
    // NAVEGACIÓN CON CAMBIOS PENDIENTES
    // ============================================================

    document.addEventListener(
        'click',
        e => {

            const link =
                e.target.closest('a');

            if (
                !link
                || !link.href
                || link.target
                || link.href.startsWith(
                    'javascript:'
                )
                || link.href.includes('#')
            ) {
                return;
            }


            const url =
                new URL(
                    link.href,
                    window.location.href
                );


            if (
                url.origin
                !== window.location.origin
            ) {
                return;
            }


            const modificados =
                obtenerProductosModificados();

            if (modificados.length === 0) {
                return;
            }


            e.preventDefault();


            ejecutarAccionConCambios(
                async () => {

                    window.location.href =
                        link.href;
                },

                false
            );
        }
    );


    window.addEventListener(
        'beforeunload',
        e => {

            if (
                obtenerProductosModificados().length
                > 0
            ) {
                e.preventDefault();
                e.returnValue = '';
            }
        }
    );


    // ============================================================
    // EXPONER API DEL MÓDULO
    // ============================================================

    window.obtenerProductosModificados =
        obtenerProductosModificados;

    window.obtenerDetalleCambiosProductos =
        obtenerDetalleCambiosProductos;

    window.renderizarCambiosProductos =
        renderizarCambiosProductos;

    window.marcarCambiosComoGuardados =
        marcarCambiosComoGuardados;

    window.limpiarEstadoCambiosProductos =
        limpiarEstadoCambiosProductos;

    window.cerrarModalCambiosProductos =
        cerrarModalCambiosProductos;

    window.resolverCambiosProductos =
        resolverCambiosProductos;

    window.ejecutarAccionConCambios =
        ejecutarAccionConCambios;

    window.guardarDatosModificados =
        guardarDatosModificados;

})();