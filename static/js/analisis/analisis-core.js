
        // =========================================================
        // BUSCADOR DE PRODUCTOS — INTEGRACIÓN CON ANÁLISIS
        // =========================================================

        window.onProductoSeleccionadoBuscador =
            async function (codigo, input) {

                if (!input) {
                    return;
                }

                // El buscador compartido entrega el código.
                // Análisis conserva su lógica original.
                consultarProductoCodigo(input);
            };

        window.matrizTiendas = window.matrizTiendas || {};
        window.tiendaActivaPestana =
            window.tiendaActivaPestana || 'CENTRO';


        // Función para borrar todos los productos de la tabla de análisis
        async function limpiarListaProductos() {
            const tbody = document.getElementById('filas-tabla-analisis');

            if (!tbody) return;

            const matriz = window.matrizTiendas || {};

            // También detecta productos ocultos en la memoria de otras tiendas.
            const hayProductosEnMemoria = Object.values(matriz).some(
                productos => productos && Object.keys(productos).length > 0
            );

            if (!tbody.children.length && !hayProductosEnMemoria) return;

            const confirmado = await mostrarConfirmacion({
                tipo: 'warning',
                titulo: 'Limpiar pedido',
                mensaje:
                    'Se eliminarán los productos y cantidades del pedido actual ' +
                    'en todas las tiendas. ¿Deseas continuar?',
                textoAceptar: 'Limpiar tabla',
                textoCancelar: 'Cancelar'
            });

            if (!confirmado) return;

            // Retira la selección y cierra el tooltip.
            window.desseleccionarCeldas?.();

            // Elimina las filas visibles.
            tbody.replaceChildren();

            // Vacía todas las tiendas conservando las referencias a sus objetos.
            Object.values(matriz).forEach(productos => {
                if (!productos || typeof productos !== 'object') return;

                Object.keys(productos).forEach(codigo => {
                    delete productos[codigo];
                });
            });

            // Actualiza los totales de la pantalla.
            if (typeof calcularTotalesAnalisis === 'function') {
                calcularTotalesAnalisis();
            } else if (typeof calcularTotales === 'function') {
                calcularTotales();
            }
        }
        let indiceDestacadoAnalisis = -1;

        // --- TIENDA SEARCH LOGIC ---
        function mostrarOpcionesTiendaAnalisis() {
            // Despliega el menú flotante de tiendas
            document.getElementById('opciones_tienda_analisis').classList.remove('hidden');
        }

        function filtrarTiendasAnalisis() {
            const texto = document.getElementById('buscar_tienda_analisis').value.toLowerCase().trim();
            const opciones = document.querySelectorAll('.opcion-tienda-analisis');
            document.getElementById('opciones_tienda_analisis').classList.remove('hidden');

            indiceDestacadoTiendaAnalisis = -1;
            // Filtra las opciones visibles según lo ingresado en el buscador
            opciones.forEach(opcion => {
                const nombre = opcion.getAttribute('data-nombre') || '';
                opcion.classList.remove('bg-slate-100', 'text-slate-900', 'font-semibold');
                if (nombre.includes(texto)) {
                    opcion.classList.remove('hidden');
                } else {
                    opcion.classList.add('hidden');
                }
            });
        }

        function navegarTiendasAnalisis(e) {
            const dropdown = document.getElementById('opciones_tienda_analisis');
            const opciones = Array.from(document.querySelectorAll('.opcion-tienda-analisis')).filter(el => !el.classList.contains('hidden'));

            // Permite la navegación por teclado (flechas arriba/abajo y Enter)
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (dropdown.classList.contains('hidden')) mostrarOpcionesTiendaAnalisis();
                indiceDestacadoTiendaAnalisis = Math.min(indiceDestacadoTiendaAnalisis + 1, opciones.length - 1);
                resaltarOpcionTiendaAnalisis(opciones);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                indiceDestacadoTiendaAnalisis = Math.max(indiceDestacadoTiendaAnalisis - 1, 0);
                resaltarOpcionTiendaAnalisis(opciones);
            } else if (e.key === 'Enter') {
                if (!dropdown.classList.contains('hidden') && indiceDestacadoTiendaAnalisis >= 0 && opciones[indiceDestacadoTiendaAnalisis]) {
                    e.preventDefault();
                    opciones[indiceDestacadoTiendaAnalisis].click();
                }
            } else if (e.key === 'Escape') {
                dropdown.classList.add('hidden');
            }
        }

        function resaltarOpcionTiendaAnalisis(opciones) {
            // Marca la opción activa en la navegación por teclado
            opciones.forEach(op => op.classList.remove('bg-slate-100', 'text-slate-900', 'font-semibold'));
            if (opciones[indiceDestacadoTiendaAnalisis]) {
                opciones[indiceDestacadoTiendaAnalisis].classList.add('bg-slate-100', 'text-slate-900', 'font-semibold');
                opciones[indiceDestacadoTiendaAnalisis].scrollIntoView({ block: 'nearest' });
            }
        }

        function seleccionarTiendaAnalisis(val, nombre) {
            // Establece el valor final en el input oculto y en el buscador visible
            document.getElementById('tienda_destino').value = val;
            document.getElementById('buscar_tienda_analisis').value = val ? nombre : '';
            document.getElementById('opciones_tienda_analisis').classList.add('hidden');
        }

        function limpiarTiendaAnalisis() {
            // Limpia el campo de selección
            seleccionarTiendaAnalisis('', '');
        }

        // Muestra el menú desplegable al hacer clic o posicionarse en el buscador
