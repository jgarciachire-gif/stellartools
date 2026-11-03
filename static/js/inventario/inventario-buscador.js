
    (() => {
        'use strict';

        const raiz = document.getElementById('buscador-inventarios');
        if (!raiz) return;

        const input = document.getElementById('input-buscador-inventarios');
        const badges = document.getElementById('badges-buscador-inventarios');
        const lista = document.getElementById('listado-inventarios');
        const estado = document.getElementById('estado-buscador-inventarios');
        const spinner = document.getElementById('spinner-buscador-inventarios');
        const limpiar = document.getElementById('limpiar-buscador-inventarios');
        const btnTienda = document.getElementById('btn-tiendas-buscador');
        const menuTienda = document.getElementById('menu-tiendas-buscador');
        const btnFecha = document.getElementById('btn-fecha-buscador');
        const inputFecha = document.getElementById('fecha-buscador-inventarios');

        if (!input || !badges || !lista || !estado) return;

        const TIENDAS = [
            'CENTRO', 'NAGUANAGUA', 'ISABELICA',
            'CIUDAD ALIANZA', 'GARIBALDI', 'SAN DIEGO'
        ];

        const esProvisional = raiz.dataset.esProvisional === 'true';
        const tiendaAsignada = raiz.dataset.tiendaAsignada || '';

        let criterios = [];
        let tienda = '';
        let fecha = '';
        let fechaHasta = '';
        let filtrosAdicionales = new URLSearchParams();
        let temporizador = null;
        let temporizadorSpinner = null;
        let controlador = null;
        let secuencia = 0;

        const normalizar = valor => String(valor || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .trim()
            .toLowerCase();

        // Validar y convertir dd/mm, dd-mm-aa y dd-mm-aaaa.
        function interpretarFecha(valor) {
            const m = String(valor).trim()
                .match(/^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2}|\d{4}))?$/);

            if (!m) return null;

            const dia = Number(m[1]);
            const mes = Number(m[2]);
            const actual = new Date().getFullYear();
            const anio = !m[3] ? actual :
                m[3].length === 2 ? 2000 + Number(m[3]) : Number(m[3]);

            const comprobacion = new Date(anio, mes - 1, dia);

            if (comprobacion.getFullYear() !== anio ||
                comprobacion.getMonth() !== mes - 1 ||
                comprobacion.getDate() !== dia) return null;

            return `${anio}-${String(mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
        }

        function fechaVisible(iso) {
            const [anio, mes, dia] = iso.split('-');
            return `${dia}/${mes}/${anio}`;
        }

        // Reconstruir criterios al volver a la página o usar paginación.
        function recuperarURL() {
            const params = new URLSearchParams(location.search);
            criterios = params.getAll('tags').slice(0, 12)
                .map(t => t.trim().slice(0, 150)).filter(Boolean);
            tienda = esProvisional ? tiendaAsignada : (params.get('tienda') || '');
            fecha = params.get('fecha_desde') || '';
            fechaHasta = params.get('fecha_hasta') || '';
            filtrosAdicionales = new URLSearchParams();
            ['realizado_por', 'estado'].forEach(clave => {
                if (params.get(clave)) filtrosAdicionales.set(clave, params.get(clave));
            });
            input.value = params.get('q') || '';
            inputFecha.value = fecha;
            dibujarBadges();
        }

        // Crear badges seguros, sin inyectar HTML recibido del usuario.
        function crearBadge(texto, tipo, eliminar) {
            const badge = document.createElement('span');
            badge.className = 'inline-flex max-w-full items-center gap-1 rounded-md ' +
                'border border-indigo-200 bg-indigo-50 px-2 py-1 ' +
                'text-[11px] font-semibold text-indigo-700';

            const etiqueta = document.createElement('span');
            etiqueta.className = 'max-w-[180px] truncate';
            etiqueta.textContent = texto;

            const boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'ml-0.5 text-indigo-400 hover:text-rose-600';
            boton.textContent = '×';
            boton.setAttribute('aria-label', `Quitar ${texto}`);
            boton.addEventListener('click', eliminar);

            badge.appendChild(etiqueta);
            if (tipo !== 'fija') badge.appendChild(boton);
            badges.appendChild(badge);
        }

        function dibujarBadges() {
            badges.replaceChildren();

            criterios.forEach((texto, indice) => {
                crearBadge(texto, 'texto', () => {
                    criterios.splice(indice, 1);
                    dibujarBadges();
                    programarBusqueda(0);
                });
            });

            if (tienda) {
                crearBadge(tienda, esProvisional ? 'fija' : 'tienda', () => {
                    if (esProvisional) return;
                    tienda = '';
                    dibujarBadges();
                    programarBusqueda(0);
                });
            }

            filtrosAdicionales.forEach((valor, clave) => {
                crearBadge(valor, clave, () => {
                    filtrosAdicionales.delete(clave);
                    programarBusqueda(0);
                });
            });

            if (fecha || fechaHasta) {
                const etiquetaFecha = fecha && fechaHasta && fecha !== fechaHasta
                    ? `${fechaVisible(fecha)} – ${fechaVisible(fechaHasta)}`
                    : fechaVisible(fecha || fechaHasta);
                crearBadge(etiquetaFecha, 'fecha', () => {
                    fecha = '';
                    fechaHasta = '';
                    inputFecha.value = '';
                    dibujarBadges();
                    programarBusqueda(0);
                });
            }

            limpiar.classList.toggle(
                'hidden',
                !(criterios.length || (!esProvisional && tienda) || fecha || fechaHasta ||
                    filtrosAdicionales.size || input.value.trim())
            );
        }

        function agregarCriterio() {
            const valor = input.value.trim();
            if (!valor) return;

            const fechaDetectada = interpretarFecha(valor);

            if (fechaDetectada) {
                fecha = fechaDetectada;
                fechaHasta = fechaDetectada;
                inputFecha.value = fecha;
            } else if (
                criterios.length < 12 &&
                !criterios.some(t => normalizar(t) === normalizar(valor))
            ) {
                criterios.push(valor);
            } else if (criterios.length >= 12) {
                estado.textContent = 'Puedes agregar hasta 12 criterios.';
                return;
            }

            input.value = '';
            dibujarBadges();
            programarBusqueda(0);
        }

        // Preparar parámetros compatibles con inventario.py.
        function construirURL(pagina = 1) {
            const url = new URL('/inventario', location.origin);
            const p = url.searchParams;

            if (input.value.trim()) p.set('q', input.value.trim());

            criterios.forEach(t => p.append('tags', t));

            if (tienda) p.set('tienda', tienda);

            if (fecha) p.set('fecha_desde', fecha);
            if (fechaHasta) p.set('fecha_hasta', fechaHasta);
            filtrosAdicionales.forEach((valor, clave) => p.set(clave, valor));

            p.set('page', String(pagina));
            return url;
        }

        function programarBusqueda(demora = 250) {
            clearTimeout(temporizador);
            clearTimeout(temporizadorSpinner);
            controlador?.abort();
            secuencia++;
            spinner.classList.add('hidden');
            dibujarBadges();
            temporizador = setTimeout(() => buscar(), demora);
        }

        async function buscar(pagina = 1, actualizarURL = true) {
            clearTimeout(temporizador);
            clearTimeout(temporizadorSpinner);

            controlador?.abort();
            controlador = new AbortController();
            const turno = ++secuencia;
            const url = construirURL(pagina);

            temporizadorSpinner = setTimeout(() => {
                if (turno === secuencia) {
                    spinner.classList.remove('hidden');
                    estado.textContent = 'Buscando inventarios...';
                }
            }, 120);

            try {
                const respuesta = await fetch(url, {
                    signal: controlador.signal,
                    credentials: 'same-origin',
                    headers: { 'Accept': 'text/html' }
                });

                if (!respuesta.ok || respuesta.redirected) {
                    throw new Error('No se pudo actualizar la búsqueda.');
                }

                const documento = new DOMParser().parseFromString(
                    await respuesta.text(), 'text/html'
                );

                const nuevoListado = documento.getElementById('listado-inventarios');
                const nuevoEstado = documento.getElementById('estado-buscador-inventarios');

                if (!nuevoListado || !nuevoEstado) {
                    throw new Error('Respuesta de inventarios no válida.');
                }

                if (turno !== secuencia) return;

                // Sustituir resultados sin recargar toda la página.
                const listadoActual = document.getElementById('listado-inventarios');
                if (!listadoActual) throw new Error('No se encontró el listado actual.');
                listadoActual.replaceWith(nuevoListado);
                window.formatearFechasInventarios?.();

                // Restaurar eventos de selección de filas.
                window.reconectarSeleccionInventarios?.();

                estado.textContent = nuevoEstado.textContent.trim();

                if (actualizarURL) {
                    history.replaceState(null, '', url.pathname + url.search);
                }
            } catch (error) {
                if (error.name !== 'AbortError' && turno === secuencia) {
                    estado.textContent = 'Error de conexión. Intenta nuevamente.';
                    console.error('Error buscando inventarios:', error);
                }
            } finally {
                if (turno === secuencia) {
                    clearTimeout(temporizadorSpinner);
                    spinner.classList.add('hidden');
                }
            }
        }

        // Consultar al escribir, sin bloquear el teclado.
        input.addEventListener('input', () => programarBusqueda());

        input.addEventListener('keydown', evento => {
            if (evento.isComposing) return;
            if (evento.key === 'Enter') {
                evento.preventDefault();
                agregarCriterio();
            } else if (
                evento.key === 'Backspace' &&
                !input.value &&
                criterios.length
            ) {
                criterios.pop();
                programarBusqueda(0);
            }
        });

        // Selector de tiendas.
        TIENDAS.forEach(nombre => {
            if (esProvisional && nombre !== tiendaAsignada) return;

            const opcion = document.createElement('button');
            opcion.type = 'button';
            opcion.className = 'block w-full rounded-lg px-3 py-2 ' +
                'text-left text-xs text-slate-700 hover:bg-indigo-50';
            opcion.textContent = nombre;

            opcion.addEventListener('click', () => {
                tienda = nombre;
                menuTienda.classList.add('hidden');
                btnTienda.setAttribute('aria-expanded', 'false');
                programarBusqueda(0);
            });

            menuTienda.appendChild(opcion);
        });

        btnTienda.addEventListener('click', () => {
            const abierto = menuTienda.classList.toggle('hidden') === false;
            btnTienda.setAttribute('aria-expanded', String(abierto));
        });

        document.addEventListener('click', evento => {
            if (!document.getElementById('selector-tiendas-buscador')
                .contains(evento.target)) {
                menuTienda.classList.add('hidden');
                btnTienda.setAttribute('aria-expanded', 'false');
            }
        });

        // Calendario nativo.
        btnFecha.addEventListener('click', () => {
            if (typeof inputFecha.showPicker === 'function') {
                try { inputFecha.showPicker(); } catch { inputFecha.focus(); inputFecha.click(); }
            } else {
                inputFecha.click();
            }
        });

        inputFecha.addEventListener('change', () => {
            fecha = inputFecha.value;
            fechaHasta = fecha;
            programarBusqueda(0);
        });

        limpiar.addEventListener('click', () => {
            criterios = [];
            tienda = esProvisional ? tiendaAsignada : '';
            fecha = '';
            fechaHasta = '';
            filtrosAdicionales = new URLSearchParams();
            input.value = '';
            inputFecha.value = '';
            programarBusqueda(0);
            input.focus();
        });

        // Conservar la actualización automática en la paginación.
        document.addEventListener('click', evento => {
            const enlace = evento.target.closest('#listado-inventarios a[href]');
            if (!enlace || evento.defaultPrevented || evento.button !== 0 ||
                evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.altKey) return;

            const url = new URL(enlace.href, location.origin);
            if (url.pathname !== '/inventario') return;

            evento.preventDefault();
            const pagina = Math.max(Number(url.searchParams.get('page')) || 1, 1);
            buscar(pagina);
        });

        recuperarURL();

        window.addEventListener('popstate', () => {
            recuperarURL();
            buscar(Number(new URLSearchParams(location.search).get('page')) || 1, false);
        });

        // Fin de la inicialización de Administrar Listas.

    })();
