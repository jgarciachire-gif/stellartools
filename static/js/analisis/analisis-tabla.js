        // Cargar 1 filas iniciales al abrir la vista
        document.addEventListener('DOMContentLoaded', () => {
            const cantidadFilasIniciales = 1;
            for (let i = 0; i < cantidadFilasIniciales; i++) {
                agregarFilaAnalisis();
            }
        });

        // --- LÓGICA DE ORDENACIÓN DE COLUMNAS ---
        let colOrdenActual = -1;
        let ascOrdenActual = true;

        function ordenarTablaAnalisis(colIndex, tipo) {
            const tbody = document.getElementById('filas-tabla-analisis');
            const filas = Array.from(tbody.querySelectorAll('tr'));

            // Si se hace clic en la misma columna, invierte el sentido; si es otra, inicia ascendente
            if (colOrdenActual === colIndex) {
                ascOrdenActual = !ascOrdenActual;
            } else {
                colOrdenActual = colIndex;
                ascOrdenActual = true;
            }

            // Actualizar iconos visuales en las cabeceras
            document.querySelectorAll('#tabla-analisis thead .th-icon').forEach((icon, idx) => {
                icon.className = 'fa-solid fa-sort text-[10px] opacity-40 th-icon';
                if (idx === colIndex) {
                    icon.className = `fa-solid ${ascOrdenActual ? 'fa-sort-up' : 'fa-sort-down'} text-[10px] text-blue-400 opacity-100 th-icon`;
                }
            });

            // Extraer el valor correspondiente de la celda según su tipo de control
            const obtenerValor = (tr) => {
                const celda = tr.children[colIndex];
                if (!celda) return '';

                const input = celda.querySelector('input');
                if (input) {
                    return input.value.trim();
                }

                const spanSubtotal = celda.querySelector('.txt-subtotal');
                if (spanSubtotal) {
                    // Limpia el formato de moneda $ X.XXX,XX a valor float para ordenar numéricamente
                    const numStr = spanSubtotal.textContent.replace('$', '').replace(/\./g, '').replace(',', '.').trim();
                    return parseFloat(numStr) || 0;
                }

                return celda.textContent.trim();
            };

            // Algoritmo de ordenación según el tipo de datos (Texto o Número)
            filas.sort((a, b) => {
                let valA = obtenerValor(a);
                let valB = obtenerValor(b);

                if (tipo === 'numero' || tipo === 'subtotal') {
                    valA = parseFloat(valA) || 0;
                    valB = parseFloat(valB) || 0;
                    return ascOrdenActual ? valA - valB : valB - valA;
                } else {
                    valA = valA.toString().toLowerCase();
                    valB = valB.toString().toLowerCase();
                    return ascOrdenActual ? valA.localeCompare(valB) : valB.localeCompare(valA);
                }
            });

            // Reinsertar las filas ordenadas dentro del DOM
            filas.forEach(tr => tbody.appendChild(tr));
        }
        // --- LÓGICA DE ALMACENAMIENTO Y EXPORTACIÓN A TXT ---

        // Obtiene el nombre del proveedor activo en el contenedor 1
        function obtenerNombreProveedor() {
            const el = document.getElementById('buscar_proveedor_analisis')
                || document.querySelector('#combo-proveedor-analisis input[type="text"]');
            if (!el) return 'PROVEEDOR';

            const valor = (el.value !== undefined && el.value !== '' ? el.value : el.textContent || el.innerText || '').trim();

            if (!valor || valor.toUpperCase().includes('SELECCIONAR') || valor === '-- Seleccionar Proveedor --') {
                return 'PROVEEDOR';
            }
            return valor;
        }

        // Extrae el valor numérico de un input o celda
        function obtenerValorCelda(tr, selector) {
            const el = tr.querySelector(selector);
            if (!el) return 0;
            const texto = (el.value !== undefined && el.value !== '' ? el.value : el.textContent || el.innerText || '0').trim();
            return parseFloat(texto) || 0;
        }

        // Guarda todos los datos de la pantalla (pre, invEmp, emp, uni, costo) en la matriz de la tienda dada
        function guardarEstadoTablaEnMemoria(tienda) {
            if (!tienda) return;
            asegurarEstructuraTienda(tienda); // Inicializa el objeto de la tienda si no existe

            document.querySelectorAll('#filas-tabla-analisis tr').forEach(tr => {
                const codigo = obtenerCodigoFila(tr); // Obtiene código válido
                if (!codigo) return;

                const pre = obtenerValorCelda(tr, '.inp-pre') || 1; // Presentación (Unidades por caja)
                const invEmp = obtenerValorCelda(tr, '.inp-inv-emp'); // Inventario empaques
                const emp = obtenerValorCelda(tr, '.inp-emp'); // Empaques pedido

                // Captura el valor de la columna UNI directamente desde input o texto HTML
                const elUni = tr.querySelector('.inp-uni');
                const valUni = elUni ? parseFloat(elUni.value || elUni.textContent || 0) : obtenerValorCelda(tr, '.inp-uni');

                // Prioriza el valor real de la columna UNI. Si está en 0 pero hay empaques, calcula (Empaques * Presentación)
                const uni = (!isNaN(valUni) && valUni > 0) ? valUni : (emp * pre);
                const costo = obtenerValorCelda(tr, '.inp-costo'); // Costo unitario

                matrizTiendas[tienda][codigo] = {
                    ...matrizTiendas[tienda][codigo],
                    pre: pre,
                    invEmp: invEmp,
                    emp: emp,
                    uni: uni,
                    costo: costo
                };
            });
        }

        // Obtiene directamente y de forma estricta el valor de la columna Unidades (UNI.)
        function obtenerUnidadesTienda(tienda, codigo) {
            const codNorm = typeof normalizarCodigoAnalisis === 'function' ? normalizarCodigoAnalisis(codigo) : codigo;

            // 1. Si la tienda está visible en pantalla, lee directamente la celda/input de la columna UNI.
            if (typeof tiendaActivaPestana !== 'undefined' && tienda === tiendaActivaPestana) {
                const fila = document.querySelector(`#filas-tabla-analisis tr[data-codigo="${codNorm}"]`);
                if (fila) {
                    const inputUni = fila.querySelector('.inp-uni, input[data-tipo="uni"], .td-uni');
                    if (inputUni) {
                        const val = parseFloat(inputUni.value !== undefined ? inputUni.value : inputUni.textContent);
                        return isNaN(val) ? 0 : val;
                    }
                }
            }

            // 2. Si es una tienda guardada en memoria, lee directamente la propiedad "uni"
            if (typeof matrizTiendas !== 'undefined' && matrizTiendas[tienda] && matrizTiendas[tienda][codNorm]) {
                const val = parseFloat(matrizTiendas[tienda][codNorm].uni);
                return isNaN(val) ? 0 : val;
            }

            return 0; // Si no existe el registro, retorna 0
        }
