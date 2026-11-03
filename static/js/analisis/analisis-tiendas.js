        // Bloquear scroll de la página al usar teclas de navegación dentro de la tabla
        document.getElementById('tabla-analisis')?.addEventListener('keydown', function (e) {
            if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.key)) {
                // Evita el desplazamiento si la tecla proviene de cualquier elemento de la tabla
                e.preventDefault();
            }
        });
        // Evita que las flechas desplacen la página si el foco está en el body o en la tabla
        window.addEventListener('keydown', function (e) {
            if (['ArrowUp', 'ArrowDown'].includes(e.key)) {
                // Si el elemento enfocado es el body o la propia tabla, bloquea el scroll nativo
                if (document.activeElement === document.body || document.activeElement.closest('#tabla-analisis')) {
                    e.preventDefault();
                }
            }
        });

        // Función para cambiar de tienda activa en la barra de pestañas manteniendo los datos
        async function cambiarTiendaPestana(nuevaTienda) {

            // Normaliza la nueva tienda.
            const tiendaNueva = String(nuevaTienda || '')
                .trim()
                .toUpperCase();

            if (!tiendaNueva) {
                return;
            }

            // Si ya estamos en esa tienda, no hacemos nada.
            if (tiendaNueva === window.tiendaActivaPestana) {
                return;
            }

            // Guarda los datos de la tienda actualmente visible.
            guardarEstadoTablaEnMemoria(
                window.tiendaActivaPestana
            );

            // Cambia la tienda activa.
            window.tiendaActivaPestana = tiendaNueva;

            // Actualiza visualmente las pestañas.
            document
                .querySelectorAll('.btn-pestana-tienda')
                .forEach(btn => {

                    const esActiva =
                        String(btn.dataset.tienda || '')
                            .trim()
                            .toUpperCase() === tiendaNueva;

                    btn.className =
                        `btn-pestana-tienda px-4 py-2 rounded-xl text-xs transition ${esActiva
                            ? 'font-bold border border-slate-900 bg-slate-900 text-white shadow-xs'
                            : 'font-semibold border border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-200 hover:text-slate-900'
                        }`;
                });


            // Carga los datos correspondientes a la nueva tienda.
            cargarEstadoTablaDesdeMemoria(tiendaNueva);

            // Espera a que se actualicen las fechas y el mensaje de cobertura.
            await actualizarCoberturaKardexDesdeAnalisis(true);

            // Comprueba que la tienda no haya cambiado durante la espera.
            if (tiendaNueva !== window.tiendaActivaPestana) {
                return;
            }

            // Actualiza la demanda histórica y la comparación con las fechas correctas.
            await actualizarDemandaKardexAlCambiarTienda();

        }




        async function actualizarDemandaKardexAlCambiarTienda() {
            const panel = document.getElementById(
                'kardex-comparacion-contenedor'
            );

            // Actualiza solamente una comparación que esté abierta.
            if (!panel || panel.classList.contains('hidden')) return;

            // Reutiliza los meses e intervalos elegidos en el modal.
            if (!ultimaConfiguracionPeriodosKardex?.length) return;

            // Evita consultas sin productos.
            if (!obtenerCodigosTablaAnalisis().length) return;

            await compararDemandaKardexDesdeAnalisis();
        }


        function cargarEstadoTablaDesdeMemoria(tienda) {
            asegurarEstructuraTienda(tienda); // Garantiza objeto inicializado para la tienda
            const filas = document.querySelectorAll('#filas-tabla-analisis tr'); // Captura las filas del DOM

            filas.forEach(tr => {
                const codigo = obtenerCodigoFila(tr); // Código del producto
                if (!codigo) return;

                const datos = matrizTiendas[tienda]?.[codigo] || { invEmp: 0, emp: 0, uni: 0 }; // Extrae datos o valores por defecto

                const inpInv = tr.querySelector('.inp-inv-emp'); // Input inventario empaques
                const inpEmp = tr.querySelector('.inp-emp'); // Input empaques pedido

                if (inpInv) inpInv.value = datos.invEmp || 0; // Asigna inventario recuperado
                if (inpEmp) {
                    inpEmp.value = datos.emp || 0; // Asigna empaques recuperados
                    calcularFila(inpEmp); // Recalcula unidades y subtotal de la fila
                }
            });
        }
