// Mantiene la creación de filas síncrona y agrupa los cambios de cada importación.
(() => {
    function iniciarTransicionTablaAnalisis() {
        const contenedor = document.getElementById('contenedor-tabla-productos-analisis');
        const tabla = document.getElementById('tabla-analisis');
        const filas = document.getElementById('filas-tabla-analisis');
        if (!contenedor || !tabla || !filas) return;

        let alturaAnterior = null;
        let animacion = null;
        let aparicion = null;
        let revision = 0;

        const observador = new ResizeObserver(() => {
            // Observa la tabla natural, no el contenedor cuya altura se anima.
            const alturaVisible = contenedor.getBoundingClientRect().height;
            const alturaInicial = animacion || contenedor.style.height
                ? alturaVisible : alturaAnterior;
            animacion?.cancel();
            animacion = null;
            contenedor.style.height = '';
            const alturaFinal = contenedor.getBoundingClientRect().height;

            if (alturaAnterior === null) {
                alturaAnterior = alturaFinal;
                return;
            }
            const actual = ++revision;
            alturaAnterior = alturaFinal;
            contenedor.style.height = `${alturaInicial}px`;
            contenedor.style.overflowY = 'hidden';

            const terminar = () => {
                if (actual !== revision) return;
                contenedor.style.height = '';
                contenedor.style.overflowY = '';
                animacion?.cancel();
                animacion = null;
            };

            if (Math.abs(alturaFinal - alturaInicial) < 1) {
                terminar();
                return;
            }

            // Separa la altura de origen del inicio de la transición entre fotogramas.
            requestAnimationFrame(() => requestAnimationFrame(() => {
                if (actual !== revision) return;
                const movimientoReducido = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                const duracion = movimientoReducido ? 180
                    : Math.min(1000, 750 + Math.abs(alturaFinal - alturaInicial) * .2);
                animacion = contenedor.animate(
                    [{ height: `${alturaInicial}px` }, { height: `${alturaFinal}px` }],
                    { duration: duracion, easing: 'cubic-bezier(0.4, 0, 0.15, 1)', fill: 'both' }
                );
                animacion.onfinish = terminar;
                aparicion?.cancel();
                aparicion = filas.animate([{ opacity: .4 }, { opacity: 1 }], {
                    duration: movimientoReducido ? 180 : 320,
                    delay: movimientoReducido ? 0 : 100,
                    easing: 'ease-out', fill: 'backwards'
                });
            }));
        });
        observador.observe(tabla);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciarTransicionTablaAnalisis, { once: true });
    } else {
        iniciarTransicionTablaAnalisis();
    }
})();
