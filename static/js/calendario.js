// Variable global para almacenar el nombre del usuario desde la sesión
const USUARIO_NOMBRE_SESION = document.getElementById('usuario-sesion-data')?.dataset.nombre || 'Usuario Sistema';

// Componente principal de Alpine JS para el control del calendario
function calendarioReposicion() {
    return {
        fechaActual: new Date(),
        diaSeleccionado: new Date().toISOString().split('T')[0],
        modalAbierto: false,
        programaciones: [],
        listaProveedoresBD: JSON.parse(document.getElementById('proveedores-data')?.textContent || '[]'),
        proveedorSeleccionadoId: '',
        proveedoresAbiertos: {},

        toggleProveedor(nombreProv) {
            this.proveedoresAbiertos[nombreProv] = !this.proveedoresAbiertos[nombreProv];
        },

        esProveedorAbierto(nombreProv) {
            return !!this.proveedoresAbiertos[nombreProv];
        },

        get nombreMesAno() {
            return this.fechaActual.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })
                .replace(/^\w/, c => c.toUpperCase());
        },

        get diasMes() {
            const año = this.fechaActual.getFullYear();
            const mes = this.fechaActual.getMonth();
            const primerDia = new Date(año, mes, 1);
            const ultimoDia = new Date(año, mes + 1, 0);
            const dias = [];
            const hoyStr = new Date().toISOString().split('T')[0];

            const diaSemanaInicio = primerDia.getDay();
            for (let i = diaSemanaInicio - 1; i >= 0; i--) {
                const d = new Date(año, mes, -i);
                dias.push({
                    numero: d.getDate(),
                    fechaStr: d.toISOString().split('T')[0],
                    esMesActual: false,
                    esHoy: d.toISOString().split('T')[0] === hoyStr
                });
            }

            for (let i = 1; i <= ultimoDia.getDate(); i++) {
                const fStr = `${año}-${String(mes + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
                dias.push({
                    numero: i,
                    fechaStr: fStr,
                    esMesActual: true,
                    esHoy: fStr === hoyStr
                });
            }

            const celdasRestantes = (7 - (dias.length % 7)) % 7;
            for (let i = 1; i <= celdasRestantes; i++) {
                const d = new Date(año, mes + 1, i);
                dias.push({
                    numero: d.getDate(),
                    fechaStr: d.toISOString().split('T')[0],
                    esMesActual: false,
                    esHoy: d.toISOString().split('T')[0] === hoyStr
                });
            }

            return dias;
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

        async cargarProgramaciones() {
            try {
                const res = await fetch('/api/programaciones');
                if (res.ok) {
                    const datos = await res.json();
                    this.programaciones = datos.map(item => ({
                        id: item.id,
                        proveedor: item.proveedor,
                        departamento: item.departamento || 'Sin Depto.',
                        grupo: item.grupo || 'TODOS LOS GRUPOS',
                        usuarioNombre: item.nombre_comprador || item.usuario_nombre || 'Usuario Desconocido',
                        usuarioId: item.usuario_id || null,
                        fechaInicio: item.fecha_inicio,
                        frecuencia: parseInt(item.frecuencia)
                    }));
                }
            } catch (e) {
                console.error("Error al cargar programaciones:", e);
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
                if (inputFecha) inputFecha.value = this.diaSeleccionado || new Date().toISOString().split('T')[0];
            });
        },

        mesAnterior() {
            this.fechaActual = new Date(this.fechaActual.getFullYear(), this.fechaActual.getMonth() - 1, 1);
        },

        mesSiguiente() {
            this.fechaActual = new Date(this.fechaActual.getFullYear(), this.fechaActual.getMonth() + 1, 1);
        },

        obtenerProgramacionDia(fechaStr) {
            const fechaEvaluada = new Date(fechaStr + 'T00:00:00');
            return this.programaciones.filter(prog => {
                const fechaInicio = new Date(prog.fechaInicio + 'T00:00:00');
                if (fechaEvaluada < fechaInicio) return false;

                const diferenciaTiempo = fechaEvaluada.getTime() - fechaInicio.getTime();
                const diferenciaDias = Math.round(diferenciaTiempo / (1000 * 3600 * 24));

                return diferenciaDias % prog.frecuencia === 0;
            });
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
            return usr.usuarioNombre === USUARIO_NOMBRE_SESION;
        },

        async guardarProgramacion() {
            const proveedor = document.getElementById('buscar_proveedor_modal')?.value;
            const departamento = document.getElementById('depto_modal')?.value || '';
            const grupo = document.getElementById('grupo_modal')?.value || '';
            const fechaInicio = document.getElementById('fecha_inicio_modal')?.value;
            const frecuencia = parseInt(document.getElementById('frecuencia_pedidos')?.value) || 0;

            if (!proveedor || !fechaInicio || !frecuencia) return;

            try {
                const res = await fetch('/api/programaciones', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        proveedor,
                        departamento,
                        grupo,
                        nombre_comprador: USUARIO_NOMBRE_SESION,
                        fechaInicio,
                        frecuencia
                    })
                });

                if (res.ok) {
                    const creado = await res.json();
                    const nuevoItem = {
                        id: creado.id,
                        proveedor: creado.proveedor,
                        departamento: creado.departamento || departamento || 'Sin Depto.',
                        grupo: creado.grupo || grupo || 'Sin Grupo',
                        usuarioNombre: creado.nombre_comprador || USUARIO_NOMBRE_SESION,
                        usuarioId: creado.usuario_id || null,
                        fechaInicio: creado.fecha_inicio,
                        frecuencia: parseInt(creado.frecuencia)
                    };

                    const idx = this.programaciones.findIndex(p => p.id === creado.id);
                    if (idx !== -1) {
                        this.programaciones[idx] = nuevoItem;
                    } else {
                        this.programaciones.push(nuevoItem);
                    }

                    this.modalAbierto = false;
                }
            } catch (e) {
                console.error("Error al guardar programación:", e);
            }
        },

        async eliminarProgramacion(id) {
            try {
                const res = await fetch(`/api/programaciones/${id}`, { method: 'DELETE' });
                if (res.ok) {
                    this.programaciones = this.programaciones.filter(p => p.id !== id);
                }
            } catch (e) {
                console.error("Error al eliminar programación:", e);
            }
        }
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

    if (inputId) inputId.value = id;
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
    if (dropdown) dropdown.classList.add('hidden');

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
        inputBuscar.focus();
    }
}

document.addEventListener('click', function (e) {
    const combo = document.getElementById('combo-proveedor-modal');
    const dropdown = document.getElementById('opciones_proveedor_modal');
    if (combo && dropdown && !combo.contains(e.target)) {
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

    const deptos = [...new Set(datosClasificacionModal.map(item => item.departamento))].filter(Boolean);

    if (deptos.length > 0) {
        inpDepto.disabled = false;
        let html = `<div onclick="seleccionarDeptoModal('', 'Todos los departamentos')" class="px-3 py-1.5 text-xs text-slate-400 hover:bg-slate-50 cursor-pointer border-b border-slate-100">Todos los departamentos</div>`;
        deptos.forEach(d => {
            html += `<div onclick="seleccionarDeptoModal('${d}', '${d}')" data-nombre="${d.toLowerCase()}" class="opcion-depto-modal px-3 py-1.5 text-xs text-slate-700 hover:bg-blue-50 hover:text-blue-600 cursor-pointer">${d}</div>`;
        });
        container.innerHTML = html;
    } else {
        inpDepto.disabled = true;
    }
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

    const grupos = [...new Set(datosClasificacionModal.filter(item => item.departamento === deptoSel).map(item => item.grupo))].filter(Boolean);

    let html = `<div onclick="seleccionarGrupoModal('Todos los Grupos', 'Todos los Grupos')" data-nombre="todos los grupos" class="opcion-grupo-modal px-3 py-1.5 text-xs font-semibold text-indigo-600 hover:bg-blue-50 cursor-pointer border-b border-slate-100">TODOS LOS GRUPOS</div>`;
    grupos.forEach(g => {
        if (g !== 'TODOS LOS GRUPOS') {
            html += `<div onclick="seleccionarGrupoModal('${g}', '${g}')" data-nombre="${g.toLowerCase()}" class="opcion-grupo-modal px-3 py-1.5 text-xs text-slate-700 hover:bg-blue-50 hover:text-blue-600 cursor-pointer">${g}</div>`;
        }
    });
    container.innerHTML = html;
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