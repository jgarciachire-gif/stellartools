        let coberturaKardexCache = null;
        let promesaCargaCoberturaKardex = null;

        async function actualizarCoberturaKardexDesdeAnalisis(
            mostrarMensaje = true,
            forzarConsulta = false
        ) {
            try {
                if (forzarConsulta) {
                    coberturaKardexCache = null;
                    promesaCargaCoberturaKardex = null;
                }

                if (!coberturaKardexCache) {
                    // Comparador y exportación comparten la misma consulta.
                    if (!promesaCargaCoberturaKardex) {
                        promesaCargaCoberturaKardex = (async () => {
                            const respuesta = await fetch(
                                '/analisis/cobertura-kardex',
                                { credentials: 'same-origin' }
                            );

                            const resultado = await respuesta.json();

                            if (
                                !respuesta.ok ||
                                resultado.status !== 'ok' ||
                                !Array.isArray(resultado.data)
                            ) {
                                throw new Error(
                                    'No se pudo consultar la cobertura del Kardex.'
                                );
                            }

                            return resultado.data;
                        })();
                    }

                    const pendiente = promesaCargaCoberturaKardex;

                    try {
                        const datos = await pendiente;

                        // Una consulta anterior no reemplaza una recarga nueva.
                        if (promesaCargaCoberturaKardex === pendiente) {
                            coberturaKardexCache = datos;
                        }

                        return datos;
                    } finally {
                        if (promesaCargaCoberturaKardex === pendiente) {
                            promesaCargaCoberturaKardex = null;
                        }
                    }
                }

                return coberturaKardexCache;

            } catch (error) {
                console.error('Cobertura del Kardex:', error);

                if (mostrarMensaje) {
                    mostrarMensajeKardex(error.message, true);
                }

                return [];
            }
        }



        function mostrarMensajeKardex(mensaje, error = false) {
            mostrarNotificacion({
                tipo: error ? 'error' : 'info',
                mensaje
            });
        }


        function mostrarEstadoPanelKardex(idMensaje, mensaje, error = false) {
            // Actualiza el mensaje del panel indicado, sin afectar al otro.
            const elemento = document.getElementById(idMensaje);
            if (!elemento) return;

            elemento.textContent = mensaje;
            elemento.classList.remove('hidden', 'text-slate-600', 'text-rose-600');
            elemento.classList.add(error ? 'text-rose-600' : 'text-slate-600');
        }

        function alternarCargaPanelKardex(idCarga, mostrar) {
            // Activa o desactiva únicamente el indicador solicitado.
            const indicador = document.getElementById(idCarga);
            if (!indicador) return;

            indicador.classList.toggle('hidden', !mostrar);
            indicador.classList.toggle('flex', mostrar);
        }

        let animacionAlturaComparacion = null;
        let animacionesContenidoComparacion = [];
        let revisionAlturaComparacion = 0;

        async function ajustarAlturaComparacion(actualizar, mantenerAltura = false) {
            const panel = document.getElementById('kardex-comparacion-contenedor');
            const revision = ++revisionAlturaComparacion;
            // Parte de la altura visible, incluso si la transición anterior sigue activa.
            const alturaInicial = panel.getBoundingClientRect().height;
            animacionAlturaComparacion?.cancel();
            animacionAlturaComparacion = null;
            animacionesContenidoComparacion.forEach(animacion => animacion.cancel());
            animacionesContenidoComparacion = [];

            actualizar();
            panel.style.height = 'auto';
            const alturaFinal = panel.getBoundingClientRect().height;
            panel.style.height = `${alturaInicial}px`;
            panel.style.overflowY = 'hidden';

            const terminar = () => {
                if (revision !== revisionAlturaComparacion) return;
                panel.style.height = mantenerAltura ? `${alturaFinal}px` : '';
                if (!mantenerAltura) {
                    panel.style.overflowY = '';
                }
                animacionAlturaComparacion?.cancel();
                animacionAlturaComparacion = null;
            };

            // Conserva un fotograma con la altura de origen antes de expandir o contraer.
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            if (revision !== revisionAlturaComparacion) return;

            // Da tiempo a percibir el cambio sin acelerar los listados más altos.
            const movimientoReducido = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            const duracion = movimientoReducido ? 180
                : Math.min(1000, 750 + Math.abs(alturaFinal - alturaInicial) * .2);
            animacionesContenidoComparacion = Array.from(panel.children)
                .slice(1)
                .filter(elemento => elemento.getClientRects().length && elemento.textContent.trim())
                .map(elemento => elemento.animate(
                    [{ opacity: 0 }, { opacity: 1 }],
                    {
                        duration: movimientoReducido ? 180 : 320, delay: movimientoReducido ? 0 : 100,
                        easing: 'ease-out', fill: 'backwards'
                    }
                ));

            if (Math.abs(alturaInicial - alturaFinal) < 1) {
                terminar();
                return;
            }

            animacionAlturaComparacion = panel.animate(
                [{ height: `${alturaInicial}px` }, { height: `${alturaFinal}px` }],
                { duration: duracion, easing: 'cubic-bezier(0.4, 0, 0.15, 1)', fill: 'both' }
            );
            animacionAlturaComparacion.onfinish = terminar;
        }


        let importacionKardexEnCurso = false;
        let focoAnteriorImportarKardex = null;
        let archivosKardex = [];

        function elementoModalKardex(id) {
            return document.getElementById(id);
        }

        function actualizarBotonesImportarKardex() {
            const pendientes = archivosKardex.filter(item => item.estado !== 'ok');
            const hayFallidos = pendientes.some(item => item.estado === 'error');

            elementoModalKardex('kardex-archivo-csv').disabled = importacionKardexEnCurso;
            elementoModalKardex('btn-procesar-kardex').disabled = importacionKardexEnCurso;
            elementoModalKardex('btn-cancelar-kardex').disabled = importacionKardexEnCurso;
            elementoModalKardex('btn-cancelar-kardex').textContent = 'Cancelar';

            elementoModalKardex('btn-spinner-kardex')
                .classList.toggle('hidden', !importacionKardexEnCurso);

            // Determina el texto a partir del estado real de la carga.
            elementoModalKardex('btn-texto-kardex').textContent =
                importacionKardexEnCurso ? 'Procesando…'
                    : pendientes.length === 0 ? 'Aceptar'
                        : hayFallidos ? 'Reintentar fallidos'
                            : 'Procesar';
        }

        function seleccionarArchivosKardex() {
            if (importacionKardexEnCurso) return;

            // Una nueva selección comienza un grupo independiente.
            archivosKardex = Array.from(
                elementoModalKardex('kardex-archivo-csv').files || []
            ).map(archivo => ({
                archivo,
                estado: 'pendiente',
                error: '',
                resultado: null
            }));

            elementoModalKardex('contenedor-progreso-kardex').classList.add('hidden');
            elementoModalKardex('resultado-importar-kardex').classList.add('hidden');

            actualizarBotonesImportarKardex();
        }

        function abrirModalImportarKardex() {
            const modal = elementoModalKardex('modal-importar-kardex');
            if (!modal || modal.open || importacionKardexEnCurso) return;

            focoAnteriorImportarKardex = document.activeElement;

            if (modal.parentElement !== document.body) {
                document.body.appendChild(modal);
            }

            elementoModalKardex('form-importar-kardex').reset();
            seleccionarArchivosKardex();

            modal.showModal();
            elementoModalKardex('kardex-archivo-csv').focus();
        }

        function cerrarModalImportarKardex() {
            // Cerrar no interrumpe solicitudes ni revierte registros importados.
            if (importacionKardexEnCurso) return;

            elementoModalKardex('modal-importar-kardex')?.close();
            archivosKardex = [];
            elementoModalKardex('form-importar-kardex').reset();
            focoAnteriorImportarKardex?.focus();
        }

        function mostrarResumenImportarKardex() {
            const correctos = archivosKardex.filter(item => item.estado === 'ok');
            const fallidos = archivosKardex.filter(item => item.estado === 'error');

            const sumar = campo => correctos.reduce(
                (total, item) => total + Number(item.resultado?.[campo] ?? 0),
                0
            );

            const lineas = [
                `Archivos cargados: ${correctos.length} de ${archivosKardex.length}.`,
                `Ventas: ${sumar('filas_venta')}. Recepciones: ${sumar('filas_recepcion')}.`,
                `Registros procesados: ${sumar('registros_consolidados')}.`,
                `Filas ignoradas: ${sumar('filas_ignoradas')}.`,
                '',
                ...archivosKardex.map(item =>
                    item.estado === 'ok'
                        ? `✓ ${item.archivo.name}: cargado.`
                        : item.estado === 'error'
                            ? `✗ ${item.archivo.name}: ${item.error}`
                            : `• ${item.archivo.name}: pendiente.`
                )
            ];

            if (fallidos.length) {
                lineas.push(
                    '',
                    'Reintentar fallidos enviará únicamente los archivos con error.',
                    'Cancelar cerrará el modal y conservará lo ya importado.'
                );
            }

            const elemento = elementoModalKardex('resultado-importar-kardex');

            // Muestra nombres y errores como texto para evitar inyección de HTML.
            elemento.textContent = lineas.join('\n');
            elemento.className =
                'mb-4 max-h-52 overflow-y-auto whitespace-pre-line break-words text-xs ' +
                (fallidos.length ? 'text-rose-600' : 'text-emerald-700');
        }

        async function importarKardexDesdeAnalisis(event) {
            event.preventDefault();
            if (importacionKardexEnCurso) return;

            // Los archivos correctos nunca se vuelven a enviar al reintentar.
            const pendientes = archivosKardex.filter(item => item.estado !== 'ok');

            if (pendientes.length === 0) {
                cerrarModalImportarKardex();
                return;
            }

            const input = elementoModalKardex('kardex-archivo-csv');
            const contenedor = elementoModalKardex('contenedor-progreso-kardex');
            const progreso = elementoModalKardex('progreso-importar-kardex');
            const barra = elementoModalKardex('barra-progreso-kardex');
            const porcentaje = elementoModalKardex('porcentaje-progreso-kardex');
            const estado = elementoModalKardex('texto-estado-progreso-kardex');

            importacionKardexEnCurso = true;
            actualizarBotonesImportarKardex();

            contenedor.classList.remove('hidden');
            barra.classList.add('animate-pulse');
            barra.style.width = '0%';
            progreso.setAttribute('aria-valuenow', '0');
            porcentaje.textContent = '0%';
            elementoModalKardex('resultado-importar-kardex').classList.add('hidden');

            let huboSolicitud = false;

            try {
                for (const [indice, item] of pendientes.entries()) {
                    const archivo = item.archivo;

                    item.estado = 'pendiente';
                    item.error = '';
                    item.resultado = null;

                    estado.textContent =
                        `Procesando ${indice + 1} de ${pendientes.length}: ${archivo.name}`;

                    try {
                        if (!archivo.name.toLowerCase().endsWith('.csv')) {
                            throw new Error('El archivo debe estar en formato CSV.');
                        }

                        if (archivo.size > 50 * 1024 * 1024) {
                            throw new Error('El archivo supera el límite de 50 MB.');
                        }

                        const datos = new FormData();
                        datos.append('file', archivo);

                        huboSolicitud = true;

                        // Conserva el endpoint actual: recibe un archivo por solicitud.
                        const respuesta = await fetch('/analisis/cargar-kardex-ventas', {
                            method: 'POST',
                            body: datos,
                            credentials: 'same-origin'
                        });

                        const resultado = await respuesta.json().catch(() => null);

                        if (!respuesta.ok || resultado?.status !== 'ok') {
                            throw new Error(
                                typeof resultado?.detail === 'string'
                                    ? resultado.detail
                                    : `No se pudo confirmar la carga (HTTP ${respuesta.status}).`
                            );
                        }

                        item.estado = 'ok';
                        item.resultado = resultado;
                    } catch (error) {
                        // Un error individual no detiene el resto de los archivos.
                        item.estado = 'error';
                        item.error = error.message || 'No se pudo cargar el archivo.';
                        console.error(`Importación de ${archivo.name}:`, error);
                    }

                    // El porcentaje mide archivos revisados, incluidos los fallidos.
                    const avance = Math.round(
                        ((indice + 1) / pendientes.length) * 100
                    );

                    barra.style.width = `${avance}%`;
                    porcentaje.textContent = `${avance}%`;
                    progreso.setAttribute('aria-valuenow', String(avance));
                    mostrarResumenImportarKardex();
                }

                const fallidos = archivosKardex.filter(item => item.estado === 'error');

                estado.textContent = fallidos.length
                    ? `Revisión finalizada. Archivos con error: ${fallidos.length}.`
                    : '¡Carga completada correctamente!';

                input.value = '';
            } finally {
                barra.classList.remove('animate-pulse');

                try {
                    if (huboSolicitud) {
                        // Refresca también si un archivo pudo guardarse parcialmente.
                        document.dispatchEvent(new Event('kardex-ventas-actualizado'));
                        await actualizarCoberturaKardexDesdeAnalisis(true, true);
                    }
                } catch (error) {
                    console.error('Error al actualizar la cobertura:', error);
                } finally {
                    importacionKardexEnCurso = false;
                    actualizarBotonesImportarKardex();
                }
            }
        }


        function normalizarSedeKardex(sede) {
            // Unifica el nombre de Ciudad Alianza.
            const valor = String(sede || '').trim().toUpperCase();

            return ['ALIANZA', 'C. ALIANZA'].includes(valor)
                ? 'CIUDAD ALIANZA'
                : valor;
        }

        function obtenerDescripcionesProductosKardex() {
            const descripciones = new Map();

            // Lee los códigos y descripciones visibles en la tabla de análisis.
            document.querySelectorAll('#filas-tabla-analisis tr').forEach(fila => {
                const codigo = normalizarCodigoAnalisis(
                    fila.querySelector('.inp-codigo')?.value || ''
                );

                const descripcion = String(
                    fila.querySelector('.inp-desc')?.value || ''
                ).trim();

                if (codigo) {
                    descripciones.set(codigo, descripcion || 'Sin descripción');
                }
            });

            return descripciones;
        }


        function cerrarResultadosKardex(idContenedor) {
            if (idContenedor === 'kardex-comparacion-contenedor') {
                revisionAlturaComparacion++;
                animacionAlturaComparacion?.cancel();
                animacionAlturaComparacion = null;
                animacionesContenidoComparacion.forEach(animacion => animacion.cancel());
                animacionesContenidoComparacion = [];
                const panel = document.getElementById(idContenedor);
                panel.style.height = '';
                panel.style.overflowY = '';
            }

            document.getElementById(
                idContenedor
            )?.classList.add('hidden');

            if (idContenedor === 'kardex-comparacion-contenedor') {
                // Devuelve el foco al acceso del header.
                document.getElementById(
                    'btn-menu-estadisticas'
                )?.focus({ preventScroll: true });
            }
        }


        function formatearDiasIntervaloKardex(
            diasConVentas,
            diasIntervalo
        ) {
            const dias = Number(diasConVentas ?? 0);
            const intervalo = Number(diasIntervalo);

            if (
                !Number.isInteger(dias) ||
                !Number.isInteger(intervalo) ||
                dias < 0 ||
                intervalo < 1 ||
                dias > intervalo
            ) {
                throw new Error(
                    'La consulta devolvió días de venta o intervalo inválidos.'
                );
            }

            return `${dias}/${intervalo}`;
        }

        let solicitudModalExportacionXML = 0;

        function cerrarModalExportarDemandaXML() {
            // Invalida cualquier carga pendiente del modal cerrado.
            solicitudModalExportacionXML++;

            document.getElementById(
                'modal-exportar-demanda-xml'
            ).close();

            document.querySelector(
                '[x-ref="exportar"]'
            )?.focus({ preventScroll: true });
        }

        async function abrirModalExportarDemandaXML() {
            if (!obtenerCodigosTablaAnalisis().length) {
                mostrarNotificacion({
                    tipo: 'info',
                    mensaje: 'Agrega productos antes de exportar.'
                });
                return;
            }

            const modal = document.getElementById(
                'modal-exportar-demanda-xml'
            );

            if (modal.open) return;

            const solicitud = ++solicitudModalExportacionXML;

            const inicio = document.getElementById('kardex-fecha-inicio');
            const fin = document.getElementById('kardex-fecha-fin');
            const boton = document.getElementById('btn-exportar-demanda-xml');
            const mensaje = document.getElementById(
                'estado-exportacion-demanda-xml'
            );

            inicio.disabled = fin.disabled = boton.disabled = true;
            mensaje.textContent = 'Consultando fechas disponibles…';

            // Apertura nativa con foco contenido dentro del modal.
            modal.showModal();

            const coberturas = await actualizarCoberturaKardexDesdeAnalisis(
                false
            );

            // Descarta respuestas de una apertura anterior.
            if (
                !modal.open ||
                solicitud !== solicitudModalExportacionXML
            ) {
                return;
            }

            const disponibles = coberturas.filter(
                x => x.fecha_minima && x.fecha_maxima
            );

            if (!disponibles.length) {
                mensaje.textContent =
                    'No hay cobertura disponible. Importa el Kardex ' +
                    'o vuelve a intentarlo.';
                return;
            }

            // La exportación abarca todas las tiendas.
            const minimo = disponibles
                .map(x => x.fecha_minima)
                .sort()[0];

            const maximo = disponibles
                .map(x => x.fecha_maxima)
                .sort()
                .at(-1);

            for (const campo of [inicio, fin]) {
                campo.min = minimo;
                campo.max = maximo;
                campo.disabled = false;
            }

            // Sugiere los últimos siete días del historial disponible.
            const desde = new Date(maximo + 'T12:00:00');
            desde.setDate(desde.getDate() - 6);

            const sugerido = fechaISOAnalisis(desde);

            if (
                !fin.value ||
                fin.value < minimo ||
                fin.value > maximo
            ) {
                fin.value = maximo;
            }

            if (
                !inicio.value ||
                inicio.value < minimo ||
                inicio.value > maximo ||
                inicio.value > fin.value
            ) {
                inicio.value = sugerido < minimo ? minimo : sugerido;

                if (inicio.value > fin.value) {
                    inicio.value = fin.value;
                }
            }

            mensaje.textContent =
                'Historial disponible: ' +
                formatearFechaKardex(minimo) + ' a ' +
                formatearFechaKardex(maximo) + '.';

            boton.disabled = false;
            inicio.focus();
        }


        async function exportarDemandaKardexXML() {
            const boton = document.getElementById('btn-exportar-demanda-xml');

            // Evita descargas duplicadas por varios clics.
            if (!boton || boton.disabled) return;

            const fechaInicio = document.getElementById(
                'kardex-fecha-inicio'
            )?.value;

            const fechaFin = document.getElementById(
                'kardex-fecha-fin'
            )?.value;

            if (!fechaInicio || !fechaFin || fechaInicio > fechaFin) {
                alert('Selecciona un período válido para consultar la demanda.');
                return;
            }

            // Consulta solamente los productos presentes en la tabla principal.
            const codigos = [...new Set(obtenerCodigosTablaAnalisis())];

            if (!codigos.length) {
                alert('Agrega al menos un producto a la tabla de análisis.');
                return;
            }


            const parametros = new URLSearchParams({
                fecha_inicio: fechaInicio,
                fecha_fin: fechaFin,
                modo: 'intervalo'
            });


            codigos.forEach(codigo => parametros.append('codigos', codigo));

            // Captura las descripciones antes de iniciar la consulta.
            const descripciones = obtenerDescripcionesProductosKardex();
            const contenidoOriginal = boton.innerHTML;
            let filas = [];

            boton.disabled = true;
            boton.innerHTML = `
        <i class="fa-solid fa-spinner fa-spin mr-1"></i>
        Consultando todas las tiendas...
    `;

            try {
                // Sin filtro de sede: solicita la demanda de todas las tiendas.
                const respuesta = await fetch(
                    `/analisis/demanda-kardex?${parametros.toString()}`,
                    {
                        method: 'GET',
                        credentials: 'same-origin'
                    }
                );

                const resultado = await respuesta.json();

                if (!respuesta.ok) {
                    throw new Error(
                        typeof resultado.detail === 'string'
                            ? resultado.detail
                            : 'No se pudo consultar la demanda de todas las tiendas.'
                    );
                }

                if (!Array.isArray(resultado.data)) {
                    throw new Error('La respuesta de demanda tiene un formato inesperado.');
                }

                const codigosSolicitados = new Set(
                    codigos.map(codigo => normalizarCodigoAnalisis(codigo))
                );

                const registros = resultado.data
                    .filter(item => codigosSolicitados.has(
                        normalizarCodigoAnalisis(item.codigo || '')
                    ))
                    .sort((a, b) => {
                        // Agrupa por tienda y ordena por código dentro de cada tienda.
                        const sedeA = normalizarSedeKardex(a.sede);
                        const sedeB = normalizarSedeKardex(b.sede);

                        return sedeA.localeCompare(sedeB, 'es')
                            || String(a.codigo).localeCompare(String(b.codigo), 'es');
                    });

                if (!registros.length) {
                    alert('No se encontraron ventas para los productos y el período seleccionado.');
                    return;
                }

                const formatoNumero = valor => {
                    const numero = Number(valor ?? 0);

                    if (!Number.isFinite(numero)) {
                        throw new Error('La consulta devolvió una cantidad no válida.');
                    }

                    return numero.toLocaleString('es-VE', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                    });
                };

                // Prepara filas para el exportador existente sin modificar la pantalla.
                filas = registros.map(item => {
                    const codigo = normalizarCodigoAnalisis(item.codigo || '');
                    const fila = document.createElement('tr');

                    const valores = [
                        String(item.sede || '').trim(),
                        codigo,
                        descripciones.get(codigo) || 'Sin descripción',
                        formatoNumero(item.unidades_vendidas),

                        formatearDiasIntervaloKardex(
                            item.dias_con_ventas,
                            resultado.dias_intervalo
                        ),

                        formatoNumero(item.demanda_diaria)
                    ];

                    valores.forEach(valor => {
                        const celda = document.createElement('td');
                        celda.textContent = valor;
                        fila.appendChild(celda);
                    });

                    return fila;
                });
            } catch (error) {
                console.error('Error al consultar demanda para exportar:', error);
                alert(error.message || 'No se pudo consultar la demanda.');
                return;
            } finally {
                boton.disabled = false;
                boton.innerHTML = contenidoOriginal;
            }

            // Continúa aquí el bloque existente: const encabezados = [

            const encabezados = [
                'Sede',
                'Código',
                'Descripción',
                'Unidades vendidas',
                'Días con ventas / Intervalo',
                'Demanda diaria'
            ];

            // Protege los textos y elimina caracteres incompatibles con XML.
            const escaparXML = valor => String(valor)
                .replace(
                    /[^\u0009\u000A\u000D\u0020-\uD7FF\uE000-\uFFFD\u{10000}-\u{10FFFF}]/gu,
                    ''
                )
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&apos;');

            // Convierte el formato visible 1.234,56 a un número de Excel.
            const convertirNumero = texto => {
                const numero = Number(
                    texto.trim()
                        .replace(/\s/g, '')
                        .replace(/\./g, '')
                        .replace(',', '.')
                );

                if (!Number.isFinite(numero)) {
                    throw new Error(`Cantidad no válida: ${texto}`);
                }

                return numero;
            };

            try {
                const cabecera = `
            <Row ss:Height="30">
                ${encabezados.map(titulo => `
                    <Cell ss:StyleID="Cabecera">
                        <Data ss:Type="String">${escaparXML(titulo)}</Data>
                    </Cell>
                `).join('')}
            </Row>
        `;

                const datos = filas.map(fila => `
            <Row>
                ${[...fila.cells].map((celda, indice) => {
                    const texto = celda.textContent.trim();

                    // Sede, código y descripción permanecen como texto.

                    if (indice < 3 || indice === 4) {

                        return `
                            <Cell ss:StyleID="Texto">
                                <Data ss:Type="String">${escaparXML(texto)}</Data>
                            </Cell>
                        `;
                    }

                    // Las cantidades se exportan como números utilizables.
                    const estilo = 'Decimal';

                    return `
                        <Cell ss:StyleID="${estilo}">
                            <Data ss:Type="Number">${convertirNumero(texto)}</Data>
                        </Cell>
                    `;
                }).join('')}
            </Row>
        `).join('');

                // SpreadsheetML: formato XML de hoja de cálculo de Excel.
                const contenido = `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook
    xmlns="urn:schemas-microsoft-com:office:spreadsheet"
    xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
    xmlns:x="urn:schemas-microsoft-com:office:excel">
    <Styles>
        <Style ss:ID="Default" ss:Name="Normal">
            <Alignment ss:Vertical="Center"/>
            <Font ss:FontName="Calibri" ss:Size="11"/>
        </Style>
        <Style ss:ID="Cabecera">
            <Alignment ss:Vertical="Center" ss:WrapText="1"/>
            <Font ss:FontName="Calibri" ss:Size="11"
                ss:Bold="1" ss:Color="#FFFFFF"/>
            <Interior ss:Color="#0F172A" ss:Pattern="Solid"/>
        </Style>
        <Style ss:ID="Texto">
            <NumberFormat ss:Format="@"/>
        </Style>
        <Style ss:ID="Decimal">
            <NumberFormat ss:Format="#,##0.00"/>
        </Style>
        <Style ss:ID="Entero">
            <NumberFormat ss:Format="0"/>
        </Style>
    </Styles>
    <Worksheet ss:Name="Consultar demanda">
        <Table ss:ExpandedColumnCount="6"
            ss:ExpandedRowCount="${filas.length + 1}">
            <Column ss:Width="105"/>
            <Column ss:Width="75"/>
            <Column ss:Width="360"/>
            <Column ss:Width="125"/>
            <Column ss:Width="170"/>
            <Column ss:Width="115"/>
            ${cabecera}
            ${datos}
        </Table>
        <x:WorksheetOptions>
            <x:FreezePanes/>
            <x:FrozenNoSplit/>
            <x:SplitHorizontal>1</x:SplitHorizontal>
            <x:TopRowBottomPane>1</x:TopRowBottomPane>
            <x:ActivePane>2</x:ActivePane>
        </x:WorksheetOptions>
    </Worksheet>
</Workbook>`;

                const archivo = new Blob([contenido], {
                    type: 'application/xml;charset=utf-8'
                });

                const url = URL.createObjectURL(archivo);
                const enlace = document.createElement('a');

                enlace.href = url;
                // Identifica el alcance y el período del documento.
                enlace.download = `demanda_todas_las_tiendas_${fechaInicio}_${fechaFin}.xml`;
                document.body.appendChild(enlace);
                enlace.click();  // Inicia la descarga del XML generado.
                enlace.remove();

                setTimeout(() => URL.revokeObjectURL(url), 1000);

                // Cierra el modal después de generar e iniciar la descarga.
                cerrarModalExportarDemandaXML();
            } catch (error) {
                console.error('Error al exportar demanda:', error);
                alert(error.message || 'No se pudo exportar la demanda.');
            }
        }


        function formatearFechaKardex(fecha) {
            // Convierte AAAA-MM-DD a DD-MM-AAAA sin alterar la fecha.
            const [anio, mes, dia] = String(fecha).split('-');
            return `${dia}-${mes}-${anio}`;
        }



        const MESES_NOMBRE_KARDEX = [
            'Ene.', 'Feb.', 'Mar.', 'Abr.', 'May.', 'Jun.',
            'Jul.', 'Ago.', 'Sep.', 'Oct.', 'Nov.', 'Dic.'
        ];

        let sedeModalMesesKardex = '';
        let anioVistaMesesKardex = new Date().getFullYear();
        let limitesVistaMesesKardex = {
            min: 2000, max: 2100, ultimaFecha: ''
        };
        let mesesDisponiblesVistaKardex = [];
        let mesesElegidosKardex = [];
        let ultimaConfiguracionPeriodosKardex = null;
        let solicitudMesesKardex = 0;

        const dosDigitosMesesKardex = n => String(n).padStart(2, '0');

        const claveMesesKardex = m =>
            `${m.anio}-${dosDigitosMesesKardex(m.mes)}`;

        const nombreMesesKardex = m =>
            `${MESES_NOMBRE_KARDEX[m.mes - 1]} ${m.anio}`;

        function mesesElegidosOrdenadosKardex() {
            return [...mesesElegidosKardex].sort((a, b) =>
                claveMesesKardex(a).localeCompare(claveMesesKardex(b))
            );
        }

        async function consultarMesesDisponiblesKardex(sede, anio) {
            const parametros = new URLSearchParams({
                sede,
                anio: String(anio)
            });

            const respuesta = await fetch(
                `/analisis/meses-kardex?${parametros}`,
                { credentials: 'same-origin' }
            );

            const resultado = await respuesta.json();

            if (!respuesta.ok || resultado.status !== 'ok' ||
                !Array.isArray(resultado.data)) {
                throw new Error(
                    resultado.detail || 'No se pudieron consultar los meses con ventas.'
                );
            }

            return resultado.data;
        }

        function cerrarModalMesesKardex() {
            const modal = document.getElementById(
                'modal-meses-comparacion-kardex'
            );
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }

        async function abrirModalMesesKardex() {
            const modal = document.getElementById(
                'modal-meses-comparacion-kardex'
            );

            const sede = normalizarSedeKardex(
                window.tiendaActivaPestana || 'CENTRO'
            );

            modal.classList.remove('hidden');
            modal.classList.add('flex');

            if (sedeModalMesesKardex !== sede) {
                mesesElegidosKardex = [];
            }

            sedeModalMesesKardex = sede;

            try {
                await actualizarCoberturaKardexDesdeAnalisis(false);

                const cobertura = coberturaKardexCache?.find(
                    x => normalizarSedeKardex(x.sede) === sede
                );

                if (!cobertura?.fecha_minima || !cobertura?.fecha_maxima) {
                    throw new Error(
                        `No existe cobertura de ventas para ${sede}.`
                    );
                }

                limitesVistaMesesKardex = {
                    min: Number(cobertura.fecha_minima.slice(0, 4)),
                    max: Number(cobertura.fecha_maxima.slice(0, 4)),
                    ultimaFecha: cobertura.fecha_maxima
                };

                if (
                    anioVistaMesesKardex < limitesVistaMesesKardex.min ||
                    anioVistaMesesKardex > limitesVistaMesesKardex.max
                ) {
                    anioVistaMesesKardex = limitesVistaMesesKardex.max;
                }

                await cargarAnioMesesKardex(anioVistaMesesKardex);

            } catch (error) {
                document.getElementById(
                    'mensaje-meses-comparacion-kardex'
                ).textContent = error.message;

                document.getElementById(
                    'btn-confirmar-meses-kardex'
                ).disabled = true;
            }
        }

        async function cambiarAnioMesesKardex(delta) {
            const siguiente = anioVistaMesesKardex + delta;

            if (
                siguiente < limitesVistaMesesKardex.min ||
                siguiente > limitesVistaMesesKardex.max
            ) return;

            await cargarAnioMesesKardex(siguiente);
        }

        async function cargarAnioMesesKardex(anio) {
            const solicitud = ++solicitudMesesKardex;
            const sede = sedeModalMesesKardex;

            const mensaje = document.getElementById(
                'mensaje-meses-comparacion-kardex'
            );

            mensaje.textContent = 'Consultando meses disponibles...';

            document.getElementById(
                'btn-confirmar-meses-kardex'
            ).disabled = true;

            try {
                const datos = await consultarMesesDisponiblesKardex(sede, anio);

                if (
                    solicitud !== solicitudMesesKardex ||
                    sede !== sedeModalMesesKardex
                ) return;

                anioVistaMesesKardex = anio;
                mesesDisponiblesVistaKardex = datos;

                pintarMesesKardex();

            } catch (error) {
                if (solicitud !== solicitudMesesKardex) return;

                mensaje.textContent = error.message;

                document.getElementById(
                    'grid-meses-comparacion-kardex'
                ).replaceChildren();
            }
        }

        function pintarMesesKardex() {
            document.getElementById(
                'anio-meses-comparacion-kardex'
            ).textContent = `${anioVistaMesesKardex} · ${sedeModalMesesKardex}`;

            document.getElementById(
                'anio-meses-anterior-kardex'
            ).disabled = anioVistaMesesKardex <= limitesVistaMesesKardex.min;

            document.getElementById(
                'anio-meses-siguiente-kardex'
            ).disabled = anioVistaMesesKardex >= limitesVistaMesesKardex.max;

            const grid = document.getElementById(
                'grid-meses-comparacion-kardex'
            );

            grid.replaceChildren();

            for (let mes = 1; mes <= 12; mes++) {
                const informacion = mesesDisponiblesVistaKardex.find(
                    item => Number(item.mes) === mes
                );

                const elegido = mesesElegidosKardex.some(
                    item =>
                        item.anio === anioVistaMesesKardex &&
                        item.mes === mes
                );

                const inhabilitado = !informacion ||
                    (!elegido && mesesElegidosKardex.length >= 3);

                const etiqueta = document.createElement('label');

                etiqueta.className =
                    `flex items-center gap-2 rounded-lg border p-2 text-xs ${inhabilitado
                        ? 'bg-slate-100 text-slate-400 opacity-60'
                        : elegido
                            ? 'bg-indigo-50 border-indigo-400 text-indigo-900'
                            : 'bg-white border-slate-200 text-slate-700 cursor-pointer'
                    }`;

                etiqueta.title = informacion
                    ? `Ventas registradas: ${informacion.fecha_minima} a ${informacion.fecha_maxima}`
                    : 'Sin ventas registradas para esta sede';

                const casilla = document.createElement('input');
                casilla.type = 'checkbox';
                casilla.checked = elegido;
                casilla.disabled = inhabilitado;
                casilla.className = 'rounded border-slate-300 text-indigo-600';

                casilla.onchange = () =>
                    seleccionarMesKardex(mes, casilla.checked);

                etiqueta.append(
                    casilla,
                    document.createTextNode(MESES_NOMBRE_KARDEX[mes - 1])
                );

                grid.appendChild(etiqueta);
            }

            actualizarFechasModalMesesKardex();
        }

        function seleccionarMesKardex(mes, marcado) {
            const clave =
                `${anioVistaMesesKardex}-${dosDigitosMesesKardex(mes)}`;

            if (marcado) {
                const dato = mesesDisponiblesVistaKardex.find(
                    x => Number(x.mes) === mes
                );

                if (!dato || mesesElegidosKardex.length >= 3) return;

                if (!mesesElegidosKardex.some(
                    x => claveMesesKardex(x) === clave
                )) {
                    mesesElegidosKardex.push({
                        anio: anioVistaMesesKardex,
                        mes,
                        fecha_minima: dato.fecha_minima,
                        fecha_maxima: dato.fecha_maxima
                    });
                }
            } else {
                mesesElegidosKardex = mesesElegidosKardex.filter(
                    x => claveMesesKardex(x) !== clave
                );
            }

            pintarMesesKardex();
        }

        function obtenerLimitesDiasComparacionKardex(meses) {
            if (!meses.length || meses.length > 3) {
                throw new Error('Selecciona entre 1 y 3 meses con ventas.');
            }

            let primero = 1;
            let ultimo = 31;

            for (const mes of meses) {
                const prefijo = claveMesesKardex(mes);
                const minimo = String(mes.fecha_minima || '');
                const maximo = String(mes.fecha_maxima || '');

                // Comprueba que las fechas pertenezcan al mes seleccionado.
                if (
                    !/^\d{4}-\d{2}-\d{2}$/.test(minimo) ||
                    !/^\d{4}-\d{2}-\d{2}$/.test(maximo) ||
                    minimo.slice(0, 7) !== prefijo ||
                    maximo.slice(0, 7) !== prefijo ||
                    minimo > maximo
                ) {
                    throw new Error('Fechas de ventas no disponibles.');
                }

                // Obtiene el intervalo común entre todos los meses.
                primero = Math.max(primero, Number(minimo.slice(-2)));
                ultimo = Math.min(
                    ultimo,
                    Number(maximo.slice(-2)),
                    new Date(Date.UTC(mes.anio, mes.mes, 0)).getUTCDate()
                );
            }

            if (primero > ultimo) {
                throw new Error(
                    'Los meses seleccionados no tienen un intervalo de días ' +
                    'en común con datos cargados.'
                );
            }

            return { primero, ultimo };
        }

        function actualizarFechasModalMesesKardex() {
            const inicio = document.getElementById('meses-comparacion-inicio');
            const fin = document.getElementById('meses-comparacion-fin');
            const meses = mesesElegidosOrdenadosKardex();

            try {
                const { primero, ultimo } =
                    obtenerLimitesDiasComparacionKardex(meses);

                const prefijo = claveMesesKardex(meses[0]);
                const minimo = `${prefijo}-${dosDigitosMesesKardex(primero)}`;
                const maximo = `${prefijo}-${dosDigitosMesesKardex(ultimo)}`;

                // Conserva la selección anterior dentro del rango permitido.
                const ajustarDia = dia =>
                    Math.max(primero, Math.min(dia, ultimo));

                const diaInicio = ajustarDia(
                    Number(inicio.value.slice(-2)) || primero
                );

                const diaFin = Math.max(
                    diaInicio,
                    ajustarDia(Number(fin.value.slice(-2)) || Math.min(15, ultimo))
                );

                for (const calendario of [inicio, fin]) {
                    calendario.disabled = false;

                    // El calendario bloquea fechas anteriores y posteriores.
                    calendario.min = minimo;
                    calendario.max = maximo;

                    calendario.title =
                        `Intervalo disponible para comparar: ` +
                        `${formatearFechaKardex(minimo)} a ` +
                        `${formatearFechaKardex(maximo)}`;
                }

                inicio.value = `${prefijo}-${dosDigitosMesesKardex(diaInicio)}`;
                fin.value = `${prefijo}-${dosDigitosMesesKardex(diaFin)}`;
            } catch (error) {
                // Sin un intervalo válido, impide seleccionar fechas.
                for (const calendario of [inicio, fin]) {
                    calendario.disabled = true;
                    calendario.value = '';
                    calendario.removeAttribute('min');
                    calendario.removeAttribute('max');
                    calendario.removeAttribute('title');
                }
            }

            mostrarResumenMesesKardex();
        }

        function validarIntervalosMesesKardex() {
            const meses = mesesElegidosOrdenadosKardex();
            const { primero, ultimo } =
                obtenerLimitesDiasComparacionKardex(meses);

            const inputInicio = document.getElementById('meses-comparacion-inicio');
            const inputFin = document.getElementById('meses-comparacion-fin');

            const desde = inputInicio.value;
            const hasta = inputFin.value;
            const referencia = claveMesesKardex(meses[0]);

            // Valida también fechas introducidas manualmente.
            if (
                !desde || !hasta ||
                !inputInicio.validity.valid ||
                !inputFin.validity.valid ||
                desde.slice(0, 7) !== referencia ||
                hasta.slice(0, 7) !== referencia ||
                desde > hasta
            ) {
                throw new Error(
                    `Selecciona un intervalo válido entre los días ` +
                    `${primero} y ${ultimo}.`
                );
            }

            const diaInicio = Number(desde.slice(-2));
            const diaFin = Number(hasta.slice(-2));

            if (diaInicio < primero || diaFin > ultimo) {
                throw new Error(
                    `Los datos permiten comparar únicamente entre los días ` +
                    `${primero} y ${ultimo}.`
                );
            }

            return meses.map(mes => {
                const prefijo = claveMesesKardex(mes);
                const inicio = `${prefijo}-${dosDigitosMesesKardex(diaInicio)}`;
                const fin = `${prefijo}-${dosDigitosMesesKardex(diaFin)}`;

                // Verificación adicional contra las fechas reales de cada mes.
                if (inicio < mes.fecha_minima || fin > mes.fecha_maxima) {
                    throw new Error(
                        `${nombreMesesKardex(mes)}: ventas registradas desde ` +
                        `${formatearFechaKardex(mes.fecha_minima)} hasta ` +
                        `${formatearFechaKardex(mes.fecha_maxima)}.`
                    );
                }

                return {
                    anio: mes.anio,
                    mes: mes.mes,
                    inicio,
                    fin,
                    dias: diaFin - diaInicio + 1
                };
            });
        }

        function mostrarResumenMesesKardex() {
            const mensaje = document.getElementById(
                'mensaje-meses-comparacion-kardex'
            );

            const boton = document.getElementById(
                'btn-confirmar-meses-kardex'
            );

            try {
                const periodos = validarIntervalosMesesKardex();

                mensaje.textContent = periodos.map(p =>
                    `${nombreMesesKardex(p)}: ` +
                    `${formatearFechaKardex(p.inicio)} a ` +
                    `${formatearFechaKardex(p.fin)}`
                ).join(' · ');

                boton.disabled = false;

            } catch (error) {
                mensaje.textContent = error.message;
                boton.disabled = true;
            }
        }

        async function confirmarMesesComparacionKardex() {
            let periodos;

            try {
                periodos = validarIntervalosMesesKardex();
            } catch (error) {
                mostrarResumenMesesKardex();
                return;
            }

            cerrarModalMesesKardex();
            await compararDemandaKardexDesdeAnalisis(periodos);
        }



        async function compararDemandaKardexDesdeAnalisis(periodosNuevos = null) {
            const periodos = periodosNuevos ||
                ultimaConfiguracionPeriodosKardex;

            const panel = document.getElementById(
                'kardex-comparacion-contenedor'
            );
            const cabecera = document.getElementById(
                'kardex-comparacion-encabezados'
            );
            const tbody = document.getElementById(
                'kardex-comparacion-resultados'
            );
            const etiqueta = document.getElementById(
                'kardex-comparacion-periodos'
            );
            const boton = document.getElementById(
                'btn-comparar-kardex'
            );

            const sede = normalizarSedeKardex(
                window.tiendaActivaPestana || 'CENTRO'
            );

            const codigos = [...new Set(
                obtenerCodigosTablaAnalisis()
                    .map(normalizarCodigoAnalisis)
                    .filter(Boolean)
            )];

            if (!periodos?.length) {
                mostrarMensajeKardex(
                    'Abre Comparar períodos para seleccionar meses e intervalo.',
                    true
                );
                return;
            }

            if (!codigos.length) {
                mostrarMensajeKardex(
                    'Agrega productos a la tabla antes de comparar.',
                    true
                );
                return;
            }

            boton.disabled = true;

            await ajustarAlturaComparacion(() => {
                panel.classList.remove('hidden');
                cabecera.replaceChildren();
                tbody.replaceChildren();
                etiqueta.textContent = '';

                mostrarEstadoPanelKardex(
                    'kardex-comparacion-mensaje',
                    'Validando meses e intervalos...'
                );

                alternarCargaPanelKardex('cargando-comparacion-periodos', true);
            }, true);

            try {
                // Revalida la disponibilidad en la tienda actual.
                const anios = [...new Set(periodos.map(p => p.anio))];

                const disponibilidad = (
                    await Promise.all(
                        anios.map(anio =>
                            consultarMesesDisponiblesKardex(sede, anio)
                        )
                    )
                ).flat();

                const coberturaActual = coberturaKardexCache?.find(
                    x => normalizarSedeKardex(x.sede) === sede
                );

                for (const p of periodos) {
                    const disponible = disponibilidad.some(
                        x =>
                            Number(x.anio) === p.anio &&
                            Number(x.mes) === p.mes
                    );

                    if (!disponible) {
                        throw new Error(
                            `No hay ventas disponibles en ${nombreMesesKardex(p)} para ${sede}.`
                        );
                    }

                    if (
                        coberturaActual?.fecha_maxima &&
                        p.fin > coberturaActual.fecha_maxima
                    ) {
                        throw new Error(
                            `El intervalo de ${nombreMesesKardex(p)} ` +
                            `supera la última fecha cargada en ${sede}.`
                        );
                    }
                }

                // Consulta hasta tres meses de forma secuencial
                // para limitar la carga simultánea en Supabase.
                const resultados = [];

                for (const [indice, p] of periodos.entries()) {
                    mostrarEstadoPanelKardex(
                        'kardex-comparacion-mensaje',
                        `Consultando ${indice + 1}/${periodos.length}: ` +
                        `${nombreMesesKardex(p)}...`
                    );

                    const parametros = new URLSearchParams({
                        fecha_inicio: p.inicio,
                        fecha_fin: p.fin,
                        modo: 'intervalo'
                    });

                    codigos.forEach(codigo =>
                        parametros.append('codigos', codigo)
                    );

                    const respuesta = await fetch(
                        `/analisis/demanda-kardex?${parametros}`,
                        { credentials: 'same-origin' }
                    );

                    const json = await respuesta.json();

                    if (!respuesta.ok || !Array.isArray(json.data)) {
                        throw new Error(
                            json.detail || 'Error al consultar la demanda del Kardex.'
                        );
                    }

                    const porCodigo = new Map(
                        json.data
                            .filter(x =>
                                normalizarSedeKardex(x.sede) === sede
                            )
                            .map(x => [
                                normalizarCodigoAnalisis(x.codigo),
                                x
                            ])
                    );

                    resultados.push({
                        periodo: p,
                        porCodigo
                    });
                }

                if (
                    normalizarSedeKardex(
                        window.tiendaActivaPestana
                    ) !== sede
                ) {
                    throw new Error(
                        'La tienda cambió durante la comparación.'
                    );
                }

                // Genera los encabezados según los meses elegidos.
                const crearTh = (titulo, alinearDerecha = false) => {
                    const th = document.createElement('th');

                    th.className =
                        `px-3 py-2 whitespace-nowrap ${alinearDerecha ? 'text-right' : 'text-left'
                        }`;

                    th.textContent = titulo;
                    cabecera.appendChild(th);
                };


                ['Código', 'Descripción'].forEach(
                    titulo => crearTh(titulo)
                );



                periodos.forEach(p =>
                    crearTh(`Venta ${MESES_NOMBRE_KARDEX[p.mes - 1]}`, true)
                );

                periodos.forEach(p =>
                    crearTh(`Part. ${MESES_NOMBRE_KARDEX[p.mes - 1]}`, true)
                );

                periodos.forEach(p =>
                    crearTh(`Demanda ${MESES_NOMBRE_KARDEX[p.mes - 1]}`, true)
                );


                crearTh('Variación unidades', true);

                const formatoNumero = numero =>
                    Number(numero).toLocaleString('es-VE', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                    });

                const descripciones =
                    obtenerDescripcionesProductosKardex();

                const crearCelda = (
                    fila,
                    texto,
                    alinearDerecha = false
                ) => {
                    const celda = document.createElement('td');

                    celda.className =
                        `px-3 py-2 border-b border-slate-100 ${alinearDerecha
                            ? 'text-right tabular-nums whitespace-nowrap'
                            : 'text-left'
                        }`;

                    celda.textContent = String(texto);
                    fila.appendChild(celda);

                    return celda;
                };

                // Una fila por producto presente en la tabla principal.

                codigos.forEach(codigo => {
                    const fila = document.createElement('tr');

                    crearCelda(fila, codigo);


                    crearCelda(
                        fila,
                        descripciones.get(codigo) || 'Sin descripción'
                    );

                    const ventas = resultados.map(({ porCodigo }) => {
                        const numero = Number(
                            porCodigo.get(codigo)?.unidades_vendidas ?? 0
                        );

                        if (!Number.isFinite(numero) || numero < 0) {
                            throw new Error(
                                `Ventas inválidas para ${codigo}.`
                            );
                        }

                        return numero;
                    });

                    // Columnas de ventas.
                    ventas.forEach(numero =>
                        crearCelda(fila, formatoNumero(numero), true)
                    );

                    // Columnas de participación.
                    resultados.forEach(({ periodo, porCodigo }) => {
                        const dias = Number(
                            porCodigo.get(codigo)?.dias_con_ventas ?? 0
                        );

                        if (
                            !Number.isInteger(dias) ||
                            dias < 0 ||
                            dias > periodo.dias
                        ) {
                            throw new Error(
                                `Días con ventas inválidos para ${codigo}.`
                            );
                        }

                        crearCelda(
                            fila,
                            `${dias}/${periodo.dias}`,
                            true
                        );
                    });

                    // Demanda = unidades vendidas / días de intervalo.
                    ventas.forEach((numero, indice) => {
                        const demanda = numero / periodos[indice].dias;

                        crearCelda(
                            fila,
                            formatoNumero(demanda),
                            true
                        );
                    });

                    // Una única columna con las variaciones consecutivas.
                    const celdaVariacion = crearCelda(fila, '', true);

                    if (periodos.length === 1) {
                        celdaVariacion.textContent = '—';
                    }

                    for (let i = 1; i < periodos.length; i++) {
                        const anterior = ventas[i - 1];
                        const actual = ventas[i];

                        const linea = document.createElement('div');

                        let texto;
                        let color = 'text-slate-500';

                        if (anterior === 0 && actual > 0) {
                            texto = '↑ Nuevo (sin base %)';
                            color = 'text-emerald-600';

                        } else if (anterior === 0) {
                            texto = '→ 0,00 %';

                        } else {
                            const variacion =
                                ((actual - anterior) / anterior) * 100;

                            if (variacion > 0) {
                                texto =
                                    `↑ +${formatoNumero(variacion)} %`;
                                color = 'text-emerald-600';

                            } else if (variacion < 0) {
                                texto =
                                    `↓ ${formatoNumero(variacion)} %`;
                                color = 'text-rose-600';

                            } else {
                                texto = '→ 0,00 %';
                            }
                        }

                        linea.className =
                            `${color} font-semibold whitespace-nowrap`;

                        linea.textContent =
                            `${MESES_NOMBRE_KARDEX[periodos[i - 1].mes - 1]}` +
                            `→${MESES_NOMBRE_KARDEX[periodos[i].mes - 1]}: ` +
                            texto;

                        celdaVariacion.appendChild(linea);
                    }

                    tbody.appendChild(fila);
                });

                etiqueta.textContent = periodos.map(p =>
                    `${nombreMesesKardex(p)}: ` +
                    `${formatearFechaKardex(p.inicio)} a ` +
                    `${formatearFechaKardex(p.fin)}`
                ).join(' | ') +
                    ` · ${periodos[0].dias} días por intervalo.`;

                // Permite actualizar la comparación al cambiar de tienda.
                ultimaConfiguracionPeriodosKardex =
                    periodos.map(p => ({ ...p }));

                const mensajeComparacion = document.getElementById('kardex-comparacion-mensaje');
                mensajeComparacion.textContent = '';
                mensajeComparacion.classList.add('hidden');

            } catch (error) {
                cabecera.replaceChildren();
                tbody.replaceChildren();

                mostrarEstadoPanelKardex(
                    'kardex-comparacion-mensaje',
                    error.message || 'Error al comparar los meses.',
                    true
                );

            } finally {
                await ajustarAlturaComparacion(() => {
                    alternarCargaPanelKardex('cargando-comparacion-periodos', false);
                });

                boton.disabled = false;
            }
        }
