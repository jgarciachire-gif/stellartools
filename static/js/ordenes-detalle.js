/* Preserve server rendering/formatting; request product lines only when opened. */
(() => {
    const estados = new WeakMap();
    window.toggleDetalleOC = async function (id, reintentar = false) {
        const fila = document.getElementById(`detalle-${id}`);
        if (!fila || !/^\d+$/.test(String(id))) return;
        if (reintentar) fila.classList.remove('hidden');
        else fila.classList.toggle('hidden');
        document.getElementById(`icono-desplegar-${id}`)?.classList.toggle('rotate-90', !fila.classList.contains('hidden'));
        if (fila.classList.contains('hidden')) return;
        const estado = estados.get(fila) || {};
        if (estado.cargado || estado.cargando) return;
        estados.set(fila, estado);
        estado.cargando = true;
        const contenido = fila.querySelector('[data-detalle-contenido]');
        contenido.innerHTML = '<p class="p-4 text-sm text-slate-500"><i class="fa-solid fa-circle-notch fa-spin mr-2"></i>Cargando productos…</p>';
        const controlador = new AbortController();
        const timeout = setTimeout(() => controlador.abort(), 20000);
        try {
            const respuesta = await fetch(`/ordenes/${id}/detalle`, { signal: controlador.signal, headers: { Accept: 'text/html' } });
            if (!respuesta.ok || respuesta.redirected || !respuesta.headers.get('content-type')?.includes('text/html')) {
                throw new Error('No se pudo cargar el detalle. Verifica tu sesión y vuelve a intentarlo.');
            }
            contenido.innerHTML = await respuesta.text();
            estado.cargado = true;
        } catch (_) {
            contenido.innerHTML = '<p class="p-3 text-sm text-rose-700">No se pudo cargar el detalle. Puedes cerrar la orden o reintentar.</p>';
            const boton = document.createElement('button');
            boton.type = 'button'; boton.className = 'px-3 py-2 text-xs font-semibold text-blue-700 hover:bg-blue-50 rounded-lg';
            boton.textContent = 'Reintentar'; boton.addEventListener('click', () => window.toggleDetalleOC(id, true));
            contenido.appendChild(boton);
        } finally {
            clearTimeout(timeout); estado.cargando = false;
        }
    };
})();
