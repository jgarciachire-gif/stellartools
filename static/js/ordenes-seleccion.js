/* La selección y la eliminación comparten el mismo alcance: filas visibles. */
document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);
    const filas = () => [...document.querySelectorAll('.row-orden')];
    const idOrden = valor => /^\d+$/.test(String(valor)) && Number.isSafeInteger(Number(valor)) && Number(valor) > 0
        ? Number(valor) : null;
    let confirmando = false;
    let eliminando = false;

    function visible(fila) {
        for (let elemento = fila; elemento; elemento = elemento.parentElement) {
            if (elemento.hidden || elemento.style.display === 'none' || elemento.classList.contains('hidden')) return false;
            if (elemento.tagName === 'DETAILS' && !elemento.open) return false;
        }
        return true;
    }

    function casillasVisibles() {
        return filas().filter(visible).map(fila => fila.querySelector('.select-row'))
            .filter(casilla => casilla && !casilla.disabled && idOrden(casilla.dataset.id || casilla.value) !== null);
    }

    function idsVisibles(soloSeleccionadas = true) {
        return [...new Set(casillasVisibles().filter(casilla => !soloSeleccionadas || casilla.checked)
            .map(casilla => idOrden(casilla.dataset.id || casilla.value)))];
    }

    function actualizarEstadoSeleccion() {
        filas().forEach(fila => {
            const casilla = fila.querySelector('.select-row');
            if (!casilla) return;
            if (!visible(fila)) casilla.checked = false;
            fila.classList.toggle('bg-blue-50/50', casilla.checked);
        });
        const seleccionadas = idsVisibles();
        const visibles = casillasVisibles();
        $('contador-seleccion').textContent = `${seleccionadas.length} seleccionado${seleccionadas.length !== 1 ? 's' : ''}`;
        const eliminar = $('btnEliminarMasivo');
        eliminar.disabled = eliminando || !seleccionadas.length;
        ['opacity-50', 'cursor-not-allowed', 'pointer-events-none'].forEach(clase => eliminar.classList.toggle(clase, eliminar.disabled));
        const todo = $('btn-seleccionar-todo');
        todo.disabled = eliminando || !visibles.length;
        todo.textContent = visibles.length && visibles.every(casilla => casilla.checked) ? 'Desmarcar Todo' : 'Seleccionar Todo';
        todo.classList.toggle('opacity-50', todo.disabled);
    }
    window.actualizarEstadoSeleccion = actualizarEstadoSeleccion;
    window.actualizarContador = actualizarEstadoSeleccion;

    window.abrirModalEliminar = async function (ids = null) {
        if (eliminando || confirmando) return;
        actualizarEstadoSeleccion();
        const visibles = idsVisibles(ids === null);
        const solicitados = ids === null ? visibles : (Array.isArray(ids) ? ids : [ids]).map(idOrden);
        const objetivos = [...new Set(solicitados.filter(id => id !== null && visibles.includes(id)))];
        if (!objetivos.length) {
            window.mostrarNotificacion({ tipo: 'warning', mensaje: 'Selecciona al menos una orden visible para eliminar.' });
            return;
        }
        confirmando = true;
        try {
            const aceptado = await window.mostrarConfirmacion({
                tipo: 'warning', titulo: 'Eliminar órdenes',
                mensaje: `Se eliminarán ${objetivos.length} orden(es) de forma permanente. Esta acción no se puede deshacer.`,
                textoAceptar: 'Eliminar', textoCancelar: 'Cancelar'
            });
            if (!aceptado) return;
            actualizarEstadoSeleccion();
            const actuales = idsVisibles(ids === null);
            if (objetivos.some(id => !actuales.includes(id)) || (ids === null && actuales.length !== objetivos.length)) {
                window.mostrarNotificacion({ tipo: 'warning', mensaje: 'La selección o los filtros cambiaron. Revisa las órdenes y vuelve a confirmar la eliminación.' });
                return;
            }
            await eliminarOrdenes(objetivos);
        } finally {
            confirmando = false;
            actualizarEstadoSeleccion();
        }
    };

    async function eliminarOrdenes(ids) {
        const boton = $('btnEliminarMasivo');
        const contenido = boton.innerHTML;
        const controlador = new AbortController();
        const timeout = setTimeout(() => controlador.abort(), 60000);
        eliminando = true;
        boton.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i><span>Eliminando...</span>';
        actualizarEstadoSeleccion();
        try {
            const respuesta = await fetch('/ordenes/eliminar_masivo', {
                method: 'POST', signal: controlador.signal,
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify({ ids })
            });
            if (respuesta.redirected || respuesta.status === 401 || respuesta.status === 403) {
                throw new Error('Tu sesión venció o no tienes permiso. Inicia sesión y vuelve a intentarlo.');
            }
            const datos = await respuesta.json();
            if (!respuesta.ok || datos?.success !== true) throw new Error(datos?.message || 'No se pudo confirmar la eliminación. Revisa el listado antes de reintentar.');
            window.mostrarNotificacion({ tipo: 'success', mensaje: `${ids.length} orden(es) eliminada(s).` });
            await new Promise(resolve => setTimeout(resolve, 1200));
            window.location.reload();
        } catch (error) {
            window.mostrarNotificacion({ tipo: 'error', duracion: 6500, mensaje:
                error.name === 'AbortError' || error instanceof TypeError || error instanceof SyntaxError
                    ? 'No se pudo confirmar la respuesta. Actualiza el listado antes de reintentar: las órdenes podrían haberse eliminado.' : error.message });
        } finally {
            clearTimeout(timeout);
            eliminando = false;
            boton.innerHTML = contenido;
            actualizarEstadoSeleccion();
        }
    }

    $('btn-activar-seleccion').addEventListener('click', () => {
        $('barra-seleccion').classList.remove('hidden');
        document.querySelectorAll('.col-seleccion').forEach(columna => columna.classList.remove('hidden'));
        $('btn-activar-seleccion').disabled = true;
        actualizarEstadoSeleccion();
    });
    $('btn-cancelar-seleccion').addEventListener('click', () => {
        if (eliminando) return;
        $('barra-seleccion').classList.add('hidden');
        document.querySelectorAll('.col-seleccion').forEach(columna => columna.classList.add('hidden'));
        $('btn-activar-seleccion').disabled = false;
        filas().forEach(fila => { const casilla = fila.querySelector('.select-row'); if (casilla) casilla.checked = false; });
        actualizarEstadoSeleccion();
    });
    $('btn-seleccionar-todo').addEventListener('click', () => {
        if (eliminando) return;
        actualizarEstadoSeleccion();
        const visibles = casillasVisibles();
        const marcar = !visibles.every(casilla => casilla.checked);
        visibles.forEach(casilla => { casilla.checked = marcar; });
        actualizarEstadoSeleccion();
    });
    const enlazadas = new WeakSet();
    function enlazarFilas() {
        const activo = !$('barra-seleccion').classList.contains('hidden');
        document.querySelectorAll('.col-seleccion').forEach(columna => columna.classList.toggle('hidden', !activo));
        filas().forEach(fila => {
            if (enlazadas.has(fila)) return;
            enlazadas.add(fila);
            fila.querySelector('.select-row')?.addEventListener('change', actualizarEstadoSeleccion);
            fila.addEventListener('click', evento => {
                if (eliminando || !visible(fila) || $('barra-seleccion').classList.contains('hidden')
                    || evento.target.closest('button, input, label, a, select, textarea')) return;
                const casilla = fila.querySelector('.select-row');
                if (!casilla || casilla.disabled) return;
                casilla.checked = !casilla.checked;
                actualizarEstadoSeleccion();
            });
        });
        document.querySelectorAll('details.group').forEach(grupo => grupo.addEventListener('toggle', actualizarEstadoSeleccion));
        actualizarEstadoSeleccion();
    }
    enlazarFilas();
    document.addEventListener('ordenes:listado', enlazarFilas);
});
