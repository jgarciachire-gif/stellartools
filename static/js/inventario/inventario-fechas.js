
    /*
     * Formatea fechas ISO de Supabase para mostrarlas
     * de forma amigable en la Biblioteca.
     *
     * Ejemplo:
     * 2026-10-01T12:42:04.844559+00:00
     * →
     * 01-10-2026 08:42 AM
     */
    window.formatearFechasInventarios = function () {

        document
            .querySelectorAll('#listado-inventarios [data-fecha]')
            .forEach(function (elemento) {

                const fechaISO =
                    elemento.dataset.fecha;

                if (!fechaISO) {
                    return;
                }

                const fecha =
                    new Date(fechaISO);

                if (
                    Number.isNaN(
                        fecha.getTime()
                    )
                ) {
                    return;
                }

                const dia =
                    String(
                        fecha.getDate()
                    ).padStart(2, '0');

                const mes =
                    String(
                        fecha.getMonth() + 1
                    ).padStart(2, '0');

                const año =
                    fecha.getFullYear();

                let horas =
                    fecha.getHours();

                const minutos =
                    String(
                        fecha.getMinutes()
                    ).padStart(2, '0');

                const periodo =
                    horas >= 12
                        ? 'PM'
                        : 'AM';

                horas =
                    horas % 12 || 12;

                const horasFormateadas =
                    String(horas)
                        .padStart(2, '0');

                elemento.textContent =
                    `${dia}-${mes}-${año} ` +
                    `${horasFormateadas}:${minutos} ` +
                    `${periodo}`;
            });
    };
    document.addEventListener('DOMContentLoaded', window.formatearFechasInventarios);
