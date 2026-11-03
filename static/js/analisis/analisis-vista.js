
        (() => {
            // Coloca los modales fuera del contenedor que tiene desenfoque.
            const idsModales = [
                'modal-meses-comparacion-kardex',
                'modal-exportar-tiendas',
                'modal-cambios-productos',
                'modal-importar-inventarios',
                'modal-confirmar-importacion-inventario',
                'modal-productos-proveedor',
                'modal-exportar-demanda-xml'
            ];

            idsModales.forEach(id => {
                const modal = document.getElementById(id);

                if (modal && modal.parentElement !== document.body) {
                    // Mueve el elemento original, conservando sus eventos y datos.
                    document.body.appendChild(modal);
                }
            });
        })();

        (() => {
            function iniciarCabecerasFijas() {
                // Evita registrar el comportamiento más de una vez.
                if (document.getElementById('cabecera-fija-pedido')) return;

                const header = document.querySelector('body > header');

                const tablas = [
                    document.querySelector('#kardex-comparacion-contenedor > table'),
                    document.getElementById('tabla-analisis')
                ].filter(Boolean);

                if (!header || !tablas.length) return;

                const flotante = document.createElement('div');
                flotante.id = 'cabecera-fija-pedido';
                flotante.className = 'pedido-cabecera-flotante';
                flotante.setAttribute('aria-hidden', 'true');
                flotante.hidden = true;

                // Fuera del área con desenfoque y de los contenedores con scroll.
                document.body.appendChild(flotante);

                let tablaActiva = null;
                let firmaAnterior = '';
                let pendiente = false;
                let reconstruir = true;

                function programar() {
                    if (pendiente) return;

                    pendiente = true;
                    requestAnimationFrame(actualizar);
                }

                function actualizar() {
                    pendiente = false;

                    // Usa el borde inferior real del header, sin alturas fijas.
                    const limite = Math.max(
                        0,
                        header.getBoundingClientRect().bottom
                    );

                    const tabla = tablas.find(elemento => {
                        const cabecera = elemento.tHead;

                        return (
                            elemento.getClientRects().length &&
                            cabecera?.rows.length &&
                            elemento.tBodies[0]?.rows.length &&
                            cabecera.getBoundingClientRect().top < limite &&
                            elemento.getBoundingClientRect().bottom > limite
                        );
                    });

                    // Ninguna tabla está atravesando la posición del encabezado.
                    if (!tabla) {
                        flotante.hidden = true;
                        tablaActiva = null;
                        return;
                    }

                    const rect = tabla.getBoundingClientRect();
                    const marco = tabla.parentElement;
                    const borde = marco.getBoundingClientRect();

                    // Limita la copia al área horizontal visible de su tabla.
                    const izquierda = Math.max(
                        0,
                        borde.left + marco.clientLeft
                    );

                    const derecha = Math.min(
                        document.documentElement.clientWidth,
                        borde.left + marco.clientLeft + marco.clientWidth
                    );

                    const alto = tabla.tHead.getBoundingClientRect().height;

                    const anchos = Array.from(
                        tabla.tHead.rows[0].cells,
                        celda => celda.getBoundingClientRect().width
                    );

                    const firma = JSON.stringify([rect.width, alto, anchos]);

                    if (
                        reconstruir ||
                        tablaActiva !== tabla ||
                        firmaAnterior !== firma
                    ) {
                        const copia = tabla.cloneNode(false);
                        const columnas = document.createElement('colgroup');

                        // Replica los anchos reales, incluso con columnas dinámicas.
                        anchos.forEach(ancho => {
                            const columna = document.createElement('col');
                            columna.style.width = `${ancho}px`;
                            columnas.appendChild(columna);
                        });

                        copia.append(columnas, tabla.tHead.cloneNode(true));

                        // Evita IDs duplicados y ejecutar dos veces los onclick.
                        [copia, ...copia.querySelectorAll('*')].forEach(elemento => {
                            elemento.removeAttribute('id');

                            Array.from(elemento.attributes).forEach(atributo => {
                                if (/^on/i.test(atributo.name)) {
                                    elemento.removeAttribute(atributo.name);
                                }
                            });
                        });

                        Array.from(copia.tHead.rows[0].cells).forEach((celda, indice) => {
                            celda.style.width = `${anchos[indice]}px`;
                        });

                        copia.style.cssText =
                            `width:${rect.width}px;table-layout:fixed;margin:0`;

                        flotante.replaceChildren(copia);

                        tablaActiva = tabla;
                        firmaAnterior = firma;
                        reconstruir = false;
                    }

                    // Hace salir el encabezado junto con el final de su tabla.
                    const desplazamiento = Math.min(
                        0,
                        rect.bottom - limite - alto
                    );

                    flotante.hidden = derecha <= izquierda;

                    Object.assign(flotante.style, {
                        top: `${limite}px`,
                        left: `${izquierda}px`,
                        width: `${Math.max(0, derecha - izquierda)}px`,
                        height: `${Math.min(alto, rect.bottom - limite)}px`
                    });

                    // Acompaña también el desplazamiento horizontal.
                    flotante.firstElementChild.style.transform =
                        `translate(${rect.left - izquierda}px, ${desplazamiento}px)`;
                }

                // Conserva la ordenación de las columnas de productos.
                flotante.addEventListener('click', evento => {
                    const celda = evento.target.closest('th');

                    if (celda && tablaActiva) {
                        tablaActiva.tHead.rows[celda.parentElement.rowIndex]
                            ?.cells[celda.cellIndex]?.click();
                    }
                });

                // Actualiza títulos, iconos y columnas al cambiar la comparación.
                const cambios = new MutationObserver(() => {
                    reconstruir = true;
                    programar();
                });

                const tamanios = new ResizeObserver(programar);
                tamanios.observe(header);

                tablas.forEach(tabla => {
                    tamanios.observe(tabla);
                    tamanios.observe(tabla.parentElement);

                    cambios.observe(tabla.tHead, {
                        childList: true,
                        subtree: true,
                        attributes: true,
                        characterData: true
                    });

                    if (tabla.tBodies[0]) {
                        cambios.observe(tabla.tBodies[0], {
                            childList: true,
                            subtree: true,
                            characterData: true
                        });
                    }
                });

                document.addEventListener('scroll', programar, {
                    capture: true,
                    passive: true
                });

                window.addEventListener('resize', programar, {
                    passive: true
                });

                document.fonts?.ready.then(() => {
                    reconstruir = true;
                    programar();
                });

                programar();
            }

            if (document.readyState === 'loading') {
                document.addEventListener(
                    'DOMContentLoaded',
                    iniciarCabecerasFijas,
                    { once: true }
                );
            } else {
                iniciarCabecerasFijas();
            }
        })();
