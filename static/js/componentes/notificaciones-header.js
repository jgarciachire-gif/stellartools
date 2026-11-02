window.notificacionesHeader = (usuarioId = '', tipo = 'reposicion', tienda = '') => ({
    esInventario: tipo === 'inventarios',
    urlApi: tipo === 'inventarios' ? '/api/notificaciones/inventarios' : '/api/notificaciones/reposicion',
    abierto: false,
    cargando: false,
    error: '',
    notificaciones: [],
    avisosRecibidos: [],
    descartadas: [],
    total: 0,
    ultimaCarga: null,
    claveCache: usuarioId ? (tipo === 'inventarios' ? `stellartools:notificaciones:inventarios:${usuarioId}:${tienda}`
        : `stellartools:notificaciones:reposicion:${usuarioId}`) : null,
    claveDescartadas: usuarioId && tipo !== 'inventarios' ? `stellartools:notificaciones:descartadas:${usuarioId}` : null,
    intervalo: null,
    alCambiarVisibilidad: null,

    init() {
        if (this.claveDescartadas) {
            try {
                const guardadas = JSON.parse(window.localStorage.getItem(this.claveDescartadas));
                if (Array.isArray(guardadas)) {
                    this.descartadas = guardadas.filter(aviso => typeof aviso?.proveedor === 'string'
                        && typeof aviso.version === 'string');
                }
            } catch { /* Los descartes funcionan en memoria si no hay almacenamiento. */ }
        }
        if (this.claveCache) {
            try {
                const datos = JSON.parse(window.sessionStorage.getItem(this.claveCache));
                if (datos && Array.isArray(datos.notificaciones) && Number.isInteger(datos.total) && datos.total >= 0
                    && Number.isFinite(datos.ultimaCarga) && datos.ultimaCarga <= Date.now()) {
                    this.avisosRecibidos = datos.notificaciones;
                    this.aplicarDescartadas();
                    this.ultimaCarga = this.esInventario || datos.notificaciones.every(aviso => typeof aviso.version_estado === 'string')
                        ? datos.ultimaCarga : null;
                }
            } catch { /* La carga continúa si el navegador no permite almacenar datos. */ }
        }
        this.cargar();
        this.intervalo = window.setInterval(() => {
            if (document.visibilityState === 'visible') this.cargar(true);
        }, 60000);
        this.alCambiarVisibilidad = () => {
            if (document.visibilityState === 'visible') this.cargar();
        };
        document.addEventListener('visibilitychange', this.alCambiarVisibilidad);
    },

    destroy() {
        window.clearInterval(this.intervalo);
        document.removeEventListener('visibilitychange', this.alCambiarVisibilidad);
    },

    guardarCache() {
        if (!this.claveCache) return;
        try {
            if (this.ultimaCarga === null) {
                window.sessionStorage.removeItem(this.claveCache);
            } else {
                window.sessionStorage.setItem(this.claveCache, JSON.stringify({
                    notificaciones: this.avisosRecibidos, total: this.avisosRecibidos.length, ultimaCarga: this.ultimaCarga
                }));
            }
        } catch { /* El conteo sigue funcionando sin caché persistente. */ }
    },

    guardarDescartadas() {
        if (!this.claveDescartadas) return;
        try {
            window.localStorage.setItem(this.claveDescartadas, JSON.stringify(this.descartadas));
        } catch { /* El aviso sigue oculto en esta página si el almacenamiento no está disponible. */ }
    },

    aplicarDescartadas(reconciliar = false) {
        if (this.esInventario) {
            this.notificaciones = this.avisosRecibidos;
            this.total = this.notificaciones.length;
            return;
        }
        if (reconciliar) {
            // Si salió de alerta o cambió de estado/ciclo, libera el descarte anterior.
            this.descartadas = this.descartadas.filter(descartada => this.avisosRecibidos.some(aviso =>
                aviso.proveedor === descartada.proveedor && aviso.version_estado === descartada.version));
            this.guardarDescartadas();
        }
        this.notificaciones = this.avisosRecibidos.filter(aviso => !this.descartadas.some(descartada =>
            descartada.proveedor === aviso.proveedor && descartada.version === aviso.version_estado));
        this.total = this.notificaciones.length;
    },

    descartar(aviso) {
        if (this.esInventario || !aviso.version_estado) return;
        // El botón desaparecerá: conserva el foco dentro del desplegable antes de retirarlo.
        this.$refs?.campana?.focus({preventScroll: true});
        this.descartadas = this.descartadas.filter(descartada => descartada.proveedor !== aviso.proveedor);
        this.descartadas.push({proveedor: aviso.proveedor, version: aviso.version_estado});
        this.guardarDescartadas();
        this.aplicarDescartadas();
    },

    alternar() {
        this.abierto = !this.abierto;
        if (this.abierto) this.cargar();
    },

    actualizarDocumento(detalle) {
        if (!this.esInventario) return;
        if (detalle.estado === 'completado') {
            this.avisosRecibidos = this.avisosRecibidos.filter(aviso => String(aviso.documento_id) !== String(detalle.id));
            this.aplicarDescartadas();
            this.guardarCache();
        }
        this.cargar(true);
    },

    async cargar(forzar = false) {
        if (this.cargando || (!forzar && this.ultimaCarga !== null && Date.now() - this.ultimaCarga < 60000)) return;
        this.cargando = true;
        this.error = '';
        try {
            const respuesta = await fetch(this.urlApi, {
                credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' }
            });
            if (respuesta.status === 401 || (respuesta.redirected && new URL(respuesta.url).pathname === '/login')) {
                this.notificaciones = [];
                this.avisosRecibidos = [];
                this.total = 0;
                this.ultimaCarga = null;
                this.guardarCache();
                throw new Error('Tu sesión ha vencido. Inicia sesión nuevamente.');
            }
            if (!respuesta.ok) throw new Error('No se pudieron cargar las notificaciones. Intenta nuevamente.');
            let datos;
            try { datos = await respuesta.json(); } catch {
                throw new Error('No se pudieron cargar las notificaciones. Intenta nuevamente.');
            }
            if (!Array.isArray(datos.notificaciones) || !Number.isInteger(datos.total) || datos.total < 0) {
                throw new Error('La respuesta de notificaciones no es válida. Intenta nuevamente.');
            }
            this.avisosRecibidos = datos.notificaciones;
            this.aplicarDescartadas(true);
            this.ultimaCarga = Date.now();
            this.guardarCache();
        } catch (error) {
            this.error = error.message || 'No se pudieron cargar las notificaciones.';
        } finally {
            this.cargando = false;
        }
    }
});
