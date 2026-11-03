

    // =========================================================
    // ABRIR INVENTARIO DE FORMA SEGURA
    // =========================================================

    async function abrirInventarioSeguro(
        inventarioId
    ) {

        if (!inventarioId) {
            return;
        }

        try {

            const response =
                await fetch(
                    `/inventario/${encodeURIComponent(inventarioId)}`,
                    {
                        method: 'GET',
                        cache: 'no-store',
                        headers: {
                            'Accept': 'text/html'
                        }
                    }
                );

            // El documento fue eliminado
            // desde otra sesión o usuario.
            if (response.status === 404) {

                mostrarNotificacionInventarioLista(
                    'El documento ya no existe. La lista de documentos se actualizará.'
                );

                setTimeout(
                    () => {
                        window.location.reload();
                    },
                    1200
                );

                return;
            }

            // Si el servidor rechaza el acceso,
            // no intentamos abrir nuevamente.
            if (response.status === 403) {

                mostrarNotificacionInventarioLista(
                    'No tienes permiso para acceder a este documento.'
                );

                return;
            }

            // Si hubo otro error del servidor.
            if (!response.ok) {

                mostrarNotificacionInventarioLista(
                    'No se pudo abrir el documento. Inténtalo nuevamente.'
                );

                return;
            }

            // El documento todavía existe.
            window.location.href =
                `/inventario/${encodeURIComponent(inventarioId)}`;

        } catch (error) {

            console.error(
                'Error verificando inventario:',
                error
            );

            mostrarNotificacionInventarioLista(
                'No se pudo verificar el documento. Revisa tu conexión.'
            );

        }

    }


    // =========================================================
    // NOTIFICACIÓN DE LA LISTA DE INVENTARIOS
    // =========================================================

    function mostrarNotificacionInventarioLista(
        mensaje
    ) {

        const existente =
            document.getElementById(
                'notificacion-inventario-lista'
            );

        if (existente) {
            existente.remove();
        }

        const notificacion =
            document.createElement('div');

        notificacion.id =
            'notificacion-inventario-lista';

        notificacion.className =
            'fixed top-4 right-4 z-[9999] ' +
            'max-w-sm w-[calc(100%-2rem)] sm:w-auto ' +
            'bg-slate-900 text-white ' +
            'rounded-xl shadow-2xl ' +
            'px-4 py-3 ' +
            'flex items-start gap-3 ' +
            'text-sm font-medium';

        notificacion.innerHTML = `
            <i class="fa-solid fa-circle-exclamation
                      text-amber-400 mt-0.5"></i>

            <span class="leading-5">
                ${mensaje}
            </span>
        `;

        document.body.appendChild(
            notificacion
        );

        setTimeout(
            () => {

                notificacion.classList.add(
                    'opacity-0'
                );

                notificacion.style.transition =
                    'opacity 200ms ease';

                setTimeout(
                    () => {
                        notificacion.remove();
                    },
                    200
                );

            },
            1000
        );

    }

    function abrirModalNuevoInventario() {

        const modal =
            document.getElementById(
                'modal-nuevo-inventario'
            );

        if (!modal) {
            return;
        }

        modal.classList.remove('hidden');
        modal.classList.add('flex');

        cargarProveedoresNuevoInventario();

        setTimeout(
            function () {

                document
                    .getElementById(
                        'inventario-nombre'
                    )
                    ?.focus();

            },
            50
        );

    }




    function cerrarModalNuevoInventario() {

        const modal = document.getElementById(
            'modal-nuevo-inventario'
        );

        if (!modal) return;

        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }

    // =========================================================
    // BUSCADOR DE PROVEEDORES — CREAR LISTA
    // =========================================================

    let proveedoresNuevoInventario = [];
    let indiceProveedorNuevoInventario = -1;


    // Cargar proveedores una sola vez.
    async function cargarProveedoresNuevoInventario() {

        if (
            Array.isArray(proveedoresNuevoInventario) &&
            proveedoresNuevoInventario.length
        ) {
            renderizarProveedoresNuevoInventario(
                proveedoresNuevoInventario
            );

            return;
        }

        try {

            const response =
                await fetch(
                    '/api/proveedores'
                );

            if (!response.ok) {
                throw new Error(
                    'No se pudieron cargar los proveedores.'
                );
            }

            const proveedores =
                await response.json();

            proveedoresNuevoInventario =
                Array.isArray(proveedores)
                    ? proveedores
                    : [];

            renderizarProveedoresNuevoInventario(
                proveedoresNuevoInventario
            );

        } catch (error) {

            console.error(
                'Error cargando proveedores:',
                error
            );

            if (
                typeof mostrarNotificacion ===
                'function'
            ) {
                mostrarNotificacion(
                    'No se pudieron cargar los proveedores.'
                );
            }

        }

    }


    // Normalizar texto para que la búsqueda
    // ignore mayúsculas y acentos.
    function normalizarProveedorNuevoInventario(
        texto
    ) {

        return String(
            texto || ''
        )
            .normalize('NFD')
            .replace(
                /[\u0300-\u036f]/g,
                ''
            )
            .toLowerCase()
            .trim();

    }


    // Renderizar las opciones del proveedor.
    function renderizarProveedoresNuevoInventario(
        proveedores
    ) {

        const dropdown =
            document.getElementById(
                'opciones-proveedor-nuevo-inventario'
            );

        if (!dropdown) {
            return;
        }

        dropdown.innerHTML = '';

        proveedores.forEach(
            function (proveedor) {

                const nombre =
                    String(
                        proveedor?.nombre || ''
                    ).trim();

                if (!nombre) {
                    return;
                }

                const opcion =
                    document.createElement(
                        'div'
                    );

                opcion.className =
                    'opcion-proveedor-nuevo-inventario ' +
                    'px-4 py-2.5 ' +
                    'text-sm text-slate-700 ' +
                    'hover:bg-indigo-50 ' +
                    'hover:text-indigo-600 ' +
                    'cursor-pointer';

                opcion.dataset.nombre =
                    nombre;

                opcion.dataset.id =
                    proveedor.id || '';

                opcion.textContent =
                    nombre;

                opcion.addEventListener(
                    'click',
                    function () {

                        seleccionarProveedorNuevoInventario(
                            nombre
                        );

                    }
                );

                dropdown.appendChild(
                    opcion
                );

            }
        );

    }


    // Mostrar proveedores.
    function mostrarOpcionesProveedorNuevoInventario() {

        const input =
            document.getElementById(
                'inventario-nombre'
            );

        const dropdown =
            document.getElementById(
                'opciones-proveedor-nuevo-inventario'
            );

        if (!input || !dropdown) {
            return;
        }

        dropdown.classList.remove(
            'hidden'
        );

        filtrarProveedoresNuevoInventario();

    }


    // Filtrar mientras el usuario escribe.
    function filtrarProveedoresNuevoInventario() {

        const input =
            document.getElementById(
                'inventario-nombre'
            );

        const dropdown =
            document.getElementById(
                'opciones-proveedor-nuevo-inventario'
            );

        if (!input || !dropdown) {
            return;
        }

        const filtro =
            normalizarProveedorNuevoInventario(
                input.value
            );

        const opciones =
            dropdown.querySelectorAll(
                '.opcion-proveedor-nuevo-inventario'
            );

        indiceProveedorNuevoInventario = -1;

        // Limpiar el resaltado anterior al cambiar el filtro.
        dropdown
            .querySelectorAll(
                '.opcion-proveedor-nuevo-inventario'
            )
            .forEach(
                function (opcion) {

                    opcion.classList.remove(
                        'bg-indigo-100',
                        'text-indigo-700'
                    );

                }
            );

        opciones.forEach(
            function (opcion) {

                const nombre =
                    normalizarProveedorNuevoInventario(
                        opcion.dataset.nombre
                    );

                opcion.classList.toggle(
                    'hidden',
                    !nombre.includes(filtro)
                );

            }
        );

        dropdown.classList.remove(
            'hidden'
        );

    }


    function resaltarProveedorNuevoInventario() {

        const dropdown =
            document.getElementById(
                'opciones-proveedor-nuevo-inventario'
            );

        if (!dropdown) {
            return;
        }

        const opciones =
            Array.from(
                dropdown.querySelectorAll(
                    '.opcion-proveedor-nuevo-inventario'
                )
            ).filter(
                function (opcion) {
                    return !opcion.classList.contains(
                        'hidden'
                    );
                }
            );

        // Quitar resaltado anterior.
        opciones.forEach(
            function (opcion) {

                opcion.classList.remove(
                    'bg-indigo-100',
                    'text-indigo-700'
                );

            }
        );

        if (
            indiceProveedorNuevoInventario < 0
            || !opciones.length
        ) {
            return;
        }

        const opcion =
            opciones[
            indiceProveedorNuevoInventario
            ];

        if (!opcion) {
            return;
        }

        opcion.classList.add(
            'bg-indigo-100',
            'text-indigo-700'
        );

        // Mantener visible la opción seleccionada
        // cuando la lista tiene desplazamiento.
        opcion.scrollIntoView({
            block: 'nearest'
        });

    }


    function manejarTecladoProveedorNuevoInventario(
        e
    ) {

        const dropdown =
            document.getElementById(
                'opciones-proveedor-nuevo-inventario'
            );

        const input =
            document.getElementById(
                'inventario-nombre'
            );

        if (!dropdown || !input) {
            return;
        }

        const opciones =
            Array.from(
                dropdown.querySelectorAll(
                    '.opcion-proveedor-nuevo-inventario'
                )
            ).filter(
                function (opcion) {
                    return !opcion.classList.contains(
                        'hidden'
                    );
                }
            );

        if (!opciones.length) {
            return;
        }

        // Flecha abajo.
        if (e.key === 'ArrowDown') {

            e.preventDefault();

            dropdown.classList.remove(
                'hidden'
            );

            indiceProveedorNuevoInventario++;

            if (
                indiceProveedorNuevoInventario
                >= opciones.length
            ) {
                indiceProveedorNuevoInventario = 0;
            }

            resaltarProveedorNuevoInventario();

            return;
        }

        // Flecha arriba.
        if (e.key === 'ArrowUp') {

            e.preventDefault();

            dropdown.classList.remove(
                'hidden'
            );

            indiceProveedorNuevoInventario--;

            if (
                indiceProveedorNuevoInventario < 0
            ) {
                indiceProveedorNuevoInventario =
                    opciones.length - 1;
            }

            resaltarProveedorNuevoInventario();

            return;
        }

        // Enter selecciona el proveedor resaltado.
        if (e.key === 'Enter') {

            if (
                indiceProveedorNuevoInventario < 0
                || !opciones[
                indiceProveedorNuevoInventario
                ]
            ) {
                return;
            }

            e.preventDefault();

            const opcion =
                opciones[
                indiceProveedorNuevoInventario
                ];

            seleccionarProveedorNuevoInventario(
                opcion.dataset.nombre || ''
            );

        }

    }


    // Seleccionar un proveedor real.
    // Desde aquí el usuario ya no puede escribir
    // un nombre arbitrario.
    function seleccionarProveedorNuevoInventario(
        nombre
    ) {

        const input =
            document.getElementById(
                'inventario-nombre'
            );

        const dropdown =
            document.getElementById(
                'opciones-proveedor-nuevo-inventario'
            );

        const btnLimpiar =
            document.getElementById(
                'btn-limpiar-proveedor-nuevo-inventario'
            );

        if (!input) {
            return;
        }

        input.value =
            nombre || '';

        input.readOnly =
            !!nombre;

        input.classList.toggle(
            'bg-slate-100',
            !!nombre
        );

        input.classList.toggle(
            'cursor-default',
            !!nombre
        );

        if (btnLimpiar) {

            btnLimpiar.classList.toggle(
                'hidden',
                !nombre
            );

        }

        dropdown?.classList.add(
            'hidden'
        );

        indiceProveedorNuevoInventario = -1;

    }


    // Limpiar selección y volver a permitir búsqueda.
    function limpiarProveedorNuevoInventario() {

        seleccionarProveedorNuevoInventario(
            ''
        );

        const input =
            document.getElementById(
                'inventario-nombre'
            );

        input?.focus();

        mostrarOpcionesProveedorNuevoInventario();

    }


    // Eventos del buscador.
    document
        .getElementById(
            'inventario-nombre'
        )
        ?.addEventListener(
            'input',
            filtrarProveedoresNuevoInventario
        );

    document
        .getElementById(
            'inventario-nombre'
        )
        ?.addEventListener(
            'keydown',
            manejarTecladoProveedorNuevoInventario
        );

    document
        .getElementById(
            'inventario-nombre'
        )
        ?.addEventListener(
            'focus',
            mostrarOpcionesProveedorNuevoInventario
        );

    document
        .getElementById(
            'btn-limpiar-proveedor-nuevo-inventario'
        )
        ?.addEventListener(
            'click',
            limpiarProveedorNuevoInventario
        );

    document.addEventListener(
        'click',
        function (e) {

            const combo =
                document.getElementById(
                    'combo-proveedor-nuevo-inventario'
                );

            const dropdown =
                document.getElementById(
                    'opciones-proveedor-nuevo-inventario'
                );

            if (
                !combo ||
                !dropdown
            ) {
                return;
            }

            if (
                !combo.contains(
                    e.target
                )
            ) {
                dropdown.classList.add(
                    'hidden'
                );
            }

        }
    );


    document.addEventListener(
        'keydown',
        function (e) {

            if (e.key !== 'Escape') {
                return;
            }

            const modal = document.getElementById(
                'modal-nuevo-inventario'
            );

            if (
                modal &&
                !modal.classList.contains('hidden')
            ) {
                cerrarModalNuevoInventario();
            }

        }
    );


    document.getElementById(
        'modal-nuevo-inventario'
    )?.addEventListener(
        'click',
        function (e) {

            if (e.target === this) {
                cerrarModalNuevoInventario();
            }

        }
    );

