
(function () {
    'use strict';

    let modalActivo = null;
    let resolverActivo = null;


    function escaparHTML(valor) {
        return String(valor ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }


    function obtenerIcono(tipo) {
        switch (tipo) {
            case 'success':
                return {
                    icono: 'fa-circle-check',
                    clase: 'text-emerald-600 bg-emerald-100'
                };

            case 'error':
                return {
                    icono: 'fa-circle-xmark',
                    clase: 'text-rose-600 bg-rose-100'
                };

            case 'warning':
                return {
                    icono: 'fa-triangle-exclamation',
                    clase: 'text-amber-600 bg-amber-100'
                };

            default:
                return {
                    icono: 'fa-circle-info',
                    clase: 'text-blue-600 bg-blue-100'
                };
        }
    }


    function cerrarModalInterno(resultado) {
        if (!modalActivo) {
            return;
        }

        const modal = modalActivo;

        modal.classList.add('opacity-0');

        setTimeout(() => {
            modal.remove();
        }, 150);

        modalActivo = null;

        if (resolverActivo) {
            const resolver = resolverActivo;

            resolverActivo = null;

            resolver(resultado);
        }
    }


    function crearModal({
        tipo = 'info',
        titulo = 'Información',
        mensaje = '',
        textoAceptar = 'Entendido',
        textoCancelar = null
    }) {

        // Si existe otro modal del sistema, lo cerramos primero.
        if (modalActivo) {
            cerrarModalInterno(false);
        }

        const icono = obtenerIcono(tipo);

        const modal = document.createElement('div');

        modal.className =
            'fixed inset-0 bg-slate-900/60 backdrop-blur-sm '
            + 'z-[9999] flex items-center justify-center p-4 '
            + 'opacity-0 transition-opacity duration-150';

        modal.innerHTML = `
            <div
                class="bg-white rounded-2xl shadow-2xl
                       max-w-md w-full p-6
                       transform transition-all">

                <div class="flex items-start gap-4">

                    <div
                        class="w-12 h-12 rounded-full
                               flex items-center justify-center
                               shrink-0
                               ${icono.clase}">

                        <i class="fa-solid ${icono.icono} text-xl"></i>
                    </div>

                    <div class="min-w-0 flex-1">

                        <h3
                            class="text-lg font-bold text-slate-800 mb-1">

                            ${escaparHTML(titulo)}

                        </h3>

                        <p
                            class="text-sm text-slate-600 whitespace-pre-line">

                            ${escaparHTML(mensaje)}

                        </p>

                    </div>

                </div>

                <div class="flex justify-end gap-3 mt-6">

                    ${textoCancelar
                ? `
                                <button
                                    type="button"
                                    data-modal-cancelar
                                    class="px-4 py-2
                                           text-sm font-semibold
                                           text-slate-700
                                           bg-slate-100
                                           hover:bg-slate-200
                                           rounded-xl transition">

                                    ${escaparHTML(textoCancelar)}

                                </button>
                            `
                : ''
            }

                    <button
                        type="button"
                        data-modal-aceptar
                        class="px-4 py-2
                               text-sm font-semibold
                               text-white
                               bg-slate-800
                               hover:bg-slate-900
                               rounded-xl transition">

                        ${escaparHTML(textoAceptar)}

                    </button>

                </div>
            </div>
        `;

        document.body.appendChild(modal);

        modalActivo = modal;

        const botonAceptar =
            modal.querySelector('[data-modal-aceptar]');

        const botonCancelar =
            modal.querySelector('[data-modal-cancelar]');

        botonAceptar?.addEventListener('click', () => {
            cerrarModalInterno(true);
        });

        botonCancelar?.addEventListener('click', () => {
            cerrarModalInterno(false);
        });

        modal.addEventListener('click', (event) => {
            if (event.target === modal && textoCancelar) {
                cerrarModalInterno(false);
            }
        });

        const manejarEscape = (event) => {
            if (event.key !== 'Escape') {
                return;
            }

            document.removeEventListener(
                'keydown',
                manejarEscape
            );

            cerrarModalInterno(
                textoCancelar ? false : true
            );
        };

        document.addEventListener(
            'keydown',
            manejarEscape
        );

        requestAnimationFrame(() => {
            modal.classList.remove('opacity-0');
        });

        setTimeout(() => {
            botonAceptar?.focus();
        }, 50);
    }

    function mostrarNotificacion({
        tipo = 'success',
        mensaje = '',
        duracion = 3000
    } = {}) {

        const estilos = {
            success: {
                icono: 'fa-circle-check',
                clase:
                    'bg-emerald-50 border-emerald-200 text-emerald-800'
            },

            error: {
                icono: 'fa-circle-xmark',
                clase:
                    'bg-rose-50 border-rose-200 text-rose-800'
            },

            warning: {
                icono: 'fa-triangle-exclamation',
                clase:
                    'bg-amber-50 border-amber-200 text-amber-800'
            },

            info: {
                icono: 'fa-circle-info',
                clase:
                    'bg-blue-50 border-blue-200 text-blue-800'
            }
        };

        const estilo =
            estilos[tipo] || estilos.info;

        const notificacion =
            document.createElement('div');

        notificacion.className =
            'fixed top-5 left-1/2 -translate-x-1/2 '
            + 'z-[10000] max-w-md w-[calc(100%-2rem)] '
            + 'border rounded-xl shadow-lg '
            + 'px-4 py-3 '
            + 'flex items-center gap-3 '
            + 'opacity-0 -translate-y-3 '
            + 'transition-all duration-200 '
            + estilo.clase;

        notificacion.innerHTML = `
        <i
            class="fa-solid ${estilo.icono} text-lg shrink-0">
        </i>

        <span
            class="text-sm font-semibold leading-5">
            ${escaparHTML(mensaje)}
        </span>
    `;

        document.body.appendChild(notificacion);

        requestAnimationFrame(() => {
            notificacion.classList.remove(
                'opacity-0',
                '-translate-y-3'
            );
        });

        setTimeout(() => {
            notificacion.classList.add(
                'opacity-0',
                '-translate-y-3'
            );

            setTimeout(() => {
                notificacion.remove();
            }, 200);

        }, duracion);
    }

    window.mostrarAlerta = function ({
        tipo = 'info',
        titulo = 'Información',
        mensaje = '',
        textoAceptar = 'Entendido'
    } = {}) {

        return new Promise(resolve => {

            resolverActivo = resolve;

            crearModal({
                tipo,
                titulo,
                mensaje,
                textoAceptar
            });

        });
    };


    window.mostrarConfirmacion = function ({
        tipo = 'warning',
        titulo = 'Confirmar acción',
        mensaje = '',
        textoAceptar = 'Aceptar',
        textoCancelar = 'Cancelar'
    } = {}) {

        return new Promise(resolve => {

            resolverActivo = resolve;

            crearModal({
                tipo,
                titulo,
                mensaje,
                textoAceptar,
                textoCancelar
            });

        });
    };

    window.mostrarNotificacion = function ({
        tipo = 'success',
        mensaje = '',
        duracion = 3000
    } = {}) {

        mostrarNotificacion({
            tipo,
            mensaje,
            duracion
        });
    };

    window.cerrarModalGlobal = function () {
        cerrarModalInterno(false);
    };

})();