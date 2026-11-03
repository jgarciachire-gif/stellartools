        // Set global para rastrear las tiendas elegidas en la ventana modal
        let tiendasSeleccionadasExportar = new Set();

        // Abre el modal y renderiza la lista de tiendas
        function abrirModalExportarSeparado() {
            const contenedor = document.getElementById('contenedor-etiquetas-exportar'); // Obtener contenedor de etiquetas
            if (!contenedor) return;

            contenedor.innerHTML = ''; // Limpiar etiquetas previas
            tiendasSeleccionadasExportar.clear(); // Limpiar datos del Set

            // Obtener la lista de tiendas desde LISTA_TIENDAS o las claves del objeto matrizTiendas
            const listaTiendas = (typeof LISTA_TIENDAS !== 'undefined' && LISTA_TIENDAS.length > 0)
                ? LISTA_TIENDAS
                : Object.keys(matrizTiendas || {});

            if (listaTiendas.length === 0) {
                mostrarNotificacion({
                    tipo: 'info',
                    mensaje: 'No hay tiendas disponibles para exportar.'
                });

                return;
            }

            // Generar dinámicamente las etiquetas de cada tienda
            listaTiendas.forEach(tienda => {
                tiendasSeleccionadasExportar.add(tienda); // Seleccionar por defecto

                const tag = document.createElement('div'); // Crear elemento visual
                tag.className = 'tag-tienda-exportar activa'; // Clase activa inicial
                tag.textContent = tienda; // Nombre visible
                tag.dataset.tienda = tienda; // Atributo identificador

                tag.onclick = () => toggleTiendaExportar(tienda, tag); // Evento clic para alternar

                contenedor.appendChild(tag); // Agregar al contenedor
            });

            document.getElementById('modal-exportar-tiendas').style.display = 'flex'; // Mostrar modal centrado
        }

        // Alterna la selección individual de una tienda
        function toggleTiendaExportar(tienda, elementoHTML) {
            if (tiendasSeleccionadasExportar.has(tienda)) {
                tiendasSeleccionadasExportar.delete(tienda); // Desmarcar tienda
                elementoHTML.classList.remove('activa'); // Quitar estilo activo
            } else {
                tiendasSeleccionadasExportar.add(tienda); // Marcar tienda
                elementoHTML.classList.add('activa'); // Agregar estilo activo
            }
        }

        // Marca o desmarca todas las tiendas
        function toggleTodasLasTiendasExportar() {
            const contenedor = document.getElementById('contenedor-etiquetas-exportar');
            const tags = contenedor.querySelectorAll('.tag-tienda-exportar');
            const listaTiendas = (typeof LISTA_TIENDAS !== 'undefined' && LISTA_TIENDAS.length > 0)
                ? LISTA_TIENDAS
                : Object.keys(matrizTiendas || {});

            const seleccionarTodas = tiendasSeleccionadasExportar.size < listaTiendas.length;
            tiendasSeleccionadasExportar.clear();

            tags.forEach(tag => {
                const tienda = tag.dataset.tienda;
                if (seleccionarTodas) {
                    tiendasSeleccionadasExportar.add(tienda); // Agregar tienda al Set
                    tag.classList.add('activa'); // Estilo activo
                } else {
                    tag.classList.remove('activa'); // Estilo inactivo
                }
            });
        }

        // Cierra la ventana emergente
        function cerrarModalExportarTiendas() {
            document.getElementById('modal-exportar-tiendas').style.display = 'none'; // Ocultar modal
        }
