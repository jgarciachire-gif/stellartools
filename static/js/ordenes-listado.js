/* Searches span all server-side headers; only the current 20 rows reach the DOM. */
(() => {
    let temporizador, controlador, generacion = 0;
    const $ = id => document.getElementById(id);
    function indicarCarga(cargando) {
        let indicador = $('ordenes-cargando');
        if (!indicador) {
            indicador = document.createElement('p'); indicador.id = 'ordenes-cargando';
            indicador.className = 'text-xs text-slate-500 py-2'; indicador.setAttribute('role', 'status');
            indicador.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin mr-2"></i>Buscando órdenes…';
            $('ordenes-resultados').before(indicador);
        }
        indicador.hidden = !cargando;
        $('ordenes-resultados').setAttribute('aria-busy', String(cargando));
    }
    window.consultarListadoOrdenes = function (pagina = 1, inmediato = false) {
        const turno = ++generacion;
        clearTimeout(temporizador); controlador?.abort();
        indicarCarga(true);
        temporizador = setTimeout(async () => {
            const url = new URL(window.location.href);
            const tags = typeof etiquetasFiltro === 'undefined' ? [] : etiquetasFiltro;
            url.searchParams.set('page', String(pagina));
            const valores = { q: $('buscador-ordenes').value.trim(), fecha: $('filtro-fecha').value,
                tags: tags.length ? JSON.stringify(tags) : '' };
            for (const [clave, valor] of Object.entries(valores)) {
                if (valor) url.searchParams.set(clave, valor); else url.searchParams.delete(clave);
            }
            const solicitud = new AbortController(); controlador = solicitud;
            const timeout = setTimeout(() => solicitud.abort(), 20000);
            try {
                const respuesta = await fetch(url, { signal: solicitud.signal, headers: { Accept: 'text/html' } });
                if (!respuesta.ok || respuesta.redirected) throw Error('No se pudo consultar el listado. Verifica tu sesión.');
                const html = new DOMParser().parseFromString(await respuesta.text(), 'text/html');
                if (turno !== generacion) return;
                const nuevo = html.getElementById('ordenes-resultados');
                if (!nuevo) throw Error('La respuesta no contiene el listado de órdenes.');
                const seleccionadas = new Set([...document.querySelectorAll('.row-orden .select-row:checked')].map(c => c.dataset.id));
                nuevo.querySelectorAll('.select-row').forEach(c => c.checked = seleccionadas.has(c.dataset.id));
                $('ordenes-resultados').replaceWith(nuevo);
                document.dispatchEvent(new Event('ordenes:listado'));
                window.history.replaceState(null, '', url);
            } catch (error) {
                if (turno !== generacion) return;
                window.mostrarNotificacion?.({ tipo: 'error', mensaje: error.name === 'AbortError'
                    ? 'La consulta tardó demasiado. Puedes volver a buscar.' : error.message });
            } finally {
                clearTimeout(timeout);
                if (turno === generacion) indicarCarga(false);
            }
        }, inmediato ? 0 : 350);
    };
    document.addEventListener('click', evento => {
        const pagina = evento.target.closest('[data-pagina-ordenes]');
        if (!pagina || evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.altKey) return;
        evento.preventDefault(); window.consultarListadoOrdenes(Number(pagina.dataset.paginaOrdenes), true);
    });
    document.addEventListener('DOMContentLoaded', () => {
        const filtros = JSON.parse($('ordenes-filtros-iniciales').textContent);
        $('buscador-ordenes').value = filtros.q || '';
        $('filtro-fecha').value = filtros.fecha || '';
        window.renderizarEtiquetas?.();
    });
})();
