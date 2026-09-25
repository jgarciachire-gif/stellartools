/**
 * Gestión de productos del Análisis de Pedido.
 *
 * Responsabilidades:
 * - Normalizar códigos.
 * - Crear y eliminar filas de productos.
 * - Bloquear/desbloquear códigos.
 * - Mantener la estructura de tiendas.
 */

(function () {
    'use strict';

    const matrizTiendas =
        window.matrizTiendas ||
        (window.matrizTiendas = {});


    // ============================================================
    // NORMALIZACIÓN DE CÓDIGOS
    // ============================================================

    function normalizarCodigoAnalisis(cod) {

        if (!cod) {
            return '';
        }

        const str = String(cod).trim();

        return /^\d+$/.test(str)
            ? str.padStart(6, '0')
            : str;
    }


    // ============================================================
    // ESTRUCTURA DE TIENDAS
    // ============================================================

    function asegurarEstructuraTienda(tienda) {

        if (!tienda) {
            return;
        }

        if (!window.matrizTiendas[tienda]) {
            window.matrizTiendas[tienda] = {};
        }
    }


    // ============================================================
    // BLOQUEO DEL CÓDIGO DEL PRODUCTO
    // ============================================================

    function bloquearCeldaCodigo(inputCodigo) {

        if (!inputCodigo) {
            return;
        }

        if (inputCodigo.value.trim() !== '') {

            inputCodigo.readOnly = true;

            inputCodigo.classList.add(
                'bg-slate-100',
                'cursor-default',
                'select-none'
            );

            inputCodigo.classList.remove(
                'focus:bg-white',
                'cursor-pointer'
            );
        }
    }


    // ============================================================
    // DESBLOQUEAR CÓDIGO
    // ============================================================

    function desbloquearCeldaCodigo(inputCodigo) {

        if (!inputCodigo) {
            return;
        }

        if (inputCodigo.readOnly) {

            inputCodigo.readOnly = false;

            inputCodigo.classList.remove(
                'bg-slate-100',
                'cursor-default',
                'select-none'
            );

            inputCodigo.classList.add(
                'focus:bg-white'
            );

            inputCodigo.focus();
            inputCodigo.select();
        }
    }


    // ============================================================
    // CREAR FILA DE PRODUCTO
    // ============================================================

    function agregarFilaAnalisis() {

        const tbody =
            document.getElementById(
                'filas-tabla-analisis'
            );

        if (!tbody) {
            return null;
        }

        const tr =
            document.createElement('tr');

        tr.className =
            'hover:bg-blue-50/40 transition text-xs';

        tr.innerHTML = `
            <td class="border border-slate-200 p-0 celda-interactiva relative">
                <input
                    type="text"
                    autocomplete="off"
                    spellcheck="false"
                    class="inp-codigo w-full px-2 py-1.5 border-0 text-xs font-normal uppercase focus:bg-white focus:outline-none bg-transparent"
                    onmousedown="iniciarArrastre(this)"
                    onmouseenter="arrastrarSobreCelda(this)"
                    ondblclick="desbloquearCeldaCodigo(this)"
                    onkeydown="manejarKeyNav(event, this, 'codigo')"
                    onchange="consultarProductoCodigo(this)"
                    onpaste="manejarPegadoCodigo(event, this)"
                >
            </td>

            <td class="border border-slate-200 p-0 celda-interactiva relative">
                <input
                    type="text"
                    readonly
                    tabindex="-1"
                    class="inp-desc w-full px-2 py-1.5 bg-slate-50 text-xs font-normal text-slate-600 focus:outline-none cursor-default border-0"
                    onmousedown="iniciarArrastre(this)"
                    onmouseenter="arrastrarSobreCelda(this)"
                >
            </td>

            <td class="border border-slate-200 p-0 celda-interactiva relative">
                <input
                    type="number"
                    step="1"
                    min="1"
                    value="1"
                    class="inp-pre text-center w-full px-2 py-1.5 border-0 text-xs font-normal focus:bg-white focus:outline-none bg-transparent"
                    onmousedown="iniciarArrastre(this)"
                    onmouseenter="arrastrarSobreCelda(this)"
                    onkeydown="manejarKeyNav(event, this, 'pre')"
                    oninput="if(this.value < 1 && this.value !== '') this.value = 1; recancularFilaConInventario(this)"
                    onpaste="manejarPegadoColumna(event, this, 'pre')"
                    onfocus="iniciarEdicion(this)"
                >
            </td>

            <td class="border border-slate-200 p-0 celda-interactiva relative bg-amber-50/30">
                <input
                    type="number"
                    step="1"
                    min="0"
                    value="0"
                    class="inp-inv-emp text-center w-full px-2 py-1.5 border-0 text-xs font-semibold text-amber-800 focus:bg-white focus:outline-none bg-transparent"
                    onmousedown="iniciarArrastre(this)"
                    onmouseenter="arrastrarSobreCelda(this)"
                    onkeydown="manejarKeyNav(event, this, 'inv-emp')"
                    oninput="if(this.value < 0) this.value = 0; recancularFilaConInventario(this)"
                    onpaste="manejarPegadoColumna(event, this, 'inv-emp')"
                    onfocus="iniciarEdicion(this)"
                >
            </td>

            <td class="border border-slate-200 p-0 celda-interactiva relative">
                <input
                    type="number"
                    step="1"
                    min="0"
                    value="0"
                    class="inp-emp text-center w-full px-2 py-1.5 border-0 text-xs font-normal focus:bg-white focus:outline-none bg-transparent"
                    onmousedown="iniciarArrastre(this)"
                    onmouseenter="arrastrarSobreCelda(this)"
                    onkeydown="manejarKeyNav(event, this, 'emp')"
                    oninput="if(this.value < 0) this.value = 0; calcularFila(this)"
                    onpaste="manejarPegadoColumna(event, this, 'emp')"
                    onfocus="iniciarEdicion(this)"
                >
            </td>

            <td class="border border-slate-200 p-0 celda-interactiva relative">
                <input
                    type="number"
                    step="1"
                    min="0"
                    value="0"
                    class="inp-uni text-center w-full px-2 py-1.5 border-0 text-xs font-normal focus:bg-white focus:outline-none bg-transparent"
                    onmousedown="iniciarArrastre(this)"
                    onmouseenter="arrastrarSobreCelda(this)"
                    onkeydown="manejarKeyNav(event, this, 'uni')"
                    oninput="if(this.value < 0) this.value = 0; ajustarPorUnidades(this)"
                    onpaste="manejarPegadoColumna(event, this, 'uni')"
                    onfocus="iniciarEdicion(this)"
                >
            </td>

            <td class="border border-slate-200 p-0 celda-interactiva relative">
                <input
                    type="number"
                    step="0.01"
                    min="0"
                    value="0.00"
                    class="inp-costo text-right w-full px-2 py-1.5 border-0 text-xs font-normal focus:bg-white focus:outline-none bg-transparent"
                    onmousedown="iniciarArrastre(this)"
                    onmouseenter="arrastrarSobreCelda(this)"
                    onkeydown="manejarKeyNav(event, this, 'costo')"
                    oninput="if(this.value < 0) this.value = 0; calcularFila(this)"
                    onpaste="manejarPegadoColumna(event, this, 'costo')"
                >
            </td>

            <td class="border border-slate-200 px-2 py-1.5 text-right font-normal text-slate-700 bg-slate-50/50">
                <span class="txt-subtotal">$ 0,00</span>
            </td>

            <td class="border border-slate-200 p-0 text-center bg-slate-50/50">
                <button
                    type="button"
                    onclick="eliminarFila(this)"
                    class="w-full h-full text-slate-400 hover:text-rose-600 transition py-1.5"
                >
                    <i class="fa-solid fa-trash-can text-xs"></i>
                </button>
            </td>
        `;

        tbody.appendChild(tr);

        return tr;
    }

    async function manejarPegadoCodigo(e, inputActual) {
        const clipboardData =
            e.clipboardData || window.clipboardData;

        const pastedData =
            clipboardData.getData('Text');

        const lineas = pastedData
            .split(/\r\n|\n|\r/)
            .map(linea => linea.trim())
            .filter(Boolean);

        // Un solo código: mantiene el comportamiento normal.
        if (lineas.length <= 1) {
            return;
        }

        e.preventDefault();

        // ========================================================
        // 1. NORMALIZAR Y DEDUPLICAR CÓDIGOS PEGADOS
        // ========================================================

        const codigosPegados = [
            ...new Set(
                lineas
                    .map(codigo =>
                        normalizarCodigoAnalisis(codigo)
                    )
                    .filter(Boolean)
            )
        ];

        if (codigosPegados.length === 0) {
            return;
        }

        // ========================================================
        // 2. OMITIR CÓDIGOS QUE YA EXISTEN EN LA TABLA
        // ========================================================

        const codigosExistentes = new Set(
            Array.from(
                document.querySelectorAll(
                    '#filas-tabla-analisis .inp-codigo'
                )
            )
                .map(input =>
                    normalizarCodigoAnalisis(input.value)
                )
                .filter(Boolean)
        );

        const codigosPendientes =
            codigosPegados.filter(
                codigo => !codigosExistentes.has(codigo)
            );

        if (codigosPendientes.length === 0) {
            return;
        }

        // ========================================================
        // 3. UNA SOLA CONSULTA HTTP PARA TODOS LOS CÓDIGOS
        // ========================================================

        let productos = [];

        try {
            const response = await fetch(
                '/api/productos/buscar-lote',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        codigos: codigosPendientes
                    })
                }
            );

            const resultado = await response.json();

            if (!response.ok) {
                throw new Error(
                    resultado?.error
                    || 'No se pudieron consultar los productos.'
                );
            }

            productos = Array.isArray(resultado)
                ? resultado
                : [];

        } catch (error) {
            console.error(
                'Error en búsqueda masiva de productos:',
                error
            );

            await mostrarAlerta({
                tipo: 'error',
                titulo: 'Error al cargar códigos',
                mensaje: 'No se pudieron cargar los códigos pegados.'
            });

            return;
        }

        // ========================================================
        // 4. MAPEAR RESULTADOS PARA ACCESO INMEDIATO
        // ========================================================

        const productosMap = new Map(
            productos.map(producto => [
                normalizarCodigoAnalisis(
                    producto.codigo_st
                ),
                producto
            ])
        );

        // ========================================================
        // 5. LOCALIZAR LA FILA DESDE LA QUE SE PEGÓ
        // ========================================================

        let trActual = inputActual.closest('tr');

        // ========================================================
        // 6. RELLENAR LA TABLA SIN HACER MÁS PETICIONES
        // ========================================================

        codigosPendientes.forEach(codigo => {
            if (!trActual) {
                trActual = agregarFilaAnalisis();
            }

            const inpCodigo =
                trActual.querySelector('.inp-codigo');

            const inpDesc =
                trActual.querySelector('.inp-desc');

            const inpPre =
                trActual.querySelector('.inp-pre');

            const inpCosto =
                trActual.querySelector('.inp-costo');

            const producto =
                productosMap.get(codigo);

            inpCodigo.value = codigo;

            if (producto) {
                inpDesc.value =
                    producto.descripcion || '';

                inpPre.value =
                    producto.unidad_manejo || 1;

                inpCosto.value =
                    Number(
                        producto.precio || 0
                    ).toFixed(2);

                inpPre.dataset.original =
                    inpPre.value;

                inpCosto.dataset.original =
                    inpCosto.value;

                bloquearCeldaCodigo(
                    inpCodigo
                );
            } else {
                inpDesc.value =
                    'PRODUCTO NO ENCONTRADO';

                inpPre.value = '1';
                inpCosto.value = '0.00';
            }

            trActual =
                trActual.nextElementSibling;
        });

        // Una sola actualización de totales.
        totalizarAnalisis();
    }


    function manejarPegadoColumna(e, inputActual, tipo) {
        // Obtiene el texto pegado desde el portapapeles.
        const clipboardData =
            e.clipboardData || window.clipboardData;

        const pastedData =
            clipboardData.getData('Text');

        // Separa las líneas pegadas y descarta filas vacías.
        const lineas = pastedData
            .split(/\r\n|\n|\r/)
            .map(l => l.trim())
            .filter(l => l.length > 0);

        // Si solo contiene un valor,
        // permite el pegado nativo por defecto.
        if (lineas.length <= 1) {
            return;
        }

        e.preventDefault();

        let trActual = inputActual.closest('tr');

        lineas.forEach(valor => {
            // Si no existen suficientes filas,
            // agrega una nueva automáticamente.
            if (!trActual) {
                trActual = agregarFilaAnalisis();
            }

            const inputDestino =
                trActual.querySelector(`.inp-${tipo}`);

            if (inputDestino) {
                // Reemplaza comas por puntos.
                const valorLimpio =
                    valor.replace(',', '.');

                inputDestino.value =
                    isNaN(parseFloat(valorLimpio))
                        ? 0
                        : valorLimpio;

                // Ejecuta el recálculo correspondiente.
                if (tipo === 'uni') {
                    ajustarPorUnidades(inputDestino);

                } else if (tipo === 'inv-emp') {
                    recancularFilaConInventario(
                        inputDestino
                    );

                } else {
                    calcularFila(inputDestino);
                }
            }

            // Pasa a la fila siguiente.
            trActual =
                trActual.nextElementSibling;
        });
    }

    function eliminarFila(btn) {
        const tbody =
            document.getElementById('filas-tabla-analisis');

        const tr =
            btn.closest('tr');

        const codigoABorrar =
            tr
                .querySelector('.inp-codigo')
                ?.value
                ?.trim();

        // Purga el producto de la memoria global
        // para todas las sedes.
        if (
            codigoABorrar &&
            window.matrizTiendas
        ) {
            for (const sede in window.matrizTiendas) {
                delete window.matrizTiendas[sede][codigoABorrar];
            }
        }

        if (tbody.children.length > 1) {
            tr.remove();

            totalizarAnalisis();

        } else {
            // Si queda una sola fila,
            // la conservamos y limpiamos sus datos.
            tr.querySelectorAll('input').forEach(input => {

                if (input.classList.contains('inp-pre')) {
                    input.value = '1';

                } else if (
                    input.classList.contains('inp-costo')
                ) {
                    input.value = '0.00';

                } else {
                    input.value = '';
                }
            });

            const subtotalEl =
                tr.querySelector('.txt-subtotal');

            if (subtotalEl) {
                subtotalEl.textContent = '$ 0,00';
            }

            totalizarAnalisis();
        }
    }

    function obtenerCodigoFila(tr) {
        const el =
            tr.querySelector('.inp-codigo');

        if (!el) {
            return '';
        }

        const codigo =
            (
                el.value !== undefined &&
                    el.value !== ''
                    ? el.value
                    : el.textContent ||
                    el.innerText ||
                    ''
            ).trim();

        if (
            !codigo ||
            codigo.toUpperCase() === 'NULL' ||
            codigo.toUpperCase() === 'UNDEFINED'
        ) {
            return '';
        }

        return normalizarCodigoAnalisis(codigo);
    }
    async function consultarProductoCodigo(inputCodigo) {

        let codigo =
            inputCodigo.value.trim();

        const tr =
            inputCodigo.closest('tr');

        const inpDesc =
            tr.querySelector('.inp-desc');

        const inpPre =
            tr.querySelector('.inp-pre');

        const inpCosto =
            tr.querySelector('.inp-costo');


        // Si se borra el código,
        // limpiamos los datos asociados.
        if (!codigo) {

            inpDesc.value = '';
            inpCosto.value = '0.00';
            inpPre.value = '1';

            delete inpCosto.dataset.original;
            delete inpPre.dataset.original;

            calcularFila(inputCodigo);

            return;
        }


        // Normaliza códigos numéricos a 6 dígitos.
        if (/^\d+$/.test(codigo)) {

            codigo =
                codigo.padStart(6, '0');

            inputCodigo.value =
                codigo;
        }


        try {

            const res =
                await fetch(
                    `/api/productos/buscar-codigo/${encodeURIComponent(codigo)}`
                );

            const data =
                await res.json();


            if (data && data.descripcion) {

                inpDesc.value =
                    data.descripcion;


                inpCosto.value =
                    Number(
                        data.precio || 0
                    ).toFixed(2);


                const numManejo =
                    parseInt(
                        data.unidad_manejo
                    );


                if (
                    !isNaN(numManejo)
                    && numManejo > 0
                ) {
                    inpPre.value =
                        numManejo;
                }


                inpPre.dataset.original =
                    inpPre.value;

                inpCosto.dataset.original =
                    inpCosto.value;


                bloquearCeldaCodigo(
                    inputCodigo
                );

            } else {

                inpDesc.value =
                    'PRODUCTO NO ENCONTRADO';

                inpCosto.value =
                    '0.00';

                inpPre.value =
                    '1';
            }

        } catch (e) {

            inpDesc.value =
                'ERROR DE CONEXIÓN';

            inpCosto.value =
                '0.00';

            inpPre.value =
                '1';

            console.error(
                'Error al consultar producto:',
                e
            );
        }


        calcularFila(inputCodigo);
    }

    async function consultarProductoCodigo(inputCodigo) {
        let codigo =
            inputCodigo.value.trim();

        const tr =
            inputCodigo.closest('tr');

        const inpDesc =
            tr.querySelector('.inp-desc');

        const inpPre =
            tr.querySelector('.inp-pre');

        const inpCosto =
            tr.querySelector('.inp-costo');

        // Si se borra el código, limpiar datos
        // y recalcular la fila.
        if (!codigo) {
            inpDesc.value = '';
            inpCosto.value = '0.00';
            inpPre.value = '1';

            delete inpCosto.dataset.original;
            delete inpPre.dataset.original;

            calcularFila(inputCodigo);

            return;
        }

        // Completar códigos numéricos a 6 dígitos.
        if (/^\d+$/.test(codigo)) {
            codigo =
                codigo.padStart(6, '0');

            inputCodigo.value =
                codigo;
        }

        try {
            const res =
                await fetch(
                    `/api/productos/buscar-codigo/${encodeURIComponent(codigo)}`
                );

            const data =
                await res.json();

            if (
                data &&
                data.descripcion
            ) {
                inpDesc.value =
                    data.descripcion;

                inpCosto.value =
                    Number(
                        data.precio || 0
                    ).toFixed(2);

                const numManejo =
                    parseInt(
                        data.unidad_manejo
                    );

                if (
                    !isNaN(numManejo) &&
                    numManejo > 0
                ) {
                    inpPre.value =
                        numManejo;
                }

                inpPre.dataset.original =
                    inpPre.value;

                inpCosto.dataset.original =
                    inpCosto.value;

                bloquearCeldaCodigo(
                    inputCodigo
                );

            } else {
                inpDesc.value =
                    'PRODUCTO NO ENCONTRADO';

                inpCosto.value =
                    '0.00';

                inpPre.value =
                    '1';
            }

        } catch (e) {
            inpDesc.value =
                'ERROR DE CONEXIÓN';

            inpCosto.value =
                '0.00';

            inpPre.value =
                '1';
        }

        calcularFila(inputCodigo);
    }

    function calcularFila(elem) {

        const tr =
            elem.closest('tr');

        const pre =
            parseFloat(
                tr.querySelector('.inp-pre').value
            ) || 1;

        const emp =
            parseFloat(
                tr.querySelector('.inp-emp').value
            ) || 0;

        const costo =
            parseFloat(
                tr.querySelector('.inp-costo').value
            ) || 0;


        const uniInput =
            tr.querySelector('.inp-uni');

        const totalUni =
            pre * emp;

        uniInput.value =
            totalUni;


        const subtotal =
            totalUni * costo;

        tr.querySelector(
            '.txt-subtotal'
        ).textContent =
            `$ ${subtotal.toLocaleString(
                'es-VE',
                {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                }
            )}`;


        totalizarAnalisis();
    }

    function recancularFilaConInventario(elem) {
        const tr = elem.closest('tr');

        const codigo =
            tr.querySelector('.inp-codigo').value.trim();

        const pre =
            parseFloat(
                tr.querySelector('.inp-pre').value
            ) || 1;

        const invEmp =
            parseFloat(
                tr.querySelector('.inp-inv-emp').value
            ) || 0;

        // Obtener demanda diaria guardada en la matriz
        // para la tienda activa.
        asegurarEstructuraTienda(
            window.tiendaActivaPestana
        );

        const datosProd =
            window.matrizTiendas[
            window.tiendaActivaPestana
            ][codigo] || {
                demandaDiaria: 0
            };

        const demandaDiaria =
            datosProd.demandaDiaria || 0;

        const diasCobertura =
            parseFloat(
                document.getElementById(
                    'dias_cobertura'
                ).value
            ) || 7;

        // Convertir Inventario Físico en Empaques
        // a Unidades.
        const invUnidades =
            invEmp * pre;

        // Unidades Requeridas =
        // (Demanda Diaria * Días Cobertura)
        // - Inventario en Unidades.
        const unidadesRequeridas =
            (demandaDiaria * diasCobertura)
            - invUnidades;

        // EMP. Sugerido =
        // Redondear Arriba(
        //   Max(0, Unidades Requeridas) / Presentación
        // )
        let empSugerido = 0;

        if (
            unidadesRequeridas > 0 &&
            pre > 0
        ) {
            empSugerido =
                Math.ceil(
                    unidadesRequeridas / pre
                );
        }

        // Auto-completar EMP con el valor sugerido.
        tr.querySelector('.inp-emp').value =
            empSugerido;

        // Guardar estado en memoria para no perderlo
        // al cambiar de pestaña.
        window.matrizTiendas[
            window.tiendaActivaPestana
        ][codigo] = {
            invEmp: invEmp,
            emp: empSugerido,
            demandaDiaria: demandaDiaria
        };

        // Calcular Unidades Totales y Subtotal.
        calcularFila(elem);
    }

    function ajustarPorUnidades(elem) {

        const tr =
            elem.closest('tr');

        const pre =
            parseFloat(
                tr.querySelector('.inp-pre').value
            ) || 1;

        const uni =
            parseFloat(
                tr.querySelector('.inp-uni').value
            ) || 0;

        const costo =
            parseFloat(
                tr.querySelector('.inp-costo').value
            ) || 0;


        const empInput =
            tr.querySelector('.inp-emp');

        empInput.value =
            pre > 0
                ? (uni / pre)
                : 0;


        const subtotal =
            uni * costo;

        tr.querySelector(
            '.txt-subtotal'
        ).textContent =
            `$ ${subtotal.toLocaleString(
                'es-VE',
                {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                }
            )}`;


        totalizarAnalisis();
    }

    function totalizarAnalisis() {

        let totEmp = 0;
        let totUni = 0;
        let totMonto = 0;


        document
            .querySelectorAll('#filas-tabla-analisis tr')
            .forEach(tr => {

                const emp =
                    parseFloat(
                        tr.querySelector('.inp-emp')?.value
                    ) || 0;

                const uni =
                    parseFloat(
                        tr.querySelector('.inp-uni')?.value
                    ) || 0;

                const costo =
                    parseFloat(
                        tr.querySelector('.inp-costo')?.value
                    ) || 0;


                totEmp += emp;
                totUni += uni;
                totMonto += uni * costo;
            });


        document.getElementById(
            'tot-empaques'
        ).textContent =
            totEmp.toLocaleString('es-VE');


        document.getElementById(
            'tot-unidades'
        ).textContent =
            totUni.toLocaleString('es-VE');


        document.getElementById(
            'tot-monto'
        ).textContent =
            `$ ${totMonto.toLocaleString(
                'es-VE',
                {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                }
            )}`;
    }

    function eliminarFila(btn) {

        const tbody =
            document.getElementById(
                'filas-tabla-analisis'
            );

        const tr =
            btn.closest('tr');

        const codigoABorrar =
            tr
                .querySelector('.inp-codigo')
                ?.value
                ?.trim();


        // Elimina el producto de la matriz
        // en todas las tiendas.
        if (
            codigoABorrar
            && typeof matrizTiendas !== 'undefined'
        ) {

            for (const sede in matrizTiendas) {
                delete matrizTiendas[sede][codigoABorrar];
            }
        }


        // Conserva siempre al menos una fila.
        if (tbody.children.length > 1) {

            tr.remove();

        } else {

            tr
                .querySelectorAll('input')
                .forEach(input => {

                    input.value = '';

                    delete input.dataset.original;
                });

            const inpPre =
                tr.querySelector('.inp-pre');

            if (inpPre) {
                inpPre.value = '1';
            }

            const inpCosto =
                tr.querySelector('.inp-costo');

            if (inpCosto) {
                inpCosto.value = '0.00';
            }

            const inpUni =
                tr.querySelector('.inp-uni');

            if (inpUni) {
                inpUni.value = '0';
            }

            const inpEmp =
                tr.querySelector('.inp-emp');

            if (inpEmp) {
                inpEmp.value = '0';
            }

            const descripcion =
                tr.querySelector('.inp-desc');

            if (descripcion) {
                descripcion.value = '';
            }

            const subtotal =
                tr.querySelector('.txt-subtotal');

            if (subtotal) {
                subtotal.textContent = '$ 0,00';
            }
        }


        totalizarAnalisis();
    }

    // ============================================================
    // EXPONER API DEL MÓDULO
    // ============================================================

    window.normalizarCodigoAnalisis =
        normalizarCodigoAnalisis;

    window.asegurarEstructuraTienda =
        asegurarEstructuraTienda;

    window.bloquearCeldaCodigo =
        bloquearCeldaCodigo;

    window.desbloquearCeldaCodigo =
        desbloquearCeldaCodigo;

    window.agregarFilaAnalisis =
        agregarFilaAnalisis;

    window.manejarPegadoCodigo =
        manejarPegadoCodigo;

    window.manejarPegadoColumna =
        manejarPegadoColumna;

    window.eliminarFila =
        eliminarFila;

    window.obtenerCodigoFila =
        obtenerCodigoFila;

    window.consultarProductoCodigo =
        consultarProductoCodigo;

    window.calcularFila =
        calcularFila;

    window.ajustarPorUnidades =
        ajustarPorUnidades;

    window.totalizarAnalisis =
        totalizarAnalisis;

    window.eliminarFila =
        eliminarFila;

    window.recancularFilaConInventario =
        recancularFilaConInventario;

    window.consultarProductoCodigo =
        consultarProductoCodigo;

})();