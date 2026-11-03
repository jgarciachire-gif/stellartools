
    (function () {
        const menusHeader = document.getElementById('menus-header-inventarios');
        const menuArchivo = document.getElementById('menu-archivo-inventarios');
        const btnArchivo = document.getElementById('btn-menu-archivo-inventarios');
        const opcionesArchivo = document.getElementById('opciones-archivo-inventarios');
        const btnNuevaLista = document.getElementById('btn-nueva-lista-inventarios');
        const menu = document.getElementById('menu-seleccion-inventarios');
        const btnMenu = document.getElementById('btn-menu-seleccion-inventarios');
        const opciones = document.getElementById('opciones-seleccion-inventarios');
        const btnActivar = document.getElementById('btn-activar-seleccion-inventarios');
        const btnCancelar = document.getElementById('btn-cancelar-seleccion-inventarios');
        let seleccionarPagina = document.getElementById('seleccionar-pagina-inventarios');
        const btnEliminar = document.getElementById('btn-eliminar-seleccion-inventarios');

        if (
            !menusHeader ||
            !menuArchivo ||
            !btnArchivo ||
            !opcionesArchivo ||
            !btnNuevaLista
        ) {
            return;
        }

        let modoSeleccion = false;

        function cerrarMenusInventarios() {
            opcionesArchivo.classList.add('hidden');
            btnArchivo.setAttribute('aria-expanded', 'false');
            opciones?.classList.add('hidden');
            btnMenu?.setAttribute('aria-expanded', 'false');
        }

        btnArchivo.addEventListener('click', function () {
            const abrir = opcionesArchivo.classList.contains('hidden');
            cerrarMenusInventarios();
            opcionesArchivo.classList.toggle('hidden', !abrir);
            btnArchivo.setAttribute('aria-expanded', String(abrir));
        });

        btnNuevaLista.addEventListener('click', function () {
            cerrarMenusInventarios();
            abrirModalNuevoInventario();
        });

        menusHeader.addEventListener('keydown', function (evento) {
            if (evento.key !== 'Escape') return;
            const activo = btnArchivo.getAttribute('aria-expanded') === 'true'
                ? btnArchivo
                : btnMenu?.getAttribute('aria-expanded') === 'true' ? btnMenu : null;
            if (!activo) return;
            evento.preventDefault();
            evento.stopPropagation();
            cerrarMenusInventarios();
            activo.focus();
        });

        menusHeader.addEventListener('focusout', function (evento) {
            if (!menusHeader.contains(evento.relatedTarget)) cerrarMenusInventarios();
        });

        // Cerrar Archivo al pulsar fuera, también para Provisional.
        document.addEventListener('click', function (evento) {
            if (!menusHeader.contains(evento.target)) {
                cerrarMenusInventarios();
            }
        });

        // Administrar Listas solo existe para Normal y Administrador.
        if (
            menu &&
            btnMenu &&
            opciones &&
            btnActivar &&
            btnCancelar &&
            btnEliminar
        ) {


            function obtenerCasillas() {
                return Array.from(document.querySelectorAll('.checkbox-inventario'));
            }

            function actualizarSeleccion() {
                const casillas = obtenerCasillas();
                const marcadas = casillas.filter(c => c.checked);
                const idsMarcados = new Set(marcadas.map(c => c.value));

                // Sincroniza las casillas de escritorio y móvil del mismo documento.
                casillas.forEach(c => {
                    c.checked = idsMarcados.has(c.value);
                });

                const idsUnicos = new Set(marcadas.map(c => c.value));

                btnEliminar.disabled = idsUnicos.size === 0;

                if (seleccionarPagina) {
                    const visibles = Array.from(
                        document.querySelectorAll(
                            'tbody .checkbox-inventario, .md\\:hidden .checkbox-inventario'
                        )
                    );

                    const todasMarcadas = visibles.length > 0 &&
                        visibles.every(c => c.checked);

                    seleccionarPagina.checked = todasMarcadas;
                }
            }



            function cambiarModoSeleccion(activar) {
                modoSeleccion = activar;

                // Mostrar u ocultar la columna completa de selección.
                document.querySelectorAll(
                    '#columna-seleccion-encabezado, .columna-seleccion-inventario'
                ).forEach(celda => {
                    celda.classList.toggle('hidden', !activar);
                });

                // Mostrar u ocultar la barra y las acciones.
                btnActivar.classList.toggle('hidden', activar);
                btnCancelar.classList.toggle('hidden', !activar);
                btnEliminar.classList.toggle('hidden', !activar);

                // Mostrar u ocultar las casillas individuales.
                obtenerCasillas().forEach(casilla => {
                    casilla.classList.toggle('hidden', !activar);
                });

                // Mostrar u ocultar el selector de la cabecera.
                if (seleccionarPagina) {
                    seleccionarPagina.classList.toggle('hidden', !activar);
                }

                const flecha = document.getElementById(
                    'flecha-seleccionar-pagina-inventarios'
                );

                if (flecha) {
                    flecha.classList.toggle('hidden', !activar);
                }

                // Conservar la esquina superior izquierda redondeada.
                const encabezadoSeleccion = document.getElementById(
                    'columna-seleccion-encabezado'
                );
                const encabezadoNombre = document.getElementById(
                    'encabezado-nombre-inventario'
                );

                if (encabezadoSeleccion) {
                    encabezadoSeleccion.classList.toggle('rounded-tl-2xl', activar);
                }

                if (encabezadoNombre) {
                    encabezadoNombre.classList.toggle('rounded-tl-2xl', !activar);
                }

                // Limpiar la selección al salir del modo.
                if (!activar) {
                    obtenerCasillas().forEach(casilla => {
                        casilla.checked = false;
                    });

                    if (seleccionarPagina) {
                        seleccionarPagina.checked = false;
                        seleccionarPagina.indeterminate = false;
                    }
                }

                actualizarSeleccion();

                opciones.classList.add('hidden');
                btnMenu.setAttribute('aria-expanded', 'false');
            }



            btnMenu.addEventListener('click', function (e) {
                e.stopPropagation();
                const abrir = opciones.classList.contains('hidden');
                cerrarMenusInventarios();
                opciones.classList.toggle('hidden', !abrir);
                btnMenu.setAttribute('aria-expanded', String(abrir));
            });

            btnActivar.addEventListener('click', function () {
                cambiarModoSeleccion(true);
            });

            btnCancelar.addEventListener('click', function () {
                cambiarModoSeleccion(false);
            });

            // Reconectar las casillas cuando cambien los resultados.
            window.reconectarSeleccionInventarios = function () {
                seleccionarPagina = document.getElementById(
                    'seleccionar-pagina-inventarios'
                );

                obtenerCasillas().forEach(casilla => {
                    casilla.addEventListener('click', evento => {
                        evento.stopPropagation();
                    });

                    casilla.addEventListener('change', () => {
                        if (!modoSeleccion) {
                            casilla.checked = false;
                            return;
                        }

                        const valor = casilla.value;
                        const marcado = casilla.checked;

                        obtenerCasillas().forEach(otra => {
                            if (otra.value === valor) otra.checked = marcado;
                        });

                        actualizarSeleccion();
                    });
                });

                seleccionarPagina?.addEventListener('change', () => {
                    if (!modoSeleccion) return;

                    obtenerCasillas().forEach(casilla => {
                        casilla.checked = seleccionarPagina.checked;
                    });

                    actualizarSeleccion();
                });

                // Mantener visibles las casillas si la selección está activa.
                if (modoSeleccion) {
                    document.querySelectorAll(
                        '#columna-seleccion-encabezado, .columna-seleccion-inventario'
                    ).forEach(celda => celda.classList.remove('hidden'));

                    obtenerCasillas().forEach(casilla => {
                        casilla.classList.remove('hidden');
                    });

                    seleccionarPagina?.classList.remove('hidden');
                }

                actualizarSeleccion();
            };

            // Conectar los elementos existentes al cargar la página.
            window.reconectarSeleccionInventarios();

            btnEliminar.addEventListener('click', async function () {
                cerrarMenusInventarios();
                // Obtener IDs únicos seleccionados.
                const ids = [
                    ...new Set(
                        obtenerCasillas()
                            .filter(casilla => casilla.checked)
                            .map(casilla => casilla.value)
                    )
                ];

                if (ids.length === 0) {
                    await window.mostrarConfirmacion({
                        tipo: 'warning',
                        titulo: 'Sin inventarios seleccionados',
                        mensaje: 'Selecciona al menos un inventario.',
                        textoAceptar: 'Entendido',
                        textoCancelar: ''
                    });
                    return;
                }

                const confirmar = await window.mostrarConfirmacion({
                    tipo: 'warning',
                    titulo: '¿Eliminar documentos?',
                    mensaje:
                        `Hay ${ids.length} documento(s) seleccionado(s) para eliminar.\n\n` +
                        'Esta acción no se puede deshacer.',
                    textoAceptar: 'Eliminar',
                    textoCancelar: 'Cancelar'
                });

                if (!confirmar) return;

                const textoOriginal = btnEliminar.innerHTML;

                btnEliminar.disabled = true;
                btnEliminar.textContent = 'Eliminando...';

                try {
                    const response = await fetch(
                        '/api/inventarios/eliminar-masivo',
                        {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Accept': 'application/json'
                            },
                            body: JSON.stringify({ ids })
                        }
                    );

                    const data = await response.json().catch(() => ({}));

                    if (!response.ok || !data.ok) {
                        // Reflejar eliminaciones parciales, si el servidor las reporta.
                        if (
                            Array.isArray(data.eliminados) &&
                            data.eliminados.length > 0
                        ) {
                            await window.mostrarConfirmacion({
                                tipo: 'warning',
                                titulo: 'Eliminación incompleta',
                                mensaje:
                                    (data.error || 'La eliminación no se completó.') +
                                    '\nLa lista se actualizará para reflejar los cambios.',
                                textoAceptar: 'Entendido',
                                textoCancelar: ''
                            });

                            window.location.reload();
                            return;
                        }

                        throw new Error(
                            data.error || 'No se pudieron eliminar los inventarios.'
                        );
                    }

                    await window.mostrarConfirmacion({
                        tipo: 'success',
                        titulo: 'Eliminación completada',
                        mensaje:
                            `Se eliminaron ${data.cantidad} inventario(s) correctamente.`,
                        textoAceptar: 'Entendido',
                        textoCancelar: ''
                    });

                    window.location.reload();

                } catch (error) {
                    console.error('Error en eliminación múltiple:', error);

                    await window.mostrarConfirmacion({
                        tipo: 'error',
                        titulo: 'No se pudo eliminar',
                        mensaje:
                            error.message ||
                            'Ocurrió un error al eliminar los inventarios.',
                        textoAceptar: 'Entendido',
                        textoCancelar: ''
                    });

                } finally {
                    btnEliminar.disabled = false;
                    btnEliminar.innerHTML = textoOriginal;
                }
            });

        }

    })();
