        // --- ACCIONES DE EXPORTACIÓN A TXT ---

        // Exporta un archivo .txt por cada tienda seleccionada directamente a la carpeta de descargas
        async function confirmarExportacionSeparada() {
            guardarEstadoTablaEnMemoria(tiendaActivaPestana); // Sincroniza la tabla visible en la matriz
            const proveedor = obtenerNombreProveedor(); // Obtiene nombre del proveedor del contenedor 1
            const hoy = new Date();
            const dia = String(hoy.getDate()).padStart(2, '0'); // Día a 2 dígitos
            const mes = String(hoy.getMonth() + 1).padStart(2, '0'); // Mes a 2 dígitos
            const anio = String(hoy.getFullYear()).slice(-2); // Año a 2 dígitos (AA)
            const fechaActual = `${dia}-${mes}-${anio}`; // Formato DD-MM-AA

            const tagsActivos = document.querySelectorAll('#contenedor-etiquetas-exportar .tag-tienda-exportar.activa');
            const tiendasSeleccionadas = Array.from(tagsActivos).map(tag => tag.dataset.tienda);

            if (tiendasSeleccionadas.length === 0) {
                await mostrarAlerta({
                    tipo: 'warning',
                    titulo: 'Selecciona una tienda',
                    mensaje: 'Por favor, selecciona al menos una tienda para exportar.'
                });

                return;
            }

            // Exporta únicamente códigos presentes en la tabla del pedido actual.
            // Las cantidades se siguen obteniendo de cada tienda seleccionada.
            const codigosSet = new Set(
                obtenerCodigosTablaAnalisis()
            );

            let archivosGenerados = 0;

            tiendasSeleccionadas.forEach((tienda, index) => {
                let lineas = [];

                codigosSet.forEach(codigo => {
                    const unidades = obtenerUnidadesTienda(tienda, codigo); // Obtiene unidades de esa tienda
                    if (unidades > 0) {
                        lineas.push(`${codigo}|${unidades}|`); // Formato exacto CODIGO|UNIDADES|
                    }
                });

                if (lineas.length > 0) {
                    archivosGenerados++;
                    // Usa enlaces HTML5 dinámicos con atributo 'download' para guardar directo sin pedir carpeta
                    setTimeout(() => {
                        const contenido = lineas.join('\r\n') + '\r\n'; // Salto de línea CRLF compatible con Windows
                        const blob = new Blob([contenido], { type: 'text/plain;charset=utf-8' });
                        const url = URL.createObjectURL(blob); // Crea URL temporal en memoria para el archivo
                        const a = document.createElement('a'); // Crea un elemento de enlace invisible

                        a.href = url;
                        const nombreLimpio = `${proveedor} - ${tienda} - ${fechaActual}`.replace(/[/\\?%*:|"<>]/g, '');
                        a.download = `${nombreLimpio}.txt`; // El atributo 'download' fuerza la descarga directa a Descargas

                        document.body.appendChild(a); // Inserta el enlace temporalmente en el DOM
                        a.click(); // Dispara la descarga automática sin abrir selector de archivos
                        document.body.removeChild(a); // Elimina el enlace del DOM

                        // Retarda la liberación de memoria para evitar interrupciones en la descarga
                        setTimeout(() => URL.revokeObjectURL(url), 1000);
                    }, index * 300); // 300ms de separación para evitar que el navegador bloquee descargas múltiples
                }
            });

            if (archivosGenerados === 0) {
                await mostrarAlerta({
                    tipo: 'info',
                    titulo: 'Sin productos para exportar',
                    mensaje: 'No hay productos con unidades mayores a cero en las tiendas seleccionadas.'
                });
            } else {
                cerrarModalExportarTiendas();
            }
        }

        // Exporta un archivo .xml consolidado sumando los empaques (Emp) de todas las tiendas
        async function exportarConsolidado() {
            // Sincroniza la tienda actual visible en la matriz de memoria
            guardarEstadoTablaEnMemoria(tiendaActivaPestana);

            // Obtiene el nombre del proveedor y la fecha actual formateada
            const proveedor = obtenerNombreProveedor();
            const hoy = new Date();
            const dia = String(hoy.getDate()).padStart(2, '0');
            const mes = String(hoy.getMonth() + 1).padStart(2, '0');
            const anio = String(hoy.getFullYear()).slice(-2);
            const fechaActual = `${dia}-${mes}-${anio}`;

            // Lista de las sedes o tiendas disponibles
            const sedes = ['CENTRO', 'NAGUANAGUA', 'ISABELICA', 'CIUDAD ALIANZA', 'GARIBALDI', 'SAN DIEGO'];

            // Mapa para asociar de forma única cada código con su descripción
            const mapaProductos = new Map();

            // 1. Recolecta códigos y descripciones desde la tabla visual activa
            document.querySelectorAll('#filas-tabla-analisis tr').forEach(tr => {
                const cod = obtenerCodigoFila(tr);
                if (cod) {
                    const desc = tr.querySelector('.inp-desc')?.value || '';
                    mapaProductos.set(cod, desc);
                }
            });

            // Función de seguridad para escapar caracteres especiales XML (&, <, >, ", ')
            const escaparXML = (str) => String(str || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&apos;');

            let nodosProductosXML = [];

            // 3. Recorre cada código único y calcula la suma total de Empaques (Emp) entre todas las tiendas
            mapaProductos.forEach((descripcion, codigo) => {
                let totalEmpaques = 0;

                sedes.forEach(tienda => {
                    // Si la tienda es la activa en pantalla, lee el input directamente
                    if (tienda === tiendaActivaPestana) {
                        document.querySelectorAll('#filas-tabla-analisis tr').forEach(tr => {
                            if (obtenerCodigoFila(tr) === codigo) {
                                totalEmpaques += obtenerValorCelda(tr, '.inp-emp');
                            }
                        });
                    } else if (matrizTiendas[tienda] && matrizTiendas[tienda][codigo]) {
                        // Si la tienda está en memoria, toma el valor guardado
                        totalEmpaques += parseFloat(matrizTiendas[tienda][codigo].emp) || 0;
                    }
                });

                // Solo agrega al XML los productos con empaques totales mayores a cero
                if (totalEmpaques > 0) {
                    nodosProductosXML.push(`    <producto>
        <codigo>${escaparXML(codigo)}</codigo>
        <descripcion>${escaparXML(descripcion)}</descripcion>
        <emp>${totalEmpaques}</emp>
    </producto>`);
                }
            });

            // Muestra alerta si no hay registros con empaques
            if (nodosProductosXML.length === 0) {
                await mostrarAlerta({
                    tipo: 'info',
                    titulo: 'Sin productos para exportar',
                    mensaje: 'No hay productos con empaques consolidados mayores a cero para exportar.'
                });

                return;
            }

            // 4. Construye la estructura jerárquica del archivo XML
            const contenidoXML = `<?xml version="1.0" encoding="UTF-8"?>
<consolidado proveedor="${escaparXML(proveedor)}" fecha="${fechaActual}">
${nodosProductosXML.join('\n')}
</consolidado>`;

            // 5. Genera el archivo Blob con codificación UTF-8 e inicia la descarga .xml
            const blob = new Blob([contenidoXML], { type: 'application/xml;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            // Nombre de archivo: NOMBRE PROVEEDOR - CONSOLIDADO GLOBAL - DD-MM-AA.xml
            const nombreLimpio = `${proveedor} - CONSOLIDADO GLOBAL - ${fechaActual}`.replace(/[/\\?%*:|"<>]/g, '');
            a.download = `${nombreLimpio}.xml`;

            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
