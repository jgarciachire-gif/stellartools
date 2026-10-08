'use strict';

/*
 * ============================================================
 * STELLARTOOLS — SERVICE WORKER
 * ============================================================
 *
 * PRINCIPIO DE SEGURIDAD:
 *
 * - SOLO se cachean recursos estáticos.
 * - NO se cachean páginas HTML.
 * - NO se cachean APIs.
 * - NO se cachean respuestas de Supabase.
 * - NO se cachean peticiones POST/PUT/PATCH/DELETE.
 * - NO se cachean cookies, sesiones ni datos privados.
 *
 * Esto permite acelerar la interfaz sin almacenar información
 * sensible del usuario en la caché del navegador.
 * ============================================================
 */

const CACHE_NAME = 'stellartools-static-v1';


/*
 * ============================================================
 * INSTALACIÓN
 * ============================================================
 */

self.addEventListener('install', event => {

    /*
     * Activa inmediatamente la nueva versión.
     *
     * Esto evita que una versión antigua permanezca esperando
     * indefinidamente mientras existen pestañas abiertas.
     */
    self.skipWaiting();

});


/*
 * ============================================================
 * ACTIVACIÓN
 * ============================================================
 */

self.addEventListener('activate', event => {

    event.waitUntil(
        (async () => {

            /*
             * Elimina versiones antiguas de la caché.
             */
            const cacheNames =
                await caches.keys();

            await Promise.all(
                cacheNames
                    .filter(nombre =>
                        nombre.startsWith('stellartools-')
                        && nombre !== CACHE_NAME
                    )
                    .map(nombre =>
                        caches.delete(nombre)
                    )
            );

            /*
             * Permite que el nuevo Service Worker controle
             * inmediatamente las pestañas abiertas.
             */
            await self.clients.claim();

        })()
    );

});


/*
 * ============================================================
 * PETICIONES DE RED
 * ============================================================
 */

self.addEventListener('fetch', event => {

    const request = event.request;


    /*
     * Solo GET puede utilizar caché.
     *
     * POST / PUT / PATCH / DELETE pasan directamente a la red.
     */
    if (request.method !== 'GET') {
        return;
    }


    const url = new URL(request.url);


    /*
     * Solo procesamos peticiones del mismo origen.
     *
     * CDN externos como Tailwind o Font Awesome siguen
     * funcionando directamente desde el navegador.
     */
    if (url.origin !== self.location.origin) {
        return;
    }


    /*
     * ========================================================
     * SERVICE WORKER
     * ========================================================
     *
     * Nunca interceptamos nuestro propio archivo.
     */
    if (url.pathname === '/service-worker.js') {
        return;
    }


    /*
     * ========================================================
     * SOLO RECURSOS ESTÁTICOS
     * ========================================================
     *
     * No hacemos caché de:
     *
     * /login
     * /
     * /inventario
     * /api/...
     * /ordenes/...
     * /proveedores/...
     * etc.
     *
     * Únicamente archivos ubicados bajo /static/.
     */
    if (!url.pathname.startsWith('/static/')) {
        return;
    }


    /*
     * Determina si el recurso es un archivo estático
     * apropiado para caché.
     */
    const extension =
        url.pathname
            .split('?')[0]
            .split('.')
            .pop()
            .toLowerCase();


    const extensionesPermitidas = new Set([
        'css',
        'js',
        'mjs',
        'png',
        'jpg',
        'jpeg',
        'webp',
        'gif',
        'svg',
        'ico',
        'woff',
        'woff2',
        'ttf',
        'otf',
        'json'
    ]);


    if (!extensionesPermitidas.has(extension)) {
        return;
    }


    /*
     * ========================================================
     * ESTRATEGIA:
     *
     * STALE-WHILE-REVALIDATE
     * ========================================================
     *
     * 1. Si existe una copia local:
     *      → se entrega inmediatamente.
     *
     * 2. En paralelo:
     *      → se consulta la versión actual al servidor.
     *
     * 3. Si cambia:
     *      → se actualiza la caché.
     *
     * Resultado:
     *      - interfaz rápida
     *      - actualización automática
     *      - sin almacenar datos privados
     */
    event.respondWith(
        (async () => {

            const cache =
                await caches.open(CACHE_NAME);

            const respuestaCache =
                await cache.match(request);


            const actualizarCache =
                fetch(request)
                    .then(respuesta => {

                        /*
                         * Solo almacenamos respuestas HTTP
                         * válidas.
                         */
                        if (
                            respuesta &&
                            respuesta.ok &&
                            respuesta.type === 'basic'
                        ) {

                            cache.put(
                                request,
                                respuesta.clone()
                            );

                        }

                        return respuesta;

                    })
                    .catch(() => null);


            /*
             * Si tenemos una copia local, la entregamos
             * inmediatamente.
             */
            if (respuestaCache) {

                /*
                 * La actualización continúa en segundo plano.
                 */
                event.waitUntil(
                    actualizarCache
                );

                return respuestaCache;
            }


            /*
             * Primera visita al recurso:
             * esperamos la red.
             */
            const respuestaRed =
                await actualizarCache;

            if (respuestaRed) {
                return respuestaRed;
            }


            /*
             * Si no existe caché ni conexión, dejamos que
             * el navegador gestione el fallo normalmente.
             */
            return new Response(
                '',
                {
                    status: 503,
                    statusText: 'Service Unavailable'
                }
            );

        })()
    );

});