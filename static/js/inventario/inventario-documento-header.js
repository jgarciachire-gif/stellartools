
        // =========================================================
        // BUSCADOR DE PRODUCTOS — INTEGRACIÓN CON INVENTARIO
        // =========================================================

        window.onProductoSeleccionadoBuscador =
            async function (codigo, input) {

                if (!input) {
                    return;
                }

                // Inventario conserva su propia lógica
                // para completar y validar el producto.
                if (
                    typeof window.consultarProductoInventario ===
                    'function'
                ) {
                    await window.consultarProductoInventario(
                        input
                    );

                    // Sincronizar la vista móvil
                    // después de completar el producto.
                    renderizarProductosMovil();
                }
            };
    