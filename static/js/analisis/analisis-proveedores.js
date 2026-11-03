        function mostrarOpcionesProvAnalisis() {
            const input = document.getElementById('buscar_proveedor_analisis'); // Campo de búsqueda

            // Si el input está en modo lectura (proveedor seleccionado), no despliega la lista
            if (input && input.readOnly) return;

            const dropdown = document.getElementById('opciones_proveedor_analisis'); // Contenedor del menú
            if (dropdown) dropdown.classList.remove('hidden'); // Muestra la lista desplegable
        }

        // Filtra los proveedores en tiempo real a medida que el usuario escribe
        function filtrarProveedoresAnalisis() {
            const input = document.getElementById('buscar_proveedor_analisis'); // Campo de texto
            const filtro = input.value.toLowerCase().trim(); // Convierte la búsqueda a minúsculas y quita espacios
            const opciones = document.querySelectorAll('.opcion-prov-analisis'); // Lista de opciones dinámicas
            const dropdown = document.getElementById('opciones_proveedor_analisis'); // Contenedor del menú

            dropdown.classList.remove('hidden'); // Mantiene visible el menú mientras se escribe

            opciones.forEach(opcion => {
                // Lee el nombre desde el data-nombre o el texto visible
                const nombre = (opcion.dataset.nombre || opcion.textContent).toLowerCase();

                // Compara si el texto escrito está incluido en el nombre del proveedor
                if (nombre.includes(filtro)) {
                    opcion.classList.remove('hidden'); // Muestra la opción si coincide
                } else {
                    opcion.classList.add('hidden'); // Oculta la opción si no coincide
                }
            });
        }

        // Cierra automáticamente el menú desplegable al hacer clic fuera del campo
        document.addEventListener('click', function (e) {
            const combo = document.getElementById('combo-proveedor-analisis'); // Contenedor padre
            const dropdown = document.getElementById('opciones_proveedor_analisis'); // Menú flotante

            // Si el clic ocurrió fuera del buscador y del menú, lo oculta
            if (combo && dropdown && !combo.contains(e.target)) {
                dropdown.classList.add('hidden');
            }
        });

        function navegarProveedoresAnalisis(e) {
            const dropdown = document.getElementById('opciones_proveedor_analisis');
            const opciones = Array.from(document.querySelectorAll('.opcion-prov-analisis')).filter(el => !el.classList.contains('hidden'));

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (dropdown.classList.contains('hidden')) mostrarOpcionesProvAnalisis();
                indiceDestacadoAnalisis = Math.min(indiceDestacadoAnalisis + 1, opciones.length - 1);
                resaltarOpcionAnalisis(opciones);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                indiceDestacadoAnalisis = Math.max(indiceDestacadoAnalisis - 1, 0);
                resaltarOpcionAnalisis(opciones);
            } else if (e.key === 'Enter') {
                if (!dropdown.classList.contains('hidden') && indiceDestacadoAnalisis >= 0 && opciones[indiceDestacadoAnalisis]) {
                    e.preventDefault();
                    opciones[indiceDestacadoAnalisis].click();
                }
            } else if (e.key === 'Escape') {
                dropdown.classList.add('hidden');
            }
        }

        function resaltarOpcionAnalisis(opciones) {
            opciones.forEach(op => op.classList.remove('bg-slate-100', 'text-slate-900', 'font-semibold'));
            if (opciones[indiceDestacadoAnalisis]) {
                opciones[indiceDestacadoAnalisis].classList.add('bg-slate-100', 'text-slate-900', 'font-semibold');
                opciones[indiceDestacadoAnalisis].scrollIntoView({ block: 'nearest' });
            }
        }

        // Variable global para almacenar la estructura de clasificación del proveedor activo
        let datosClasificacionAnalisis = [];

        // Filtra y reemplaza valores nulos, vacíos o cadenas 'None'/'null' por un guion '-'
        function limpiarValorBD(val) {
            if (!val || val === 'None' || val === 'null' || val === 'undefined') return '-';
            return val;
        }

        function posicionarListaMarcaModal() {
            const modal = document.getElementById('modal-productos-proveedor');
            const input = document.getElementById('buscar_marca_analisis');
            const lista = document.getElementById('opciones_marca_analisis');

            if (
                !modal || !input || !lista ||
                modal.classList.contains('hidden') ||
                lista.classList.contains('hidden')
            ) {
                return;
            }

            const rect = input.getBoundingClientRect();

            // Coloca la lista debajo del input, fuera del recorte del modal.
            lista.style.top = `${rect.bottom + 4}px`;
            lista.style.left = `${rect.left}px`;
            lista.style.width = `${rect.width}px`;

            // Limita la altura al espacio disponible en la pantalla.
            const espacio = window.innerHeight - rect.bottom - 12;

            lista.style.maxHeight =
                `${Math.max(0, Math.min(192, espacio))}px`;
        }

        // Mantiene la lista alineada al desplazar o redimensionar.
        window.addEventListener(
            'scroll', posicionarListaMarcaModal, true
        );

        window.addEventListener(
            'resize', posicionarListaMarcaModal
        );

        let solicitudClasificacionProductos = 0;
        let importandoProductosProveedor = false;
        let focoAntesModalProductos = null;

        function mostrarCargaClasificacionProductos(cargando) {
            document.getElementById('estado-carga-clasificacion-productos')
                .classList.toggle('hidden', !cargando);
            const seccion = document.getElementById('sec-filtros-clasificacion');
            seccion.setAttribute('aria-busy', String(cargando));
            seccion.inert = cargando || document.getElementById('btn_importar_productos').disabled;
        }

        function abrirModalProductosProveedor() {
            const proveedor = document.getElementById(
                'proveedor_id_analisis'
            ).value;

            const boton = document.getElementById('btn_importar_productos');

            if (!proveedor) {
                mostrarNotificacion({
                    tipo: 'info',
                    mensaje: 'Selecciona primero un proveedor.'
                });
                return;
            }

            const modal = document.getElementById('modal-productos-proveedor');

            if (!modal.classList.contains('hidden')) return;

            focoAntesModalProductos = document.activeElement;

            document.getElementById(
                'nombre-proveedor-modal-productos'
            ).textContent = document.getElementById(
                'buscar_proveedor_analisis'
            ).value;

            modal.classList.remove('hidden');
            modal.classList.add('flex');

            document.getElementById(boton.disabled
                ? 'btn-cerrar-productos-proveedor' : 'buscar_depto_analisis').focus();
        }

        function cerrarModalProductosProveedor() {
            // Evita cerrar mientras se están incorporando productos.
            if (importandoProductosProveedor) return;

            const modal = document.getElementById('modal-productos-proveedor');

            modal.classList.add('hidden');
            modal.classList.remove('flex');

            // Oculta las listas para la siguiente apertura.
            [
                'opciones_depto_analisis',
                'opciones_grupo_analisis',
                'opciones_subgrupo_analisis',
                'opciones_marca_analisis'
            ].forEach(id => {
                document.getElementById(id)?.classList.add('hidden');
            });

            const destino =
                focoAntesModalProductos?.isConnected &&
                    focoAntesModalProductos.getClientRects().length
                    ? focoAntesModalProductos
                    : document.querySelector('[x-ref="archivo"]');

            destino?.focus();
        }

        function tecladoModalProductosProveedor(evento) {
            // Impide que el teclado del modal controle la tabla.
            evento.stopPropagation();

            if (evento.key === 'Escape') {
                evento.preventDefault();
                cerrarModalProductosProveedor();
                return;
            }

            if (evento.key !== 'Tab') return;

            // Mantiene el foco dentro del modal.
            const controles = [
                ...evento.currentTarget.querySelectorAll(
                    'button:not(:disabled), input:not(:disabled):not([type="hidden"])'
                )
            ].filter(el => el.getClientRects().length && !el.closest('[inert]'));

            if (!controles.length) {
                evento.preventDefault();
                return;
            }

            const primero = controles[0];
            const ultimo = controles.at(-1);

            if (evento.shiftKey && document.activeElement === primero) {
                evento.preventDefault();
                ultimo.focus();
            } else if (!evento.shiftKey && document.activeElement === ultimo) {
                evento.preventDefault();
                primero.focus();
            }
        }

        async function confirmarProductosProveedor() {
            const boton = document.getElementById('btn_importar_productos');

            if (importandoProductosProveedor || boton.disabled) return;

            const seccion = document.getElementById('sec-filtros-clasificacion');
            const textoOriginal = boton.innerHTML;

            const botonesCerrar = [
                document.getElementById('btn-cerrar-productos-proveedor'),
                document.getElementById('btn-cancelar-productos-proveedor')
            ];

            importandoProductosProveedor = true;
            boton.disabled = true;
            boton.textContent = 'Importando…';

            botonesCerrar.forEach(btn => btn.disabled = true);
            seccion.classList.add('pointer-events-none');

            try {
                const correcto = await importarProductosAnalisis();

                if (correcto) {
                    importandoProductosProveedor = false;
                    cerrarModalProductosProveedor();
                }
            } finally {
                importandoProductosProveedor = false;
                boton.disabled = false;
                boton.innerHTML = textoOriginal;

                botonesCerrar.forEach(btn => btn.disabled = false);
                seccion.classList.remove('pointer-events-none');
            }
        }

        // Extrae los datos sanitizados desde los atributos data-* del elemento
        function seleccionarProveedorDesdeElemento(el) {
            const d = el.dataset; // Lee los atributos data-* en notación camello
            seleccionarProveedorAnalisis(
                d.id || '',
                d.nombre || '',
                d.contacto || '',
                d.telefono || '',
                d.diasCredito || '',
                d.frecuencia || '',
                d.etiquetas || ''
            );
        }

        // --- SELECCIÓN LIMPIA Y CARGA AUTOMÁTICA DEL PROVEEDOR DESDE LA BD ---
        async function seleccionarProveedorAnalisis(id, nombre) {
            const seleccion = ++solicitudClasificacionProductos;
            const inputBuscar = document.getElementById('buscar_proveedor_analisis'); // Campo de búsqueda visible
            const inputId = document.getElementById('proveedor_id_analisis'); // Campo de ID oculto

            if (inputId) inputId.value = id;
            if (inputBuscar) {
                inputBuscar.value = id ? nombre : '';
                inputBuscar.readOnly = !!id; // Bloquea la edición del campo si hay un proveedor seleccionado
                if (id) {
                    inputBuscar.classList.add('bg-slate-100', 'cursor-default');
                } else {
                    inputBuscar.classList.remove('bg-slate-100', 'cursor-default');
                }
            }

            const dropdown = document.getElementById('opciones_proveedor_analisis');
            if (dropdown) dropdown.classList.add('hidden'); // Oculta el menú desplegable

            const secFiltros = document.getElementById('sec-filtros-clasificacion');
            const inpDepto = document.getElementById('buscar_depto_analisis');
            const btnImportar = document.getElementById('btn_importar_productos');

            if (typeof limpiarDeptoAnalisis === 'function') limpiarDeptoAnalisis();

            // Evita conservar una marca del proveedor anterior.
            limpiarMarcaAnalisis();

            // Si se limpia el proveedor (ID vacío), resetea el formulario
            if (!id) {
                if (secFiltros) secFiltros.classList.add('opacity-50', 'pointer-events-none');
                if (inpDepto) inpDepto.disabled = true;
                if (btnImportar) btnImportar.disabled = true;
                datosClasificacionAnalisis = [];
                mostrarCargaClasificacionProductos(false);

                if (document.getElementById('prov_contacto')) document.getElementById('prov_contacto').value = '-';
                if (document.getElementById('prov_telefono')) document.getElementById('prov_telefono').value = '-';
                if (document.getElementById('prov_dias_credito')) document.getElementById('prov_dias_credito').value = '-';
                if (document.getElementById('prov_frecuencia')) document.getElementById('prov_frecuencia').value = '-';

                const contEtiquetas = document.getElementById('prov_etiquetas');
                if (contEtiquetas) contEtiquetas.innerHTML = '<span class="text-xs text-slate-400 italic">Sin proveedor seleccionado</span>';
                return;
            }

            // Se habilitan cuando termine de cargar la clasificación.
            if (secFiltros) secFiltros.classList.add('opacity-50', 'pointer-events-none');
            if (inpDepto) inpDepto.disabled = true;
            if (btnImportar) btnImportar.disabled = true;
            datosClasificacionAnalisis = [];
            mostrarCargaClasificacionProductos(true);
            abrirModalProductosProveedor();

            try {
                // Consulta asíncrona a la API de FastAPI
                const respuesta = await fetch(`/api/proveedores/${id}`);
                if (respuesta.ok) {
                    const data = await respuesta.json();
                    // Evita mostrar información de una selección anterior.
                    if (seleccion !== solicitudClasificacionProductos || String(inputId.value) !== String(id)) return;

                    // Vuelca los datos obtenidos de Supabase a los inputs del HTML
                    const elemContacto = document.getElementById('prov_contacto');
                    const elemTelefono = document.getElementById('prov_telefono');
                    const elemCredito = document.getElementById('prov_dias_credito');
                    const elemFrecuencia = document.getElementById('prov_frecuencia');

                    if (elemContacto) elemContacto.value = data.contacto || '-';
                    if (elemTelefono) elemTelefono.value = data.telefono || '-';
                    if (elemCredito) elemCredito.value = (data.dias_credito !== undefined && data.dias_credito !== null && data.dias_credito !== '') ? data.dias_credito : '-';
                    if (elemFrecuencia) elemFrecuencia.value = data.frecuencia || '-';

                    // Dibuja las etiquetas/categorías
                    const contEtiquetas = document.getElementById('prov_etiquetas');
                    if (contEtiquetas) {
                        contEtiquetas.innerHTML = '';
                        const etiquetas = data.etiquetas || '';
                        if (etiquetas && etiquetas.length > 0) {
                            const lista = typeof etiquetas === 'string' ? etiquetas.split(',') : etiquetas;
                            lista.forEach(tag => {
                                const badge = document.createElement('span');
                                badge.className = 'px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg text-[11px] font-semibold';
                                badge.textContent = String(tag).trim();
                                contEtiquetas.appendChild(badge);
                            });
                        } else {
                            contEtiquetas.innerHTML = '<span class="text-xs text-slate-400 italic">Sin etiquetas</span>';
                        }
                    }
                }
            } catch (error) {
                console.error("Error al obtener los datos del proveedor:", error);
            }

            if (seleccion !== solicitudClasificacionProductos || String(inputId.value) !== String(id)) return;

            await cargarClasificacionProveedor(id);
        }

        function limpiarProveedorAnalisis() {
            seleccionarProveedorAnalisis('', ''); // Llama a la selección vacía para restablecer los inputs y desbloquear el campo

            const inputBuscar = document.getElementById('buscar_proveedor_analisis');
            if (inputBuscar) {
                inputBuscar.value = ''; // Limpia el texto
                inputBuscar.focus(); // Coloca el cursor listo para escribir una nueva búsqueda
            }
        }

        // Maneja el flujo visual y estados del botón 'Calcular Sugerido'
        async function ejecutarCalculoSugeridoConSpinner() {
            const btn = document.getElementById('btn-calcular-sugerido');
            const icono = document.getElementById('icono-btn-calcular');
            const texto = document.getElementById('texto-btn-calcular');

            if (!btn) return;

            // Deshabilita el botón y cambia el icono por un Spinner activo
            btn.disabled = true;
            icono.className = 'fa-solid fa-spinner fa-spin';
            texto.textContent = 'Calculado...'; // Muestra estado inicial de cálculo

            // Simula la transición hacia la carga a la tabla
            setTimeout(async () => {
                texto.textContent = 'Cargando a la tabla...'; // Muestra estado de inserción en tabla

                try {
                    if (typeof calcularSugeridoSedeActual === 'function') {
                        await calcularSugeridoSedeActual();
                    }
                } catch (e) {
                    console.error('Error durante el cálculo:', e);
                } finally {
                    // Restablece el botón a su estado original al terminar
                    setTimeout(() => {
                        icono.className = 'fa-solid fa-bolt';
                        texto.textContent = 'Calcular Sugerido';
                        btn.disabled = false;
                    }, 300);
                }
            }, 400);
        }

        async function cargarClasificacionProveedor(proveedorId) {
            const solicitud = ++solicitudClasificacionProductos;
            const boton = document.getElementById('btn_importar_productos');
            const seccion = document.getElementById('sec-filtros-clasificacion');

            boton.disabled = true;
            seccion.classList.add('opacity-50', 'pointer-events-none');
            mostrarCargaClasificacionProductos(true);

            try {
                const res = await fetch(
                    '/api/clasificacion?proveedor_id=' +
                    encodeURIComponent(proveedorId)
                );

                if (!res.ok) {
                    throw new Error('No se pudieron cargar los filtros.');
                }

                const datos = await res.json();

                // Descarta respuestas de un proveedor que ya no está seleccionado.
                if (
                    solicitud !== solicitudClasificacionProductos ||
                    String(
                        document.getElementById('proveedor_id_analisis').value
                    ) !== String(proveedorId)
                ) {
                    return false;
                }

                if (!Array.isArray(datos)) {
                    throw new Error('La clasificación recibida no es válida.');
                }

                datosClasificacionAnalisis = datos;
                poblarDepartamentosAnalisis();
                poblarMarcasAnalisis();

                seccion.classList.remove('opacity-50', 'pointer-events-none');
                document.getElementById('buscar_depto_analisis').disabled = false;
                boton.disabled = false;

                return true;

            } catch (error) {
                if (solicitud === solicitudClasificacionProductos) {
                    mostrarNotificacion({
                        tipo: 'error',
                        mensaje: error.message
                    });
                }

                return false;
            } finally {
                if (solicitud === solicitudClasificacionProductos) {
                    mostrarCargaClasificacionProductos(false);
                }
            }
        }

        function poblarDepartamentosAnalisis() {
            const container = document.getElementById('opciones_depto_analisis');
            const deptos = [...new Set(datosClasificacionAnalisis.map(item => item.departamento))].filter(Boolean);

            let html = `<div onclick="seleccionarDeptoAnalisis('', 'Todos los departamentos')" class="px-4 py-2 text-sm text-slate-400 hover:bg-slate-50 cursor-pointer border-b border-slate-100">Todos los departamentos</div>`;
            deptos.forEach(d => {
                html += `<div onclick="seleccionarDeptoAnalisis('${d}', '${d}')" data-nombre="${d.toLowerCase()}" class="opcion-depto-analisis px-4 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-600 cursor-pointer">${d}</div>`;
            });
            container.innerHTML = html;
        }

        function seleccionarDeptoAnalisis(val, label) {
            document.getElementById('depto_analisis').value = val;
            document.getElementById('buscar_depto_analisis').value = val ? label : '';
            document.getElementById('opciones_depto_analisis').classList.add('hidden');

            limpiarGrupoAnalisis();

            const inpGrupo = document.getElementById('buscar_grupo_analisis');
            if (val) {
                inpGrupo.disabled = false;
                poblarGruposAnalisis(val);
            } else {
                inpGrupo.disabled = true;
            }
            poblarMarcasAnalisis(); // Refresca las marcas según el departamento
        }

        function poblarGruposAnalisis(deptoSel) {
            const container = document.getElementById('opciones_grupo_analisis');
            const grupos = [...new Set(datosClasificacionAnalisis.filter(item => item.departamento === deptoSel).map(item => item.grupo))].filter(Boolean);

            let html = `<div onclick="seleccionarGrupoAnalisis('', 'Todos los grupos')" class="px-4 py-2 text-sm text-slate-400 hover:bg-slate-50 cursor-pointer border-b border-slate-100">Todos los grupos</div>`;
            grupos.forEach(g => {
                html += `<div onclick="seleccionarGrupoAnalisis('${g}', '${g}')" data-nombre="${g.toLowerCase()}" class="opcion-grupo-analisis px-4 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-600 cursor-pointer">${g}</div>`;
            });
            container.innerHTML = html;
        }

        function seleccionarGrupoAnalisis(val, label) {
            document.getElementById('grupo_analisis').value = val;
            document.getElementById('buscar_grupo_analisis').value = val ? label : '';
            document.getElementById('opciones_grupo_analisis').classList.add('hidden');

            limpiarSubgrupoAnalisis();

            const inpSubgrupo = document.getElementById('buscar_subgrupo_analisis');
            if (val) {
                inpSubgrupo.disabled = false;
                poblarSubgruposAnalisis(document.getElementById('depto_analisis').value, val);
            } else {
                inpSubgrupo.disabled = true;
            }
            poblarMarcasAnalisis(); // Refresca las marcas según el grupo
        }

        function poblarSubgruposAnalisis(deptoSel, grupoSel) {
            const container = document.getElementById('opciones_subgrupo_analisis');
            const subgrupos = [...new Set(datosClasificacionAnalisis.filter(item => item.departamento === deptoSel && item.grupo === grupoSel).map(item => item.subgrupo))].filter(Boolean);

            let html = `<div onclick="seleccionarSubgrupoAnalisis('', 'Todos los subgrupos')" class="px-4 py-2 text-sm text-slate-400 hover:bg-slate-50 cursor-pointer border-b border-slate-100">Todos los subgrupos</div>`;
            subgrupos.forEach(s => {
                html += `<div onclick="seleccionarSubgrupoAnalisis('${s}', '${s}')" data-nombre="${s.toLowerCase()}" class="opcion-subgrupo-analisis px-4 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-600 cursor-pointer">${s}</div>`;
            });
            container.innerHTML = html;
        }

        function seleccionarSubgrupoAnalisis(val, label) {
            document.getElementById('subgrupo_analisis').value = val;
            document.getElementById('buscar_subgrupo_analisis').value = val ? label : '';
            document.getElementById('opciones_subgrupo_analisis').classList.add('hidden');
            poblarMarcasAnalisis(); // Refresca las marcas según el subgrupo
        }

        // --- LÓGICA DEL FILTRO DE MARCA ---
        // Actualiza el listado de marcas según los filtros de depto, grupo y subgrupo seleccionados
        function poblarMarcasAnalisis() {
            const container = document.getElementById('opciones_marca_analisis');
            if (!container) return;

            // Obtiene los valores actualmente seleccionados en la cascada
            const deptoSel = document.getElementById('depto_analisis')?.value || '';
            const grupoSel = document.getElementById('grupo_analisis')?.value || '';
            const subgrupoSel = document.getElementById('subgrupo_analisis')?.value || '';

            // Si depto, grupo y subgrupo están vacíos, usa todo el universo del proveedor; si hay selección, filtra
            let itemsFiltrados = datosClasificacionAnalisis;
            if (deptoSel) itemsFiltrados = itemsFiltrados.filter(item => item.departamento === deptoSel);
            if (grupoSel) itemsFiltrados = itemsFiltrados.filter(item => item.grupo === grupoSel);
            if (subgrupoSel) itemsFiltrados = itemsFiltrados.filter(item => item.subgrupo === subgrupoSel);

            // Extrae marcas únicas del conjunto filtrado y las ordena alfabéticamente
            const marcas = [...new Set(itemsFiltrados.map(item => item.marca))].filter(Boolean).sort();

            // Si había una marca seleccionada que ya no pertenece al nuevo filtro, se resetea
            const marcaActual = document.getElementById('marca_analisis')?.value || '';
            if (marcaActual && !marcas.includes(marcaActual)) {
                limpiarMarcaAnalisis();
            }

            // Renderiza la lista desplegable
            let html = `<div onclick="seleccionarMarcaAnalisis('', 'Todas las marcas')" class="px-4 py-2 text-sm text-slate-400 hover:bg-slate-50 cursor-pointer border-b border-slate-100">Todas las marcas</div>`;
            marcas.forEach(m => {
                html += `<div onclick="seleccionarMarcaAnalisis('${m}', '${m}')" data-nombre="${m.toLowerCase()}" class="opcion-marca-analisis px-4 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-600 cursor-pointer">${m}</div>`;
            });
            container.innerHTML = html;
        }

        // Asigna el valor seleccionado al input oculto y cierra el menú
        function seleccionarMarcaAnalisis(val, label) {
            document.getElementById('marca_analisis').value = val;
            document.getElementById('buscar_marca_analisis').value = val ? label : '';
            document.getElementById('opciones_marca_analisis').classList.add('hidden');
        }

        // Filtra las opciones de marca visibles en tiempo real
        function filtrarMarcasAnalisis() {
            const texto = document.getElementById('buscar_marca_analisis').value.toLowerCase().trim();
            document.querySelectorAll('.opcion-marca-analisis').forEach(op => {
                op.classList.toggle('hidden', !op.getAttribute('data-nombre').includes(texto));
            });
            document.getElementById('opciones_marca_analisis').classList.remove('hidden');
        }

        // Muestra el desplegable de marcas
        function mostrarOpcionesMarcaAnalisis() {
            document.getElementById('opciones_marca_analisis').classList.remove('hidden');
        }

        // Restablece el campo de marca
        function limpiarMarcaAnalisis() {
            document.getElementById('marca_analisis').value = '';
            document.getElementById('buscar_marca_analisis').value = '';
            document.getElementById('opciones_marca_analisis').classList.add('hidden');
        }

        // Funciones de filtro de texto para los combos
        function filtrarDeptosAnalisis() {
            const texto = document.getElementById('buscar_depto_analisis').value.toLowerCase().trim();
            document.querySelectorAll('.opcion-depto-analisis').forEach(op => {
                op.classList.toggle('hidden', !op.getAttribute('data-nombre').includes(texto));
            });
            document.getElementById('opciones_depto_analisis').classList.remove('hidden');
        }
        function mostrarOpcionesDeptoAnalisis() {
            document.getElementById('opciones_depto_analisis').classList.remove('hidden');
        }

        function filtrarGruposAnalisis() {
            const texto = document.getElementById('buscar_grupo_analisis').value.toLowerCase().trim();
            document.querySelectorAll('.opcion-grupo-analisis').forEach(op => {
                op.classList.toggle('hidden', !op.getAttribute('data-nombre').includes(texto));
            });
            document.getElementById('opciones_grupo_analisis').classList.remove('hidden');
        }
        function mostrarOpcionesGrupoAnalisis() {
            document.getElementById('opciones_grupo_analisis').classList.remove('hidden');
        }

        function filtrarSubgruposAnalisis() {
            const texto = document.getElementById('buscar_subgrupo_analisis').value.toLowerCase().trim();
            document.querySelectorAll('.opcion-subgrupo-analisis').forEach(op => {
                op.classList.toggle('hidden', !op.getAttribute('data-nombre').includes(texto));
            });
            document.getElementById('opciones_subgrupo_analisis').classList.remove('hidden');
        }
        function mostrarOpcionesSubgrupoAnalisis() {
            document.getElementById('opciones_subgrupo_analisis').classList.remove('hidden');
        }

        // Limpieza de combos
        function limpiarDeptoAnalisis() {
            document.getElementById('depto_analisis').value = '';
            document.getElementById('buscar_depto_analisis').value = '';
            document.getElementById('opciones_depto_analisis').classList.add('hidden');
            limpiarGrupoAnalisis();
            poblarMarcasAnalisis(); // Refresca marcas con la cascada limpia
        }

        function limpiarGrupoAnalisis() {
            document.getElementById('grupo_analisis').value = '';
            document.getElementById('buscar_grupo_analisis').value = '';
            document.getElementById('opciones_grupo_analisis').classList.add('hidden');
            limpiarSubgrupoAnalisis(); // Limpia subgrupo en cadena
            poblarMarcasAnalisis(); // Refresca las marcas disponibles
        }

        function limpiarSubgrupoAnalisis() {
            document.getElementById('subgrupo_analisis').value = '';
            document.getElementById('buscar_subgrupo_analisis').value = '';
            document.getElementById('opciones_subgrupo_analisis').classList.add('hidden');
            poblarMarcasAnalisis(); // Refresca las marcas disponibles
        }

        // --- IMPORTACIÓN MASIVA DE PRODUCTOS A LA TABLA ---
        async function importarProductosAnalisis() {
            const proveedorId = document.getElementById(
                'proveedor_id_analisis'
            ).value;

            if (!proveedorId) return;

            const depto = document.getElementById(
                'depto_analisis'
            ).value;

            const grupo = document.getElementById(
                'grupo_analisis'
            ).value;

            const subgrupo = document.getElementById(
                'subgrupo_analisis'
            ).value;

            const marca = document.getElementById(
                'marca_analisis'
            ).value;

            const params = new URLSearchParams({
                proveedor_id: proveedorId,
                departamento: depto,
                grupo: grupo,
                subgrupo: subgrupo,
                marca: marca
            });

            try {
                const res = await fetch(
                    `/api/productos/importar-analisis?${params.toString()}`
                );

                if (!res.ok) {
                    throw new Error(
                        'No se pudo obtener la lista de productos.'
                    );
                }

                const productos = await res.json();

                if (
                    !Array.isArray(productos)
                    || productos.length === 0
                ) {
                    await mostrarAlerta({
                        tipo: 'info',
                        titulo: 'Sin resultados',
                        mensaje: 'No se encontraron productos para los filtros seleccionados.'
                    });

                    return;
                }

                const tbody = document.getElementById(
                    'filas-tabla-analisis'
                );

                // ========================================================
                // 1. OBTENER CÓDIGOS YA PRESENTES EN LA TABLA
                // ========================================================

                const codigosExistentes = new Set(
                    Array.from(
                        tbody.querySelectorAll('.inp-codigo')
                    )
                        .map(input =>
                            normalizarCodigoAnalisis(input.value)
                        )
                        .filter(Boolean)
                );

                // ========================================================
                // 2. ELIMINAR DUPLICADOS DEL RESULTADO DEL FILTRO
                //    Y OMITIR LOS QUE YA ESTÁN EN LA TABLA
                // ========================================================

                const productosNuevos = [];
                const codigosImportados = new Set();

                for (const prod of productos) {
                    const codigo = normalizarCodigoAnalisis(
                        prod.codigo
                    );

                    if (!codigo) continue;

                    // Ya existe en la tabla.
                    if (codigosExistentes.has(codigo)) {
                        continue;
                    }

                    // Evita duplicados dentro de la misma respuesta.
                    if (codigosImportados.has(codigo)) {
                        continue;
                    }

                    codigosImportados.add(codigo);

                    productosNuevos.push({
                        ...prod,
                        codigo
                    });
                }

                if (productosNuevos.length === 0) {
                    mostrarNotificacion({
                        tipo: 'info',
                        mensaje: 'Los productos de estos filtros ya están en la tabla.'
                    });

                    return false;
                }

                // ========================================================
                // 3. REUTILIZAR FILAS VACÍAS ANTES DE CREAR NUEVAS
                // ========================================================

                const filasVacias = Array.from(
                    tbody.querySelectorAll('tr')
                ).filter(tr => {
                    const inpCod = tr.querySelector('.inp-codigo');

                    return (
                        inpCod
                        && !normalizarCodigoAnalisis(
                            inpCod.value
                        )
                    );
                });

                // ========================================================
                // 4. INSERTAR SOLAMENTE LOS PRODUCTOS QUE FALTAN
                // ========================================================

                productosNuevos.forEach((prod, index) => {
                    let tr = filasVacias[index];

                    if (!tr) {
                        tr = agregarFilaAnalisis();
                    }

                    const inpCod = tr.querySelector('.inp-codigo');
                    const inpDesc = tr.querySelector('.inp-desc');
                    const inpPre = tr.querySelector('.inp-pre');
                    const inpCosto = tr.querySelector('.inp-costo');
                    const inpEmp = tr.querySelector('.inp-emp');

                    inpCod.value = prod.codigo;
                    inpDesc.value = prod.descripcion || '';
                    inpPre.value = prod.unidad_manejo || 1;
                    inpCosto.value = Number(
                        prod.precio || 0
                    ).toFixed(2);

                    inpPre.dataset.original =
                        inpPre.value;

                    inpCosto.dataset.original =
                        inpCosto.value;

                    inpEmp.value = 0;

                    bloquearCeldaCodigo(inpCod);
                });

                // Una sola recalculación al finalizar la importación.
                totalizarAnalisis();
                // Permite cerrar el modal después de importar correctamente.
                return true;

            } catch (e) {
                console.error(
                    'Error al importar productos:',
                    e
                );

                await mostrarAlerta({
                    tipo: 'error',
                    titulo: 'Error al importar',
                    mensaje: 'Ocurrió un error al importar los productos.'
                });
            }
        }

        // Cierra desplegables al hacer clic fuera
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#combo-proveedor-analisis')) {
                document.getElementById('opciones_proveedor_analisis')?.classList.add('hidden');
            }
            if (!e.target.closest('#combo-tienda-analisis')) {
                document.getElementById('opciones_tienda_analisis')?.classList.add('hidden');
            }
            if (!e.target.closest('#combo-depto-analisis')) {
                document.getElementById('opciones_depto_analisis')?.classList.add('hidden');
            }
            if (!e.target.closest('#combo-grupo-analisis')) {
                document.getElementById('opciones_grupo_analisis')?.classList.add('hidden');
            }
            if (!e.target.closest('#combo-subgrupo-analisis')) {
                document.getElementById('opciones_subgrupo_analisis')?.classList.add('hidden');
            }
            // Oculta el desplegable de marca al hacer clic fuera
            if (!e.target.closest('#combo-marca-analisis')) {
                document.getElementById('opciones_marca_analisis')?.classList.add('hidden');
            }
        });
