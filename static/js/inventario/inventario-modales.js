
    (() => {
        // Saca los modales del contenedor con desenfoque.
        const idsModales = [
            'modal-nuevo-inventario',
            'modal-multitienda'
        ];

        idsModales.forEach(id => {
            const modal = document.getElementById(id);

            // Multitienda solo existe para los perfiles autorizados.
            if (modal && modal.parentElement !== document.body) {
                // Conserva el elemento original, sus datos y sus eventos.
                document.body.appendChild(modal);
            }
        });
    })();
