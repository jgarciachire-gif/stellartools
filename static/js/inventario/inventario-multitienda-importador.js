/* Adaptador del modal compartido para preparar la lista multitienda. */
(() => {
    'use strict';
    window.crearImportadorMultitienda = ({ obtenerProveedores, alImportar }) => {
        const $ = id => document.getElementById(id);
        const modal = $('modal-importar-inventario');
        const boton = $('btn-ejecutar-importacion-inventario');
        const carga = $('estado-carga-clasificacion-inventario');
        const info = $('inventario-importacion-info');
        const campos = ['departamento', 'grupo', 'subgrupo', 'marca'];
        const etiquetas = ['Todos los departamentos', 'Todos los grupos', 'Todos los subgrupos', 'Todas las marcas'];
        const normalizar = valor => String(valor || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
        let proveedores = [], clasificacion = [], proveedor = null, turno = 0, solicitud;
        let ocupado = false;

        function mensaje(texto) {
            info.textContent = texto;
            info.classList.toggle('hidden', !texto);
        }
        function cerrar() {
            turno++;
            solicitud?.abort();
            modal.classList.add('hidden');
            ocupado = false;
        }
        function bloquear(valor) {
            ocupado = valor;
            boton.disabled = valor || !proveedor;
            boton.classList.toggle('opacity-50', boton.disabled);
            carga.classList.toggle('hidden', !valor);
            modal.setAttribute('aria-busy', String(valor));
        }
        async function consultar(url, signal) {
            const respuesta = await fetch(url, { credentials: 'same-origin', signal });
            if (!respuesta.ok || respuesta.redirected) throw Error('No se pudieron cargar los datos. Verifica tu sesión e inténtalo nuevamente.');
            const datos = await respuesta.json();
            if (!Array.isArray(datos)) throw Error('El servidor devolvió una respuesta no válida.');
            return datos;
        }
        function valores(campo) {
            const indice = campos.indexOf(campo);
            return [...new Set(clasificacion.filter(fila => campos.slice(0, indice).every(anterior =>
                !$('inventario-' + anterior).value || String(fila[anterior] ?? '') === $('inventario-' + anterior).value
            )).map(fila => String(fila[campo] ?? '').trim()).filter(Boolean))]
                .sort((a, b) => a.localeCompare(b, 'es', { sensitivity: 'base' }));
        }
        function opciones(campo) {
            const input = $('buscar-' + campo + '-inventario');
            const lista = $('opciones-' + campo + '-inventario');
            const seleccion = $('inventario-' + campo).value;
            const filtro = seleccion ? '' : normalizar(input.value);
            lista.replaceChildren();
            for (const valor of ['', ...valores(campo).filter(v => normalizar(v).includes(filtro))]) {
                const opcion = document.createElement('button');
                opcion.type = 'button';
                opcion.className = 'block w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-indigo-50';
                opcion.textContent = valor || etiquetas[campos.indexOf(campo)];
                opcion.addEventListener('click', () => {
                    if (ocupado) return;
                    $('inventario-' + campo).value = valor;
                    input.value = valor;
                    lista.classList.add('hidden');
                    for (const posterior of campos.slice(campos.indexOf(campo) + 1)) limpiar(posterior);
                    mensaje('');
                });
                lista.append(opcion);
            }
            lista.classList.remove('hidden');
        }
        function limpiar(campo) {
            $('inventario-' + campo).value = '';
            $('buscar-' + campo + '-inventario').value = '';
            $('opciones-' + campo + '-inventario').classList.add('hidden');
        }
        async function seleccionar(item) {
            const actual = ++turno;
            solicitud?.abort();
            const controlador = new AbortController();
            solicitud = controlador;
            const timeout = setTimeout(() => controlador.abort(), 20000);
            proveedor = item;
            clasificacion = [];
            $('inventario-proveedor').value = item?.id || '';
            const input = $('buscar-proveedor-inventario');
            input.value = item?.nombre || '';
            input.readOnly = Boolean(item);
            input.classList.toggle('bg-slate-100', Boolean(item));
            $('btn-limpiar-proveedor-inventario').classList.toggle('hidden', !item);
            $('opciones-proveedor-inventario').classList.add('hidden');
            campos.forEach(limpiar);
            mensaje('');
            bloquear(Boolean(item));
            campos.forEach(campo => $('buscar-' + campo + '-inventario').disabled = true);
            try {
                if (!item) return;
                const datos = await consultar('/api/clasificacion?proveedor_id=' + encodeURIComponent(item.id), controlador.signal);
                if (actual !== turno) return;
                clasificacion = datos;
                campos.forEach(campo => {
                    const input = $('buscar-' + campo + '-inventario');
                    input.disabled = false;
                    input.readOnly = false;
                });
            } catch (error) {
                if (actual === turno) mensaje(error.name === 'AbortError' ? 'La carga tardó demasiado. Selecciona nuevamente el proveedor para reintentar.' : error.message);
            } finally {
                clearTimeout(timeout);
                if (actual === turno) bloquear(false);
            }
        }
        function opcionesProveedor() {
            if (ocupado || $('buscar-proveedor-inventario').readOnly) return;
            const texto = normalizar($('buscar-proveedor-inventario').value);
            const lista = $('opciones-proveedor-inventario');
            lista.replaceChildren();
            for (const item of proveedores.filter(p => normalizar(p.nombre).includes(texto))) {
                const opcion = document.createElement('button');
                opcion.type = 'button';
                opcion.className = 'block w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-indigo-50';
                opcion.textContent = item.nombre;
                opcion.addEventListener('click', () => seleccionar(item));
                lista.append(opcion);
            }
            lista.classList.remove('hidden');
        }
        campos.forEach(campo => {
            const input = $('buscar-' + campo + '-inventario');
            input.addEventListener('focus', () => opciones(campo));
            input.addEventListener('click', () => { if (!ocupado && !input.disabled) opciones(campo); });
            input.addEventListener('input', () => {
                $('inventario-' + campo).value = '';
                campos.slice(campos.indexOf(campo) + 1).forEach(limpiar);
                opciones(campo);
            });
            $('btn-limpiar-' + campo + '-inventario').addEventListener('click', () => {
                if (!ocupado) campos.slice(campos.indexOf(campo)).forEach(limpiar);
            });
        });
        $('buscar-proveedor-inventario').addEventListener('input', opcionesProveedor);
        $('buscar-proveedor-inventario').addEventListener('focus', opcionesProveedor);
        $('buscar-proveedor-inventario').addEventListener('click', opcionesProveedor);
        $('btn-limpiar-proveedor-inventario').addEventListener('click', () => { if (!ocupado) seleccionar(null); });
        $('btn-cerrar-importador-inventario').addEventListener('click', cerrar);
        $('btn-cancelar-importador-inventario').addEventListener('click', cerrar);
        modal.addEventListener('keydown', evento => {
            if (evento.key === 'Escape') { evento.stopPropagation(); cerrar(); }
        });
        document.addEventListener('click', evento => {
            for (const campo of ['proveedor', ...campos]) {
                if (!$('combo-' + campo + '-inventario').contains(evento.target)) $('opciones-' + campo + '-inventario').classList.add('hidden');
            }
        });
        boton.addEventListener('click', async () => {
            if (ocupado || !proveedor) return;
            const actual = ++turno;
            solicitud?.abort();
            const controlador = new AbortController();
            solicitud = controlador;
            const timeout = setTimeout(() => controlador.abort(), 20000);
            const seleccionado = proveedor;
            const params = new URLSearchParams({ proveedor_id: seleccionado.id });
            campos.forEach(campo => params.set(campo, $('inventario-' + campo).value));
            bloquear(true);
            carga.querySelector('span').textContent = 'Cargando productos…';
            mensaje('');
            try {
                const productos = await consultar('/api/productos/importar-analisis?' + params, controlador.signal);
                if (actual !== turno) return;
                const codigos = [...new Set(productos.map(p => String(p.codigo_st || p.codigo || '').trim()).filter(Boolean)
                    .map(c => /^\d+$/.test(c) && c.length <= 6 ? c.padStart(6, '0') : c))];
                if (!codigos.length) throw Error('No se encontraron productos con los filtros seleccionados.');
                if (codigos.length > 500) throw Error('La lista supera los 500 códigos. Ajusta los filtros para reducirla.');
                await alImportar(codigos, seleccionado);
                if (actual === turno) cerrar();
            } catch (error) {
                if (actual === turno) mensaje(error.name === 'AbortError' ? 'La consulta tardó demasiado. Puedes reintentar.' : error.message);
            } finally {
                clearTimeout(timeout);
                if (actual === turno) bloquear(false);
            }
        });
        return {
            cerrar,
            async abrir(nombre) {
                const actual = ++turno;
                modal.style.zIndex = '120';
                modal.classList.remove('hidden');
                carga.querySelector('span').textContent = 'Cargando departamentos, grupos, subgrupos y marcas…';
                mensaje('');
                bloquear(true);
                try {
                    proveedores = await obtenerProveedores();
                    if (actual !== turno) return;
                    await seleccionar(proveedores.find(p => normalizar(p.nombre) === normalizar(nombre)) || null);
                    if (!proveedor) $('buscar-proveedor-inventario').focus();
                } catch (error) {
                    if (actual === turno) { bloquear(false); mensaje(error.message); }
                }
            }
        };
    };
})();
