# Análisis de pedido

La plantilla conserva la configuración que genera Jinja y los elementos HTML.
Los archivos JavaScript son scripts clásicos: comparten las funciones y variables
globales que ya utilizaban el HTML, las filas dinámicas y los módulos existentes.

## Responsabilidades y carga

Los cinco módulos que ya estaban activos se conservan sin cambios:

- `analisis-productos.js`: filas, consulta de productos, cálculos y totales.
- `analisis-tabla-transicion.js`: animación de altura y aparición de filas.
- `analisis-importar-inventario.js`: listado, filtros, selección e importación de inventarios.
- `analisis-interaccion.js`: edición, navegación, selección y portapapeles. También se utiliza en `inventario_nuevo.html`.
- `analisis-cambios.js`: cambios pendientes en productos y protección de acciones.

El JavaScript extraído de la plantilla se carga después, en este orden:

| Archivo | Responsabilidad |
| --- | --- |
| `analisis-core.js` | Integración con el buscador, estado inicial, limpieza del pedido y selector de tienda. |
| `analisis-proveedores.js` | Proveedor, clasificación, modal e importación de productos. |
| `analisis-tabla.js` | Fila inicial, ordenación, lectura de celdas y guardado de la tabla en memoria. |
| `analisis-exportacion.js` | Generación de pedidos en TXT y XML consolidado. |
| `analisis-pedidos.js` | Guardado y restauración del pedido completo. |
| `analisis-tiendas.js` | Cambio de tienda, restauración de sus cantidades y navegación de la tabla. |
| `analisis-sugeridos.js` | Demanda, cobertura, crecimiento y cálculo de sugeridos. |
| `analisis-exportacion-tiendas.js` | Selector de tiendas para exportación. |
| `analisis-kardex.js` | Cobertura, importación de Kardex, períodos, comparación y exportación de demanda. |

`analisis-vista.js` se carga en el bloque de modales, después de su HTML. Coloca los
modales fuera del contenedor principal y gestiona las cabeceras flotantes.

La separación de exportación y su selector conserva la secuencia original de
declaraciones e inicializaciones. No se cambió el orden de los eventos.

## Contratos que deben conservarse

- Mantener los nombres públicos usados por `onclick`, `oninput`, `onkeydown` y por las filas creadas mediante JavaScript.
- Mantener las referencias de `window.matrizTiendas` y la tienda activa; varios flujos sincronizan la tabla con esta memoria.
- Conservar las llamadas entre guardado, importación, sugeridos y cambios pendientes.
- No añadir `async`, `defer`, `type="module"` ni envolver estos archivos en nuevos ámbitos sin revisar antes sus dependencias. La transición mantiene su `defer` original.
- Las declaraciones duplicadas existentes en `analisis-productos.js` se conservaron. Su revisión debe hacerse por separado, con pruebas de comportamiento.
- La modularización organiza y permite cachear el JavaScript externo; no cambia las fórmulas ni los contratos de la API.

## Verificación

Desde la raíz del proyecto:

```powershell
node --test tests/analisis-modularizacion.test.cjs tests/analisis-importar-inventario.test.cjs tests/analisis-tabla-transicion.test.cjs
python tests/analisis_navegador.py
```

La prueba de navegador utiliza la plantilla real, Microsoft Edge sin ventana y una
API local simulada. No inicializa la configuración del servidor ni accede a datos
reales. Descarga las bibliotecas públicas de interfaz que utiliza la plantilla.
