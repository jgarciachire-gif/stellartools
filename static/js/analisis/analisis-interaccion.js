(function () {
    'use strict';

    const CONFIG_TABLAS = {
        analisis: {
            tabla: '#tabla-analisis',
            tbody: '#filas-tabla-analisis',

            columnas: [
                'codigo',
                'desc',
                'pre',
                'inv-emp',
                'emp',
                'uni',
                'costo',
                'subtotal'
            ]
        },

        inventario: {
            tabla: '#tabla-inventario',
            tbody: '#filas-tabla-inventario',

            columnas: [
                'codigo',
                'desc',
                'cantidad'
            ]
        }
    };


    function obtenerConfiguracionTabla() {

        if (
            document.querySelector(
                CONFIG_TABLAS.inventario.tabla
            )
        ) {
            return CONFIG_TABLAS.inventario;
        }

        return CONFIG_TABLAS.analisis;
    }

    function obtenerSelectorTbodyActual() {

        return obtenerConfiguracionTabla().tbody;

    }

    const CLASE_SELECCION = 'excel-celda-seleccionada';
    const CLASE_ACTIVA = 'excel-celda-activa';
    const CLASE_COPIADA = 'excel-celda-copiada';

    function instalarEstilosExcel() {
        if (document.getElementById('estilos-interaccion-excel')) {
            return;
        }

        const style = document.createElement('style');

        style.id = 'estilos-interaccion-excel';

        style.textContent = `
        /*
         * Estado normal:
         * el mouse usa cursor-default.
         */
        #tabla-analisis tbody td,
        #tabla-analisis tbody td input,
        #tabla-analisis tbody td .txt-subtotal,

        #tabla-inventario tbody td,
        #tabla-inventario tbody td input {
            cursor: default !important;
        }

        /*
         * Rango seleccionado:
         * azul muy suave + borde azul fino.
         */

        /* ============================================================
        * RANGO SELECCIONADO
        * ============================================================ */

        #tabla-analisis tbody td.excel-celda-seleccionada,
        #tabla-inventario tbody td.excel-celda-seleccionada {
            background-color: rgba(59, 130, 246, 0.07) !important;

            box-shadow:
                inset 0 0 0 1px rgba(59, 130, 246, 0.55);
        }

        /*
        * El input no debe tapar el sombreado del TD.
        * Esto corrige especialmente:
        * - Código
        * - Descripción
        */
        #tabla-analisis tbody td.excel-celda-seleccionada input,
        #tabla-inventario tbody td.excel-celda-seleccionada input {
            background-color: transparent !important;
        }


        /* ============================================================
        * CELDA ACTIVA
        * ============================================================ */

        #tabla-analisis tbody td.excel-celda-activa,
        #tabla-inventario tbody td.excel-celda-activa {
            background-color: rgba(59, 130, 246, 0.13) !important;

            box-shadow:
                inset 0 0 0 2px rgba(37, 99, 235, 0.90);
        }

        /*
        * La celda activa también debe transmitir su fondo
        * al input interno.
        */
        #tabla-analisis tbody td.excel-celda-activa input,
        #tabla-inventario tbody td.excel-celda-activa input {
            background-color: transparent !important;
        }

        /*
         * Mientras realmente se edita:
         * el cursor vuelve a ser de texto.
         */
        #tabla-analisis tbody td.excel-celda-en-edicion input,
        #tabla-inventario tbody td.excel-celda-en-edicion input {
            cursor: text !important;
        }

        /*
         * Código bloqueado:
         * continúa mostrando cursor normal.
         */
        #tabla-analisis tbody td .inp-codigo[readonly] {
            cursor: default !important;
        }
    `;

        document.head.appendChild(style);
    }

    instalarEstilosExcel();


    let celdasSeleccionadasAnalisis = [];
    let celdaInicio = null;
    let celdaActiva = null;

    let isArrastrando = false;
    let estaEditando = false;

    // ============================================================
    // UTILIDADES
    // ============================================================

    function obtenerTbody() {

        const config =
            obtenerConfiguracionTabla();

        return document.querySelector(
            config.tbody
        );
    }

    function obtenerFilas() {
        const tbody = obtenerTbody();

        if (!tbody) {
            return [];
        }

        return Array.from(tbody.children)
            .filter(tr => tr.tagName === 'TR');
    }

    function obtenerIndiceFila(td) {
        const tr = td?.closest('tr');

        if (!tr) {
            return -1;
        }

        return obtenerFilas().indexOf(tr);
    }

    function obtenerIndiceColumna(td) {
        if (!td) {
            return -1;
        }

        const tr = td.closest('tr');

        if (!tr) {
            return -1;
        }

        const celdas = Array.from(tr.children);

        const indice = celdas.indexOf(td);

        /*
         * La última columna es el botón de eliminar.
         * Nunca forma parte de la cuadrícula.
         */
        const config =
            obtenerConfiguracionTabla();

        return indice >= 0 &&
            indice < config.columnas.length
            ? indice
            : -1;
    }

    function obtenerCelda(fila, columna) {
        const filas = obtenerFilas();
        const tr = filas[fila];

        if (!tr) {
            return null;
        }

        return tr.children[columna] || null;
    }

    function obtenerInputCelda(td) {
        return td?.querySelector('input') || null;
    }

    function obtenerValorCelda(td) {
        if (!td) {
            return '';
        }

        const input = obtenerInputCelda(td);

        if (input) {
            return input.value ?? '';
        }

        const subtotal = td.querySelector('.txt-subtotal');

        if (subtotal) {
            return subtotal.textContent.trim();
        }

        return td.textContent.trim();
    }

    function obtenerCampo(td) {
        if (!td) {
            return null;
        }

        const input = obtenerInputCelda(td);

        if (!input) {
            return null;
        }

        if (input.classList.contains('inp-codigo')) {
            return 'codigo';
        }

        if (input.classList.contains('inp-pre')) {
            return 'pre';
        }

        if (input.classList.contains('inp-inv-emp')) {
            return 'inv-emp';
        }

        if (input.classList.contains('inp-emp')) {
            return 'emp';
        }

        if (input.classList.contains('inp-uni')) {
            return 'uni';
        }

        if (input.classList.contains('inp-costo')) {
            return 'costo';
        }

        if (input.classList.contains('inp-desc')) {
            return 'desc';
        }

        if (input.classList.contains('inp-cantidad')) {
            return 'cantidad';
        }

        return null;
    }

    function esCeldaEditable(td) {
        const input = obtenerInputCelda(td);

        if (!input) {
            return false;
        }

        if (input.readOnly) {
            return false;
        }

        return [
            'inp-codigo',
            'inp-pre',
            'inp-inv-emp',
            'inp-emp',
            'inp-uni',
            'inp-costo',
            'inp-cantidad'
        ].some(
            clase => input.classList.contains(clase)
        );
    }

    // ============================================================
    // ESTILO DE SELECCIÓN
    // ============================================================

    function limpiarClasesCelda(td) {
        if (!td) {
            return;
        }

        td.classList.remove(
            CLASE_SELECCION,
            CLASE_ACTIVA
        );
    }

    function limpiarSeleccionVisual() {

        const config =
            obtenerConfiguracionTabla();

        document
            .querySelectorAll(
                `${config.tbody} td.${CLASE_SELECCION},
             ${config.tbody} td.${CLASE_ACTIVA},
             ${config.tbody} td.${CLASE_COPIADA}`
            )
            .forEach(td => {

                limpiarClasesCelda(td);

                td.classList.remove(
                    CLASE_COPIADA
                );

            });
    }

    function limpiarResaltadoCopiado() {

        const config =
            obtenerConfiguracionTabla();

        document
            .querySelectorAll(
                `${config.tbody} td.${CLASE_COPIADA}`
            )
            .forEach(td => {

                td.classList.remove(
                    CLASE_COPIADA
                );

            });
    }

    function resaltarSeleccionCopiada() {
        limpiarResaltadoCopiado();

        celdasSeleccionadasAnalisis.forEach(td => {
            if (td) {
                td.classList.add(CLASE_COPIADA);
            }
        });
    }

    function desseleccionarCeldas() {
        limpiarSeleccionVisual();

        celdasSeleccionadasAnalisis = [];
        celdaInicio = null;
        celdaActiva = null;

        estaEditando = false;
    }

    function aplicarSeleccionVisual(celdas) {
        limpiarSeleccionVisual();

        celdasSeleccionadasAnalisis = [];

        celdas.forEach(td => {
            if (!td) {
                return;
            }

            td.classList.add(CLASE_SELECCION);

            celdasSeleccionadasAnalisis.push(td);
        });

        if (celdaActiva) {
            celdaActiva.classList.add(CLASE_ACTIVA);
        }
    }

    // ============================================================
    // SELECCIÓN RECTANGULAR
    // ============================================================

    function actualizarSeleccionRango(celdaActual) {
        if (!celdaActual) {
            return;
        }

        const filaInicio = obtenerIndiceFila(celdaInicio);
        const filaFin = obtenerIndiceFila(celdaActual);

        const colInicio = obtenerIndiceColumna(celdaInicio);
        const colFin = obtenerIndiceColumna(celdaActual);

        if (
            filaInicio < 0 ||
            filaFin < 0 ||
            colInicio < 0 ||
            colFin < 0
        ) {
            return;
        }

        const filaMin = Math.min(filaInicio, filaFin);
        const filaMax = Math.max(filaInicio, filaFin);

        const colMin = Math.min(colInicio, colFin);
        const colMax = Math.max(colInicio, colFin);

        const seleccion = [];

        for (let fila = filaMin; fila <= filaMax; fila++) {
            for (let columna = colMin; columna <= colMax; columna++) {
                const td = obtenerCelda(fila, columna);

                if (td) {
                    seleccion.push(td);
                }
            }
        }

        if (!celdaActiva) {
            celdaActiva = celdaInicio || celdaActual;
        }

        aplicarSeleccionVisual(seleccion);
    }

    // ============================================================
    // CLICK / ARRASTRE
    // ============================================================

    function iniciarArrastre(inputOtd, e = null) {
        const td = inputOtd?.closest
            ? inputOtd.closest('td')
            : inputOtd;

        if (!td) {
            return;
        }

        if (obtenerIndiceColumna(td) < 0) {
            return;
        }

        /*
         * Evita que un simple clic coloque el cursor
         * dentro del input.
         *
         * El usuario primero selecciona la celda.
         */
        e?.preventDefault?.();

        const shift = e?.shiftKey === true;

        if (shift && celdaInicio) {
            actualizarSeleccionRango(td);
        } else {
            celdaInicio = td;
            celdaActiva = td;

            actualizarSeleccionRango(td);
        }

        isArrastrando = true;

        window.getSelection()?.removeAllRanges();
    }

    function arrastrarSobreCelda(inputOtd) {
        if (!isArrastrando || !celdaInicio) {
            return;
        }

        const td = inputOtd?.closest
            ? inputOtd.closest('td')
            : inputOtd;

        if (!td) {
            return;
        }

        if (obtenerIndiceColumna(td) < 0) {
            return;
        }

        window.getSelection()?.removeAllRanges();

        actualizarSeleccionRango(td);
    }

    // ============================================================
    // EDICIÓN
    // ============================================================


    function seleccionarContenidoInput(input) {
        if (!input) {
            return;
        }

        const tiposSeleccionables = [
            'text',
            'search',
            'url',
            'tel',
            'password'
        ];

        const tipo = String(input.type || 'text')
            .toLowerCase();

        if (!tiposSeleccionables.includes(tipo)) {
            return;
        }

        try {
            input.select();
        } catch (_) {
            // Algunos navegadores pueden impedir la selección.
        }
    }

    function iniciarEdicion(input) {
        if (!input || input.readOnly) {
            return;
        }

        const td = input.closest('td');

        if (td) {
            celdaActiva = td;

            if (!celdaInicio) {
                celdaInicio = td;
            }

            actualizarSeleccionRango(td);

            td.classList.add('excel-celda-en-edicion');
        }

        // Guardar el valor antes de modificarlo.
        input.dataset.valorOriginal = input.value;

        estaEditando = true;

        input.focus();

        // Solo selecciona cuando el tipo de input lo permite.
        setTimeout(() => {
            seleccionarContenidoInput(input);
        }, 0);
    }

    function entrarEnEdicion(
        td,
        reemplazar = false,
        primerCaracter = ''
    ) {
        const input = obtenerInputCelda(td);

        if (!input || input.readOnly) {
            return false;
        }

        // Guardar el valor original para permitir Escape.
        input.dataset.valorOriginal = input.value;

        celdaActiva = td;
        estaEditando = true;

        td.classList.add('excel-celda-en-edicion');

        input.focus();

        if (reemplazar) {
            /*
             * Cuando se escribe directamente sobre una celda
             * seleccionada, el primer carácter reemplaza todo
             * el contenido anterior.
             */
            input.value = primerCaracter;

            /*
             * El valor fue asignado por JavaScript, por lo que
             * el navegador no dispara automáticamente "input".
             *
             * Lo notificamos para que se ejecute inmediatamente
             * el cálculo correspondiente:
             *
             * EMP  -> calcularFila() -> UNI = PRE × EMP
             * UNI  -> ajustarPorUnidades()
             * PRE  -> recancularFilaConInventario()
             * etc.
             */
            input.dispatchEvent(
                new Event('input', {
                    bubbles: true
                })
            );
        } else {
            /*
             * F2 / doble clic:
             * selecciona solamente si el tipo de input
             * soporta selección de texto.
             */
            seleccionarContenidoInput(input);
        }

        return true;
    }

    function enfocarYSombrearCelda(input) {
        if (!input) {
            return;
        }

        const td = input.closest('td');

        if (!td) {
            return;
        }

        celdaInicio = td;
        celdaActiva = td;

        actualizarSeleccionRango(td);

        /*
         * IMPORTANTE:
         * No entramos en edición con un clic normal.
         */
        input.blur();
    }

    // ============================================================
    // NAVEGACIÓN
    // ============================================================

    function moverCelda(fila, columna, extender = false) {
        const filas = obtenerFilas();

        if (!filas.length) {
            return null;
        }

        fila = Math.max(
            0,
            Math.min(filas.length - 1, fila)
        );

        const config =
            obtenerConfiguracionTabla();

        columna = Math.max(
            0,
            Math.min(
                config.columnas.length - 1,
                columna
            )
        );

        const destino = obtenerCelda(fila, columna);

        if (!destino) {
            return null;
        }

        if (extender && celdaInicio) {
            actualizarSeleccionRango(destino);
        } else {
            celdaInicio = destino;
            celdaActiva = destino;

            actualizarSeleccionRango(destino);
        }

        return destino;
    }

    function moverPorDireccion(tecla, extender = false) {
        if (!celdaActiva) {
            return;
        }

        let fila = obtenerIndiceFila(celdaActiva);
        let columna = obtenerIndiceColumna(celdaActiva);

        if (fila < 0 || columna < 0) {
            return;
        }

        if (tecla === 'ArrowUp') {
            fila--;
        }

        if (tecla === 'ArrowDown') {
            fila++;
        }

        if (tecla === 'ArrowLeft') {
            columna--;
        }

        if (tecla === 'ArrowRight') {
            columna++;
        }

        /*
         * No permitimos salir de la cuadrícula.
         */
        if (
            fila < 0 ||
            fila >= obtenerFilas().length ||
            columna < 0 ||
            columna >= obtenerConfiguracionTabla().columnas.length
        ) {
            return;
        }

        moverCelda(
            fila,
            columna,
            extender
        );
    }

    function moverPorTab(reverse = false) {
        if (!celdaActiva) {
            return;
        }

        let fila = obtenerIndiceFila(celdaActiva);
        let columna = obtenerIndiceColumna(celdaActiva);

        if (reverse) {
            columna--;

            if (columna < 0) {
                fila--;
                columna =
                    obtenerConfiguracionTabla()
                        .columnas.length - 1;
            }
        } else {
            columna++;

            if (
                columna >=
                obtenerConfiguracionTabla()
                    .columnas.length
            ) {
                fila++;
                columna = 0;
            }
        }

        /*
         * Tab al final de la última fila:
         * mantiene el comportamiento existente de crear una fila.
         */
        if (
            !reverse &&
            fila >= obtenerFilas().length
        ) {

            const config =
                obtenerConfiguracionTabla();

            if (
                config === CONFIG_TABLAS.inventario
            ) {

                if (
                    typeof agregarFilaInventario ===
                    'function'
                ) {
                    agregarFilaInventario();
                }

            } else {

                if (
                    typeof agregarFilaAnalisis ===
                    'function'
                ) {
                    agregarFilaAnalisis();
                }

            }
        }

        if (fila < 0) {
            return;
        }

        const destino = obtenerCelda(
            fila,
            columna
        );

        if (!destino) {
            return;
        }

        celdaInicio = destino;
        celdaActiva = destino;

        actualizarSeleccionRango(destino);
    }
    /**
 * Finaliza la edición de la celda actualmente editada.
 *
 * No modifica el valor.
 * Solo cierra correctamente el estado visual y de teclado.
 */
    function finalizarEdicion(input) {
        if (!input) {
            estaEditando = false;
            return;
        }

        const td = input.closest('td');

        if (td) {
            td.classList.remove(
                'excel-celda-en-edicion'
            );
        }

        delete input.dataset.valorOriginal;

        estaEditando = false;

        input.blur();
    }

    function finalizarEdicionActual() {

        const elementoActivo = document.activeElement;

        if (
            elementoActivo instanceof HTMLInputElement &&
            elementoActivo.closest(obtenerSelectorTbodyActual())
        ) {
            finalizarEdicion(elementoActivo);
            return;
        }

        if (estaEditando && celdaActiva) {
            const input = obtenerInputCelda(celdaActiva);

            if (input) {
                finalizarEdicion(input);
            } else {
                estaEditando = false;
            }
        }
    }

    function cerrarEdicionAlCambiarCelda(nuevaTd) {
        if (!estaEditando) {
            return;
        }

        if (!nuevaTd) {
            return;
        }

        const tdAnterior = celdaActiva;

        // Si realmente seguimos sobre la misma celda,
        // no cerramos nada.
        if (tdAnterior === nuevaTd) {
            return;
        }

        const inputAnterior =
            obtenerInputCelda(tdAnterior);

        if (inputAnterior) {
            finalizarEdicion(inputAnterior);
        } else {
            estaEditando = false;
        }
    }

    // ============================================================
    // ENTER
    // ============================================================

    async function manejarEnter(td) {
        const campo = obtenerCampo(td);
        const input = obtenerInputCelda(td);

        /*
         * Código:
         * si está siendo editado, primero consultamos
         * el producto y luego bajamos a EMP.
         */
        if (
            campo === 'codigo' &&
            input &&
            !input.readOnly
        ) {
            /*
             * Cerramos visualmente la edición ANTES
             * de movernos a otra celda.
             */
            finalizarEdicion(input);

            const config =
                obtenerConfiguracionTabla();

            if (
                config === CONFIG_TABLAS.inventario
            ) {

                if (
                    typeof consultarProductoInventario ===
                    'function'
                ) {
                    await consultarProductoInventario(
                        input
                    );
                }

            } else {

                if (
                    typeof consultarProductoCodigo ===
                    'function'
                ) {
                    await consultarProductoCodigo(
                        input
                    );
                }

            }

            if (
                config === CONFIG_TABLAS.inventario
            ) {

                const cantidad =
                    td.closest('tr')
                        ?.querySelector('.inp-cantidad');

                if (cantidad) {

                    const destino =
                        cantidad.closest('td');

                    celdaInicio = destino;
                    celdaActiva = destino;

                    actualizarSeleccionRango(
                        destino
                    );
                }

                return;
            }


            const emp =
                td.closest('tr')
                    ?.querySelector('.inp-emp');

            if (emp) {

                const destino =
                    emp.closest('td');

                celdaInicio = destino;
                celdaActiva = destino;

                actualizarSeleccionRango(
                    destino
                );
            }

            return;
        }

        if (
            obtenerConfiguracionTabla() ===
            CONFIG_TABLAS.inventario
            && campo === 'cantidad'
        ) {

            const valor =
                String(input?.value || '')
                    .trim()
                    .replace(',', '.');

            const numero =
                valor === ''
                    ? 0
                    : Number(valor);

            if (
                !Number.isFinite(numero)
                || numero < 0
            ) {
                input.value = '0';
            } else {
                input.value =
                    String(numero);
            }
        }

        /*
         * Desde PRE., INV. EMP., EMP., UNI., COSTO, etc.:
         * Enter baja a la siguiente fila conservando columna.
         */
        const fila = obtenerIndiceFila(td);
        const columna = obtenerIndiceColumna(td);

        if (
            fila < 0 ||
            columna < 0
        ) {
            finalizarEdicion(input);
            return;
        }

        /*
         * IMPORTANTE:
         * cerramos la edición de la celda anterior
         * antes de cambiar celdaActiva.
         */
        finalizarEdicion(input);

        const siguiente = obtenerCelda(
            fila + 1,
            columna
        );

        if (siguiente) {
            celdaInicio = siguiente;
            celdaActiva = siguiente;

            actualizarSeleccionRango(siguiente);
        }
    }

    // ============================================================
    // PEGADO
    // ============================================================

    function obtenerMatrizPortapapeles(texto) {
        return String(texto || '')
            .replace(/\r\n/g, '\n')
            .replace(/\r/g, '\n')
            .split('\n')
            .filter((fila, indice, array) => {
                return (
                    fila !== '' ||
                    indice < array.length - 1
                );
            })
            .map(fila => fila.split('\t'));
    }

    function escribirValorCelda(td, valor) {
        const input = obtenerInputCelda(td);

        /*
         * SUBTOTAL / DESCRIPCIÓN no se pueden pegar.
         */
        if (!input) {
            return false;
        }

        if (input.readOnly) {
            return false;
        }

        const campo = obtenerCampo(td);

        if (![
            'codigo',
            'pre',
            'inv-emp',
            'emp',
            'uni',
            'costo',
            'cantidad'
        ].includes(campo)) {
            return false;
        }

        input.value = String(valor ?? '');

        /*
         * Reutilizamos las funciones de negocio existentes.
         * No duplicamos cálculos aquí.
         */
        if (campo === 'codigo') {
            input.dispatchEvent(
                new Event('change', {
                    bubbles: true
                })
            );
        }

        if (campo === 'pre') {
            if (typeof recancularFilaConInventario === 'function') {
                recancularFilaConInventario(input);
            }
        }

        if (campo === 'emp' || campo === 'costo') {
            if (typeof calcularFila === 'function') {
                calcularFila(input);
            }
        }

        if (campo === 'uni') {
            if (typeof ajustarPorUnidades === 'function') {
                ajustarPorUnidades(input);
            }
        }

        if (campo === 'cantidad') {

            const valor =
                String(input.value ?? '')
                    .trim()
                    .replace(',', '.');

            /*
             * Inventario:
             * - permite 0
             * - permite decimales
             * - máximo 3 decimales
             * - no permite negativos
             */
            if (
                valor === '' ||
                !/^\d+(?:\.\d{0,3})?$/.test(valor) ||
                Number(valor) < 0
            ) {
                input.value = '0';
            }

            if (
                typeof recalcularTotalEmpaques ===
                'function'
            ) {
                recalcularTotalEmpaques();
            }
        }

        return true;
    }

    async function pegarMatrizDesdePortapapeles(texto) {
        if (!celdaActiva) {
            return;
        }

        const matriz = obtenerMatrizPortapapeles(texto);

        if (!matriz.length) {
            return;
        }

        const filaInicio = obtenerIndiceFila(celdaActiva);
        const colInicio = obtenerIndiceColumna(celdaActiva);

        if (
            filaInicio < 0 ||
            colInicio < 0
        ) {
            return;
        }

        for (
            let filaOffset = 0;
            filaOffset < matriz.length;
            filaOffset++
        ) {
            let filaDestino =
                filaInicio + filaOffset;

            /*
             * Si Excel pega más filas de las existentes,
             * agregamos filas.
             */
            while (
                filaDestino >= obtenerFilas().length
            ) {
                const config =
                    obtenerConfiguracionTabla();

                if (config === CONFIG_TABLAS.inventario) {

                    if (
                        typeof agregarFilaInventario ===
                        'function'
                    ) {
                        agregarFilaInventario();
                    } else {
                        break;
                    }

                } else {

                    const config =
                        obtenerConfiguracionTabla();

                    if (
                        config === CONFIG_TABLAS.inventario
                    ) {

                        if (
                            typeof agregarFilaInventario ===
                            'function'
                        ) {
                            agregarFilaInventario();

                        } else {
                            break;
                        }

                    } else {

                        if (
                            typeof agregarFilaAnalisis ===
                            'function'
                        ) {
                            agregarFilaAnalisis();

                        } else {
                            break;
                        }
                    }

                }
            }

            for (
                let colOffset = 0;
                colOffset < matriz[filaOffset].length;
                colOffset++
            ) {
                const colDestino =
                    colInicio + colOffset;

                const config =
                    obtenerConfiguracionTabla();

                if (
                    colDestino >= config.columnas.length
                ) {
                    break;
                }

                const td = obtenerCelda(
                    filaDestino,
                    colDestino
                );

                if (!td) {
                    continue;
                }

                /*
                 * Solo escribimos campos realmente editables.
                 * Descripción y subtotal se saltan.
                 */
                escribirValorCelda(
                    td,
                    matriz[filaOffset][colOffset]
                );
            }
        }

        const configActual = obtenerConfiguracionTabla();

        if (configActual === CONFIG_TABLAS.inventario) {
            if (typeof recalcularTotalEmpaques === 'function') {
                recalcularTotalEmpaques();
            }
        } else {
            if (typeof totalizarAnalisis === 'function') {
                totalizarAnalisis();
            }
        }

        /*
         * Seleccionamos el área pegada.
         */
        const ultimaFila =
            Math.min(
                filaInicio + matriz.length - 1,
                obtenerFilas().length - 1
            );

        const ultimaCol =
            Math.min(
                colInicio +
                Math.max(
                    ...matriz.map(fila => fila.length)
                ) - 1,
                obtenerConfiguracionTabla()
                    .columnas.length - 1
            );

        const destinoFinal =
            obtenerCelda(
                ultimaFila,
                ultimaCol
            );

        if (destinoFinal) {
            actualizarSeleccionRango(
                destinoFinal
            );
        }
    }

    // ============================================================
    // COPIAR
    // ============================================================

    function copiarSeleccion() {
        if (!celdasSeleccionadasAnalisis.length) {
            return;
        }

        const primera = celdasSeleccionadasAnalisis[0];

        const filaInicio =
            obtenerIndiceFila(primera);

        const colInicio =
            obtenerIndiceColumna(primera);

        const ultima =
            celdasSeleccionadasAnalisis[
            celdasSeleccionadasAnalisis.length - 1
            ];

        const filaFin =
            obtenerIndiceFila(ultima);

        const colFin =
            obtenerIndiceColumna(ultima);

        const matriz = [];

        for (
            let fila = filaInicio;
            fila <= filaFin;
            fila++
        ) {
            const valores = [];

            for (
                let columna = colInicio;
                columna <= colFin;
                columna++
            ) {
                valores.push(
                    obtenerValorCelda(
                        obtenerCelda(
                            fila,
                            columna
                        )
                    )
                );
            }

            matriz.push(valores.join('\t'));
        }

        navigator.clipboard
            ?.writeText(matriz.join('\n'))
            .catch(error => {
                console.warn(
                    'No se pudo copiar al portapapeles:',
                    error
                );
            });
    }

    // ============================================================
    // BORRAR
    // ============================================================

    function borrarSeleccion() {
        if (!celdasSeleccionadasAnalisis.length) {
            return;
        }

        celdasSeleccionadasAnalisis.forEach(td => {
            const input = obtenerInputCelda(td);

            if (!input) {
                return;
            }

            const campo = obtenerCampo(td);

            /*
             * ========================================================
             * CÓDIGO
             * ========================================================
             *
             * Al borrar el código sí debemos limpiar la descripción,
             * porque el producto deja de estar identificado.
             */
            if (campo === 'codigo') {
                if (
                    typeof desbloquearCeldaCodigo ===
                    'function'
                ) {
                    desbloquearCeldaCodigo(input);
                }

                input.value = '';

                const desc =
                    td.closest('tr')
                        ?.querySelector('.inp-desc');

                if (desc) {
                    desc.value = '';
                }

                delete input.dataset.valorOriginal;

                return;
            }

            /*
             * ========================================================
             * CAMPOS NUMÉRICOS
             * ========================================================
             *
             * IMPORTANTE:
             * Nunca tocar .inp-desc aquí.
             *
             * Borrar PRE, INV, EMP, UNI o COSTO solamente
             * modifica ese campo y recalcula la fila.
             */
            if (input.readOnly) {
                return;
            }

            /*
             * PRE.
             */
            if (campo === 'pre') {
                input.value = '1';

                if (
                    typeof recancularFilaConInventario ===
                    'function'
                ) {
                    recancularFilaConInventario(input);
                }

                return;
            }

            /*
             * INV. EMP.
             */
            if (campo === 'inv-emp') {
                input.value = '0';

                if (
                    typeof calcularFila ===
                    'function'
                ) {
                    calcularFila(input);
                }

                return;
            }

            /*
             * EMP.
             */
            if (campo === 'emp') {
                input.value = '0';

                if (
                    typeof calcularFila ===
                    'function'
                ) {
                    calcularFila(input);
                }

                return;
            }

            /*
             * UNI.
             */
            if (campo === 'uni') {
                input.value = '0';

                if (
                    typeof ajustarPorUnidades ===
                    'function'
                ) {
                    ajustarPorUnidades(input);
                }

                return;
            }

            /*
             * COSTO UNI.
             */
            if (campo === 'costo') {
                input.value = '0.00';

                if (
                    typeof calcularFila ===
                    'function'
                ) {
                    calcularFila(input);
                }

                return;
            }
        });

        /*
         * Actualizamos el total una sola vez después
         * de procesar toda la selección.
         */
        if (
            typeof totalizarAnalisis ===
            'function'
        ) {
            totalizarAnalisis();
        }
    }

    // ============================================================
    // TECLADO PRINCIPAL
    // ============================================================

    function manejarKeyNav(e, elem, campoActual) {
        const td = elem?.closest('td');

        if (!td) {
            return;
        }


        if (!celdaInicio) {
            celdaInicio = td;
        }

        // --------------------------------------------------------
        // F2
        // --------------------------------------------------------

        // ========================================================
        // F2 EN CÓDIGO → ABRIR BUSCADOR DE PRODUCTOS
        // ========================================================

        if (
            e.key === 'F2' &&
            campoActual === 'codigo'
        ) {
            e.preventDefault();
            e.stopPropagation();

            // IMPORTANTE:
            // No llamar iniciarEdicion().
            // El código abre directamente el modal.
            if (
                typeof abrirModalBuscadorProductos ===
                'function'
            ) {
                abrirModalBuscadorProductos(elem);
            }

            return;
        }

        // --------------------------------------------------------
        // Flechas
        // --------------------------------------------------------

        if (
            [
                'ArrowUp',
                'ArrowDown',
                'ArrowLeft',
                'ArrowRight'
            ].includes(e.key)
        ) {
            e.preventDefault();

            /*
             * IMPORTANTE:
             * primero confirmamos la celda que realmente
             * estaba siendo editada.
             *
             * NO usamos celdaActiva aquí porque puede haber
             * quedado apuntando a otra celda.
             */
            if (estaEditando) {
                finalizarEdicionActual();
            }

            /*
             * Ahora la celda actual ya está fuera de edición.
             * Restauramos la referencia correcta para navegar.
             */
            celdaActiva = td;

            if (!celdaInicio) {
                celdaInicio = td;
            }

            /*
             * Movemos la selección.
             */
            moverPorDireccion(
                e.key,
                e.shiftKey
            );

            return;
        }

        // --------------------------------------------------------
        // TAB
        // --------------------------------------------------------

        if (e.key === 'Tab') {
            e.preventDefault();

            moverPorTab(
                e.shiftKey
            );

            return;
        }

        // --------------------------------------------------------
        // ENTER
        // --------------------------------------------------------

        if (e.key === 'Enter') {
            e.preventDefault();

            manejarEnter(td);

            return;
        }

        // --------------------------------------------------------
        // ESCAPE
        // --------------------------------------------------------

        if (e.key === 'Escape') {
            e.preventDefault();

            if (
                estaEditando &&
                elem.dataset.valorOriginal !== undefined
            ) {
                elem.value = elem.dataset.valorOriginal;

                const tdEditando = elem.closest('td');

                tdEditando?.classList.remove(
                    'excel-celda-en-edicion'
                );

                if (campoActual === 'uni') {
                    if (typeof ajustarPorUnidades === 'function') {
                        ajustarPorUnidades(elem);
                    }
                } else if (
                    ['pre', 'inv-emp', 'emp', 'costo'].includes(campoActual)
                ) {
                    if (typeof calcularFila === 'function') {
                        calcularFila(elem);
                    }
                }

                elem.blur();

                delete elem.dataset.valorOriginal;

                estaEditando = false;

                return;
            }

            desseleccionarCeldas();

            return;
        }

        if (
            !estaEditando &&
            e.key.length === 1 &&
            !e.isComposing
        ) {
            const inputEdicion =
                obtenerInputCelda(td);

            // No permitir edición de campos de solo lectura.
            if (!inputEdicion || inputEdicion.readOnly) {
                return;
            }

            /*
             * Inventario → Cantidad:
             * solo permitimos iniciar edición con
             * dígitos, punto o coma.
             *
             * La validación completa de cantidad
             * continúa en inventario_nuevo.html.
             */
            if (
                obtenerConfiguracionTabla() ===
                CONFIG_TABLAS.inventario
                && campoActual === 'cantidad'
                && !/^[0-9.,]$/.test(e.key)
            ) {
                return;
            }

            e.preventDefault();

            entrarEnEdicion(
                td,
                true,
                e.key
            );

            return;
        }

        /*
         * Una tecla alfanumérica inicia edición tipo Excel.
         */
        if (
            !e.ctrlKey &&
            !e.metaKey &&
            !e.altKey &&
            e.key.length === 1 &&
            !estaEditando
        ) {
            /*
             * Evitamos interferir con inputs de texto que ya
             * están siendo editados.
             */
            if (document.activeElement === elem) {
                return;
            }

            e.preventDefault();

            entrarEnEdicion(
                td,
                true,
                e.key
            );
        }
    }

    // ============================================================
    // EVENTOS GLOBALES
    // ============================================================

    document.addEventListener(
        'mouseup',
        () => {
            isArrastrando = false;
        }
    );

    /*
     * Click simple:
     * selecciona la celda pero NO edita.
     */
    document.addEventListener(
        'click',
        e => {
            const config =
                obtenerConfiguracionTabla();

            const tabla =
                e.target.closest(
                    config.tabla
                );

            if (!tabla) {
                return;
            }

            const td =
                e.target.closest(
                    `${obtenerSelectorTbodyActual()} td`
                );

            if (!td) {
                return;
            }

            if (
                obtenerIndiceColumna(td) < 0
            ) {
                return;
            }

            const shift =
                e.shiftKey === true;

            if (
                shift &&
                celdaInicio
            ) {
                actualizarSeleccionRango(td);
            } else {
                celdaInicio = td;
                celdaActiva = td;

                actualizarSeleccionRango(td);
            }
        }
    );

    /*
     * Doble clic:
     * entra realmente en edición.
     */
    document.addEventListener(
        'dblclick',
        e => {
            const td =
                e.target.closest(
                    `${obtenerSelectorTbodyActual()} td`
                );

            if (!td) {
                return;
            }

            if (
                obtenerIndiceColumna(td) < 0
            ) {
                return;
            }

            const input =
                obtenerInputCelda(td);

            if (!input || input.readOnly) {
                return;
            }

            celdaInicio = td;
            celdaActiva = td;

            actualizarSeleccionRango(td);

            iniciarEdicion(input);
        }
    );

    /*
     * Arrastre con mouse.
     */
    document.addEventListener(
        'mousedown',
        e => {
            const td =
                e.target.closest(
                    `${obtenerSelectorTbodyActual()} td`
                );

            if (!td) {
                return;
            }

            if (
                obtenerIndiceColumna(td) < 0
            ) {
                return;
            }

            /*
             * No interceptamos botones de eliminar.
             */
            if (
                e.target.closest('button')
            ) {
                return;
            }

            /*
             * Evita que el input entre en edición
             * por un simple clic.
             */
            e.preventDefault();

            /*
             * Si venimos de otra celda que estaba en edición,
             * cerramos esa edición ANTES de cambiar celdaActiva.
             */
            cerrarEdicionAlCambiarCelda(td);

            const shift =
                e.shiftKey === true;

            if (
                shift &&
                celdaInicio
            ) {
                celdaActiva = td;

                actualizarSeleccionRango(td);
            } else {
                celdaInicio = td;
                celdaActiva = td;

                actualizarSeleccionRango(td);
            }

            isArrastrando = true;

            window.getSelection()?.removeAllRanges();

        }
    );

    document.addEventListener(
        'mouseenter',
        e => {
            if (!isArrastrando) {
                return;
            }

            const td =
                e.target.closest(
                    `${obtenerSelectorTbodyActual()} td`
                );

            if (!td) {
                return;
            }

            if (
                obtenerIndiceColumna(td) < 0
            ) {
                return;
            }

            actualizarSeleccionRango(td);
        },
        true
    );

    /*
     * Doble clic sobre código bloqueado:
     * conserva la funcionalidad existente.
     */
    document.addEventListener(
        'dblclick',
        e => {
            const input =
                e.target.closest('.inp-codigo');

            if (!input) {
                return;
            }

            if (
                input.readOnly &&
                typeof desbloquearCeldaCodigo ===
                'function'
            ) {
                desbloquearCeldaCodigo(input);
            }
        },
        true
    );

    document.addEventListener('keydown', e => {
        if (!celdaActiva) {
            return;
        }

        const inputActivo = obtenerInputCelda(celdaActiva);

        if (!inputActivo) {
            return;
        }

        // F2 entra en edición / abre buscador para Código.
        if (e.key === 'F2') {
            e.preventDefault();
            e.stopPropagation();

            const campo = obtenerCampo(celdaActiva);

            if (
                campo === 'codigo' &&
                typeof abrirModalBuscadorProductos === 'function'
            ) {
                abrirModalBuscadorProductos(inputActivo);
            } else if (campo !== 'codigo') {
                // F2 tipo Excel se mantiene para las demás celdas.
                iniciarEdicion(inputActivo);
            }

            return;
        }
    });

    document.addEventListener('keydown', e => {
        if (!celdaActiva) {
            return;
        }

        /*
         * IMPORTANTE:
         * Si el modal de búsqueda de productos está abierto
         * y la tecla proviene de cualquier elemento del modal,
         * NO debemos enviar esa tecla al controlador Excel.
         *
         * El modal tiene su propio teclado:
         * - escritura
         * - Enter
         * - ArrowUp
         * - ArrowDown
         * - Escape
         */
        const modalBusqueda =
            document.getElementById(
                'modal-buscador-productos'
            );

        if (
            modalBusqueda &&
            !modalBusqueda.classList.contains('hidden') &&
            modalBusqueda.contains(e.target)
        ) {
            return;
        }

        const input = obtenerInputCelda(celdaActiva);

        if (!input) {
            return;
        }
        if (
            e.target instanceof HTMLInputElement &&
            e.target.closest(obtenerSelectorTbodyActual()) &&
            e.target !== input
        ) {
            return;
        }

        /*
         * Si el usuario está editando un input,
         * usamos ese input como origen real del teclado.
         */
        const elementoTeclado =
            e.target instanceof HTMLInputElement &&
                e.target.closest(obtenerSelectorTbodyActual())
                ? e.target
                : input;

        const campo = obtenerCampo(celdaActiva);

        /*
         * No interferir con Ctrl/Cmd + combinaciones del navegador.
         */
        if (
            e.ctrlKey ||
            e.metaKey ||
            e.altKey
        ) {
            return;
        }

        /*
         * Escape, Enter, Tab, flechas y escritura
         * pasan por el controlador Excel.
         */
        manejarKeyNav(
            e,
            elementoTeclado,
            campo
        );
    });

    /*
     * Ctrl/Cmd + C
     */
    document.addEventListener(
        'keydown',
        e => {
            if (
                (e.ctrlKey || e.metaKey) &&
                e.key.toLowerCase() === 'c' &&
                celdasSeleccionadasAnalisis.length
            ) {
                e.preventDefault();

                copiarSeleccion();

                // Resalta visualmente el rango recién copiado.
                resaltarSeleccionCopiada();

                return;
            }

            /*
             * Delete / Supr
             */
            if (
                (
                    e.key === 'Delete' ||
                    e.key === 'Del'
                ) &&
                celdasSeleccionadasAnalisis.length
            ) {
                e.preventDefault();

                borrarSeleccion();

                return;
            }

            /*
             * Escape cuando no hay input editándose.
             */
            if (
                e.key === 'Escape' &&
                !estaEditando &&
                celdasSeleccionadasAnalisis.length
            ) {
                e.preventDefault();

                desseleccionarCeldas();
            }
        }
    );

    /*
     * Ctrl/Cmd + V.
     *
     * Permite pegar directamente sobre una celda
     * seleccionada, sin tener que entrar en edición.
     */
    document.addEventListener(
        'paste',
        e => {
            if (!celdaActiva) {
                return;
            }

            /*
             * Si el usuario está escribiendo dentro de
             * un input, dejamos que el navegador maneje
             * el pegado normal.
             */
            if (
                estaEditando &&
                document.activeElement?.tagName ===
                'INPUT'
            ) {
                return;
            }

            const texto =
                e.clipboardData?.getData(
                    'text/plain'
                );

            if (!texto) {
                return;
            }

            e.preventDefault();

            pegarMatrizDesdePortapapeles(
                texto
            );
        }
    );

    /*
     * Click fuera de la tabla.
     */
    document.addEventListener(
        'click',
        e => {
            const config =
                obtenerConfiguracionTabla();

            if (
                !e.target.closest(
                    config.tabla
                )
            ) {
                desseleccionarCeldas();
            }
        }
    );

    // ============================================================
    // API PÚBLICA
    // ============================================================

    window.iniciarArrastre =
        iniciarArrastre;

    window.arrastrarSobreCelda =
        arrastrarSobreCelda;

    window.iniciarEdicion =
        iniciarEdicion;

    window.manejarKeyNav =
        manejarKeyNav;

    window.actualizarSeleccionRango =
        actualizarSeleccionRango;

    window.desseleccionarCeldas =
        desseleccionarCeldas;

    window.enfocarYSombrearCelda =
        enfocarYSombrearCelda;

    window.pegarMatrizDesdePortapapeles =
        pegarMatrizDesdePortapapeles;

    window.copiarSeleccionAnalisis =
        copiarSeleccion;

    window.borrarSeleccionAnalisis =
        borrarSeleccion;

})();