

    // Respaldo cuando el modal global de confirmación no está disponible.
    if (typeof window.mostrarConfirmacion !== 'function') {
        window.mostrarConfirmacion = async function (opciones = {}) {
            const titulo = opciones.titulo || 'Confirmación';
            const mensaje = opciones.mensaje || '';
            const textoCancelar = opciones.textoCancelar;

            // Los mensajes informativos solo requieren aceptar.
            if (!textoCancelar) {
                window.alert(`${titulo}\n\n${mensaje}`);
                return true;
            }

            // Las acciones destructivas requieren confirmación explícita.
            return window.confirm(`${titulo}\n\n${mensaje}`);
        };
    }
    /* =========================================================
       CREAR INVENTARIOS EN VARIAS TIENDAS
       ========================================================= */
    (function () {
        'use strict';

        const modal = document.getElementById('modal-multitienda');
        const formulario = document.getElementById('form-multitienda');

        // No interferir con páginas que no tengan este modal.
        if (!modal || !formulario) return;

        const nombre = document.getElementById('multi-nombre');

        const comboProveedor = document.getElementById('multi-combo-proveedor');
        const opcionesProveedor = document.getElementById('multi-opciones-proveedor');
        const limpiarProveedor = document.getElementById('multi-limpiar-proveedor');

        let proveedoresMultitienda = [];
        let indiceProveedorMultitienda = -1;

        // Normalizar el texto para buscar sin distinguir acentos ni mayúsculas.
        function normalizarProveedor(texto) {
            return String(texto || '')
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .toLowerCase()
                .trim();
        }

        // Cargar la lista de proveedores desde el servidor.
        async function cargarProveedoresMultitienda() {
            if (proveedoresMultitienda.length) {
                renderizarOpcionesProveedor(nombre.value);
                return;
            }

            try {
                const respuesta = await fetch('/api/proveedores', {
                    credentials: 'same-origin'
                });

                if (!respuesta.ok) {
                    throw new Error('No se pudieron cargar los proveedores.');
                }

                const datos = await respuesta.json();
                proveedoresMultitienda = Array.isArray(datos) ? datos : [];

                renderizarOpcionesProveedor(nombre.value);
            } catch (error) {
                console.error('Error cargando proveedores multitienda:', error);
                opcionesProveedor.classList.add('hidden');
                mostrarEstado(
                    estadoValidacion,
                    'No se pudieron cargar los proveedores. Inténtalo nuevamente.',
                    'error'
                );
            }
        }

        // Dibujar las coincidencias del buscador.
        function renderizarOpcionesProveedor(filtro = '') {
            opcionesProveedor.replaceChildren();
            indiceProveedorMultitienda = -1;

            const busqueda = normalizarProveedor(filtro);
            const coincidencias = proveedoresMultitienda.filter(proveedor =>
                normalizarProveedor(proveedor?.nombre).includes(busqueda)
            );

            coincidencias.forEach(proveedor => {
                const nombreProveedor = String(proveedor?.nombre || '').trim();
                if (!nombreProveedor) return;

                const opcion = document.createElement('button');
                opcion.type = 'button';
                opcion.className =
                    'block w-full px-4 py-2.5 text-left text-sm text-slate-700 ' +
                    'hover:bg-indigo-50 hover:text-indigo-700';
                opcion.textContent = nombreProveedor;

                opcion.addEventListener('click', () => {
                    seleccionarProveedorMultitienda(nombreProveedor);
                });

                opcionesProveedor.appendChild(opcion);
            });

            if (!coincidencias.length) {
                const vacio = document.createElement('div');
                vacio.className = 'px-4 py-3 text-sm text-slate-500';
                vacio.textContent = 'No se encontraron proveedores.';
                opcionesProveedor.appendChild(vacio);
            }

            opcionesProveedor.classList.remove('hidden');
        }

        // Seleccionar un proveedor existente.
        function seleccionarProveedorMultitienda(nombreProveedor) {
            nombre.value = nombreProveedor;
            nombre.readOnly = true;
            nombre.classList.add('bg-slate-100', 'cursor-default');
            limpiarProveedor.classList.remove('hidden');
            opcionesProveedor.classList.add('hidden');

            actualizarBotonCrear();
        }

        // Limpiar la selección para buscar otro proveedor.
        limpiarProveedor.addEventListener('click', () => {
            nombre.value = '';
            nombre.readOnly = false;
            nombre.classList.remove('bg-slate-100', 'cursor-default');
            limpiarProveedor.classList.add('hidden');
            opcionesProveedor.classList.add('hidden');

            actualizarBotonCrear();
            nombre.focus();
        });

        // Filtrar automáticamente mientras se escribe.
        nombre.addEventListener('input', () => {
            productosValidados = null;
            actualizarBotonCrear();
            cargarProveedoresMultitienda().then(() => {
                if (!nombre.readOnly) {
                    renderizarOpcionesProveedor(nombre.value);
                }
            });
        });

        // Mostrar proveedores al entrar en el campo.
        nombre.addEventListener('focus', () => {
            if (nombre.readOnly) return;

            cargarProveedoresMultitienda().then(() => {
                if (!nombre.readOnly) {
                    renderizarOpcionesProveedor(nombre.value);
                }
            });
        });

        // Cerrar las opciones al hacer clic fuera del buscador.
        document.addEventListener('click', evento => {
            if (!comboProveedor.contains(evento.target)) {
                opcionesProveedor.classList.add('hidden');
            }
        });

        // Permitir cerrar el desplegable con Escape.
        nombre.addEventListener('keydown', evento => {
            if (evento.key === 'Escape') {
                opcionesProveedor.classList.add('hidden');
            }
        });

        const responsable = document.getElementById('multi-realizado-por');
        const contadorTiendas = document.getElementById('multi-conteo-tiendas');
        const listaTiendas = document.getElementById('multi-lista-tiendas');
        const codigosTexto = document.getElementById('multi-codigos');
        const botonCrear = document.getElementById('multi-btn-crear');
        const estadoValidacion = document.getElementById('multi-estado-validacion');
        const resultadosValidacion = document.getElementById('multi-resultados-validacion');
        const listaProductos = document.getElementById('multi-lista-productos');
        const estadoCreacion = document.getElementById('multi-estado-creacion');
        const resultadosCreacion = document.getElementById('multi-resultados-creacion');
        const listaInventarios = document.getElementById('multi-lista-inventarios');

        const almacenamientoClave = 'stellar_multitienda_pendiente_v1';

        let productosValidados = null;
        let solicitudPendiente = null;
        let validando = false;
        let creando = false;
        let codigosProveedor = [];
        const tipoCarga = () => formulario.querySelector('[name="multi-tipo-carga"]:checked')?.value || 'manual';
        const importador = window.crearImportadorMultitienda({
            obtenerProveedores: async () => {
                await cargarProveedoresMultitienda();
                opcionesProveedor.classList.add('hidden');
                if (!proveedoresMultitienda.length) throw new Error('No se pudieron cargar los proveedores. Vuelve a intentarlo.');
                return proveedoresMultitienda;
            },
            alImportar: async (codigos, proveedor) => {
                if (creando || validando || tipoCarga() !== 'proveedor') throw new Error('Espera a que termine la operación actual.');
                codigosProveedor = codigos;
                if (!nombre.value.trim()) seleccionarProveedorMultitienda(proveedor.nombre);
                invalidarValidacion();
                document.getElementById('multi-resumen-importacion').textContent = `${proveedor.nombre}: ${codigos.length} productos seleccionados.`;
                await validarProductos();
            }
        });

        function abrirImportador() {
            if (!creando && !validando) importador.abrir(nombre.value.trim());
        }
        document.getElementById('multi-abrir-importador').addEventListener('click', abrirImportador);
        formulario.querySelectorAll('[name="multi-tipo-carga"]').forEach(radio => {
            radio.addEventListener('change', () => {
                if (creando || validando) {
                    formulario.querySelector(`[name="multi-tipo-carga"][value="${radio.value === 'manual' ? 'proveedor' : 'manual'}"]`).checked = true;
                    return;
                }
                clearTimeout(temporizadorValidacion);
                const manual = tipoCarga() === 'manual';
                document.getElementById('multi-carga-manual').classList.toggle('hidden', !manual);
                document.getElementById('multi-carga-proveedor').classList.toggle('hidden', manual);
                codigosTexto.required = manual;
                codigosTexto.disabled = !manual;
                invalidarValidacion();
                if (manual) {
                    if (obtenerCodigos().length) validarProductos();
                } else abrirImportador();
            });
        });

        function mostrarEstado(elemento, mensaje, tipo) {
            elemento.textContent = mensaje;
            elemento.classList.remove(
                'hidden',
                'border-emerald-200', 'bg-emerald-50', 'text-emerald-800',
                'border-rose-200', 'bg-rose-50', 'text-rose-800',
                'border-amber-200', 'bg-amber-50', 'text-amber-800',
                'border-slate-200', 'bg-slate-50', 'text-slate-700'
            );

            const estilos = {
                exito: ['border-emerald-200', 'bg-emerald-50', 'text-emerald-800'],
                error: ['border-rose-200', 'bg-rose-50', 'text-rose-800'],
                aviso: ['border-amber-200', 'bg-amber-50', 'text-amber-800'],
                info: ['border-slate-200', 'bg-slate-50', 'text-slate-700']
            };

            elemento.classList.add(...(estilos[tipo] || estilos.info));
        }

        function ocultarEstado(elemento) {
            elemento.classList.add('hidden');
            elemento.textContent = '';
        }

        function obtenerTiendas() {
            return Array.from(
                listaTiendas.querySelectorAll('.multi-tienda-checkbox:checked')
            ).map(c => c.value);
        }


        function obtenerCodigos() {
            if (tipoCarga() === 'proveedor') return [...codigosProveedor];
            // Normalizar cada código a 6 dígitos antes de consultar.
            return [...new Set(
                codigosTexto.value
                    .split(/[\n,;]+/)
                    .map(c => c.trim())
                    .filter(Boolean)
                    .map(c => /^\d+$/.test(c) && c.length <= 6
                        ? c.padStart(6, '0')
                        : c
                    )
            )];
        }


        function obtenerDatosFormulario() {
            return {
                nombre: nombre.value.trim(),
                realizado_por: responsable.value.trim(),
                tiendas: obtenerTiendas(),
                codigos: obtenerCodigos()
            };
        }

        function firmaDatos(datos) {
            return JSON.stringify({
                nombre: datos.nombre,
                realizado_por: datos.realizado_por,
                tiendas: datos.tiendas,
                codigos: datos.codigos
            });
        }

        function guardarSolicitud(solicitud) {
            solicitudPendiente = solicitud;

            try {
                sessionStorage.setItem(
                    almacenamientoClave,
                    JSON.stringify(solicitud)
                );
            } catch (error) {
                // La solicitud se conserva en memoria si el almacenamiento falla.
            }
        }

        function recuperarSolicitud() {
            if (solicitudPendiente) return solicitudPendiente;

            try {
                const guardada = sessionStorage.getItem(almacenamientoClave);
                if (!guardada) return null;

                const solicitud = JSON.parse(guardada);

                if (
                    solicitud &&
                    typeof solicitud.firma === 'string' &&
                    solicitud.datos &&
                    Array.isArray(solicitud.claves)
                ) {
                    solicitudPendiente = solicitud;
                    return solicitud;
                }
            } catch (error) {
                // Ignorar datos de recuperación dañados.
            }

            return null;
        }

        function borrarSolicitudPendiente() {
            solicitudPendiente = null;

            try {
                sessionStorage.removeItem(almacenamientoClave);
            } catch (error) {
                // No es necesario interrumpir la interfaz.
            }
        }

        function invalidarValidacion() {
            productosValidados = null;
            botonCrear.disabled = true;
            resultadosValidacion.classList.add('hidden');
            listaProductos.replaceChildren();
            ocultarEstado(estadoValidacion);
            ocultarEstado(estadoCreacion);
            resultadosCreacion.classList.add('hidden');
            listaInventarios.replaceChildren();

            // Si cambiaron los datos, las claves anteriores ya no corresponden.
            const pendiente = recuperarSolicitud();
            if (pendiente && pendiente.firma !== firmaDatos(obtenerDatosFormulario())) {
                borrarSolicitudPendiente();
            }
        }


        function actualizarTiendas() {
            const total = obtenerTiendas().length;

            contadorTiendas.textContent =
                `${total} ${total === 1 ? 'seleccionada' : 'seleccionadas'}`;

            actualizarBotonCrear();
        }


        function actualizarBotonCrear() {
            const datos = obtenerDatosFormulario();
            if (productosValidados && JSON.stringify(productosValidados.codigos) === JSON.stringify(datos.codigos)) {
                productosValidados.firma = firmaDatos(datos);
            }
            const pendiente = recuperarSolicitud();
            const mismaSolicitud = pendiente &&
                pendiente.firma === firmaDatos(datos);

            botonCrear.disabled = creando ||
                validando ||
                (!productosValidados && !mismaSolicitud) ||
                !datos.nombre ||
                !datos.realizado_por ||
                datos.tiendas.length === 0 ||
                datos.codigos.length === 0;
        }

        function crearFilaProducto(producto, esValido) {
            const fila = document.createElement('div');
            fila.className = 'flex items-start gap-3 px-3 py-2.5 text-sm';

            const icono = document.createElement('span');
            icono.className = esValido
                ? 'mt-0.5 text-emerald-600'
                : 'mt-0.5 text-rose-600';
            icono.textContent = esValido ? '✓' : '✕';

            const contenido = document.createElement('div');
            contenido.className = 'min-w-0';

            const codigo = document.createElement('div');
            codigo.className = 'font-semibold text-slate-800';
            codigo.textContent = String(producto.codigo ?? '');

            const descripcion = document.createElement('div');
            descripcion.className = 'text-slate-500';
            descripcion.textContent = esValido
                ? String(producto.descripcion || 'Sin descripción')
                : 'Código no encontrado en el catálogo';

            contenido.append(codigo, descripcion);
            fila.append(icono, contenido);

            return fila;
        }

        function mostrarProductos(datos) {
            listaProductos.replaceChildren();

            for (const producto of datos.productos || []) {
                listaProductos.appendChild(crearFilaProducto(producto, true));
            }

            for (const codigo of datos.codigos_no_encontrados || []) {
                listaProductos.appendChild(
                    crearFilaProducto({ codigo }, false)
                );
            }

            resultadosValidacion.classList.remove('hidden');
        }

        async function leerRespuesta(respuesta) {
            let datos;

            try {
                datos = await respuesta.json();
            } catch (error) {
                throw new Error('El servidor devolvió una respuesta no válida.');
            }

            if (!respuesta.ok || datos.ok !== true) {
                throw new Error(
                    datos.error ||
                    datos.detail ||
                    'La solicitud no pudo completarse.'
                );
            }

            return datos;
        }

        async function validarProductos() {
            if (validando || creando) return;

            const datos = obtenerDatosFormulario();

            if (!datos.codigos.length) {
                mostrarEstado(
                    estadoValidacion,
                    'Introduce al menos un código de producto.',
                    'error'
                );
                return;
            }

            if (datos.codigos.length > 500) {
                mostrarEstado(
                    estadoValidacion,
                    'Puedes validar un máximo de 500 códigos.',
                    'error'
                );
                return;
            }

            validando = true;
            productosValidados = null;
            actualizarBotonCrear();

            try {
                const respuesta = await fetch(
                    '/api/inventarios/multitienda/validar-productos',
                    {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ codigos: datos.codigos })
                    }
                );

                const resultado = await leerRespuesta(respuesta);
                // Una respuesta anterior no valida códigos editados durante la consulta.
                if (JSON.stringify(datos.codigos) !== JSON.stringify(obtenerCodigos())) return;
                mostrarProductos(resultado);

                if ((resultado.codigos_no_encontrados || []).length > 0) {
                    mostrarEstado(
                        estadoValidacion,
                        `Se encontraron ${resultado.codigos_no_encontrados.length} códigos inválidos. Corrígelos antes de crear los inventarios.`,
                        'error'
                    );
                    return;
                }

                if ((resultado.productos || []).length !== datos.codigos.length) {
                    mostrarEstado(
                        estadoValidacion,
                        'La validación no coincide con los códigos introducidos. Vuelve a validar.',
                        'error'
                    );
                    return;
                }

                productosValidados = {
                    firma: firmaDatos(obtenerDatosFormulario()),
                    codigos: datos.codigos
                };

                mostrarEstado(
                    estadoValidacion,
                    `${resultado.productos.length} productos validados correctamente.`,
                    'exito'
                );
            } catch (error) {
                mostrarEstado(
                    estadoValidacion,
                    error.message || 'No se pudieron validar los productos.',
                    'error'
                );
            } finally {
                validando = false;
                actualizarBotonCrear();
            }
        }

        function generarUUID() {
            if (window.crypto && typeof window.crypto.randomUUID === 'function') {
                return window.crypto.randomUUID();
            }

            if (!window.crypto || !window.crypto.getRandomValues) {
                throw new Error(
                    'Este navegador no permite generar claves seguras. Abre la aplicación mediante HTTPS y vuelve a intentarlo.'
                );
            }

            const bytes = new Uint8Array(16);
            window.crypto.getRandomValues(bytes);
            bytes[6] = (bytes[6] & 0x0f) | 0x40;
            bytes[8] = (bytes[8] & 0x3f) | 0x80;

            const hex = Array.from(
                bytes,
                byte => byte.toString(16).padStart(2, '0')
            ).join('');

            return [
                hex.slice(0, 8),
                hex.slice(8, 12),
                hex.slice(12, 16),
                hex.slice(16, 20),
                hex.slice(20)
            ].join('-');
        }

        function mostrarInventarios(inventarios) {
            listaInventarios.replaceChildren();

            for (const inventario of inventarios) {
                const fila = document.createElement('div');
                fila.className = 'rounded-lg border border-emerald-200 bg-white px-3 py-3';

                const titulo = document.createElement('div');
                titulo.className = 'font-semibold text-emerald-900';
                titulo.textContent = `${inventario.tienda || 'Tienda'} — ${inventario.nombre || ''}`;

                const enlace = document.createElement('a');
                enlace.className = 'mt-1 inline-block font-semibold text-indigo-700 underline';
                enlace.href = `/inventario/${encodeURIComponent(inventario.id)}`;
                enlace.textContent = 'Abrir inventario';
                enlace.rel = 'noopener';

                fila.append(titulo, enlace);
                listaInventarios.appendChild(fila);
            }

            resultadosCreacion.classList.remove('hidden');
        }

        async function crearInventarios(evento) {
            evento.preventDefault();

            if (creando || validando) return;

            const datos = obtenerDatosFormulario();
            const firma = firmaDatos(datos);
            let pendiente = recuperarSolicitud();

            // Un reintento solo reutiliza claves para exactamente los mismos datos.
            if (!pendiente || pendiente.firma !== firma) {
                if (!productosValidados || productosValidados.firma !== firma) {
                    mostrarEstado(
                        estadoCreacion,
                        'Valida todos los productos antes de crear los inventarios.',
                        'error'
                    );
                    return;
                }

                if (!datos.nombre || !datos.realizado_por || !datos.tiendas.length) {
                    mostrarEstado(
                        estadoCreacion,
                        'Completa el nombre, el responsable y selecciona al menos una tienda.',
                        'error'
                    );
                    return;
                }

                try {
                    pendiente = {
                        firma,
                        datos,
                        claves: datos.tiendas.map(() => generarUUID())
                    };
                    guardarSolicitud(pendiente);
                } catch (error) {
                    mostrarEstado(
                        estadoCreacion,
                        error.message || 'No se pudieron generar las claves de operación.',
                        'error'
                    );
                    return;
                }
            }

            creando = true;
            botonCrear.disabled = true;
            botonCrear.textContent = 'Creando inventarios...';
            mostrarEstado(
                estadoCreacion,
                'Creando los inventarios. No cierres esta ventana hasta recibir el resultado.',
                'info'
            );

            try {
                const respuesta = await fetch(
                    '/api/inventarios/multitienda/crear',
                    {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            nombre: pendiente.datos.nombre,
                            realizado_por: pendiente.datos.realizado_por,
                            tiendas: pendiente.datos.tiendas,
                            codigos: pendiente.datos.codigos,
                            claves: pendiente.claves
                        })
                    }
                );

                const resultado = await leerRespuesta(respuesta);

                if (
                    !Array.isArray(resultado.inventarios) ||
                    resultado.inventarios.length !== pendiente.datos.tiendas.length
                ) {
                    // Conservar la misma solicitud para permitir un reintento seguro.
                    throw new Error(
                        'La respuesta no incluye todos los inventarios esperados. Puedes reintentar sin cambiar los datos.'
                    );
                }


                mostrarInventarios(resultado.inventarios);

                // Limpiar la operación confirmada antes de actualizar la página.
                borrarSolicitudPendiente();
                productosValidados = null;

                modal.classList.add('hidden');
                modal.classList.remove('flex');

                // Volver a consultar los documentos guardados en el servidor.
                window.location.reload();

            } catch (error) {
                mostrarEstado(
                    estadoCreacion,
                    `${error.message || 'No se pudo confirmar la creación.'} Puedes reintentar sin cambiar los datos para evitar duplicados.`,
                    'error'
                );
            } finally {
                creando = false;

                if (botonCrear.textContent !== 'Inventarios creados') {
                    botonCrear.textContent = 'Crear inventarios';
                }

                actualizarBotonCrear();
            }
        }

        window.abrirModalMultitienda = function () {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            actualizarTiendas();
        };

        window.cerrarModalMultitienda = function () {
            if (creando || validando) return;

            importador.cerrar();
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        };

        listaTiendas.addEventListener('change', function (evento) {
            if (evento.target.matches('.multi-tienda-checkbox')) {
                // La validación del catálogo es común a todas las tiendas.
                actualizarTiendas();
            }
        });


        let temporizadorValidacion = null;

        [nombre, responsable].forEach(campo => {
            campo.addEventListener('input', actualizarBotonCrear);
        });

        codigosTexto.addEventListener('input', function () {
            // Esperar a que el usuario termine de escribir o pegar códigos.
            clearTimeout(temporizadorValidacion);

            productosValidados = null;
            actualizarBotonCrear();

            ocultarEstado(estadoValidacion);
            ocultarEstado(estadoCreacion);
            resultadosValidacion.classList.add('hidden');

            const codigos = obtenerCodigos();

            if (!codigos.length) {
                return;
            }

            temporizadorValidacion = setTimeout(() => {
                validarProductos();
            }, 500);
        });

        formulario.addEventListener('submit', crearInventarios);

        // No se restaura el formulario automáticamente, pero sí se conservan
        // las claves pendientes para reintentar con los mismos datos.
        actualizarTiendas();
        actualizarBotonCrear();
    })();
