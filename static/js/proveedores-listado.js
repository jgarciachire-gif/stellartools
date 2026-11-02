let consultaListadoProveedores = null;
let consultaFichaProveedor = null;

async function cargarListadoProveedores(url, historial = 'replace') {
    consultaListadoProveedores?.abort();
    const consulta = new AbortController();
    consultaListadoProveedores = consulta;
    const lista = document.getElementById('lista-proveedores');
    const estado = document.getElementById('estado-listado-proveedores');
    const indicador = document.getElementById('cargando-listado-proveedores');
    lista.setAttribute('aria-busy', 'true');
    indicador.hidden = false;
    estado.textContent = '';
    try {
        const respuesta = await fetch(url, { signal: consulta.signal });
        if (respuesta.redirected && new URL(respuesta.url).pathname === '/login') {
            window.location.assign(respuesta.url);
            return;
        }
        if (!respuesta.ok) throw new Error('No se pudo cargar el listado de proveedores.');
        const pagina = new DOMParser().parseFromString(await respuesta.text(), 'text/html');
        const nuevaLista = pagina.getElementById('lista-proveedores');
        if (!nuevaLista) throw new Error('No se pudo cargar el listado de proveedores.');
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
        if (consultaListadoProveedores === consulta) {
            lista.removeAttribute('aria-busy');
            indicador.hidden = true;
        }
    }
}

async function abrirFichaProveedor(url) {
    consultaFichaProveedor?.abort();
    const consulta = new AbortController();
    consultaFichaProveedor = consulta;
    const modal = document.getElementById('modal-ficha-proveedor');
    const contenido = document.getElementById('contenido-ficha-proveedor');
    contenido.innerHTML = document.getElementById('plantilla-carga-ficha-proveedor').innerHTML;
    if (!modal.open) modal.showModal();
    contenido.setAttribute('aria-busy', 'true');
    try {
        const respuesta = await fetch(url, { signal: consulta.signal });
        if (respuesta.redirected && new URL(respuesta.url).pathname === '/login') {
            window.location.assign(respuesta.url);
            return;
        }
        if (!respuesta.ok) throw new Error('No se pudo cargar la ficha del proveedor.');
        const pagina = new DOMParser().parseFromString(await respuesta.text(), 'text/html');
        const ficha = pagina.getElementById('contenido-ficha-proveedor');
        if (!ficha?.querySelector('#form-proveedor-ficha')) throw new Error('El proveedor ya no está disponible.');
        if (consulta.signal.aborted || !modal.open) return;
        contenido.innerHTML = ficha.innerHTML;
        contenido.querySelector('[aria-label="Cerrar ficha del proveedor"]').focus();
    } catch (error) {
        if (!consulta.signal.aborted && error.name !== 'AbortError') {
            const mensaje = contenido.querySelector('[role="status"]');
            mensaje.textContent = error.message;
            mensaje.className = 'text-sm text-rose-600';
        }
    } finally {
        if (consultaFichaProveedor === consulta) contenido.removeAttribute('aria-busy');
    }
}

function cerrarFichaProveedor() {
    document.getElementById('modal-ficha-proveedor').close();
}

function alCerrarFichaProveedor() {
    consultaFichaProveedor?.abort();
    const url = new URL(window.location.href);
    if (url.searchParams.has('select')) {
        url.searchParams.delete('select');
        window.history.replaceState({}, '', url);
    }
}

document.addEventListener('click', evento => {
    if (evento.button !== 0 || evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.altKey) return;
    const enlace = evento.target.closest('a[data-listado-proveedores]');
    if (enlace) {
        evento.preventDefault();
        cargarListadoProveedores(enlace.href, 'push');
        return;
    }
    const fila = evento.target.closest('.fila-proveedor');
    if (fila) {
        evento.preventDefault();
        fila.querySelector('a').focus();
        abrirFichaProveedor(fila.dataset.fichaUrl);
    }
});

window.addEventListener('popstate', () => {
    const url = new URL(window.location.href);
    document.getElementById('busqueda_proveedores').value = '';
    etiquetasFiltro = (url.searchParams.get('tags') || '').split(',').filter(Boolean);
    const terminoAnterior = (url.searchParams.get('q') || '').trim();
    if (terminoAnterior && !etiquetasFiltro.some(e => e.toLowerCase() === terminoAnterior.toLowerCase())) {
        etiquetasFiltro.push(terminoAnterior);
    }
    renderizarEtiquetas();
    cargarListadoProveedores(url, 'none');
});

document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('modal-ficha-proveedor');
    // El dialog usa la capa superior del navegador y se centra en la pantalla visible.
    document.body.appendChild(modal);
    document.body.appendChild(document.getElementById('modal-proveedor'));
    document.body.appendChild(document.getElementById('modal-xml-menu'));
    if (modal.querySelector('#form-proveedor-ficha')) modal.showModal();
});
