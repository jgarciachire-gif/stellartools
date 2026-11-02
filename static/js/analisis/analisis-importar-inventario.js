
(() => {
    'use strict';

    const $ = id => document.getElementById(id);

    let inventarios = [];
    const seleccionados = new Map();
    let pendientes = [];
    let detallesPendientes = [];
    let procesando = false;
    let criterios = [];
    let tiendaFiltro = '';
    let fechaFiltro = '';
    let pagina = 1;
    let hayMas = false;
    let cargando = false;
    let preparando = false;
    let secuenciaCarga = 0;
    let solicitudListado = null;
    let solicitudDetalle = null;
    const paginasCache = new Map();
    const documentosSeleccionados = new Map();

    const normalizarBusqueda = valor => String(valor || '')
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .trim().toLocaleLowerCase();

    const normalizarTienda = valor =>
        String(valor || '').trim().toUpperCase();

    const normalizarCodigo = valor =>
        typeof window.normalizarCodigoAnalisis === 'function'
            ? window.normalizarCodigoAnalisis(valor)
            : String(valor || '').trim();

    const fechaDocumento = documento =>
        documento.updated_at || documento.created_at || '';

    const fechaVisible = documento => {
        const valor = fechaDocumento(documento);
        if (!valor) return '—';

        const fecha = new Date(valor);
        return Number.isNaN(fecha.getTime())
            ? '—'
            : fecha.toLocaleDateString('es-VE');
    };

    const escaparHTML = valor =>
        String(valor ?? '').replace(/[&<>"']/g, caracter => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        })[caracter]);

    function listaTiendasDisponibles() {
        return [
            ...new Set(
                Array.from(
                    document.querySelectorAll('.btn-pestana-tienda')
                )
                    .map(boton => normalizarTienda(boton.dataset.tienda))
                    .filter(Boolean)
            )
        ];
    }

    function documentosFiltrados() {
        const tiendasDisponibles = listaTiendasDisponibles();
        // Los filtros y la paginación se aplican antes de leer los documentos en el servidor.
        return inventarios.filter(documento => tiendasDisponibles.includes(normalizarTienda(documento.tienda)));
    }

    function documentosPorTienda() {
        const grupos = new Map();

        documentosFiltrados()
            .slice()
            .sort((a, b) =>
                fechaDocumento(b).localeCompare(fechaDocumento(a))
            )
            .forEach(documento => {
                const tienda = normalizarTienda(documento.tienda);

                if (!grupos.has(tienda)) {
                    grupos.set(tienda, []);
                }

                grupos.get(tienda).push(documento);
            });

        return grupos;
    }

    function actualizarResumen() {
        const cantidad = seleccionados.size;
        $('inventario-resumen-seleccion').textContent = cantidad
            ? `${cantidad} documento(s) seleccionado(s).`
            : '';
        $('inventario-resumen-seleccion').hidden = cantidad === 0;

        $('btn-previsualizar-importacion-inventario').disabled =
            procesando || preparando || cargando || cantidad === 0;
        $('inventario-quitar-seleccion').classList.toggle('hidden', cantidad === 0);
        const grupos = documentosPorTienda();
        const todos = grupos.size > 0 && [...grupos].every(([tienda, documentos]) =>
            documentos.some(documento => seleccionados.get(tienda) === String(documento.id)));
        const boton = $('inventario-seleccionar-visibles');
        boton.disabled = cargando || !grupos.size;
        boton.textContent = todos ? 'Desmarcar visibles' : 'Seleccionar recientes';
    }

    function renderizarDocumentos() {
        const tbody = $('inventario-lista-documentos');
        const grupos = documentosPorTienda();
        const cantidad = [...grupos.values()].reduce((total, documentos) => total + documentos.length, 0);
        $('inventario-estado-buscador').textContent = `${cantidad} inventario(s) en esta página`;

        if (!grupos.size) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="px-4 py-8 text-center text-slate-500">
                        No hay inventarios completados que coincidan con los filtros.
                    </td>
                </tr>`;
            actualizarResumen();
            return;
        }

        const filas = [];

        grupos.forEach((documentos, tienda) => {
            documentos.forEach(documento => {
                const esSeleccionado = seleccionados.get(tienda) === String(documento.id);

                const checked = esSeleccionado ? 'checked' : '';
                const idControl = `inventario-doc-${escaparHTML(documento.id)}`;

                filas.push(`
                    <tr class="transition-colors ${esSeleccionado ? 'bg-emerald-50/70' : 'hover:bg-slate-50'}">
                        <td class="px-3 py-3">
                            <label class="relative inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-xl hover:bg-emerald-100/60 transition-colors">
                            <input
                                id="${idControl}"
                                type="checkbox"
                                aria-label="Seleccionar ${escaparHTML(documento.nombre || `Inventario #${documento.id}`)} de ${escaparHTML(tienda)}"
                                data-id="${escaparHTML(documento.id)}"
                                data-tienda="${escaparHTML(tienda)}"
                                ${checked}
                                class="peer h-5 w-5 appearance-none rounded-md border-2 border-slate-300 bg-white cursor-pointer transition-all checked:border-emerald-600 checked:bg-emerald-600 checked:shadow-sm focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-emerald-100">
                            <i class="fa-solid fa-check pointer-events-none absolute text-[11px] text-white opacity-0 transition-opacity peer-checked:opacity-100" aria-hidden="true"></i>
                            </label>
                        </td>
                        <td class="px-3 py-3">
                            <label for="${idControl}" class="cursor-pointer">
                                <span class="block font-semibold text-slate-800">
                                    ${escaparHTML(documento.nombre || `Inventario #${documento.id}`)}
                                </span>
                                <span class="block text-[11px] text-slate-400">
                                    ID ${escaparHTML(documento.id)}
                                </span>
                            </label>
                        </td>
                        <td class="px-3 py-3 text-slate-600">${escaparHTML(tienda)}</td>
                        <td class="px-3 py-3 whitespace-nowrap text-slate-600">${fechaVisible(documento)}</td>
                        <td class="px-3 py-3 text-slate-600">${escaparHTML(documento.realizado_por || '—')}</td>
                        <td class="px-3 py-3">
                            <span class="inline-flex px-2 py-1 rounded-full bg-emerald-50 text-emerald-700 font-semibold">
                                Completado
                            </span>
                        </td>
                    </tr>`);
            });
        });

        tbody.innerHTML = filas.join('');

        tbody.querySelectorAll('input[data-id]').forEach(input => {
            input.addEventListener('change', () => {
                const id = String(input.dataset.id);
                const tienda = normalizarTienda(input.dataset.tienda);
                if (input.checked) {
                    seleccionados.set(tienda, id);
                    documentosSeleccionados.set(tienda, inventarios.find(documento => String(documento.id) === id));
                } else if (seleccionados.get(tienda) === id) {
                    seleccionados.delete(tienda);
                    documentosSeleccionados.delete(tienda);
                }

                renderizarDocumentos();
                $(`inventario-doc-${id}`)?.focus();
            });
        });

        actualizarResumen();
    }

    function inicializarFiltroTiendas() {
        const menu = $('inventario-menu-tiendas');
        const tiendas = ['', ...listaTiendasDisponibles()];
        menu.replaceChildren();
        tiendas.forEach(tienda => {
            const boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'block w-full rounded-lg px-3 py-2 text-left text-xs text-slate-600 hover:bg-indigo-50 hover:text-indigo-700';
            boton.textContent = tienda || 'Todas las tiendas';
            boton.addEventListener('click', () => {
                tiendaFiltro = tienda;
                cerrarMenuTiendas();
                actualizarFiltros();
            });
            menu.appendChild(boton);
        });
        dibujarBadges();
    }

    function cerrarMenuTiendas() {
        $('inventario-menu-tiendas').classList.add('hidden');
        $('inventario-btn-tiendas').setAttribute('aria-expanded', 'false');
    }

    function dibujarBadges() {
        const contenedor = $('inventario-badges-buscador');
        contenedor.replaceChildren();
        const badge = (texto, quitar) => {
            const elemento = document.createElement('span');
            elemento.className = 'inline-flex max-w-full items-center gap-1 rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[11px] font-semibold text-indigo-700';
            const etiqueta = document.createElement('span');
            etiqueta.className = 'max-w-[180px] truncate';
            etiqueta.textContent = texto;
            elemento.appendChild(etiqueta);
            if (quitar) {
                const boton = document.createElement('button');
                boton.type = 'button';
                boton.className = 'ml-0.5 text-indigo-400 hover:text-rose-600';
                boton.textContent = '×';
                boton.setAttribute('aria-label', `Quitar ${texto}`);
                boton.addEventListener('click', () => { quitar(); actualizarFiltros(); });
                elemento.appendChild(boton);
            }
            contenedor.appendChild(elemento);
        };
        criterios.forEach((texto, indice) => badge(texto, () => criterios.splice(indice, 1)));
        if (tiendaFiltro) {
            badge(tiendaFiltro, () => { tiendaFiltro = ''; });
        }
        if (fechaFiltro) {
            const [anio, mes, dia] = fechaFiltro.split('-');
            badge(`${dia}/${mes}/${anio}`, () => {
                fechaFiltro = '';
                $('inventario-fecha').value = '';
            });
        }
        $('inventario-limpiar-buscador').classList.toggle('hidden',
            !(criterios.length || tiendaFiltro || fechaFiltro || $('inventario-buscar-texto').value));
    }

    function actualizarFiltros() {
        dibujarBadges();
        return cargarInventarios(1);
    }

    function interpretarFecha(valor) {
        const partes = valor.match(/^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2}|\d{4}))?$/);
        if (!partes) return '';
        const dia = Number(partes[1]), mes = Number(partes[2]);
        const anio = !partes[3] ? new Date().getFullYear()
            : partes[3].length === 2 ? 2000 + Number(partes[3]) : Number(partes[3]);
        const fecha = new Date(anio, mes - 1, dia);
        if (fecha.getFullYear() !== anio || fecha.getMonth() !== mes - 1 || fecha.getDate() !== dia) return '';
        return `${anio}-${String(mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
    }

    function agregarCriterio() {
        const input = $('inventario-buscar-texto');
        const texto = input.value.trim();
        if (!texto) return;
        const fecha = interpretarFecha(texto);
        if (fecha) {
            fechaFiltro = fecha;
            $('inventario-fecha').value = fecha;
        } else if (!criterios.some(criterio => normalizarBusqueda(criterio) === normalizarBusqueda(texto))) {
            if (criterios.length >= 12) {
                $('inventario-estado-buscador').textContent = 'Puedes agregar hasta 12 criterios.';
                return;
            }
            criterios.push(texto);
        }
        input.value = '';
        actualizarFiltros();
    }

    function urlListado(numeroPagina) {
        const params = new URLSearchParams({ page: String(numeroPagina) });
        if (tiendaFiltro) params.set('tienda', tiendaFiltro);
        if (fechaFiltro) params.set('fecha', fechaFiltro);
        criterios.forEach(criterio => params.append('tags', criterio));
        return `/api/analisis/inventarios?${params}`;
    }

    function obtenerPagina(url) {
        if (solicitudListado && solicitudListado.url !== url) {
            solicitudListado.controlador.abort();
            solicitudListado = null;
        }
        const cache = paginasCache.get(url);
        if (cache && cache.vence > Date.now()) return Promise.resolve(cache.datos);
        if (solicitudListado?.url === url) return solicitudListado.promesa;
        solicitudListado?.controlador.abort();
        const controlador = new AbortController();
        const timeout = setTimeout(() => controlador.abort(), 30000);
        const solicitud = { url, controlador };
        solicitudListado = solicitud;
        solicitud.promesa = (async () => {
            try {
                const respuesta = await fetch(url, {
                    signal: controlador.signal, credentials: 'same-origin',
                    headers: { Accept: 'application/json' }
                });
                if (respuesta.redirected || respuesta.status === 401 || respuesta.status === 403) {
                    paginasCache.clear();
                    throw new Error('Tu sesión venció o no tienes permiso. Inicia sesión nuevamente.');
                }
                const datos = await respuesta.json();
                if (!respuesta.ok || !datos.ok || !Array.isArray(datos.inventarios)) {
                    throw new Error(datos.error || 'No se pudieron cargar los inventarios.');
                }
                paginasCache.set(url, { datos, vence: Date.now() + 60000 });
                if (paginasCache.size > 30) paginasCache.delete(paginasCache.keys().next().value);
                return datos;
            } finally {
                clearTimeout(timeout);
                if (solicitudListado === solicitud) solicitudListado = null;
            }
        })();
        return solicitud.promesa;
    }

    async function cargarInventarios(numeroPagina = 1) {
        const turno = ++secuenciaCarga;
        const url = urlListado(numeroPagina);
        cargando = true;
        inventarios = [];
        actualizarResumen();
        $('inventario-pagina-anterior').disabled = $('inventario-pagina-siguiente').disabled = true;
        const tbody = $('inventario-lista-documentos');
        tbody.innerHTML = `
            <tr><td colspan="6" class="px-4 py-8 text-center text-slate-500">
                <i class="fa-solid fa-spinner fa-spin mr-2"></i>
                Cargando inventarios...
            </td></tr>`;

        $('inventario-estado-buscador').textContent = 'Buscando inventarios…';
        try {
            const datos = await obtenerPagina(url);
            if (turno !== secuenciaCarga) return;
            inventarios = datos.inventarios;
            pagina = numeroPagina;
            hayMas = datos.hay_mas === true;
            renderizarDocumentos();
        } catch (error) {
            if (turno !== secuenciaCarga) return;
            hayMas = false;
            $('inventario-estado-buscador').textContent = 'No se pudo cargar la lista. Puedes reintentar con Actualizar.';
            tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-rose-600">${escaparHTML(
                error.name === 'AbortError' ? 'Se agotó el tiempo de espera. Intenta nuevamente.' : error.message
            )}</td></tr>`;
        } finally {
            if (turno === secuenciaCarga) {
                cargando = false;
                actualizarResumen();
                $('inventario-pagina-info').textContent = String(pagina);
                $('inventario-pagina-info').setAttribute('aria-label', `Página ${pagina}`);
                $('inventario-pagina-anterior').disabled = pagina <= 1;
                $('inventario-pagina-siguiente').disabled = !hayMas;
            }
        }
    }

    window.abrirModalImportarInventarios = async function () {
        solicitudDetalle?.abort();
        solicitudDetalle = null;
        preparando = false;
        detallesPendientes = [];
        $('btn-previsualizar-importacion-inventario').innerHTML = '<i class="fa-solid fa-file-import"></i> importar';
        $('modal-importar-inventarios').classList.remove('hidden');
        $('modal-importar-inventarios').classList.add('flex');
        $('inventario-buscar-texto').value = '';
        $('inventario-fecha').value = '';
        criterios = [];
        tiendaFiltro = '';
        fechaFiltro = '';
        seleccionados.clear();
        documentosSeleccionados.clear();
        actualizarResumen();
        inicializarFiltroTiendas();
        cerrarMenuTiendas();

        await cargarInventarios();
    };

    window.cerrarModalImportarInventarios = function () {
        if (procesando) return;
        secuenciaCarga++;
        solicitudListado?.controlador.abort();
        solicitudListado = null;
        cargando = false;
        solicitudDetalle?.abort();
        solicitudDetalle = null;
        preparando = false;
        $('modal-importar-inventarios').classList.add('hidden');
        $('modal-importar-inventarios').classList.remove('flex');
    };

    window.seleccionarInventariosVisibles = function () {
        const grupos = documentosPorTienda();
        const todos = [...grupos].every(([tienda, documentos]) =>
            documentos.some(documento => seleccionados.get(tienda) === String(documento.id)));
        grupos.forEach((documentos, tienda) => {
            if (todos) {
                seleccionados.delete(tienda);
                documentosSeleccionados.delete(tienda);
            } else {
                seleccionados.set(tienda, String(documentos[0].id));
                documentosSeleccionados.set(tienda, documentos[0]);
            }
        });
        renderizarDocumentos();
    };

    window.limpiarSeleccionInventarios = function () {
        seleccionados.clear();
        documentosSeleccionados.clear();
        renderizarDocumentos();
    };

    window.cerrarConfirmacionImportacionInventario = function () {
        if (procesando) return;
        $('modal-confirmar-importacion-inventario').classList.add('hidden');
        $('modal-confirmar-importacion-inventario').classList.remove('flex');
    };

    window.previsualizarImportacionInventarios = async function () {
        if (!seleccionados.size || procesando || preparando || cargando) return;
        preparando = true;
        const controlador = new AbortController();
        solicitudDetalle = controlador;
        const timeout = setTimeout(() => controlador.abort(), 30000);

        const boton = $('btn-previsualizar-importacion-inventario');
        boton.disabled = true;
        boton.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Preparando...';

        try {
            pendientes = Array.from(seleccionados.entries()).map(([tienda, id]) => {
                const documento = documentosSeleccionados.get(tienda);
                if (!documento || String(documento.id) !== id || normalizarTienda(documento.tienda) !== tienda || !listaTiendasDisponibles().includes(tienda)) {
                    throw new Error('Uno de los inventarios seleccionados ya no está disponible.');
                }
                return { tienda, documento };
            });

            // Obtener todos los detalles antes de modificar cualquier dato en memoria.
            detallesPendientes = [];
            const leerDetalle = async item => {
                const respuesta = await fetch(
                    `/api/analisis/inventarios/${encodeURIComponent(item.documento.id)}`,
                    { signal: controlador.signal, credentials: 'same-origin', headers: { Accept: 'application/json' } }
                );

                const datos = await respuesta.json();

                if (!respuesta.ok || !datos.ok) {
                    throw new Error(
                        `${item.tienda}: ${datos.error || 'No se pudo leer el documento.'}`
                    );
                }

                return { ...item, productos: datos.productos || [] };
            };
            // Evitar una ráfaga de consultas al revisar varias tiendas.
            const detalles = [];
            for (let indice = 0; indice < pendientes.length; indice += 2) {
                if (controlador.signal.aborted) return;
                detalles.push(...await Promise.all(pendientes.slice(indice, indice + 2).map(leerDetalle)));
            }
            if (solicitudDetalle !== controlador || controlador.signal.aborted) return;
            detallesPendientes = detalles;

            const codigosTabla = new Set(
                Array.from(document.querySelectorAll('#filas-tabla-analisis tr'))
                    .map(tr => normalizarCodigo(tr.querySelector('.inp-codigo')?.value))
                    .filter(Boolean)
            );

            const resumen = detallesPendientes.map(item => {
                const codigosDocumento = new Map();

                item.productos.forEach(producto => {
                    const codigo = normalizarCodigo(producto.codigo);
                    if (codigo) codigosDocumento.set(codigo, producto);
                });

                const coincidencias = [...codigosDocumento.keys()]
                    .filter(codigo => codigosTabla.has(codigo)).length;

                const quedaranCero = [...codigosTabla]
                    .filter(codigo => !codigosDocumento.has(codigo)).length;

                const ignorados = [...codigosDocumento.keys()]
                    .filter(codigo => !codigosTabla.has(codigo)).length;

                return `
                    <div class="border border-slate-200 rounded-xl p-4 mb-3">
                        <div class="font-semibold text-slate-800">
                            ${escaparHTML(item.tienda)} — ${escaparHTML(item.documento.nombre || `Inventario #${item.documento.id}`)}
                        </div>
                        <div class="grid grid-cols-3 gap-2 mt-3 text-center">
                            <div class="rounded-lg bg-emerald-50 p-2">
                                <div class="text-lg font-bold text-emerald-700">${coincidencias}</div>
                                <div class="text-[11px] text-slate-600">Coincidencias</div>
                            </div>
                            <div class="rounded-lg bg-amber-50 p-2">
                                <div class="text-lg font-bold text-amber-700">${quedaranCero}</div>
                                <div class="text-[11px] text-slate-600">Quedarán en cero</div>
                            </div>
                            <div class="rounded-lg bg-slate-100 p-2">
                                <div class="text-lg font-bold text-slate-700">${ignorados}</div>
                                <div class="text-[11px] text-slate-600">Códigos ignorados</div>
                            </div>
                        </div>
                        ${coincidencias === 0
                        ? '<p class="mt-3 text-xs text-rose-600">No hay coincidencias para esta tienda. Revisa la selección antes de importar.</p>'
                        : ''}
                    </div>`;
            }).join('');

            const hayCoincidencias = detallesPendientes.every(item => {
                const codigos = new Set(
                    item.productos.map(p => normalizarCodigo(p.codigo)).filter(Boolean)
                );
                return Array.from(document.querySelectorAll('#filas-tabla-analisis tr'))
                    .some(tr => codigos.has(normalizarCodigo(tr.querySelector('.inp-codigo')?.value)));
            });

            $('inventario-vista-previa').innerHTML =
                resumen +
                '<p class="text-xs text-slate-600 mt-3">Se importará un documento por tienda para reemplazar Inv-emp. Los productos ausentes del documento quedarán en cero; los códigos ajenos al análisis se ignorarán.</p>';

            $('btn-confirmar-importacion-inventario').disabled = !hayCoincidencias;
            $('modal-confirmar-importacion-inventario').classList.remove('hidden');
            $('modal-confirmar-importacion-inventario').classList.add('flex');

        } catch (error) {
            if (solicitudDetalle !== controlador) return;
            if (typeof mostrarNotificacion === 'function') {
                mostrarNotificacion({
                    tipo: 'error', mensaje: error.name === 'AbortError'
                        ? 'Se agotó el tiempo de espera. Puedes volver a revisar la importación.' : error.message
                });
            } else {
                alert(error.message);
            }
        } finally {
            clearTimeout(timeout);
            if (solicitudDetalle === controlador) {
                controlador.abort();
                solicitudDetalle = null;
                preparando = false;
                boton.disabled = false;
                boton.innerHTML = '<i class="fa-solid fa-file-import"></i> Importar';
                actualizarResumen();
            }
        }
    };

    window.confirmarImportacionInventarios = async function () {
        if (procesando || !detallesPendientes.length) return;

        procesando = true;
        const boton = $('btn-confirmar-importacion-inventario');
        boton.disabled = true;
        boton.textContent = 'Importando...';

        const tiendaOriginal = normalizarTienda(window.tiendaActivaPestana);

        const snapshotsTiendas = new Map();


        try {
            // Guarda el estado visible antes de cambiar temporalmente de tienda.
            if (typeof guardarEstadoTablaEnMemoria === 'function') {
                guardarEstadoTablaEnMemoria(tiendaOriginal);
            }

            const filas = Array.from(
                document.querySelectorAll('#filas-tabla-analisis tr')
            );

            if (!filas.length) {
                throw new Error('La tabla de análisis no contiene productos.');
            }

            const resultados = [];

            for (const item of detallesPendientes) {

                const tienda = normalizarTienda(item.tienda);
                window.asegurarEstructuraTienda(tienda);

                // Conserva una copia para revertir si falla la importación.
                if (!snapshotsTiendas.has(tienda)) {
                    snapshotsTiendas.set(
                        tienda,
                        JSON.parse(JSON.stringify(window.matrizTiendas[tienda]))
                    );
                }


                const productosDocumento = new Map();

                item.productos.forEach(producto => {
                    const codigo = normalizarCodigo(producto.codigo);
                    if (codigo) {
                        productosDocumento.set(codigo, producto);
                    }
                });

                // La función de cálculo existente depende de la tienda activa.
                window.tiendaActivaPestana = tienda;

                // Carga los valores de esta tienda antes de recalcular sus filas.
                if (typeof cargarEstadoTablaDesdeMemoria === 'function') {
                    cargarEstadoTablaDesdeMemoria(tienda);
                }

                let coincidencias = 0;

                filas.forEach(tr => {
                    const codigo = normalizarCodigo(
                        tr.querySelector('.inp-codigo')?.value
                    );

                    if (!codigo) return;

                    const inputInv = tr.querySelector('.inp-inv-emp');
                    if (!inputInv) return;

                    const producto = productosDocumento.get(codigo);
                    const cantidad = producto
                        ? Math.max(0, Number(producto.cantidad) || 0)
                        : 0;

                    if (producto) coincidencias++;

                    inputInv.value = String(cantidad);

                    // Reutiliza el cálculo existente de Emp., Uni. y subtotal.
                    if (typeof window.recancularFilaConInventario === 'function') {
                        window.recancularFilaConInventario(inputInv);
                    } else {
                        throw new Error(
                            'No está disponible recancularFilaConInventario().'
                        );
                    }
                });

                if (!coincidencias) {
                    throw new Error(
                        `La tienda ${tienda} no tiene coincidencias; no se aplicaron cambios a esa tienda.`
                    );
                }

                if (typeof guardarEstadoTablaEnMemoria === 'function') {
                    guardarEstadoTablaEnMemoria(tienda);
                }

                resultados.push({ tienda, coincidencias });
            }

            // Cierra ambos modales al terminar de aplicar los inventarios.
            [
                'modal-confirmar-importacion-inventario',
                'modal-importar-inventarios'
            ].forEach(id => {
                const modal = document.getElementById(id);

                if (modal) {
                    modal.classList.add('hidden');
                    modal.classList.remove('flex');
                }
            });

            // Restaurar la tienda que el usuario tenía abierta.
            window.tiendaActivaPestana = tiendaOriginal;

            if (typeof cargarEstadoTablaDesdeMemoria === 'function') {
                cargarEstadoTablaDesdeMemoria(tiendaOriginal);
            }

            if (typeof totalizarAnalisis === 'function') {
                totalizarAnalisis();
            }

            const mensaje = resultados
                .map(r => `${r.tienda}: ${r.coincidencias} coincidencias`)
                .join(' | ');

            if (typeof mostrarNotificacion === 'function') {
                mostrarNotificacion({
                    tipo: 'success',
                    mensaje: `Importación aplicada. ${mensaje}`
                });
            } else {
                alert(`Importación aplicada. ${mensaje}`);
            }

        } catch (error) {
            // Restaurar la tienda visible aunque falle el procesamiento.

            // Revierte todas las tiendas procesadas en esta operación.
            snapshotsTiendas.forEach((datos, tienda) => {
                window.matrizTiendas[tienda] = datos;
            });

            window.tiendaActivaPestana = tiendaOriginal;

            if (typeof cargarEstadoTablaDesdeMemoria === 'function') {
                cargarEstadoTablaDesdeMemoria(tiendaOriginal);
            }

            console.error('Error al importar inventarios:', error);

            if (typeof mostrarNotificacion === 'function') {
                mostrarNotificacion({
                    tipo: 'error',
                    mensaje: `La importación no pudo completarse: ${error.message}`
                });
            } else {
                alert(`La importación no pudo completarse: ${error.message}`);
            }

        } finally {
            procesando = false;
            boton.disabled = false;
            boton.textContent = 'Confirmar';
        }
    };

    document.addEventListener('DOMContentLoaded', () => {
        $('inventario-pagina-anterior').addEventListener('click', () => { if (!cargando && pagina > 1) cargarInventarios(pagina - 1); });
        $('inventario-pagina-siguiente').addEventListener('click', () => { if (!cargando && hayMas) cargarInventarios(pagina + 1); });
        $('inventario-actualizar-listado').addEventListener('click', () => {
            if (cargando) return;
            paginasCache.clear();
            cargarInventarios(pagina);
        });
        const input = $('inventario-buscar-texto');
        const fecha = $('inventario-fecha');
        input.addEventListener('input', dibujarBadges);
        input.addEventListener('keydown', evento => {
            if (evento.isComposing) return;
            if (evento.key === 'Enter') {
                evento.preventDefault();
                agregarCriterio();
            } else if (evento.key === 'Backspace' && !input.value && criterios.length) {
                criterios.pop();
                actualizarFiltros();
            }
        });
        $('inventario-btn-tiendas').addEventListener('click', () => {
            const oculto = $('inventario-menu-tiendas').classList.toggle('hidden');
            $('inventario-btn-tiendas').setAttribute('aria-expanded', String(!oculto));
        });
        document.addEventListener('click', evento => {
            if (!$('inventario-selector-tiendas').contains(evento.target)) cerrarMenuTiendas();
        });
        document.addEventListener('keydown', evento => {
            if (evento.key === 'Escape') cerrarMenuTiendas();
        });
        $('inventario-btn-fecha').addEventListener('click', () => {
            try {
                if (typeof fecha.showPicker === 'function') fecha.showPicker();
                else { fecha.focus(); fecha.click(); }
            } catch { fecha.focus(); fecha.click(); }
        });
        fecha.addEventListener('change', () => {
            fechaFiltro = fecha.value;
            actualizarFiltros();
        });
        $('inventario-limpiar-buscador').addEventListener('click', () => {
            criterios = [];
            tiendaFiltro = '';
            fechaFiltro = '';
            input.value = fecha.value = '';
            cerrarMenuTiendas();
            actualizarFiltros();
            input.focus();
        });
    });
})();
