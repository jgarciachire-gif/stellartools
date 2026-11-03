        // Obtiene los códigos del pedido actual para las consultas y exportaciones.
        function obtenerCodigosTablaAnalisis() {
            return [
                ...new Set(
                    Array.from(
                        document.querySelectorAll(
                            '#filas-tabla-analisis .inp-codigo'
                        )
                    )
                        .map(input =>
                            normalizarCodigoAnalisis(input.value)
                        )
                        .filter(Boolean)
                )
            ];
        }


        function fechaISOAnalisis(fecha) {
            const anio = fecha.getFullYear();
            const mes = String(fecha.getMonth() + 1).padStart(2, '0');
            const dia = String(fecha.getDate()).padStart(2, '0');

            return `${anio}-${mes}-${dia}`;
        }

        const SEDES_SUGERIDOS = [
            'CENTRO', 'NAGUANAGUA', 'ISABELICA',
            'CIUDAD ALIANZA', 'GARIBALDI', 'SAN DIEGO'
        ];

        let demandasTooltip = new Map();
        let fechaDemandaTooltip = '';
        let calculandoSugeridos = false;

        function numeroDemandaAnalisis(valor) {
            const numero = Number(String(valor ?? 0).replace(',', '.'));
            return Number.isFinite(numero) && numero > 0 ? numero : 0;
        }

        function fechaCaracasSugeridos() {
            return new Intl.DateTimeFormat('en-CA', {
                timeZone: 'America/Caracas'
            }).format(new Date());
        }

        function claveDemandaTooltip(sede, codigo) {
            return JSON.stringify([sede, codigo]);
        }

        async function cargarDemandasTooltip(codigos) {
            if (!codigos.length) {
                throw new Error('Agrega productos para calcular.');
            }

            // Solo reemplaza la memoria cuando todos los lotes están completos.
            const nuevas = new Map();
            const fechaSolicitud = fechaCaracasSugeridos();

            for (let inicio = 0; inicio < codigos.length; inicio += 50) {
                const lote = codigos.slice(inicio, inicio + 50);

                const respuesta = await fetch('/analisis/sugeridos-tooltip-lote', {
                    method: 'POST',
                    credentials: 'same-origin',
                    cache: 'no-store',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ codigos: lote }),
                    signal: AbortSignal.timeout(60000)
                });

                const resultado = await respuesta.json();

                if (!respuesta.ok) {
                    throw new Error(
                        resultado.detail || 'No se pudo consultar la demanda.'
                    );
                }

                if (
                    resultado.fecha_referencia !== fechaSolicitud ||
                    !Array.isArray(resultado.data)
                ) {
                    throw new Error('Respuesta de demanda inválida o desactualizada.');
                }

                const clavesLote = new Set();

                for (const item of resultado.data) {
                    const clave = claveDemandaTooltip(item.sede, item.codigo);

                    if (
                        !SEDES_SUGERIDOS.includes(item.sede) ||
                        !lote.includes(item.codigo) ||
                        clavesLote.has(clave) ||
                        typeof item.demanda_diaria !== 'number' ||
                        !Number.isFinite(item.demanda_diaria) ||
                        item.demanda_diaria < 0
                    ) {
                        throw new Error('Se recibieron datos de demanda inválidos.');
                    }

                    clavesLote.add(clave);
                    nuevas.set(clave, item.demanda_diaria);
                }

                if (clavesLote.size !== lote.length * SEDES_SUGERIDOS.length) {
                    throw new Error('La consulta devolvió información incompleta.');
                }
            }

            if (fechaSolicitud !== fechaCaracasSugeridos()) {
                throw new Error('Cambió la fecha. Vuelve a calcular.');
            }

            demandasTooltip = nuevas;
            fechaDemandaTooltip = fechaSolicitud;
        }

        function ejecutarCalculoSugeridosSync() {
            // No modifica cantidades antes de cargar la demanda del día.
            if (fechaDemandaTooltip !== fechaCaracasSugeridos()) return;

            const dias = Number(
                document.getElementById('dias_cobertura').value
            );

            const texto = document.getElementById(
                'porcentaje_crecimiento'
            ).value;

            if (
                !Number.isSafeInteger(dias) ||
                dias < 1 ||
                !/^\d{0,2}$/.test(texto)
            ) {
                return;
            }

            const crecimiento = Number(texto || 0);

            guardarEstadoTablaEnMemoria(tiendaActivaPestana);

            // Prepara todos los resultados antes de modificar cantidades.
            const cambios = [];

            document.querySelectorAll('#filas-tabla-analisis tr').forEach(tr => {
                const codigo = normalizarCodigoAnalisis(
                    tr.querySelector('.inp-codigo')?.value || ''
                );

                if (!codigo) return;

                // Los productos aún no consultados conservan sus cantidades.
                if (SEDES_SUGERIDOS.some(sede =>
                    !demandasTooltip.has(claveDemandaTooltip(sede, codigo))
                )) {
                    return;
                }

                const pre = Number(tr.querySelector('.inp-pre')?.value);

                if (!Number.isFinite(pre) || pre <= 0) {
                    throw new Error(
                        `Revisa la presentación del producto ${codigo}.`
                    );
                }

                SEDES_SUGERIDOS.forEach(sede => {
                    const datos = matrizTiendas[sede]?.[codigo] || {};
                    const invEmp = numeroDemandaAnalisis(datos.invEmp);

                    const demanda = demandasTooltip.get(
                        claveDemandaTooltip(sede, codigo)
                    );

                    // Calcula la demanda de cobertura y aplica el crecimiento.
                    const demandaProyectada = demanda * dias *
                        (1 + crecimiento / 100);

                    // Convierte el inventario de empaques a unidades y lo descuenta.
                    const necesidad = Math.max(
                        0,
                        demandaProyectada - invEmp * pre
                    );

                    // Convierte las unidades faltantes a empaques.
                    const cantidad = necesidad / pre;

                    // Redondea hacia arriba evitando errores decimales mínimos.
                    const emp = cantidad > 0
                        ? Math.max(1, Math.ceil(
                            cantidad -
                            Number.EPSILON * Math.max(1, cantidad) * 4
                        ))
                        : 0;

                    if (!Number.isSafeInteger(emp)) {
                        throw new Error(
                            `Cantidad fuera de rango para ${codigo}.`
                        );
                    }

                    cambios.push({
                        sede,
                        codigo,
                        datos: { ...datos, invEmp, pre, emp }
                    });
                });
            });

            cambios.forEach(({ sede, codigo, datos }) => {
                asegurarEstructuraTienda(sede);
                matrizTiendas[sede][codigo] = datos;
            });

            cargarEstadoTablaDesdeMemoria(tiendaActivaPestana);
        }

        async function calcularSugeridoSedeActual() {
            if (calculandoSugeridos) return;

            calculandoSugeridos = true;

            const controles = [
                'dias_cobertura',
                'porcentaje_crecimiento'
            ].map(id => document.getElementById(id));

            controles.forEach(input => { input.disabled = true; });

            try {
                await cargarDemandasTooltip(obtenerCodigosTablaAnalisis());
                ejecutarCalculoSugeridosSync();

            } catch (error) {
                console.error('Error al calcular sugeridos:', error);

                mostrarNotificacion({
                    tipo: 'error',
                    mensaje: error.message || 'No se pudo calcular el sugerido.'
                });

            } finally {
                calculandoSugeridos = false;
                controles.forEach(input => { input.disabled = false; });
            }
        }

        function prepararParametroSugerido(input, evento) {
            const insertando = evento.inputType?.startsWith('insert');

            // La primera escritura reemplaza el valor anterior.
            if (
                insertando &&
                (input.dataset.reemplazar === '1' || input.value === '0')
            ) {
                input.value = '';
                input.setSelectionRange(0, 0);
            }

            // Los siguientes dígitos completan la nueva cantidad.
            input.dataset.reemplazar = '0';
        }

        function normalizarParametroSugerido(input, limite = 0) {
            // Conserva únicamente dígitos y elimina ceros iniciales.
            let valor = input.value
                .replace(/\D/g, '')
                .replace(/^0+(?=\d)/, '');

            if (limite > 0) {
                valor = valor.slice(0, limite);
            }

            // Borrar todo deja el campo en cero.
            input.value = valor || '0';

            recargarSugeridosEnTabla();
        }

        function recargarSugeridosEnTabla() {
            if (calculandoSugeridos) return;

            try {
                // Reutiliza la demanda en memoria, sin consultar nuevamente.
                ejecutarCalculoSugeridosSync();

            } catch (error) {
                mostrarNotificacion({
                    tipo: 'error',
                    mensaje: error.message
                });
            }
        }

        document.addEventListener('DOMContentLoaded', async () => {
            // Prepara la vista inicial sin modificar el cálculo de sugeridos.
            cambiarTiendaPestana('CENTRO');

            // La pestaña puede estar ya activa y no ejecutar su cambio.
            await actualizarCoberturaKardexDesdeAnalisis(true);
        });
