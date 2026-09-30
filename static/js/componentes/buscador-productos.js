(function () {
    'use strict';

    // =========================================================
    // BUSCADOR DE PRODUCTOS — F2
    // Componente compartido por Análisis e Inventario
    // =========================================================

    let celdaCodigoActivaModal = null;
    let indiceProductoDestacadoModal = -1;
    let etiquetasFiltroProductosModal = [];
    let debounceBusquedaProductoModal = null;

    // Control de peticiones para evitar respuestas antiguas
    // sobrescribiendo una búsqueda más reciente.
    let controladorBusqueda = null;
    let secuenciaBusqueda = 0;


    // =========================================================
    // UTILIDADES
    // =========================================================

    function obtenerElemento(id) {
        return document.getElementById(id);
    }


    function normalizarTextoProductoModal(texto) {
        if (!texto) {
            return '';
        }

        return String(texto)
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .trim();
    }


    function mostrarMensajeResultados(
        mensaje,
        clase = 'text-slate-400'
    ) {
        const contenedor =
            obtenerElemento(
                'contenedor-resultados-productos'
            );

        if (!contenedor) {
            return;
        }

        contenedor.innerHTML = '';

        const div =
            document.createElement('div');

        div.className =
            `p-4 text-center text-xs ${clase}`;

        div.textContent = mensaje;

        contenedor.appendChild(div);
    }


    // =========================================================
    // CREACIÓN DEL MODAL
    // =========================================================

    function crearModalBuscadorProductos() {

        // Si la página ya tiene el modal, no lo duplicamos.
        if (
            obtenerElemento(
                'modal-buscador-productos'
            )
        ) {
            return;
        }

        const modal =
            document.createElement('div');

        modal.id =
            'modal-buscador-productos';

        modal.className =
            'hidden fixed inset-0 z-[110] ' +
            'flex items-center justify-center ' +
            'bg-slate-900/50 backdrop-blur-sm ' +
            'overflow-y-auto p-4';

        modal.innerHTML = `
            <div
                class="relative z-10
                       bg-white rounded-xl shadow-2xl
                       w-full max-w-lg p-6
                       flex flex-col max-h-[80vh]"
            >

                <!-- CABECERA -->

                <div
                    class="flex items-center justify-between mb-4"
                >

                    <h3
                        class="text-base font-bold text-slate-800
                               flex items-center gap-2"
                    >
                        <i
                            class="fa-solid fa-magnifying-glass
                                   text-blue-600"
                        ></i>

                        Buscar Producto
                    </h3>

                    <button
                        type="button"
                        id="btn-cerrar-buscador-productos"
                        class="text-slate-400
                               hover:text-rose-500"
                        title="Cerrar"
                    >
                        <i class="fa-solid fa-xmark text-base"></i>
                    </button>

                </div>


                <!-- BUSCADOR -->

                <div
                    id="contenedor-buscador-producto-modal"
                    class="w-full min-h-[42px]
                           px-3 py-1.5
                           border border-slate-300
                           rounded-xl bg-white
                           flex flex-wrap items-center gap-1.5
                           focus-within:ring-2
                           focus-within:ring-blue-500
                           focus-within:border-blue-500
                           transition-all cursor-text"
                >

                    <i
                        class="fa-solid fa-search
                               text-slate-400 shrink-0"
                    ></i>

                    <div
                        id="lista-etiquetas-producto-modal"
                        class="flex flex-wrap
                               items-center gap-1.5"
                    ></div>

                    <input
                        type="text"
                        id="input-buscar-producto-modal"
                        autocomplete="off"
                        spellcheck="false"
                        placeholder="Buscar código ST, EAN, descripción, proveedor..."
                        class="flex-1 min-w-[120px]
                               bg-transparent
                               border-0 p-0
                               text-xs font-medium
                               text-slate-800
                               focus:ring-0
                               focus:outline-none
                               placeholder:text-slate-400"
                    >

                </div>


                <!-- RESULTADOS -->

                <div
                    id="contenedor-resultados-productos"
                    class="flex-1 overflow-y-auto
                           border border-slate-200
                           rounded-xl
                           divide-y divide-slate-100
                           min-h-[160px]
                           max-h-60 mt-4"
                ></div>


                <!-- PIE -->

                <div
                    class="flex items-center justify-between
                           pt-4 border-t border-slate-100
                           mt-4 text-[11px] text-slate-500"
                >

                    <span>
                        Navegar:
                        <kbd
                            class="px-1 py-0.5
                                   bg-slate-100
                                   border border-slate-300
                                   rounded text-[10px]"
                        >↑</kbd>

                        <kbd
                            class="px-1 py-0.5
                                   bg-slate-100
                                   border border-slate-300
                                   rounded text-[10px]"
                        >↓</kbd>

                        |

                        Seleccionar:
                        <kbd
                            class="px-1 py-0.5
                                   bg-slate-100
                                   border border-slate-300
                                   rounded text-[10px]"
                        >Enter</kbd>
                    </span>

                    <button
                        type="button"
                        id="btn-cancelar-buscador-productos"
                        class="px-3 py-1.5
                               bg-slate-100
                               hover:bg-slate-200
                               text-slate-700
                               font-semibold rounded-lg"
                    >
                        Cancelar
                    </button>

                </div>

            </div>
        `;

        document.body.appendChild(modal);


        // -----------------------------------------------------
        // Eventos del modal
        // -----------------------------------------------------

        const btnCerrar =
            obtenerElemento(
                'btn-cerrar-buscador-productos'
            );

        const btnCancelar =
            obtenerElemento(
                'btn-cancelar-buscador-productos'
            );

        const inputBuscar =
            obtenerElemento(
                'input-buscar-producto-modal'
            );

        const contenedorBuscador =
            obtenerElemento(
                'contenedor-buscador-producto-modal'
            );


        if (btnCerrar) {
            btnCerrar.addEventListener(
                'click',
                cerrarModalBuscadorProductos
            );
        }


        if (btnCancelar) {
            btnCancelar.addEventListener(
                'click',
                cerrarModalBuscadorProductos
            );
        }


        if (inputBuscar) {

            inputBuscar.addEventListener(
                'input',
                manejarInputBusquedaProductoModal
            );

            inputBuscar.addEventListener(
                'keydown',
                manejarKeySearchModal
            );
        }


        if (contenedorBuscador) {

            contenedorBuscador.addEventListener(
                'click',
                () => {

                    if (inputBuscar) {
                        inputBuscar.focus();
                    }

                }
            );
        }


        mostrarMensajeResultados(
            'Lista de productos'
        );
    }


    // =========================================================
    // ETIQUETAS / FILTROS
    // =========================================================

    function renderizarEtiquetasProductoModal() {

        const contenedor =
            obtenerElemento(
                'lista-etiquetas-producto-modal'
            );

        if (!contenedor) {
            return;
        }

        contenedor.innerHTML = '';

        etiquetasFiltroProductosModal.forEach(
            (valor, indice) => {

                const badge =
                    document.createElement('span');

                badge.className =
                    'inline-flex items-center gap-1 ' +
                    'bg-blue-100 text-blue-800 ' +
                    'text-[11px] font-semibold ' +
                    'px-2 py-0.5 rounded-md ' +
                    'border border-blue-200';


                const texto =
                    document.createElement('span');

                texto.textContent =
                    valor;


                const boton =
                    document.createElement('button');

                boton.type =
                    'button';

                boton.className =
                    'hover:text-rose-600 ' +
                    'ml-0.5 focus:outline-none';

                boton.title =
                    'Quitar filtro';


                const icono =
                    document.createElement('i');

                icono.className =
                    'fa-solid fa-xmark text-[10px]';


                boton.appendChild(icono);

                boton.addEventListener(
                    'click',
                    (e) => {

                        e.preventDefault();
                        e.stopPropagation();

                        removerEtiquetaProductoModal(
                            indice
                        );
                    }
                );


                badge.appendChild(texto);
                badge.appendChild(boton);

                contenedor.appendChild(badge);
            }
        );
    }


    function agregarEtiquetaProductoModal(valor) {

        const valorLimpio =
            String(valor || '').trim();

        if (!valorLimpio) {
            return;
        }


        const existe =
            etiquetasFiltroProductosModal.some(
                etiqueta =>
                    normalizarTextoProductoModal(
                        etiqueta
                    ) ===
                    normalizarTextoProductoModal(
                        valorLimpio
                    )
            );


        if (existe) {
            return;
        }


        etiquetasFiltroProductosModal.push(
            valorLimpio
        );

        renderizarEtiquetasProductoModal();


        const input =
            obtenerElemento(
                'input-buscar-producto-modal'
            );

        if (input) {

            input.value = '';
            input.focus();
        }


        indiceProductoDestacadoModal =
            -1;

        ejecutarBusquedaProductoModal();
    }


    function removerEtiquetaProductoModal(indice) {

        etiquetasFiltroProductosModal.splice(
            indice,
            1
        );

        renderizarEtiquetasProductoModal();

        indiceProductoDestacadoModal =
            -1;

        ejecutarBusquedaProductoModal();
    }


    // =========================================================
    // ABRIR / CERRAR
    // =========================================================

    function abrirModalBuscadorProductos(inputElem) {

        if (!inputElem) {
            return;
        }


        crearModalBuscadorProductos();


        celdaCodigoActivaModal =
            inputElem;


        indiceProductoDestacadoModal =
            -1;


        etiquetasFiltroProductosModal =
            [];


        renderizarEtiquetasProductoModal();


        const modal =
            obtenerElemento(
                'modal-buscador-productos'
            );

        const inputBuscar =
            obtenerElemento(
                'input-buscar-producto-modal'
            );


        if (!modal) {
            return;
        }


        modal.classList.remove('hidden');


        if (inputBuscar) {

            inputBuscar.value = '';

            inputBuscar.focus();

            inputBuscar.select();
        }


        mostrarMensajeResultados(
            'Escriba un criterio de búsqueda'
        );
    }


    function cerrarModalBuscadorProductos() {

        // Cancelamos cualquier petición pendiente.
        if (controladorBusqueda) {

            controladorBusqueda.abort();

            controladorBusqueda =
                null;
        }


        clearTimeout(
            debounceBusquedaProductoModal
        );


        const modal =
            obtenerElemento(
                'modal-buscador-productos'
            );


        if (modal) {
            modal.classList.add('hidden');
        }


        if (celdaCodigoActivaModal) {

            celdaCodigoActivaModal.focus();
        }


        celdaCodigoActivaModal =
            null;

        indiceProductoDestacadoModal =
            -1;

        etiquetasFiltroProductosModal =
            [];
    }


    // =========================================================
    // BÚSQUEDA
    // =========================================================

    async function ejecutarBusquedaProductoModal() {

        const inputBuscar =
            obtenerElemento(
                'input-buscar-producto-modal'
            );


        const textoActual =
            inputBuscar?.value.trim() || '';


        const terminos = [
            ...etiquetasFiltroProductosModal
        ];


        /*
         * El texto que todavía está escribiendo
         * también participa en la búsqueda.
         */
        if (textoActual) {
            terminos.push(textoActual);
        }


        if (terminos.length === 0) {

            mostrarMensajeResultados(
                'Escriba un criterio de búsqueda'
            );

            indiceProductoDestacadoModal =
                -1;

            return;
        }


        mostrarMensajeResultados(
            'Buscando productos...',
            'text-slate-500'
        );


        // Cancela una búsqueda anterior.
        if (controladorBusqueda) {
            controladorBusqueda.abort();
        }


        controladorBusqueda =
            new AbortController();


        const miBusqueda =
            ++secuenciaBusqueda;


        try {

            const params =
                new URLSearchParams();


            params.set(
                'tags',
                terminos.join(',')
            );


            const response =
                await fetch(
                    `/api/productos/buscar?${params.toString()}`,
                    {
                        signal:
                            controladorBusqueda.signal,

                        headers: {
                            'Accept':
                                'application/json'
                        }
                    }
                );


            if (!response.ok) {

                throw new Error(
                    `Error HTTP ${response.status}`
                );
            }


            const data =
                await response.json();


            /*
             * Si llegó una respuesta vieja después
             * de otra búsqueda, la ignoramos.
             */
            if (
                miBusqueda !==
                secuenciaBusqueda
            ) {
                return;
            }


            if (
                !Array.isArray(data) ||
                data.length === 0
            ) {

                mostrarMensajeResultados(
                    'No se encontraron productos coincidentes'
                );

                indiceProductoDestacadoModal =
                    -1;

                return;
            }


            renderizarResultadosProductos(data);

        } catch (error) {

            // AbortController genera este error normalmente.
            if (
                error?.name ===
                'AbortError'
            ) {
                return;
            }


            console.error(
                'Error al buscar productos:',
                error
            );


            mostrarMensajeResultados(
                'Error al realizar la búsqueda',
                'text-rose-500'
            );


            indiceProductoDestacadoModal =
                -1;
        }
    }


    function manejarInputBusquedaProductoModal() {

        clearTimeout(
            debounceBusquedaProductoModal
        );


        indiceProductoDestacadoModal =
            -1;


        debounceBusquedaProductoModal =
            setTimeout(
                () => {
                    ejecutarBusquedaProductoModal();
                },
                300
            );
    }


    // =========================================================
    // RENDERIZADO DE RESULTADOS
    // =========================================================

    function renderizarResultadosProductos(data) {

        const contenedor =
            obtenerElemento(
                'contenedor-resultados-productos'
            );


        if (!contenedor) {
            return;
        }


        contenedor.innerHTML = '';


        indiceProductoDestacadoModal =
            -1;


        data.forEach(
            (item, index) => {

                const div =
                    document.createElement('div');


                div.className =
                    'opcion-prod-modal ' +
                    'p-2.5 text-xs ' +
                    'flex justify-between ' +
                    'items-start gap-3 ' +
                    'cursor-pointer hover:bg-blue-50 ' +
                    'transition border-b ' +
                    'border-slate-100 ' +
                    'last:border-b-0';


                div.dataset.codigo =
                    item.codigo || '';


                // -------------------------------------------------
                // Información izquierda
                // -------------------------------------------------

                const bloqueIzquierdo =
                    document.createElement('div');


                bloqueIzquierdo.className =
                    'flex flex-col min-w-0 pr-2';


                const descripcion =
                    document.createElement('span');


                descripcion.className =
                    'font-bold text-slate-800';


                descripcion.textContent =
                    item.descripcion ||
                    'Sin descripción';


                const codigo =
                    document.createElement('span');


                codigo.className =
                    'text-[10px] text-slate-400';


                codigo.textContent =
                    `Código: ${item.codigo || '-'}`;


                const contenedorBadges =
                    document.createElement('div');


                contenedorBadges.className =
                    'flex flex-wrap gap-1 mt-1';


                agregarBadgeResultado(
                    contenedorBadges,
                    item.departamento,
                    'bg-slate-200 text-slate-700'
                );


                agregarBadgeResultado(
                    contenedorBadges,
                    item.grupo,
                    'bg-sky-100 text-slate-700'
                );


                agregarBadgeResultado(
                    contenedorBadges,
                    item.subgrupo,
                    'bg-sky-100 text-slate-700'
                );


                bloqueIzquierdo.appendChild(
                    descripcion
                );

                bloqueIzquierdo.appendChild(
                    codigo
                );

                bloqueIzquierdo.appendChild(
                    contenedorBadges
                );


                // -------------------------------------------------
                // Información derecha
                // -------------------------------------------------

                const bloqueDerecho =
                    document.createElement('div');


                bloqueDerecho.className =
                    'text-right shrink-0';


                const precio =
                    document.createElement('span');


                precio.className =
                    'font-bold text-blue-600 block';


                const precioNumerico =
                    parseFloat(
                        item.precio
                    );


                precio.textContent =
                    `$ ${(Number.isFinite(precioNumerico)
                        ? precioNumerico
                        : 0
                    ).toFixed(2)}`;


                const unidad =
                    document.createElement('span');


                unidad.className =
                    'text-[10px] text-slate-400';


                unidad.textContent =
                    `Emp: ${item.unidad_manejo || 1
                    }`;


                bloqueDerecho.appendChild(
                    precio
                );

                bloqueDerecho.appendChild(
                    unidad
                );


                // -------------------------------------------------
                // Construcción de resultado
                // -------------------------------------------------

                div.appendChild(
                    bloqueIzquierdo
                );

                div.appendChild(
                    bloqueDerecho
                );


                // Click = destacar.
                div.addEventListener(
                    'click',
                    () => {

                        indiceProductoDestacadoModal =
                            index;

                        resaltarOpcionProductoModal();
                    }
                );


                // Doble click = seleccionar.
                div.addEventListener(
                    'dblclick',
                    () => {

                        seleccionarProductoDesdeModal(
                            item.codigo
                        );
                    }
                );


                contenedor.appendChild(div);
            }
        );
    }


    function agregarBadgeResultado(
        contenedor,
        valor,
        clases
    ) {

        if (
            valor === null ||
            valor === undefined ||
            String(valor).trim() === ''
        ) {
            return;
        }


        const badge =
            document.createElement('span');


        badge.className =
            `text-[10px] ${clases} ` +
            'px-1.5 py-0.5 rounded-md';


        badge.textContent =
            String(valor);


        contenedor.appendChild(
            badge
        );
    }


    // =========================================================
    // NAVEGACIÓN POR TECLADO
    // =========================================================

    function manejarKeySearchModal(e) {

        const input =
            obtenerElemento(
                'input-buscar-producto-modal'
            );


        const opciones =
            Array.from(
                document.querySelectorAll(
                    '#contenedor-resultados-productos .opcion-prod-modal'
                )
            );


        // -----------------------------------------------------
        // ENTER
        // -----------------------------------------------------

        if (e.key === 'Enter') {

            e.preventDefault();
            e.stopPropagation();


            if (
                indiceProductoDestacadoModal >= 0 &&
                opciones[
                indiceProductoDestacadoModal
                ]
            ) {

                const codigo =
                    opciones[
                        indiceProductoDestacadoModal
                    ].dataset.codigo;


                seleccionarProductoDesdeModal(
                    codigo
                );

                return;
            }


            const valor =
                input?.value.trim() || '';


            if (valor) {

                agregarEtiquetaProductoModal(
                    valor
                );

            } else {

                ejecutarBusquedaProductoModal();
            }


            return;
        }


        // -----------------------------------------------------
        // FLECHA ABAJO
        // -----------------------------------------------------

        if (e.key === 'ArrowDown') {

            e.preventDefault();
            e.stopPropagation();


            if (opciones.length > 0) {

                indiceProductoDestacadoModal =
                    Math.min(
                        indiceProductoDestacadoModal + 1,
                        opciones.length - 1
                    );


                resaltarOpcionProductoModal();
            }


            return;
        }


        // -----------------------------------------------------
        // FLECHA ARRIBA
        // -----------------------------------------------------

        if (e.key === 'ArrowUp') {

            e.preventDefault();
            e.stopPropagation();


            if (opciones.length > 0) {

                indiceProductoDestacadoModal =
                    Math.max(
                        indiceProductoDestacadoModal - 1,
                        0
                    );


                resaltarOpcionProductoModal();
            }


            return;
        }


        // -----------------------------------------------------
        // BACKSPACE
        // -----------------------------------------------------

        if (e.key === 'Backspace') {

            if (
                input &&
                input.value === '' &&
                etiquetasFiltroProductosModal.length > 0
            ) {

                e.preventDefault();
                e.stopPropagation();


                removerEtiquetaProductoModal(
                    etiquetasFiltroProductosModal.length - 1
                );
            }


            return;
        }


        // -----------------------------------------------------
        // ESCAPE
        // -----------------------------------------------------

        if (e.key === 'Escape') {

            e.preventDefault();
            e.stopPropagation();


            cerrarModalBuscadorProductos();

            return;
        }
    }


    // =========================================================
    // RESALTAR RESULTADO
    // =========================================================

    function resaltarOpcionProductoModal() {

        const opciones =
            document.querySelectorAll(
                '#contenedor-resultados-productos .opcion-prod-modal'
            );


        opciones.forEach(
            (opcion, indice) => {

                if (
                    indice ===
                    indiceProductoDestacadoModal
                ) {

                    opcion.classList.add(
                        'bg-blue-100',
                        'border-l-4',
                        'border-l-blue-600'
                    );


                    opcion.scrollIntoView({
                        block: 'nearest'
                    });

                } else {

                    opcion.classList.remove(
                        'bg-blue-100',
                        'border-l-4',
                        'border-l-blue-600'
                    );
                }
            }
        );
    }


    // =========================================================
    // SELECCIÓN DE PRODUCTO
    // =========================================================

    async function seleccionarProductoDesdeModal(
        codigo
    ) {

        const inputDestino =
            celdaCodigoActivaModal;


        if (
            !inputDestino ||
            !codigo
        ) {
            return;
        }


        inputDestino.value =
            codigo;


        cerrarModalBuscadorProductos();


        /*
         * IMPORTANTE:
         *
         * El componente NO sabe si estamos en
         * Análisis o Inventario.
         *
         * La página que lo utiliza define:
         *
         * window.onProductoSeleccionadoBuscador
         *
         * con su propia lógica.
         */

        if (
            typeof window.onProductoSeleccionadoBuscador ===
            'function'
        ) {

            await window.onProductoSeleccionadoBuscador(
                codigo,
                inputDestino
            );
        }
    }


    // =========================================================
    // INICIALIZACIÓN
    // =========================================================

    function inicializarBuscadorProductos() {

        /*
         * No creamos el modal inmediatamente.
         *
         * Se crea cuando se utiliza F2.
         *
         * Esto evita modificar innecesariamente el DOM
         * de páginas que nunca utilicen el buscador.
         */
    }


    if (
        document.readyState ===
        'loading'
    ) {

        document.addEventListener(
            'DOMContentLoaded',
            inicializarBuscadorProductos
        );

    } else {

        inicializarBuscadorProductos();
    }


    // =========================================================
    // API PÚBLICA DEL COMPONENTE
    // =========================================================

    window.abrirModalBuscadorProductos =
        abrirModalBuscadorProductos;


    window.cerrarModalBuscadorProductos =
        cerrarModalBuscadorProductos;


    window.manejarKeySearchModal =
        manejarKeySearchModal;


    window.manejarInputBusquedaProductoModal =
        manejarInputBusquedaProductoModal;


    window.agregarEtiquetaProductoModal =
        agregarEtiquetaProductoModal;


    window.removerEtiquetaProductoModal =
        removerEtiquetaProductoModal;

})();