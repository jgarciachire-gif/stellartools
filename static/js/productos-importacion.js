/* Seleccion, carga y resultado de la importacion parcial de productos. */
(() => {
    'use strict';

    const $ = id => document.getElementById(id);
    const modal = $('modal-importar-productos');
    const form = $('form-cargar-archivo');
    const archivo = $('input_archivo_excel');
    const aceptar = $('aceptar-importar-productos');
    const cerrar = $('cerrar-importar-productos');
    let procesando = false;
    let catalogoModificado = false;
    let accion = 'importar';
    let otraCarga = false;

    function prepararSeleccion() {
        form.reset();
        accion = 'importar';
        otraCarga = false;
        $('importar-productos-seleccion').hidden = false;
        $('resultado-importar-productos').hidden = true;
        $('estado-importar-productos').hidden = true;
        aceptar.textContent = 'Importar';
        cerrar.textContent = 'Cancelar';
        cerrar.hidden = false;
        archivo.focus();
    }

    function cerrarImportacion() {
        if (!procesando) modal.close();
    }

    function mostrarResultado(datos) {
        const tipo = ['success', 'warning'].includes(datos.tipo) ? datos.tipo : 'error';
        const resultado = $('resultado-importar-productos');
        resultado.dataset.tipo = tipo;
        resultado.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
        $('importar-productos-seleccion').hidden = true;
        resultado.hidden = false;
        $('titulo-resultado-importar-productos').textContent = datos.titulo || 'No se pudo importar';
        $('mensaje-resultado-importar-productos').textContent = datos.mensaje || 'Intenta nuevamente.';
        const iconos = { success: 'fa-circle-check', warning: 'fa-triangle-exclamation', error: 'fa-circle-xmark' };
        $('icono-resultado-importar-productos').className = `fa-solid ${iconos[tipo]}`;

        const resumen = datos.resumen;
        $('resumen-importar-productos').hidden = !resumen;
        if (resumen) {
            for (const campo of ['creados', 'actualizados', 'sin_cambios', 'omitidos']) {
                $(`importados-${campo.replaceAll('_', '-')}`).textContent = String(Math.max(0, Number(resumen[campo]) || 0));
            }
        }

        const avisos = Array.isArray(datos.advertencias) ? datos.advertencias : [];
        const lista = $('avisos-importar-productos');
        lista.replaceChildren();
        for (const aviso of avisos) {
            const item = document.createElement('li');
            item.textContent = String(aviso);
            lista.appendChild(item);
        }
        const detalles = $('detalles-importar-productos');
        detalles.hidden = avisos.length === 0;
        detalles.open = avisos.length > 0;
        $('limite-avisos-importar-productos').textContent = datos.total_advertencias > avisos.length
            ? `Se muestran ${avisos.length} de ${datos.total_advertencias} observaciones.` : '';

        const incierto = datos.resultado_incierto === true;
        catalogoModificado ||= datos.ok === true || incierto;
        otraCarga = datos.ok === true;
        accion = incierto || datos.ok === true ? 'cerrar' : 'elegir';
        aceptar.textContent = incierto ? 'Actualizar catálogo' : datos.ok === true ? 'Aceptar' : 'Elegir otro archivo';
        cerrar.textContent = otraCarga ? 'Importar otro archivo' : 'Cerrar';
        cerrar.hidden = incierto;
        $('titulo-resultado-importar-productos').focus();
    }

    async function importar() {
        if (procesando) return;
        const seleccionado = archivo.files?.[0];
        if (!seleccionado || !seleccionado.size || !/\.(csv|xlsx|xml)$/i.test(seleccionado.name)) {
            mostrarResultado({ tipo: 'error', titulo: 'Revisa el archivo',
                mensaje: 'Selecciona un archivo CSV, XLSX o XML que no esté vacío.' });
            return;
        }

        procesando = true;
        aceptar.disabled = cerrar.disabled = true;
        aceptar.textContent = 'Importando…';
        $('estado-importar-productos').hidden = false;
        const controlador = new AbortController();
        const timeout = setTimeout(() => controlador.abort(), 180000);
        try {
            const datos = new FormData(form);
            archivo.disabled = true;
            const respuesta = await fetch(form.action, {
                method: 'POST', body: datos, signal: controlador.signal,
                credentials: 'same-origin',
                headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (respuesta.redirected) {
                mostrarResultado({ tipo: 'error', titulo: 'Sesión vencida',
                    mensaje: 'Inicia sesión en otra pestaña y vuelve a seleccionar el archivo.' });
                return;
            }
            let resultado;
            try {
                resultado = await respuesta.json();
            } catch {
                mostrarResultado({ tipo: 'error', titulo: 'Respuesta del servidor no disponible',
                    mensaje: respuesta.status === 403
                        ? 'La sesión o la validación de seguridad rechazó la carga. Recarga la página e inicia sesión nuevamente.'
                        : 'No se recibió un resultado válido. Actualiza el catálogo para comprobar si la carga se aplicó antes de repetirla.',
                    resultado_incierto: respuesta.status !== 403 });
                return;
            }
            if (!respuesta.ok || resultado.ok !== true) {
                mostrarResultado({ ...resultado, ok: false, tipo: 'error',
                    titulo: resultado.titulo || 'No se pudo importar',
                    mensaje: resultado.mensaje || resultado.detail || 'El servidor rechazó la carga. Revisa la sesión y los permisos.',
                    resultado_incierto: resultado.resultado_incierto === true || (respuesta.status >= 500 && !('resultado_incierto' in resultado)) });
                return;
            }
            mostrarResultado(resultado);
        } catch (error) {
            mostrarResultado({ tipo: 'error', titulo: error.name === 'AbortError' ? 'Tiempo de espera agotado' : 'Se perdió la conexión',
                mensaje: 'No se pudo confirmar el resultado. Actualiza el catálogo antes de repetir la carga.',
                resultado_incierto: true });
        } finally {
            clearTimeout(timeout);
            procesando = false;
            archivo.disabled = aceptar.disabled = cerrar.disabled = false;
            $('estado-importar-productos').hidden = true;
        }
    }

    window.abrirModalImportarProductos = () => {
        if (modal.open || procesando) return;
        prepararSeleccion();
        modal.showModal();
        archivo.focus();
    };
    form.addEventListener('submit', evento => {
        evento.preventDefault();
        if (procesando) return;
        if (accion === 'cerrar') cerrarImportacion();
        else if (accion === 'elegir') prepararSeleccion();
        else importar();
    });
    cerrar.addEventListener('click', () => {
        if (procesando) return;
        if (otraCarga) prepararSeleccion();
        else cerrarImportacion();
    });
    modal.addEventListener('cancel', evento => {
        evento.preventDefault();
        cerrarImportacion();
    });
    modal.addEventListener('close', () => {
        if (catalogoModificado) window.location.reload();
    });
    window.addEventListener('beforeunload', evento => {
        if (procesando) {
            evento.preventDefault();
            evento.returnValue = '';
        }
    });
})();
