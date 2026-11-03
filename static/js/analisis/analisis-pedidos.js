        // Asegura la existencia de la variable en el objeto global de la ventana
        if (typeof window.matrizDatosPorSede === 'undefined') {
            window.matrizDatosPorSede = {};
        }

        function escapeHTML(valor) {
            return String(valor ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        async function guardarPlantillaCompleta() {
            try {
                // Obtiene el proveedor actual.
                const rawProvId = document.getElementById(
                    'proveedor_id_analisis'
                )?.value;

                // Convierte el proveedor a número cuando exista.
                const proveedorId = rawProvId
                    ? parseInt(rawProvId, 10)
                    : null;

                // Obtiene los días de cobertura.
                const diasCobertura = parseInt(
                    document.getElementById('dias_cobertura')?.value || 7,
                    10
                );

                // Guarda antes la tienda visible.
                const sedeActual = (
                    typeof tiendaActivaPestana !== 'undefined'
                    && tiendaActivaPestana
                )
                    ? tiendaActivaPestana.trim().toUpperCase()
                    : 'CENTRO';

                // Garantiza que exista la estructura de memoria.
                asegurarEstructuraTienda(sedeActual);

                // Sincroniza lo visible con la memoria.
                guardarEstadoTablaEnMemoria(sedeActual);

                // Obtiene únicamente los códigos de la tabla.
                const codigosVisiblesEnHTML = new Set(
                    Array.from(
                        document.querySelectorAll(
                            '#filas-tabla-analisis .inp-codigo'
                        )
                    )
                        .map(input =>
                            normalizarCodigoAnalisis(input.value)
                        )
                        .filter(Boolean)
                );

                // Elimina de memoria productos que ya no existen en pantalla.
                for (const sede in matrizTiendas) {
                    for (const codigo in matrizTiendas[sede]) {
                        if (!codigosVisiblesEnHTML.has(codigo)) {
                            delete matrizTiendas[sede][codigo];
                        }
                    }
                }

                // Construye un único arreglo para todas las sedes.
                const filasDetalle = [];

                for (const sede in matrizTiendas) {
                    for (const codigo in matrizTiendas[sede]) {
                        const item = matrizTiendas[sede][codigo];

                        // Ignora registros inexistentes.
                        if (!item) continue;

                        // Obtiene inventario/empaque guardado.
                        const valInv = parseFloat(
                            item.invEmp
                            ?? item.inv
                            ?? item.inventario
                            ?? item.sugerido
                            ?? item.stock
                            ?? 0
                        ) || 0;

                        // Obtiene pedido final.
                        const valEmp = parseFloat(
                            item.emp
                            ?? item.pedido_final
                            ?? 0
                        ) || 0;

                        // Mantiene el comportamiento actual de no guardar filas totalmente vacías.
                        if (valInv > 0 || valEmp > 0) {
                            filasDetalle.push({
                                sede: sede,
                                codigo: codigo,
                                sugerido: valInv,
                                pedido_final: valEmp
                            });
                        }
                    }
                }

                // No tiene sentido realizar una llamada si no hay datos.
                if (filasDetalle.length === 0) {
                    await mostrarAlerta({
                        tipo: 'warning',
                        titulo: 'Sin datos',
                        mensaje: 'No hay datos ingresados en la tabla para guardar.'
                    });

                    return;
                }

                // Envía TODO el pedido en una sola petición a FastAPI.
                const response = await fetch(
                    '/analisis/guardar-pedido',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            proveedor_id: proveedorId,
                            dias_cobertura: diasCobertura,
                            detalles: filasDetalle
                        })
                    }
                );

                // Intenta interpretar la respuesta.
                const resultado = await response.json().catch(
                    () => ({})
                );

                // Detiene el flujo ante un error HTTP.
                if (!response.ok) {
                    throw new Error(
                        resultado.detail
                        || 'No se pudo guardar el pedido.'
                    );
                }

                // Confirma guardado exitoso.
                mostrarNotificacion({
                    tipo: 'success',
                    mensaje: 'Pedido guardado correctamente.'
                });

            } catch (err) {
                // Muestra el error real en consola.
                console.error(
                    'Error al guardar el pedido:',
                    err
                );

                // Mensaje amigable al usuario.
                await mostrarAlerta({
                    tipo: 'error',
                    titulo: 'Error al guardar',
                    mensaje:
                        err.message || 'Error desconocido.'
                });
            }
        }
        // Función adaptada para cargar el pedido más reciente del usuario
        async function cargarUltimoPedidoGuardado() {
            try {
                // Solicita al backend el último pedido del usuario autenticado.
                const response = await fetch(
                    '/analisis/ultimo-pedido'
                );

                // Convierte la respuesta.
                const resultado = await response.json();

                // Valida HTTP.
                if (!response.ok) {
                    throw new Error(
                        resultado.detail
                        || 'No se pudo cargar el pedido.'
                    );
                }

                // Verifica que exista un pedido guardado.
                if (!resultado.encontrado) {
                    await mostrarAlerta({
                        tipo: 'info',
                        titulo: 'Sin pedido guardado',
                        mensaje: 'No se encontró ningún pedido guardado para este usuario.'
                    });

                    return;
                }

                // Extrae las estructuras recibidas.
                const analisis = resultado.analisis || {};
                const proveedor = resultado.proveedor || {};
                const detalles = resultado.detalles || [];
                const productos = resultado.productos || [];

                // Restaura días de cobertura.
                const inputDias = document.getElementById(
                    'dias_cobertura'
                );

                if (
                    inputDias
                    && analisis.dias_cobertura !== null
                    && analisis.dias_cobertura !== undefined
                ) {
                    inputDias.value = analisis.dias_cobertura;
                }

                // Restaura el proveedor.
                const inputProvId = document.getElementById(
                    'proveedor_id_analisis'
                );

                if (inputProvId) {
                    inputProvId.value =
                        analisis.proveedor_id || '';
                }

                // Restaura el nombre visible.
                const inputProvNombre = document.getElementById(
                    'buscar_proveedor_analisis'
                );

                if (inputProvNombre) {
                    inputProvNombre.value =
                        proveedor.nombre || '';
                }

                // Limpia la matriz anterior.
                if (typeof matrizTiendas !== 'undefined') {
                    for (const key in matrizTiendas) {
                        delete matrizTiendas[key];
                    }
                }

                // Limpia las filas actuales.
                const tbody = document.getElementById(
                    'filas-tabla-analisis'
                );

                if (tbody) {
                    tbody.innerHTML = '';
                }

                // Mapea productos por código para acceso inmediato.
                const productosMap = new Map(
                    productos.map(producto => [
                        normalizarCodigoAnalisis(
                            producto.codigo_st
                        ),
                        producto
                    ])
                );

                // Obtiene códigos únicos del pedido.
                const codigosUnicos = [
                    ...new Set(
                        detalles
                            .map(item =>
                                normalizarCodigoAnalisis(
                                    item.codigo
                                )
                            )
                            .filter(Boolean)
                    )
                ];

                // Crea las filas sin realizar una petición por producto.
                codigosUnicos.forEach(codigo => {
                    const tr = agregarFilaAnalisis();

                    const inpCod = tr.querySelector(
                        '.inp-codigo'
                    );

                    const inpDesc = tr.querySelector(
                        '.inp-desc'
                    );

                    const inpPre = tr.querySelector(
                        '.inp-pre'
                    );

                    const inpCosto = tr.querySelector(
                        '.inp-costo'
                    );

                    const producto = productosMap.get(
                        codigo
                    );

                    // Escribe el código.
                    if (inpCod) {
                        inpCod.value = codigo;
                    }

                    // Restaura información del producto.
                    if (producto) {
                        if (inpDesc) {
                            inpDesc.value =
                                producto.descripcion || '';
                        }

                        if (inpPre) {
                            inpPre.value =
                                producto.unidad_manejo || 1;

                            inpPre.dataset.original =
                                producto.unidad_manejo || 1;
                        }

                        if (inpCosto) {
                            const precio =
                                Number(producto.precio || 0)
                                    .toFixed(2);

                            inpCosto.value = precio;
                            inpCosto.dataset.original =
                                precio;
                        }

                        // Bloquea el código restaurado.
                        if (inpCod) {
                            bloquearCeldaCodigo(inpCod);
                        }
                    } else {
                        // Mantiene el código aunque el producto ya no exista.
                        if (inpDesc) {
                            inpDesc.value =
                                'PRODUCTO NO ENCONTRADO';
                        }

                        if (inpPre) {
                            inpPre.value = 1;
                        }

                        if (inpCosto) {
                            inpCosto.value = '0.00';
                        }
                    }
                });

                // Restaura cantidades por sede.
                detalles.forEach(item => {
                    const sede = String(
                        item.sede || ''
                    ).trim().toUpperCase();

                    const codigo = normalizarCodigoAnalisis(
                        item.codigo
                    );

                    // Ignora registros incompletos.
                    if (!sede || !codigo) return;

                    // Garantiza la estructura de memoria.
                    asegurarEstructuraTienda(sede);

                    // Inicializa el producto.
                    if (!matrizTiendas[sede][codigo]) {
                        matrizTiendas[sede][codigo] = {};
                    }

                    // Restaura inventario/empaque.
                    matrizTiendas[sede][codigo].invEmp =
                        parseFloat(item.sugerido) || 0;

                    // Restaura pedido final.
                    matrizTiendas[sede][codigo].emp =
                        parseFloat(item.pedido_final) || 0;
                });

                // Carga clasificación si existe proveedor.
                if (
                    analisis.proveedor_id
                    && typeof cargarClasificacionProveedor
                    === 'function'
                ) {
                    await cargarClasificacionProveedor(
                        analisis.proveedor_id
                    );
                }

                // Refresca la tienda activa.
                if (
                    typeof cargarEstadoTablaDesdeMemoria
                    === 'function'
                ) {
                    cargarEstadoTablaDesdeMemoria(
                        tiendaActivaPestana
                    );
                }

                // Confirma restauración.
                mostrarNotificacion({
                    tipo: 'success',
                    mensaje: 'Pedido cargado exitosamente.'
                });

            } catch (err) {
                // Registra el error completo.
                console.error(
                    'Error al cargar pedido:',
                    err
                );

                // Muestra un mensaje amigable.
                await mostrarAlerta({
                    tipo: 'error',
                    titulo: 'Error al cargar',
                    mensaje:
                        err.message || 'Error desconocido.'
                });
            }
        }
