

    // =========================================================
    // PROTECCIÓN CONTRA DOBLE ENVÍO — CREAR INVENTARIO
    // =========================================================

    (function () {

        const formulario =
            document.getElementById(
                'form-nuevo-inventario'
            );

        const boton =
            document.getElementById(
                'btn-crear-inventario'
            );

        const campoClave =
            document.getElementById(
                'clave-creacion-inventario'
            );

        if (
            !formulario ||
            !boton ||
            !campoClave
        ) {
            return;
        }


        /* Genera una clave UUID v4 válida para crear el inventario. */
        function generarClaveCreacion() {

            // Usar el generador UUID nativo si está disponible.
            if (
                window.crypto &&
                typeof window.crypto.randomUUID === 'function'
            ) {
                return window.crypto.randomUUID();
            }

            // Comprobar que el navegador permite generar bytes aleatorios.
            if (
                !window.crypto ||
                typeof window.crypto.getRandomValues !== 'function'
            ) {
                return '';
            }

            // Crear 16 bytes aleatorios para el UUID.
            const bytes = new Uint8Array(16);
            window.crypto.getRandomValues(bytes);

            // Establecer la versión 4 y la variante del UUID.
            bytes[6] = (bytes[6] & 0x0f) | 0x40;
            bytes[8] = (bytes[8] & 0x3f) | 0x80;

            // Convertir los bytes a texto hexadecimal.
            const hex = Array.from(
                bytes,
                byte => byte.toString(16).padStart(2, '0')
            ).join('');

            // Devolver el UUID con el formato esperado por PostgreSQL.
            return [
                hex.slice(0, 8),
                hex.slice(8, 12),
                hex.slice(12, 16),
                hex.slice(16, 20),
                hex.slice(20)
            ].join('-');
        }



        /* Generar la clave al cargar el formulario. */
        campoClave.value = generarClaveCreacion();

        /* No permitir el envío si no se pudo generar una clave válida. */
        if (!campoClave.value) {
            boton.disabled = true;
            boton.title = 'No se pudo generar la clave de creación. Recarga la página.';
        }


        formulario.addEventListener(
            'submit',
            function (e) {

                /*
                 * Si ya se está enviando,
                 * impedir cualquier segundo envío.
                 */
                if (
                    formulario.dataset.enviando === '1'
                ) {
                    e.preventDefault();
                    return;
                }

                /*
                 * Marcar inmediatamente como enviado.
                 */
                formulario.dataset.enviando = '1';

                /*
                 * Deshabilitar botón.
                 */
                boton.disabled = true;

                boton.classList.add(
                    'opacity-60',
                    'cursor-not-allowed'
                );

                /*
                 * Cambiar visualmente el contenido
                 * para informar al usuario.
                 */
                boton.innerHTML = `
                <i class="fa-solid fa-spinner
                          fa-spin mr-1"></i>
                Creando...
            `;

            }
        );

    })();

    // =========================================================
    // ORDENAMIENTO DE LA LISTA DE INVENTARIOS
    // =========================================================

    let columnaOrdenInventarios = null;
    let direccionOrdenInventarios = 'asc';


    function ordenarInventarios(columna) {

        const tabla =
            document.querySelector(
                'table'
            );

        if (!tabla) {
            return;
        }


        const tbody =
            tabla.querySelector('tbody');

        if (!tbody) {
            return;
        }


        // Si se vuelve a pulsar la misma columna,
        // invertimos el sentido del orden.
        if (
            columnaOrdenInventarios === columna
        ) {

            direccionOrdenInventarios =
                direccionOrdenInventarios === 'asc'
                    ? 'desc'
                    : 'asc';

        } else {

            columnaOrdenInventarios = columna;
            direccionOrdenInventarios = 'asc';

        }


        const filas =
            Array.from(
                tbody.querySelectorAll('tr')
            );


        filas.sort(
            function (filaA, filaB) {

                const valorA =
                    obtenerValorOrdenInventario(
                        filaA,
                        columna
                    );

                const valorB =
                    obtenerValorOrdenInventario(
                        filaB,
                        columna
                    );


                let resultado = 0;


                // -------------------------------------------------
                // FECHA
                // -------------------------------------------------

                if (columna === 'fecha') {

                    const fechaA =
                        obtenerFechaInventario(
                            filaA
                        );

                    const fechaB =
                        obtenerFechaInventario(
                            filaB
                        );

                    resultado =
                        fechaA - fechaB;

                }

                // -------------------------------------------------
                // TEXTO
                // -------------------------------------------------

                else {

                    resultado =
                        valorA.localeCompare(
                            valorB,
                            'es',
                            {
                                numeric: true,
                                sensitivity: 'base'
                            }
                        );
                }


                return (
                    direccionOrdenInventarios === 'asc'
                        ? resultado
                        : -resultado
                );
            }
        );


        // Reinsertar las filas en el nuevo orden.
        filas.forEach(
            function (fila) {
                tbody.appendChild(fila);
            }
        );


        actualizarIndicadoresOrdenInventarios(
            columna
        );
    }


    function obtenerValorOrdenInventario(
        fila,
        columna
    ) {

        if (!fila) {
            return '';
        }


        const celdas =
            fila.querySelectorAll('td');


        switch (columna) {

            case 'nombre':
                return (
                    celdas[0]?.textContent || ''
                ).trim();


            case 'tienda':
                return (
                    celdas[1]?.textContent || ''
                ).trim();


            case 'realizado_por':
                return (
                    celdas[2]?.textContent || ''
                ).trim();


            case 'fecha':
                return (
                    celdas[3]?.dataset.fecha || ''
                ).trim();


            case 'estado':
                return (
                    celdas[4]?.textContent || ''
                ).trim();


            default:
                return '';
        }
    }


    function obtenerFechaInventario(fila) {

        const celdaFecha =
            fila.querySelector(
                'td[data-fecha]'
            );

        if (!celdaFecha) {
            return 0;
        }


        const fecha =
            new Date(
                celdaFecha.dataset.fecha
            );


        const tiempo =
            fecha.getTime();


        return Number.isNaN(tiempo)
            ? 0
            : tiempo;
    }


    function actualizarIndicadoresOrdenInventarios(
        columnaActiva
    ) {

        document
            .querySelectorAll(
                '[data-columna-orden]'
            )
            .forEach(
                function (encabezado) {

                    const indicador =
                        encabezado.querySelector(
                            '.indicador-orden'
                        );

                    if (!indicador) {
                        return;
                    }


                    const columna =
                        encabezado.dataset.columnaOrden;


                    if (
                        columna !==
                        columnaActiva
                    ) {

                        indicador.textContent = '↕';

                        indicador.className =
                            'indicador-orden text-slate-400';

                        return;
                    }


                    indicador.textContent =
                        direccionOrdenInventarios === 'asc'
                            ? '↑'
                            : '↓';

                    indicador.className =
                        'indicador-orden text-white font-bold';
                }
            );
    }

