/* Carga PDF: extraer, revisar y guardar sin perder los resultados parciales. */
const cargaOC = { xhr: null, lote: false, guardando: 0, guardadas: 0 };
const ocElemento = id => document.getElementById(id);
const ocEscapar = valor => String(valor ?? '').replace(/[&<>"']/g, caracter => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[caracter]));

function ocMensaje(elemento, mensaje, error = false) {
    elemento.textContent = mensaje;
    elemento.className = `text-sm p-3 rounded-lg whitespace-pre-line max-h-32 overflow-y-auto break-words shrink-0 ${error
        ? 'bg-rose-50 text-rose-800' : 'bg-blue-50 text-blue-900'}`;
    elemento.hidden = !mensaje;
    elemento.setAttribute('role', error ? 'alert' : 'status');
}

function ocRespuestaError(status, datos) {
    if (status === 401 || status === 403) return 'Tu sesión venció o no tienes permiso. Inicia sesión en otra pestaña y vuelve a intentar sin cerrar esta revisión.';
    if (status === 413) return 'Los archivos superan el tamaño permitido. Selecciona un lote de hasta 4 MB.';
    if (status === 429) return 'Hay demasiadas solicitudes. Espera un momento antes de reintentar.';
    if (typeof datos?.mensaje === 'string') return datos.mensaje;
    if (status >= 500) return 'El servidor no pudo completar la operación. Conserva esta revisión y vuelve a intentar más tarde.';
    return 'No se pudo completar la operación. Revisa los datos e inténtalo nuevamente.';
}

function abrirModalCargarOC() {
    ocElemento('dropdown-opciones')?.classList.add('hidden');
    ocElemento('modal-cargar-oc').classList.remove('hidden');
    ocElemento('input-pdf-modal').focus();
}

function cerrarModalCargarOC() {
    if (cargaOC.xhr) {
        if (!window.confirm('¿Cancelar la extracción? Todavía no se ha guardado ninguna orden de esta carga.')) return;
        cargaOC.xhr.abort();
    }
    ocElemento('modal-cargar-oc').classList.add('hidden');
}

function validarYProcesarPDFModal(event) {
    event.preventDefault();
    if (cargaOC.xhr) return;
    const input = ocElemento('input-pdf-modal');
    const archivos = Array.from(input.files || []);
    const mensaje = ocElemento('mensaje-carga-pdf');
    if (!archivos.length) return ocMensaje(mensaje, 'Selecciona al menos un PDF.', true);
    if (archivos.length > 20) return ocMensaje(mensaje, 'Puedes procesar hasta 20 archivos por carga.', true);
    if (archivos.reduce((total, archivo) => total + archivo.size, 0) > 4 * 1024 * 1024) {
        return ocMensaje(mensaje, 'El lote supera los 4 MB. Divide los archivos en cargas más pequeñas.', true);
    }
    const invalidos = archivos.filter(archivo => !/\.pdf$/i.test(archivo.name) || archivo.size === 0);
    if (invalidos.length) return ocMensaje(mensaje, `Selecciona archivos PDF que no estén vacíos: ${invalidos.map(a => a.name).join(', ')}`, true);
    const firmas = new Set();
    if (archivos.some(archivo => {
        const firma = JSON.stringify([archivo.name, archivo.size, archivo.lastModified]);
        if (firmas.has(firma)) return true;
        firmas.add(firma);
        return false;
    })) return ocMensaje(mensaje, 'Hay archivos repetidos en la selección. Selecciona cada PDF una sola vez.', true);

    const btn = ocElemento('btn-procesar-pdf-modal');
    const texto = ocElemento('btn-texto-pdf-modal');
    const spinner = ocElemento('btn-spinner-pdf-modal');
    const progreso = ocElemento('contenedor-progreso-pdf');
    const barra = ocElemento('barra-progreso-pdf');
    const porcentaje = ocElemento('porcentaje-progreso');
    const estado = ocElemento('texto-estado-progreso');
    ocMensaje(mensaje, 'Extrayendo datos. Las órdenes se guardarán después de revisarlas.');
    btn.disabled = input.disabled = true;
    texto.textContent = 'Procesando…';
    spinner.classList.remove('hidden');
    progreso.classList.remove('hidden');
    barra.style.width = '0%';
    porcentaje.textContent = '0%';
    estado.textContent = 'Subiendo archivos…';
    const datos = new FormData();
    archivos.forEach(archivo => datos.append('archivos_pdf', archivo));
    const xhr = new XMLHttpRequest();
    cargaOC.xhr = xhr;
    xhr.open('POST', '/escanear/procesar', true);
    xhr.timeout = 120000;
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.upload.onprogress = evento => {
        if (!evento.lengthComputable) return;
        const valor = Math.round(evento.loaded / evento.total * 100);
        barra.style.width = `${valor}%`;
        porcentaje.textContent = `${valor}%`;
        if (valor === 100) estado.textContent = 'Carga completa. Extrayendo datos del PDF…';
    };
    xhr.onload = () => {
        let resultado;
        try { resultado = JSON.parse(xhr.responseText); } catch {
            ocMensaje(mensaje, xhr.responseURL?.includes('/login')
                ? ocRespuestaError(401)
                : 'El servidor devolvió una respuesta inesperada. No se guardó ninguna orden; vuelve a procesar el lote.', true);
            return;
        }
        if (xhr.status >= 200 && xhr.status < 300 && resultado.success && Array.isArray(resultado.ordenes) && resultado.ordenes.length) {
            renderizarTablaDetalleOC(resultado.ordenes, resultado);
            ocElemento('modal-cargar-oc').classList.add('hidden');
            ocElemento('modal-detalle-extraido-oc').classList.remove('hidden');
            ocElemento('titulo-revision-oc').focus();
            input.value = '';
        } else {
            const detalles = Array.isArray(resultado.errores) ? resultado.errores.map(e => `${e.archivo}: ${e.mensaje}`) : [];
            ocMensaje(mensaje, [ocRespuestaError(xhr.status, resultado), ...detalles].join('\n'), true);
        }
    };
    xhr.onerror = () => ocMensaje(mensaje, 'Se perdió la conexión durante la extracción. No se guardó ninguna orden. Comprueba tu conexión y vuelve a procesar.', true);
    xhr.ontimeout = () => ocMensaje(mensaje, 'La extracción tardó demasiado. No se guardó ninguna orden. Intenta con menos archivos.', true);
    xhr.onabort = () => ocMensaje(mensaje, 'Extracción cancelada. Puedes seleccionar otro lote.');
    xhr.onloadend = () => {
        cargaOC.xhr = null;
        btn.disabled = input.disabled = false;
        texto.textContent = 'Procesar PDF';
        spinner.classList.add('hidden');
        progreso.classList.add('hidden');
    };
    try { xhr.send(datos); } catch {
        xhr.onloadend();
        xhr.onerror();
    }
}

function renderizarTablaDetalleOC(ordenes, resultado = {}) {
    const contenedor = ocElemento('contenedor-tarjetas-oc');
    contenedor.replaceChildren();
    cargaOC.guardadas = 0;
    ocElemento('total-ordenes-count').textContent = ordenes.length;
    const avisos = [...(resultado.advertencias || [])];
    for (const error of resultado.errores || []) avisos.push(`${error.archivo}: ${error.mensaje}`);
    ocMensaje(ocElemento('resultado-extraccion-oc'), [
        `${ordenes.length} orden(es) extraídas. Aún no se han guardado.`, ...avisos
    ].join('\n'), Boolean(resultado.errores?.length));

    const campo = (nombre, etiqueta, valor, tipo = 'text', atributos = '') => `
        <label class="block text-sm text-slate-700">${etiqueta}
            <input type="${tipo}" name="${nombre}" value="${ocEscapar(valor)}" required ${atributos}
                class="mt-1 w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:ring-2 focus:ring-blue-500">
        </label>`;
    for (const datos of ordenes) {
        const productos = datos.productos || datos.detalles_productos || [];
        const advertencias = [];
        if (['numero_orden', 'proveedor', 'tienda_destino', 'fecha_emision'].some(c => !datos[c])) advertencias.push('Faltan datos por detectar: completa los campos antes de guardar.');
        const sinCatalogo = productos.filter(p => p.encontrado_en_bd === false).length;
        if (sinCatalogo) advertencias.push(`${sinCatalogo} producto(s) sin confirmar en catálogo. Revisa los códigos y precios.`);
        if (!Number(datos.monto_total)) advertencias.push('El monto total es cero. Confirma el importe con el PDF original.');
        const tarjeta = document.createElement('div');
        tarjeta.className = 'bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4 tarjeta-oc';
        tarjeta.innerHTML = `
            <p class="font-semibold text-slate-800 break-words">${ocEscapar(datos.nombre_archivo || 'Archivo PDF')}</p>
            <p class="text-sm text-amber-800">${ocEscapar(advertencias.join(' '))}</p>
            <form action="/ordenes/crear" method="POST" class="space-y-4 orden-form-modal" data-estado="pendiente">
                <input type="hidden" name="productos_json" value="${ocEscapar(JSON.stringify(productos))}">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    ${campo('numero_orden', 'Nº Orden', datos.numero_orden || '')}
                    ${campo('proveedor', 'Proveedor', datos.proveedor || '')}
                    ${campo('tienda_destino', 'Tienda destino', datos.tienda_destino || '')}
                    ${campo('monto_total', 'Monto total ($)', datos.monto_total ?? '', 'number', 'min="0" step="0.01"')}
                    ${campo('fecha_emision', 'Fecha emisión / envío', datos.fecha_emision || '', 'date')}
                    ${campo('dias_inventario', 'Días inventario', datos.dias_despacho ?? 15, 'number', 'min="1" max="99" step="1"')}
                </div>
                <details open class="text-sm text-slate-700">
                    <summary class="cursor-pointer font-medium">
                        Revisar ${productos.length} producto(s)
                    </summary>

                    <div class="overflow-x-auto mt-2">
                        <table class="w-full text-left text-xs">
                            <thead>
                                <tr>
                                    <th class="p-2">Código</th>
                                    <th class="p-2">Descripción</th>
                                    <th class="p-2">PRE</th>
                                    <th class="p-2">EMP</th>
                                    <th class="p-2">Precio ($)</th>
                                </tr>
                            </thead>

                            <tbody>
                                ${productos.map((p, indice) => `
                                    <tr data-producto-indice="${indice}">
                                        <td class="p-2">
                                            ${ocEscapar(p.codigo)}
                                        </td>

                                        <td class="p-2">
                                            ${ocEscapar(p.descripcion)}
                                        </td>

                                        <td class="p-2">
                                            <input
                                                type="number"
                                                data-campo="pre"
                                                aria-label="PRE del producto ${ocEscapar(p.codigo)}"
                                                value="${ocEscapar(p.unidad_manejo ?? p.pre ?? '')}"
                                                min="1" step="1" required
                                                class="w-20 rounded-lg border border-slate-300 px-2 py-2"
                                            >
                                        </td>

                                        <td class="p-2">
                                            <input
                                                type="number"
                                                data-campo="emp"
                                                aria-label="EMP del producto ${ocEscapar(p.codigo)}"
                                                value="${ocEscapar(p.empaques ?? p.emp ?? '')}"
                                                min="0" step="1" required
                                                class="w-20 rounded-lg border border-slate-300 px-2 py-2"
                                            >
                                        </td>

                                        <td class="p-2">
                                            <input
                                                type="number"
                                                data-campo="precio"
                                                aria-label="Precio del producto ${ocEscapar(p.codigo)}"
                                                value="${ocEscapar(p.precio_unitario ?? p.precio ?? '')}"
                                                min="0" step="any" required
                                                class="w-28 rounded-lg border border-slate-300 px-2 py-2"
                                            >
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </details>
                <p class="mensaje-orden" hidden aria-live="polite"></p>
                <div class="flex justify-end"><button type="submit" class="btn-guardar-individual bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-6 py-2 rounded-xl text-sm disabled:opacity-50">Guardar orden</button></div>
            </form>`;
        contenedor.appendChild(tarjeta);
    }
    activarEventosFormulariosModal();
    ocActualizarResumen();
}

function ocFormularios() { return [...document.querySelectorAll('.orden-form-modal')]; }
function ocActualizarResumen() {
    const forms = ocFormularios();
    const guardadas = forms.filter(f => f.dataset.estado === 'guardada').length;
    const duplicadas = forms.filter(f => f.dataset.estado === 'duplicada').length;
    const pendientes = forms.length - guardadas - duplicadas;
    ocMensaje(ocElemento('resumen-guardado-oc'), `${guardadas} guardada(s) · ${duplicadas} ya registrada(s) · ${pendientes} pendiente(s).`);
    const boton = ocElemento('btn-guardar-todo-modal');
    boton.disabled = cargaOC.lote || cargaOC.guardando > 0 || pendientes === 0;
    boton.textContent = cargaOC.lote ? 'Guardando…' : 'Guardar pendientes';
}

async function guardarOrdenModal(form, desdeLote = false) {
    if (form.dataset.estado === 'guardada' || form.dataset.estado === 'guardando' || (cargaOC.lote && !desdeLote)) return false;
    const mensaje = form.querySelector('.mensaje-orden');
    delete form.dataset.detenerLote;
    if (!form.reportValidity()) {
        ocMensaje(mensaje, 'Completa los campos indicados antes de guardar esta orden.', true);
        return false;
    }
    // Incorporar las correcciones antes de enviar la orden.
    try {
        const campoProductos = form.elements.namedItem('productos_json');
        const productos = JSON.parse(campoProductos.value);
        const filas = [...form.querySelectorAll('[data-producto-indice]')];

        if (!Array.isArray(productos) || filas.length !== productos.length) {
            throw new Error('No se pudo leer el detalle. Vuelve a procesar el PDF.');
        }

        const actualizados = filas.map(fila => {
            const producto = productos[Number(fila.dataset.productoIndice)];
            const pre = fila.querySelector('[data-campo="pre"]').valueAsNumber;
            const emp = fila.querySelector('[data-campo="emp"]').valueAsNumber;
            const precio = fila.querySelector('[data-campo="precio"]').valueAsNumber;
            const codigo = String(producto.codigo ?? '');

            // Validar PRE y EMP sin convertir valores inválidos en 1 o 0.
            if (!Number.isSafeInteger(pre) || pre < 1) {
                throw new Error(`Producto ${codigo}: PRE debe ser un entero mayor o igual a 1.`);
            }

            if (!Number.isSafeInteger(emp) || emp < 0) {
                throw new Error(`Producto ${codigo}: EMP debe ser un entero mayor o igual a 0.`);
            }

            if (!Number.isFinite(precio) || precio < 0) {
                throw new Error(`Producto ${codigo}: el precio debe ser un número mayor o igual a 0.`);
            }

            // Mantener la misma regla de unidades que utiliza el servidor.
            const cantidad = emp > 0
                ? pre * emp
                : Math.round(Number(producto.cantidad ?? 0));

            if (!Number.isSafeInteger(cantidad) || cantidad < 0) {
                throw new Error(`Producto ${codigo}: revisa la cantidad de unidades.`);
            }

            return {
                ...producto,
                pre,
                unidad_manejo: pre, // Actualizar ambos nombres del mismo dato.
                emp,
                empaques: emp,
                precio: precio,
                precio_unitario: precio,
                cantidad,
                subtotal: cantidad * precio
            };
        });

        campoProductos.value = JSON.stringify(actualizados);
    } catch (error) {
        ocMensaje(mensaje, error.message, true);
        return false;
    }

    const datos = new FormData(form);
    // Detectar repeticiones dentro del mismo lote antes de enviar otra creación.
    const clave = formulario => ['numero_orden', 'proveedor', 'tienda_destino'].map(n => formulario.elements.namedItem(n).value.trim().toLocaleLowerCase());
    const identidad = JSON.stringify(clave(form));
    if (ocFormularios().some(otra => otra !== form && ['guardada', 'guardando'].includes(otra.dataset.estado) && JSON.stringify(clave(otra)) === identidad)) {
        form.dataset.estado = 'duplicada';
        ocMensaje(mensaje, 'Esta orden está repetida en el lote y ya se está guardando o fue guardada. Revisa sus datos.', true);
        ocActualizarResumen();
        return false;
    }
    const btn = form.querySelector('.btn-guardar-individual');
    const entradas = [...form.querySelectorAll('input')];
    form.dataset.estado = 'guardando';
    cargaOC.guardando++;
    entradas.forEach(input => { input.disabled = true; });
    btn.disabled = true;
    btn.textContent = 'Guardando…';
    ocMensaje(mensaje, 'Guardando esta orden…');
    ocActualizarResumen();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
        const response = await fetch('/ordenes/crear', {
            method: 'POST', body: datos, signal: controller.signal,
            headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (response.redirected && response.url.includes('/login')) {
            form.dataset.detenerLote = '1';
            throw new Error(ocRespuestaError(401));
        }
        let resultado;
        try { resultado = await response.json(); } catch {
            form.dataset.detenerLote = '1';
            throw new Error('El servidor devolvió una respuesta inesperada. Comprueba el diario antes de reintentar; la orden podría haberse guardado.');
        }
        if (!response.ok || resultado.status !== 'ok') {
            if ([401, 403, 429].includes(response.status) || response.status >= 500) form.dataset.detenerLote = '1';
            form.dataset.estado = response.status === 409 || resultado.codigo === 'orden_duplicada' ? 'duplicada' : 'error';
            throw new Error(ocRespuestaError(response.status, resultado));
        }
        form.dataset.estado = 'guardada';
        form.classList.add('guardado-exito');
        cargaOC.guardadas++;
        btn.textContent = 'Guardada';
        ocMensaje(mensaje, 'Orden guardada en el diario. Puedes continuar con las pendientes.');
        return true;
    } catch (error) {
        if (error.name === 'AbortError' || error instanceof TypeError) form.dataset.detenerLote = '1';
        if (form.dataset.estado === 'guardando') form.dataset.estado = 'error';
        const texto = error.name === 'AbortError'
            ? 'El guardado tardó demasiado. Comprueba el diario antes de reintentar; la orden podría haberse guardado.'
            : error instanceof TypeError
                ? 'Se perdió la conexión. Comprueba el diario antes de reintentar; la orden podría haberse guardado.' : error.message;
        ocMensaje(mensaje, texto, true);
        btn.textContent = 'Volver a intentar';
        return false;
    } finally {
        clearTimeout(timeout);
        cargaOC.guardando--;
        const guardada = form.dataset.estado === 'guardada';
        entradas.forEach(input => { input.disabled = guardada; });
        btn.disabled = guardada;
        ocActualizarResumen();
    }
}

function activarEventosFormulariosModal() {
    ocFormularios().forEach(form => {
        form.addEventListener('submit', evento => { evento.preventDefault(); guardarOrdenModal(form); });
        form.addEventListener('input', () => {
            if (!['guardada', 'guardando'].includes(form.dataset.estado)) form.dataset.estado = 'pendiente';
            ocActualizarResumen();
        });
    });
    ocElemento('btn-guardar-todo-modal').onclick = async () => {
        if (cargaOC.lote || cargaOC.guardando) return;
        cargaOC.lote = true;
        ocActualizarResumen();
        try {
            for (const form of ocFormularios()) {
                if (['guardada', 'duplicada'].includes(form.dataset.estado)) continue;
                await guardarOrdenModal(form, true);
                if (form.dataset.detenerLote) break;
            }
        } finally {
            cargaOC.lote = false;
            ocActualizarResumen();
        }
    };
}

function cerrarModalDetalleOC() {
    if (cargaOC.guardando || cargaOC.lote) {
        ocMensaje(ocElemento('resumen-guardado-oc'), 'Espera a que termine el guardado para cerrar la revisión.', true);
        return;
    }
    const pendientes = ocFormularios().some(f => !['guardada', 'duplicada'].includes(f.dataset.estado));
    if (pendientes && !window.confirm('Hay órdenes sin guardar. ¿Cerrar y descartar las pendientes? Las órdenes guardadas se conservarán.')) return;
    ocElemento('modal-detalle-extraido-oc').classList.add('hidden');
    ocElemento('contenedor-tarjetas-oc').replaceChildren();
    if (cargaOC.guardadas) window.location.reload();
}

window.addEventListener('beforeunload', evento => {
    if (cargaOC.guardando || cargaOC.lote || ocFormularios().some(f => !['guardada', 'duplicada'].includes(f.dataset.estado))) {
        evento.preventDefault();
        evento.returnValue = '';
    }
});
