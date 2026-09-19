// Devuelve YYYY-MM-DD usando la fecha local del navegador.
// Debe estar fuera de calendarioReposicion() para que Alpine pueda encontrarla.
function fechaLocalKey(fecha = new Date()) {
    const año = fecha.getFullYear(); // Obtiene el año local
    const mes = String(fecha.getMonth() + 1).padStart(2, '0'); // Mes local
    const dia = String(fecha.getDate()).padStart(2, '0'); // Día local

    return `${año}-${mes}-${dia}`; // Devuelve la fecha sin conversión UTC
}
// Variable global para almacenar el nombre del usuario desde la sesión
const USUARIO_NOMBRE_SESION = document.getElementById('usuario-sesion-data')?.dataset.nombre || 'Usuario Sistema';

// Componente principal de Alpine JS para el control del calendario
function calendarioReposicion() {
    return {
        fechaActual: new Date(), // Mantiene el mes actualmente visualizado
        diaSeleccionado: fechaLocalKey(), // Usa la fecha local real
        modalAbierto: false, // Controla el modal de programación
        eventosCalendario: [], // Guarda las ocurrencias devueltas por FastAPI
        eventosPorFecha: {}, // Índice rápido fecha -> eventos
        cargandoCalendario: false, // Indica que se está consultando el servidor
        solicitudCalendario: 0, // Evita que una respuesta antigua sobrescriba una nueva
        listaProveedoresBD: JSON.parse(
            document.getElementById('proveedores-data')?.textContent || '[]'
        ), // Proveedores precargados en HTML
        proveedorSeleccionadoId: '', // Conserva el proveedor seleccionado
        proveedoresAbiertos: {}, // Estado visual de los grupos del panel


        esProveedorAbierto(nombreProv) {
            return !!this.proveedoresAbiertos[nombreProv];
        },

        toggleProveedor(nombreProv) {
            // Cambia entre abierto y cerrado para el proveedor seleccionado
            this.proveedoresAbiertos[nombreProv] =
                !this.proveedoresAbiertos[nombreProv];
        },

        esProveedorAbierto(nombreProv) {
            // Devuelve el estado actual del proveedor
            return !!this.proveedoresAbiertos[nombreProv];
        },

        get nombreMesAno() {
            return this.fechaActual.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })
                .replace(/^\w/, c => c.toUpperCase());
        },

        get diasMes() {
            const año = this.fechaActual.getFullYear(); // Año del mes visible
            const mes = this.fechaActual.getMonth(); // Mes visible
            const primerDia = new Date(año, mes, 1); // Primer día del mes
            const ultimoDia = new Date(año, mes + 1, 0); // Último día del mes
            const dias = []; // Celdas finales del calendario
            const hoyStr = fechaLocalKey(); // Fecha actual en horario local

            // Completa los días anteriores del mes
            const diaSemanaInicio = primerDia.getDay();

            for (let i = diaSemanaInicio - 1; i >= 0; i--) {
                const d = new Date(año, mes, -i);

                dias.push({
                    numero: d.getDate(),
                    fechaStr: fechaLocalKey(d),
                    esMesActual: false,
                    esHoy: fechaLocalKey(d) === hoyStr
                });
            }

            // Agrega todos los días del mes visible
            for (let i = 1; i <= ultimoDia.getDate(); i++) {
                const fStr = `${año}-${String(mes + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;

                dias.push({
                    numero: i,
                    fechaStr: fStr,
                    esMesActual: true,
                    esHoy: fStr === hoyStr
                });
            }

            // Completa las celdas posteriores necesarias para cerrar la semana
            const celdasRestantes = (7 - (dias.length % 7)) % 7;

            for (let i = 1; i <= celdasRestantes; i++) {
                const d = new Date(año, mes + 1, i);

                dias.push({
                    numero: d.getDate(),
                    fechaStr: fechaLocalKey(d),
                    esMesActual: false,
                    esHoy: fechaLocalKey(d) === hoyStr
                });
            }

            return dias;
        },

        get rangoCalendario() {
            const dias = this.diasMes; // Obtiene las celdas visibles
            return {
                inicio: dias[0]?.fechaStr, // Primera fecha visible
                fin: dias[dias.length - 1]?.fechaStr // Última fecha visible
            };
        },

        seleccionarDia(fechaStr) {
            this.diaSeleccionado = fechaStr;
        },

        formatearFechaSeleccionada() {
            if (!this.diaSeleccionado) return '';
            const partes = this.diaSeleccionado.split('-');
            const f = new Date(partes[0], partes[1] - 1, partes[2]);
            return f.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
                .replace(/^\w/, c => c.toUpperCase());
        },

        async cargarProveedoresAPI() {
            try {
                const res = await fetch('/api/proveedores');
                if (res.ok) this.listaProveedoresBD = await res.json();
            } catch (e) {
                console.error("Error al obtener proveedores:", e);
            }
        },

        async cargarCalendario() {
            const rango = this.rangoCalendario; // Calcula exactamente lo que el usuario está viendo

            if (!rango.inicio || !rango.fin) return; // Evita peticiones inválidas

            const solicitudActual = ++this.solicitudCalendario; // Identificador de esta consulta
            this.cargandoCalendario = true; // Activa indicador visual

            try {
                const params = new URLSearchParams({
                    inicio: rango.inicio,
                    fin: rango.fin
                });

                const res = await fetch(`/api/calendario?${params.toString()}`, {
                    headers: {
                        'Accept': 'application/json'
                    }
                });

                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({}));
                    throw new Error(errorData.error || errorData.detail || 'No se pudo cargar el calendario');
                }

                const eventos = await res.json();

                // Ignora respuestas antiguas cuando el usuario cambia rápidamente de mes
                if (solicitudActual !== this.solicitudCalendario) return;

                this.eventosCalendario = eventos; // Guarda las ocurrencias recibidas

                // Construye un índice para acceder en O(1) a los eventos de cada fecha
                this.eventosPorFecha = eventos.reduce((mapa, evento) => {
                    if (!mapa[evento.fecha]) {
                        mapa[evento.fecha] = [];
                    }

                    mapa[evento.fecha].push(evento);
                    return mapa;
                }, {});
            } catch (e) {
                console.error("Error al cargar calendario:", e);
                this.eventosCalendario = [];
                this.eventosPorFecha = {};
            } finally {
                if (solicitudActual === this.solicitudCalendario) {
                    this.cargandoCalendario = false; // Finaliza carga solo de la petición vigente
                }
            }
        },

        abrirModal() {
            this.modalAbierto = true;
            this.$nextTick(() => {
                limpiarProveedorCalendario();
                limpiarDeptoModal();
                const inputFrecuencia = document.getElementById('frecuencia_pedidos');
                if (inputFrecuencia) inputFrecuencia.value = '';
                const inputFecha = document.getElementById('fecha_inicio_modal');
                if (inputFecha) inputFecha.value = this.diaSeleccionado || fechaLocalKey();

            });
        },

        mesAnterior() {
            this.fechaActual = new Date(
                this.fechaActual.getFullYear(),
                this.fechaActual.getMonth() - 1,
                1
            );

            this.cargarCalendario(); // Recarga únicamente el nuevo rango visible
        },

        mesSiguiente() {
            this.fechaActual = new Date(
                this.fechaActual.getFullYear(),
                this.fechaActual.getMonth() + 1,
                1
            );

            this.cargarCalendario(); // Recarga únicamente el nuevo rango visible
        },

        irHoy() {
            const hoy = new Date(); // Obtiene la fecha local actual

            this.fechaActual = new Date(
                hoy.getFullYear(),
                hoy.getMonth(),
                1
            );

            this.diaSeleccionado = fechaLocalKey(hoy); // Selecciona hoy
            this.cargarCalendario(); // Vuelve a cargar el rango visible
        },

        obtenerProgramacionDia(fechaStr) {
            return this.eventosPorFecha[fechaStr] || []; // Acceso directo sin recalcular recurrencias
        },

        obtenerResumenDia(fechaStr) {
            const eventos = this.obtenerProgramacionDia(fechaStr); // Recupera eventos del día

            return {
                eventos: eventos.slice(0, 3), // Conserva los primeros 3
                total: eventos.length, // Cantidad total
                adicionales: Math.max(0, eventos.length - 3) // Cantidad restante
            };
        },

        obtenerProveedoresAgendadosDia(fechaStr) {
            const progs = this.obtenerProgramacionDia(fechaStr);
            return [...new Set(progs.map(p => p.proveedor))];
        },

        obtenerProgramacionAgrupadaDia() {
            if (!this.diaSeleccionado) return [];
            const items = this.obtenerProgramacionDia(this.diaSeleccionado);
            const mapaGrupos = {};

            items.forEach(item => {
                if (!mapaGrupos[item.proveedor]) {
                    mapaGrupos[item.proveedor] = {
                        proveedor: item.proveedor,
                        usuariosMap: {}
                    };
                }

                if (!mapaGrupos[item.proveedor].usuariosMap[item.usuarioNombre]) {
                    mapaGrupos[item.proveedor].usuariosMap[item.usuarioNombre] = {
                        usuarioNombre: item.usuarioNombre,
                        esCreador: item.esCreador === true, // Conserva la propiedad real del evento
                        detalles: []
                    };
                }

                mapaGrupos[item.proveedor].usuariosMap[item.usuarioNombre].detalles.push({
                    id: item.id,
                    departamento: item.departamento || 'Sin Depto.',
                    grupo: item.grupo || 'TODOS LOS GRUPOS'
                });
            });

            return Object.values(mapaGrupos)
                .map(g => ({
                    proveedor: g.proveedor,
                    usuarios: Object.values(g.usuariosMap)
                }))
                .sort((a, b) => a.proveedor.localeCompare(b.proveedor, 'es', { numeric: true, sensitivity: 'base' }));
        },

        esCreador(usr) {
            return usr.esCreador === true; // El servidor determina quién es realmente propietario
        },

        async guardarProgramacion() {
            // El ID oculto es la fuente real del proveedor seleccionado.
            const proveedorId = document.getElementById('proveedor_id_modal')?.value?.trim() || '';
            const proveedor = document.getElementById('buscar_proveedor_modal')?.value?.trim() || '';
            const departamento = document.getElementById('depto_modal')?.value?.trim() || '';
            const grupo = document.getElementById('grupo_modal')?.value?.trim() || '';
            const fechaInicio = document.getElementById('fecha_inicio_modal')?.value || '';
            const frecuencia = parseInt(
                document.getElementById('frecuencia_pedidos')?.value,
                10
            ) || 0;

            // Valida el ID, no solamente el texto visible.
            if (!proveedorId) {
                alert('⚠️ Debe seleccionar un proveedor de la lista.');
                return;
            }

            if (!fechaInicio) {
                alert('⚠️ Debe seleccionar una fecha de inicio.');
                return;
            }

            if (!frecuencia || frecuencia < 1) {
                alert('⚠️ La frecuencia debe ser mayor a 0.');
                return;
            }

            try {
                const res = await fetch('/api/programaciones', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        // Envía el ID real del proveedor.
                        proveedor_id: proveedorId,

                        // Se conserva también el nombre por compatibilidad.
                        proveedor: proveedor,

                        departamento: departamento,
                        grupo: grupo,
                        fechaInicio: fechaInicio,
                        frecuencia: frecuencia
                    })
                });

                const resultado = await res.json().catch(() => ({}));

                if (!res.ok) {
                    throw new Error(
                        resultado.error ||
                        resultado.detail ||
                        'No se pudo guardar la programación.'
                    );
                }

                // El servidor queda como fuente de verdad.
                await this.cargarCalendario();

                this.modalAbierto = false;

            } catch (e) {
                console.error('Error al guardar programación:', e);
                alert(`❌ ${e.message}`);
            }
        },

        async eliminarProgramacion(id) {
            try {
                const res = await fetch(`/api/programaciones/${id}`, {
                    method: 'DELETE',
                    headers: {
                        'Accept': 'application/json'
                    }
                });

                const resultado = await res.json().catch(() => ({}));

                if (!res.ok) {
                    throw new Error(
                        resultado.error ||
                        'No se pudo eliminar la programación.'
                    );
                }

                await this.cargarCalendario(); // Refresca el calendario desde la fuente real
            } catch (e) {
                console.error("Error al eliminar programación:", e);
                alert(e.message || 'No se pudo eliminar la programación.');
            }
        },
    };
}

let indiceDestacadoModal = -1;

function mostrarOpcionesProvCalendario() {
    const input = document.getElementById('buscar_proveedor_modal');
    if (input && input.readOnly) return;
    const dropdown = document.getElementById('opciones_proveedor_modal');
    if (dropdown) dropdown.classList.remove('hidden');
}

function filtrarProveedoresCalendario() {
    const input = document.getElementById('buscar_proveedor_modal');
    const filtro = input.value.toLowerCase().trim();
    const opciones = document.querySelectorAll('.opcion-prov-modal');
    const dropdown = document.getElementById('opciones_proveedor_modal');

    dropdown.classList.remove('hidden');
    indiceDestacadoModal = -1;

    opciones.forEach(opcion => {
        const nombre = (opcion.dataset.nombre || opcion.textContent).toLowerCase();
        if (nombre.includes(filtro)) {
            opcion.classList.remove('hidden');
        } else {
            opcion.classList.add('hidden');
        }
    });
}

function navegarProveedoresCalendario(e) {
    const dropdown = document.getElementById('opciones_proveedor_modal');
    const opciones = Array.from(document.querySelectorAll('.opcion-prov-modal')).filter(el => !el.classList.contains('hidden'));

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (dropdown.classList.contains('hidden')) mostrarOpcionesProvCalendario();
        indiceDestacadoModal = Math.min(indiceDestacadoModal + 1, opciones.length - 1);
        resaltarOpcionProvCalendario(opciones);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        indiceDestacadoModal = Math.max(indiceDestacadoModal - 1, 0);
        resaltarOpcionProvCalendario(opciones);
    } else if (e.key === 'Enter') {
        if (!dropdown.classList.contains('hidden') && indiceDestacadoModal >= 0 && opciones[indiceDestacadoModal]) {
            e.preventDefault();
            opciones[indiceDestacadoModal].click();
        }
    } else if (e.key === 'Escape') {
        dropdown.classList.add('hidden');
    }
}

function resaltarOpcionProvCalendario(opciones) {
    opciones.forEach(op => op.classList.remove('bg-blue-100', 'text-blue-700', 'font-semibold'));
    if (opciones[indiceDestacadoModal]) {
        opciones[indiceDestacadoModal].classList.add('bg-blue-100', 'text-blue-700', 'font-semibold');
        opciones[indiceDestacadoModal].scrollIntoView({ block: 'nearest' });
    }
}

async function seleccionarProveedorCalendario(id, nombre) {
    const inputBuscar = document.getElementById('buscar_proveedor_modal');
    const inputId = document.getElementById('proveedor_id_modal');
    const inputFrecuencia = document.getElementById('frecuencia_pedidos');

    // Guarda el ID real seleccionado.
    if (inputId) {
        inputId.value = String(id || '');
    }

    if (inputBuscar) {
        inputBuscar.value = id ? nombre : '';
        inputBuscar.readOnly = !!id;

        if (id) {
            inputBuscar.classList.add('bg-slate-100', 'cursor-default');
        } else {
            inputBuscar.classList.remove('bg-slate-100', 'cursor-default');
        }
    }

    const dropdown = document.getElementById('opciones_proveedor_modal');

    if (dropdown) {
        dropdown.classList.add('hidden');
    }

    if (!id) {
        if (inputFrecuencia) inputFrecuencia.value = '';
        return;
    }

    try {
        const respuesta = await fetch(`/api/proveedores/${id}`);
        if (respuesta.ok) {
            const data = await respuesta.json();
            if (inputFrecuencia) {
                inputFrecuencia.value = data.dias_despacho || data.frecuencia || '-';
            }
        }
    } catch (error) {
        console.error("Error al obtener los datos del proveedor:", error);
    }
}

function limpiarProveedorCalendario() {
    seleccionarProveedorCalendario('', '');

    const inputBuscar = document.getElementById('buscar_proveedor_modal');

    if (inputBuscar) {
        inputBuscar.value = '';

        // No hacemos focus aquí para evitar abrir el desplegable al abrir el modal.
        inputBuscar.blur();
    }

    const dropdown = document.getElementById('opciones_proveedor_modal');

    if (dropdown) {
        dropdown.classList.add('hidden');
    }
}

document.addEventListener('click', function (e) {
    const elemento = e.target instanceof Element
        ? e.target
        : null; // Evita errores si el target no es un elemento HTML

    // Procesa selección segura de proveedor
    const opcionProveedor = elemento?.closest('.opcion-prov-modal');
    // Procesa selección segura de departamento
    const opcionDepto = elemento?.closest('.opcion-depto-modal');

    if (opcionDepto) {
        seleccionarDeptoModal(
            opcionDepto.dataset.valor || '',
            opcionDepto.dataset.label || ''
        );

        return;
    }

    // Procesa selección segura de grupo
    const opcionGrupo = elemento?.closest('.opcion-grupo-modal');

    if (opcionGrupo) {
        seleccionarGrupoModal(
            opcionGrupo.dataset.valor || '',
            opcionGrupo.dataset.label || ''
        );

        return;
    }

    if (opcionProveedor) {
        seleccionarProveedorCalendario(
            opcionProveedor.dataset.id || '',
            opcionProveedor.dataset.nombre || ''
        );

        return;
    }

    // Mantiene el cierre automático del dropdown
    const combo = document.getElementById('combo-proveedor-modal');
    const dropdown = document.getElementById('opciones_proveedor_modal');

    if (combo && dropdown && !combo.contains(elemento)) {
        dropdown.classList.add('hidden');
    }
});

let datosClasificacionModal = [];

async function cargarClasificacionProveedorModal(proveedorId) {
    limpiarDeptoModal();
    if (!proveedorId) return;

    try {
        const res = await fetch(`/api/clasificacion?proveedor_id=${encodeURIComponent(proveedorId)}`);
        if (res.ok) {
            datosClasificacionModal = await res.json();
            poblarDepartamentosModal();
        }
    } catch (e) {
        console.error("Error al obtener clasificación del proveedor:", e);
    }
}

function poblarDepartamentosModal() {
    const container = document.getElementById('opciones_depto_modal');
    const inpDepto = document.getElementById('buscar_depto_modal');

    if (!container || !inpDepto) return;

    container.innerHTML = ''; // Limpia las opciones anteriores

    const deptos = [...new Set(
        datosClasificacionModal
            .map(item => String(item.departamento || '').trim())
            .filter(Boolean)
    )];

    if (deptos.length === 0) {
        inpDepto.disabled = true;
        return;
    }

    inpDepto.disabled = false;

    // Opción general
    const todos = document.createElement('button');
    todos.type = 'button';
    todos.className =
        'opcion-depto-modal w-full text-left px-3 py-1.5 text-xs text-slate-400 hover:bg-slate-50 border-b border-slate-100';
    todos.dataset.nombre = 'todos los departamentos';
    todos.dataset.valor = '';
    todos.dataset.label = 'Todos los departamentos';
    todos.textContent = 'Todos los departamentos';
    container.appendChild(todos);

    // Crea cada departamento sin innerHTML ejecutable
    deptos.forEach(depto => {
        const opcion = document.createElement('button');

        opcion.type = 'button';
        opcion.className =
            'opcion-depto-modal w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-blue-50 hover:text-blue-600';

        opcion.dataset.nombre = depto.toLowerCase();
        opcion.dataset.valor = depto;
        opcion.dataset.label = depto;
        opcion.textContent = depto;

        container.appendChild(opcion);
    });
}

function seleccionarDeptoModal(val, label) {
    document.getElementById('depto_modal').value = val;
    document.getElementById('buscar_depto_modal').value = val ? label : '';
    document.getElementById('opciones_depto_modal').classList.add('hidden');

    limpiarGrupoModal();

    const inpGrupo = document.getElementById('buscar_grupo_modal');
    if (val) {
        inpGrupo.disabled = false;
        poblarGruposModal(val);
    } else {
        inpGrupo.disabled = true;
    }
}

function poblarGruposModal(deptoSel) {
    const container = document.getElementById('opciones_grupo_modal');

    if (!container) return;

    container.innerHTML = ''; // Limpia las opciones anteriores

    const grupos = [...new Set(
        datosClasificacionModal
            .filter(item => item.departamento === deptoSel)
            .map(item => String(item.grupo || '').trim())
            .filter(Boolean)
    )];

    // Opción general
    const todos = document.createElement('button');
    todos.type = 'button';
    todos.className =
        'opcion-grupo-modal w-full text-left px-3 py-1.5 text-xs font-semibold text-indigo-600 hover:bg-blue-50 border-b border-slate-100';
    todos.dataset.nombre = 'todos los grupos';
    todos.dataset.valor = 'TODOS LOS GRUPOS';
    todos.dataset.label = 'TODOS LOS GRUPOS';
    todos.textContent = 'TODOS LOS GRUPOS';
    container.appendChild(todos);

    // Agrega grupos reales
    grupos.forEach(grupo => {
        if (grupo === 'TODOS LOS GRUPOS') return;

        const opcion = document.createElement('button');

        opcion.type = 'button';
        opcion.className =
            'opcion-grupo-modal w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-blue-50 hover:text-blue-600';

        opcion.dataset.nombre = grupo.toLowerCase();
        opcion.dataset.valor = grupo;
        opcion.dataset.label = grupo;
        opcion.textContent = grupo;

        container.appendChild(opcion);
    });
}

function seleccionarGrupoModal(val, label) {
    document.getElementById('grupo_modal').value = val;
    document.getElementById('buscar_grupo_modal').value = val ? label : '';
    document.getElementById('opciones_grupo_modal').classList.add('hidden');
}

function filtrarDeptosModal() {
    const texto = document.getElementById('buscar_depto_modal').value.toLowerCase().trim();
    document.querySelectorAll('.opcion-depto-modal').forEach(op => {
        op.classList.toggle('hidden', !op.getAttribute('data-nombre').includes(texto));
    });
    document.getElementById('opciones_depto_modal').classList.remove('hidden');
}

function mostrarOpcionesDeptoModal() {
    document.getElementById('opciones_depto_modal').classList.remove('hidden');
}

function limpiarDeptoModal() {
    document.getElementById('depto_modal').value = '';
    document.getElementById('buscar_depto_modal').value = '';
    document.getElementById('buscar_depto_modal').disabled = true;
    document.getElementById('opciones_depto_modal').classList.add('hidden');
    limpiarGrupoModal();
}

function filtrarGruposModal() {
    const texto = document.getElementById('buscar_grupo_modal').value.toLowerCase().trim();
    document.querySelectorAll('.opcion-grupo-modal').forEach(op => {
        op.classList.toggle('hidden', !op.getAttribute('data-nombre').includes(texto));
    });
    document.getElementById('opciones_grupo_modal').classList.remove('hidden');
}

function mostrarOpcionesGrupoModal() {
    document.getElementById('opciones_grupo_modal').classList.remove('hidden');
}

function limpiarGrupoModal() {
    document.getElementById('grupo_modal').value = '';
    document.getElementById('buscar_grupo_modal').value = '';
    document.getElementById('buscar_grupo_modal').disabled = true;
    document.getElementById('opciones_grupo_modal').classList.add('hidden');
}

const seleccionarProveedorCalendarioOriginal = seleccionarProveedorCalendario;
seleccionarProveedorCalendario = async function (id, nombre) {
    await seleccionarProveedorCalendarioOriginal(id, nombre);
    cargarClasificacionProveedorModal(id);
};