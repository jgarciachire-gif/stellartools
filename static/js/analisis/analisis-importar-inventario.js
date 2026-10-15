
(() => {
    'use strict';

    const $ = id => document.getElementById(id);

    let inventarios = [];
    let modo = 'tienda';
    let seleccionados = new Map();
    let pendientes = [];
    let detallesPendientes = [];
    let procesando = false;

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

    function fechaDentroDelFiltro(documento) {
        const fecha = fechaDocumento(documento).slice(0, 10);
        const desde = $('inventario-fecha-desde').value;
        const hasta = $('inventario-fecha-hasta').value;

        return (!desde || fecha >= desde) && (!hasta || fecha <= hasta);
    }

    function documentosFiltrados() {
        const texto = $('inventario-buscar-texto').value
            .trim()
            .toLocaleLowerCase();

        const tiendaFiltro = normalizarTienda(
            $('inventario-filtro-tienda').value
        );

        const tiendaActiva = normalizarTienda(
            window.tiendaActivaPestana
        );

        return inventarios.filter(documento => {
            const tienda = normalizarTienda(documento.tienda);

            if (modo === 'tienda' && tienda !== tiendaActiva) {
                return false;
            }

            if (modo === 'multiple' && !listaTiendasDisponibles().includes(tienda)) {
                return false;
            }

            if (tiendaFiltro && tienda !== tiendaFiltro) {
                return false;
            }

            if (!fechaDentroDelFiltro(documento)) {
                return false;
            }

            const contenido = [
                documento.nombre,
                documento.realizado_por,
                documento.tienda
            ].join(' ').toLocaleLowerCase();

            return contenido.includes(texto);
        });
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
            : 'Selecciona un documento para continuar.';

        $('btn-previsualizar-importacion-inventario').disabled =
            procesando || cantidad === 0;
    }

    function renderizarDocumentos() {
        const tbody = $('inventario-lista-documentos');
        const grupos = documentosPorTienda();

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
            if (modo === 'multiple' && !seleccionados.has(tienda)) {
                // En modo múltiple, la selección inicial usa el más reciente.
                const seleccionado = seleccionados.get(tienda);
                if (seleccionado) {
                    seleccionados.delete(tienda);
                }
            }

            documentos.forEach((documento, indice) => {
                const claveTienda = tienda;
                const esSeleccionado =
                    seleccionados.get(claveTienda) === String(documento.id);

                const checked = esSeleccionado ? 'checked' : '';
                const tipoControl = modo === 'tienda' ? 'radio' : 'checkbox';
                const idControl = `inventario-doc-${documento.id}`;

                filas.push(`
                    <tr class="hover:bg-emerald-50/40">
                        <td class="px-3 py-3">
                            <input
                                id="${idControl}"
                                type="${tipoControl}"
                                name="${modo === 'tienda' ? 'inventario-documento-unico' : `inventario-${escaparHTML(tienda)}`}"
                                data-id="${escaparHTML(documento.id)}"
                                data-tienda="${escaparHTML(tienda)}"
                                ${checked}
                                class="h-4 w-4 accent-emerald-600 cursor-pointer">
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
                    if (modo === 'tienda') {
                        seleccionados.clear();
                    }
                    seleccionados.set(tienda, id);
                } else if (seleccionados.get(tienda) === id) {
                    seleccionados.delete(tienda);
                }

                renderizarDocumentos();
            });
        });

        actualizarResumen();
    }

    function inicializarFiltroTiendas() {
        const select = $('inventario-filtro-tienda');
        const tiendas = listaTiendasDisponibles();
        const actual = normalizarTienda(window.tiendaActivaPestana);

        select.innerHTML =
            '<option value="">Todas las tiendas</option>' +
            tiendas.map(tienda =>
                `<option value="${escaparHTML(tienda)}">${escaparHTML(tienda)}</option>`
            ).join('');

        if (tiendas.includes(actual)) {
            select.value = actual;
        }
    }

    async function cargarInventarios() {
        const tbody = $('inventario-lista-documentos');
        tbody.innerHTML = `
            <tr><td colspan="6" class="px-4 py-8 text-center text-slate-500">
                <i class="fa-solid fa-spinner fa-spin mr-2"></i>
                Cargando inventarios...
            </td></tr>`;

        const respuesta = await fetch('/api/analisis/inventarios', {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' }
        });

        const datos = await respuesta.json();

        if (!respuesta.ok || !datos.ok) {
            throw new Error(datos.error || 'No se pudieron cargar los inventarios.');
        }

        inventarios = datos.inventarios || [];
        inicializarFiltroTiendas();

        // En modo individual, seleccionar por defecto el documento más reciente de la tienda activa.
        if (modo === 'tienda') {
            const tienda = normalizarTienda(window.tiendaActivaPestana);
            const documento = inventarios
                .filter(item => normalizarTienda(item.tienda) === tienda)
                .sort((a, b) => fechaDocumento(b).localeCompare(fechaDocumento(a)))[0];

            seleccionados.clear();

            if (documento) {
                seleccionados.set(tienda, String(documento.id));
            }
        }

        renderizarDocumentos();
    }

    window.abrirModalImportarInventarios = async function () {
        $('modal-importar-inventarios').classList.remove('hidden');
        $('modal-importar-inventarios').classList.add('flex');
        $('inventario-tienda-activa-info').textContent =
            `Tienda activa: ${normalizarTienda(window.tiendaActivaPestana) || '—'}`;

        $('inventario-buscar-texto').value = '';
        $('inventario-fecha-desde').value = '';
        $('inventario-fecha-hasta').value = '';
        modo = 'tienda';
        actualizarModoVisual();

        try {
            await cargarInventarios();
        } catch (error) {
            $('inventario-lista-documentos').innerHTML = `
                <tr><td colspan="6" class="px-4 py-8 text-center text-rose-600">
                    ${escaparHTML(error.message)}
                </td></tr>`;
        }
    };

    window.cerrarModalImportarInventarios = function () {
        if (procesando) return;
        $('modal-importar-inventarios').classList.add('hidden');
        $('modal-importar-inventarios').classList.remove('flex');
    };

    window.cambiarModoImportacionInventario = function (nuevoModo) {
        modo = nuevoModo === 'multiple' ? 'multiple' : 'tienda';
        seleccionados.clear();

        $('inventario-acciones-multiples').classList.toggle(
            'hidden',
            modo !== 'multiple'
        );

        $('inventario-filtro-tienda-wrap').classList.toggle(
            'hidden',
            modo === 'tienda'
        );

        if (modo === 'tienda') {
            $('inventario-filtro-tienda').value =
                normalizarTienda(window.tiendaActivaPestana);
        } else {
            $('inventario-filtro-tienda').value = '';
        }

        actualizarModoVisual();
        renderizarDocumentos();
    };

    function actualizarModoVisual() {
        const botones = [
            ['btn-modo-inventario-tienda', modo === 'tienda'],
            ['btn-modo-inventario-multiple', modo === 'multiple']
        ];

        botones.forEach(([id, activo]) => {
            $(id).className = activo
                ? 'px-4 py-2 rounded-lg text-xs font-semibold border border-emerald-600 bg-emerald-50 text-emerald-800'
                : 'px-4 py-2 rounded-lg text-xs font-semibold border border-slate-200 bg-white text-slate-600 hover:bg-slate-50';
        });
    }

    window.seleccionarTodasTiendasInventario = function () {
        const grupos = documentosPorTienda();
        seleccionados.clear();

        grupos.forEach((documentos, tienda) => {
            const documento = documentos
                .slice()
                .sort((a, b) => fechaDocumento(b).localeCompare(fechaDocumento(a)))[0];

            if (documento) {
                seleccionados.set(tienda, String(documento.id));
            }
        });

        renderizarDocumentos();
    };

    window.cerrarConfirmacionImportacionInventario = function () {
        if (procesando) return;
        $('modal-confirmar-importacion-inventario').classList.add('hidden');
        $('modal-confirmar-importacion-inventario').classList.remove('flex');
    };

    window.previsualizarImportacionInventarios = async function () {
        if (!seleccionados.size || procesando) return;

        const boton = $('btn-previsualizar-importacion-inventario');
        boton.disabled = true;
        boton.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Preparando...';

        try {
            pendientes = Array.from(seleccionados.entries()).map(([tienda, id]) => {
                const documento = inventarios.find(item => String(item.id) === String(id));
                if (!documento || normalizarTienda(documento.tienda) !== tienda) {
                    throw new Error(`La selección de ${tienda} ya no es válida.`);
                }
                return { tienda, documento };
            });

            // Obtener todos los detalles antes de modificar cualquier dato en memoria.
            detallesPendientes = await Promise.all(pendientes.map(async item => {
                const respuesta = await fetch(
                    `/api/analisis/inventarios/${encodeURIComponent(item.documento.id)}`,
                    { credentials: 'same-origin', headers: { Accept: 'application/json' } }
                );

                const datos = await respuesta.json();

                if (!respuesta.ok || !datos.ok) {
                    throw new Error(
                        `${item.tienda}: ${datos.error || 'No se pudo leer el documento.'}`
                    );
                }

                return { ...item, productos: datos.productos || [] };
            }));

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
                        ? '<p class="mt-3 text-xs text-rose-600">No hay coincidencias. Este documento no se podrá importar.</p>'
                        : ''}
                    </div>`;
            }).join('');

            const hayCoincidencias = detallesPendientes.some(item => {
                const codigos = new Set(
                    item.productos.map(p => normalizarCodigo(p.codigo)).filter(Boolean)
                );
                return Array.from(document.querySelectorAll('#filas-tabla-analisis tr'))
                    .some(tr => codigos.has(normalizarCodigo(tr.querySelector('.inp-codigo')?.value)));
            });

            $('inventario-vista-previa').innerHTML =
                resumen +
                '<p class="text-xs text-slate-600 mt-3">La importación reemplazará Inv-emp de los productos de la tabla. Los productos ausentes del documento quedarán en cero; los códigos ajenos al análisis se ignorarán.</p>';

            $('btn-confirmar-importacion-inventario').disabled = !hayCoincidencias;
            $('modal-confirmar-importacion-inventario').classList.remove('hidden');
            $('modal-confirmar-importacion-inventario').classList.add('flex');

        } catch (error) {
            if (typeof mostrarNotificacion === 'function') {
                mostrarNotificacion({ tipo: 'error', mensaje: error.message });
            } else {
                alert(error.message);
            }
        } finally {
            boton.disabled = false;
            boton.innerHTML = '<i class="fa-solid fa-eye mr-1"></i> Revisar importación';
            actualizarResumen();
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
            boton.textContent = 'Confirmar e importar';
        }
    };

    document.addEventListener('DOMContentLoaded', () => {
        [
            'inventario-buscar-texto',
            'inventario-filtro-tienda',
            'inventario-fecha-desde',
            'inventario-fecha-hasta'
        ].forEach(id => {
            $(id)?.addEventListener('input', renderizarDocumentos);
            $(id)?.addEventListener('change', renderizarDocumentos);
        });
    });
})();
