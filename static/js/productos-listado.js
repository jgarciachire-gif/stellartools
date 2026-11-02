let consultaListadoProductos = null;
let consultaFichaProducto = null;

async function cargarListadoProductos(url, historial = 'replace') {
    consultaListadoProductos?.abort();
    const consulta = new AbortController();
    consultaListadoProductos = consulta;
    const lista = document.getElementById('lista-productos');
    const estado = document.getElementById('estado-listado-productos');
    const indicador = document.getElementById('cargando-listado-productos');
    lista.setAttribute('aria-busy', 'true');
    indicador.hidden = false;
    estado.textContent = '';
    try {
        const respuesta = await fetch(url, { signal: consulta.signal });
        if (respuesta.redirected && new URL(respuesta.url).pathname === '/login') {
            window.location.assign(respuesta.url);
            return;
        }
        if (!respuesta.ok) throw new Error('No se pudo cargar el listado de productos.');
        const pagina = new DOMParser().parseFromString(await respuesta.text(), 'text/html');
        const nuevaLista = pagina.getElementById('lista-productos');
        if (!nuevaLista) throw new Error('No se pudo cargar el listado de productos.');
        if (consulta.signal.aborted) return;
        lista.innerHTML = nuevaLista.innerHTML;
        const destino = new URL(respuesta.url || url, window.location.origin);
        destino.searchParams.delete('select');
        if (historial !== 'none') {
            window.history[historial === 'push' ? 'pushState' : 'replaceState']({}, '', destino);
        }
    } catch (error) {
        if (!consulta.signal.aborted && error.name !== 'AbortError') estado.textContent = error.message;
    } finally {
        if (consultaListadoProductos === consulta) {
            lista.removeAttribute('aria-busy');
            indicador.hidden = true;
        }
    }
}

async function abrirFichaProducto(url) {
    consultaFichaProducto?.abort();
    const consulta = new AbortController();
    consultaFichaProducto = consulta;
    const modal = document.getElementById('modal-ficha-producto');
    const contenido = document.getElementById('contenido-ficha-producto');
    contenido.innerHTML = `
        <div class="flex items-center justify-between gap-4">
            <p role="status" class="flex items-center gap-2 text-sm text-indigo-700">
                <span class="h-4 w-4 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-700" aria-hidden="true"></span>
                Cargando ficha del producto…
            </p>
            <button type="button" onclick="cerrarFichaProducto()" aria-label="Cerrar ficha del producto"
                class="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>
        </div>`;
    if (!modal.open) modal.showModal();
    contenido.setAttribute('aria-busy', 'true');
    try {
        const respuesta = await fetch(url, { signal: consulta.signal });
        if (respuesta.redirected && new URL(respuesta.url).pathname === '/login') {
            window.location.assign(respuesta.url);
            return;
        }
        if (!respuesta.ok) throw new Error('No se pudo cargar la ficha del producto.');
        const pagina = new DOMParser().parseFromString(await respuesta.text(), 'text/html');
        const ficha = pagina.getElementById('contenido-ficha-producto');
        if (!ficha?.querySelector('#form-producto-ficha')) throw new Error('El producto ya no está disponible.');
        if (consulta.signal.aborted || !modal.open) return;
        contenido.innerHTML = ficha.innerHTML;
        contenido.querySelector('[aria-label="Cerrar ficha del producto"]').focus();
    } catch (error) {
        if (!consulta.signal.aborted && error.name !== 'AbortError') {
            const mensaje = contenido.querySelector('[role="status"]');
            mensaje.textContent = error.message;
            mensaje.className = 'text-sm text-rose-600';
        }
    } finally {
        if (consultaFichaProducto === consulta) contenido.removeAttribute('aria-busy');
    }
}

function cerrarFichaProducto() {
    document.getElementById('modal-ficha-producto').close();
}

function alCerrarFichaProducto() {
    consultaFichaProducto?.abort();
    const url = new URL(window.location.href);
    if (url.searchParams.has('select')) {
        url.searchParams.delete('select');
        window.history.replaceState({}, '', url);
    }
}

document.addEventListener('click', evento => {
    if (evento.button !== 0 || evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.altKey) return;
    const enlace = evento.target.closest('a[data-listado-productos]');
    if (enlace) {
        evento.preventDefault();
        cargarListadoProductos(enlace.href, 'push');
        return;
    }
    const fila = evento.target.closest('.fila-producto');
    if (fila) {
        evento.preventDefault();
        fila.querySelector('a').focus();
        abrirFichaProducto(fila.dataset.fichaUrl);
    }
});

window.addEventListener('popstate', () => {
    const url = new URL(window.location.href);
    document.getElementById('busqueda_productos').value = '';
    etiquetasFiltroProds = (url.searchParams.get('tags') || '').split(',').filter(Boolean);
    const terminoAnterior = (url.searchParams.get('q') || '').trim();
    if (terminoAnterior && !etiquetasFiltroProds.some(e => e.toLowerCase() === terminoAnterior.toLowerCase())) {
        etiquetasFiltroProds.push(terminoAnterior);
    }
    renderizarEtiquetasProds();
    cargarListadoProductos(url, 'none');
});

document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('modal-ficha-producto');
    // El dialog usa la capa superior del navegador y se centra en la pantalla visible.
    document.body.appendChild(modal);
    document.body.appendChild(document.getElementById('modal-producto'));
    if (modal.querySelector('#form-producto-ficha')) modal.showModal();
});
