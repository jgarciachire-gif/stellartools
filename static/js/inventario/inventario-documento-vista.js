
        // =========================================================
        // FORMATO DE FECHAS DEL INVENTARIO
        // =========================================================

        document.addEventListener(
            'DOMContentLoaded',
            function () {

                document
                    .querySelectorAll(
                        '[data-fecha-inventario]'
                    )
                    .forEach(function (elemento) {

                        const fechaISO =
                            elemento.dataset.fechaInventario;

                        if (!fechaISO) {
                            return;
                        }

                        const fecha =
                            new Date(fechaISO);

                        if (
                            Number.isNaN(
                                fecha.getTime()
                            )
                        ) {
                            return;
                        }

                        const dia =
                            String(
                                fecha.getDate()
                            ).padStart(2, '0');

                        const mes =
                            String(
                                fecha.getMonth() + 1
                            ).padStart(2, '0');

                        const año =
                            fecha.getFullYear();

                        let horas =
                            fecha.getHours();

                        const minutos =
                            String(
                                fecha.getMinutes()
                            ).padStart(2, '0');

                        const periodo =
                            horas >= 12
                                ? 'PM'
                                : 'AM';

                        horas =
                            horas % 12 || 12;

                        const horasFormateadas =
                            String(horas)
                                .padStart(2, '0');

                        elemento.textContent =
                            `${dia}-${mes}-${año} ` +
                            `${horasFormateadas}:${minutos} ` +
                            `${periodo}`;
                    });

            }
        );

        // =========================================================
        // ORDENAMIENTO DE LA TABLA DE INVENTARIO
        // =========================================================

        let columnaOrdenInventarioNuevo = null;
        let direccionOrdenInventarioNuevo = 'asc';


        function ordenarInventarioNuevo(columna) {

            const tbody =
                document.getElementById(
                    'filas-tabla-inventario'
                );

            if (!tbody) {
                return;
            }


            // Si se pulsa nuevamente la misma columna,
            // invertimos el sentido del orden.
            if (
                columnaOrdenInventarioNuevo === columna
            ) {

                direccionOrdenInventarioNuevo =
                    direccionOrdenInventarioNuevo === 'asc'
                        ? 'desc'
                        : 'asc';

            } else {

                columnaOrdenInventarioNuevo = columna;
                direccionOrdenInventarioNuevo = 'asc';

            }


            const filas =
                Array.from(
                    tbody.querySelectorAll('tr')
                );


            filas.sort(
                function (filaA, filaB) {

                    const valorA =
                        obtenerValorOrdenInventarioNuevo(
                            filaA,
                            columna
                        );

                    const valorB =
                        obtenerValorOrdenInventarioNuevo(
                            filaB,
                            columna
                        );


                    let resultado = 0;


                    // -------------------------------------------------
                    // CANTIDAD
                    // -------------------------------------------------

                    if (columna === 'cantidad') {

                        const numeroA =
                            convertirCantidadOrdenInventario(
                                valorA
                            );

                        const numeroB =
                            convertirCantidadOrdenInventario(
                                valorB
                            );

                        resultado =
                            numeroA - numeroB;

                    }

                    // -------------------------------------------------
                    // CÓDIGO Y DESCRIPCIÓN
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
                        direccionOrdenInventarioNuevo === 'asc'
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


            actualizarIndicadoresOrdenInventarioNuevo(
                columna
            );
        }


        function obtenerValorOrdenInventarioNuevo(
            fila,
            columna
        ) {

            if (!fila) {
                return '';
            }


            const inputCodigo =
                fila.querySelector('.inp-codigo');

            const inputDescripcion =
                fila.querySelector('.inp-desc');

            const inputCantidad =
                fila.querySelector('.inp-cantidad');


            switch (columna) {

                case 'codigo':
                    return (
                        inputCodigo?.value || ''
                    ).trim();


                case 'descripcion':
                    return (
                        inputDescripcion?.value || ''
                    ).trim();


                case 'cantidad':
                    return (
                        inputCantidad?.value || ''
                    ).trim();


                default:
                    return '';
            }
        }


        function convertirCantidadOrdenInventario(
            valor
        ) {

            if (
                valor === null ||
                valor === undefined ||
                String(valor).trim() === ''
            ) {
                return 0;
            }


            const numero =
                Number(
                    String(valor)
                        .trim()
                        .replace(',', '.')
                );


            return Number.isFinite(numero)
                ? numero
                : 0;
        }


        function actualizarIndicadoresOrdenInventarioNuevo(
            columnaActiva
        ) {

            document
                .querySelectorAll(
                    '[data-columna-orden-inventario]'
                )
                .forEach(
                    function (encabezado) {

                        const indicador =
                            encabezado.querySelector(
                                '.indicador-orden-inventario'
                            );

                        if (!indicador) {
                            return;
                        }


                        const columna =
                            encabezado.dataset
                                .columnaOrdenInventario;


                        if (
                            columna !==
                            columnaActiva
                        ) {

                            indicador.textContent = '↕';

                            indicador.className =
                                'indicador-orden-inventario text-slate-400';

                            return;
                        }


                        indicador.textContent =
                            direccionOrdenInventarioNuevo === 'asc'
                                ? '↑'
                                : '↓';

                        indicador.className =
                            'indicador-orden-inventario text-white font-bold';
                    }
                );
        }
    