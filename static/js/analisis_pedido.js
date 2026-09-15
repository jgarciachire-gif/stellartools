// Variables globales de estado
let indiceDestacadoAnalisis = -1;
let datosClasificacionAnalisis = [];
let celdasSeleccionadasAnalisis = [];
let celdaInicio = null;
let isArrastrando = false;
let matrizTiendas = {};
let tiendaActivaPestana = 'CENTRO';
let colOrdenActual = -1;
let ascOrdenActual = true;

// Inicializaciones
document.addEventListener('DOMContentLoaded', () => {
    const btnMenuOpciones = document.getElementById('btn-menu-opciones');
    const dropdownOpciones = document.getElementById('dropdown-opciones');

    if (btnMenuOpciones) {
        btnMenuOpciones.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdownOpciones.classList.toggle('hidden');
        });
    }

    document.addEventListener('click', () => {
        if (dropdownOpciones) dropdownOpciones.classList.add('hidden');
    });

    const cantidadFilasIniciales = 1;
    for (let i = 0; i < cantidadFilasIniciales; i++) {
        agregarFilaAnalisis();
    }
});

function limpiarListaProductos() {
    const tbody = document.getElementById('filas-tabla-analisis');
    const dropdown = document.getElementById('dropdown-opciones');

    if (dropdown) dropdown.classList.add('hidden');

    if (tbody && tbody.children.length > 0) {
        if (confirm('¿Estás seguro de que deseas vaciar todos los productos de la lista?')) {
            tbody.innerHTML = '';
            if (typeof calcularTotalesAnalisis === 'function') calcularTotalesAnalisis();
            else if (typeof calcularTotales === 'function') calcularTotales();
        }
    }
}

function mostrarOpcionesTiendaAnalisis() {
    document.getElementById('opciones_tienda_analisis').classList.remove('hidden');
}

function filtrarTiendasAnalisis() {
    const texto = document.getElementById('buscar_tienda_analisis').value.toLowerCase().trim();
    const opciones = document.querySelectorAll('.opcion-tienda-analisis');
    document.getElementById('opciones_tienda_analisis').classList.remove('hidden');

    indiceDestacadoTiendaAnalisis = -1;
    opciones.forEach(opcion => {
        const nombre = opcion.getAttribute('data-nombre') || '';
        opcion.classList.remove('bg-blue-100', 'text-blue-700', 'font-semibold');
        if (nombre.includes(texto)) opcion.classList.remove('hidden');
        else opcion.classList.add('hidden');
    });
}

function navegarTiendasAnalisis(e) {
    const dropdown = document.getElementById('opciones_tienda_analisis');
    const opciones = Array.from(document.querySelectorAll('.opcion-tienda-analisis')).filter(el => !el.classList.contains('hidden'));

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (dropdown.classList.contains('hidden')) mostrarOpcionesTiendaAnalisis();
        indiceDestacadoTiendaAnalisis = Math.min(indiceDestacadoTiendaAnalisis + 1, opciones.length - 1);
        resaltarOpcionTiendaAnalisis(opciones);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        indiceDestacadoTiendaAnalisis = Math.max(indiceDestacadoTiendaAnalisis - 1, 0);
        resaltarOpcionTiendaAnalisis(opciones);
    } else if (e.key === 'Enter') {
        if (!dropdown.classList.contains('hidden') && indiceDestacadoTiendaAnalisis >= 0 && opciones[indiceDestacadoTiendaAnalisis]) {
            e.preventDefault();
            opciones[indiceDestacadoTiendaAnalisis].click();
        }
    } else if (e.key === 'Escape') {
        dropdown.classList.add('hidden');
    }
}

function resaltarOpcionTiendaAnalisis(opciones) {
    opciones.forEach(op => op.classList.remove('bg-blue-100', 'text-blue-700', 'font-semibold'));
    if (opciones[indiceDestacadoTiendaAnalisis]) {
        opciones[indiceDestacadoTiendaAnalisis].classList.add('bg-blue-100', 'text-blue-700', 'font-semibold');
        opciones[indiceDestacadoTiendaAnalisis].scrollIntoView({ block: 'nearest' });
    }
}

function seleccionarTiendaAnalisis(val, nombre) {
    document.getElementById('tienda_destino').value = val;
    document.getElementById('buscar_tienda_analisis').value = val ? nombre : '';
    document.getElementById('opciones_tienda_analisis').classList.add('hidden');
}

function limpiarTiendaAnalisis() {
    seleccionarTiendaAnalisis('', '');
}

function mostrarOpcionesProvAnalisis() {
    const input = document.getElementById('buscar_proveedor_analisis');
    if (input && input.readOnly) return;
    const dropdown = document.getElementById('opciones_proveedor_analisis');
    if (dropdown) dropdown.classList.remove('hidden');
}

function filtrarProveedoresAnalisis() {
    const input = document.getElementById('buscar_proveedor_analisis');
    const filtro = input.value.toLowerCase().trim();
    const opciones = document.querySelectorAll('.opcion-prov-analisis');
    const dropdown = document.getElementById('opciones_proveedor_analisis');

    dropdown.classList.remove('hidden');
    opciones.forEach(opcion => {
        const nombre = (opcion.dataset.nombre || opcion.textContent).toLowerCase();
        if (nombre.includes(filtro)) opcion.classList.remove('hidden');
        else opcion.classList.add('hidden');
    });
}

document.addEventListener('click', function (e) {
    const combo = document.getElementById('combo-proveedor-analisis');
    const dropdown = document.getElementById('opciones_proveedor_analisis');
    if (combo && dropdown && !combo.contains(e.target)) dropdown.classList.add('hidden');
});

function navegarProveedoresAnalisis(e) {
    const dropdown = document.getElementById('opciones_proveedor_analisis');
    const opciones = Array.from(document.querySelectorAll('.opcion-prov-analisis')).filter(el => !el.classList.contains('hidden'));

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (dropdown.classList.contains('hidden')) mostrarOpcionesProvAnalisis();
        indiceDestacadoAnalisis = Math.min(indiceDestacadoAnalisis + 1, opciones.length - 1);
        resaltarOpcionAnalisis(opciones);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        indiceDestacadoAnalisis = Math.max(indiceDestacadoAnalisis - 1, 0);
        resaltarOpcionAnalisis(opciones);
    } else if (e.key === 'Enter') {
        if (!dropdown.classList.contains('hidden') && indiceDestacadoAnalisis >= 0 && opciones[indiceDestacadoAnalisis]) {
            e.preventDefault();
            opciones[indiceDestacadoAnalisis].click();
        }
    } else if (e.key === 'Escape') {
        dropdown.classList.add('hidden');
    }
}

function resaltarOpcionAnalisis(opciones) {
    opciones.forEach(op => op.classList.remove('bg-blue-100', 'text-blue-700', 'font-semibold'));
    if (opciones[indiceDestacadoAnalisis]) {
        opciones[indiceDestacadoAnalisis].classList.add('bg-blue-100', 'text-blue-700', 'font-semibold');
        opciones[indiceDestacadoAnalisis].scrollIntoView({ block: 'nearest' });
    }
}

function limpiarValorBD(val) {
    if (!val || val === 'None' || val === 'null' || val === 'undefined') return '-';
    return val;
}

function seleccionarProveedorDesdeElemento(el) {
    const d = el.dataset;
    seleccionarProveedorAnalisis(
        d.id || '',
        d.nombre || '',
        d.contacto || '',
        d.telefono || '',
        d.diasCredito || '',
        d.frecuencia || '',
        d.etiquetas || ''
    );
}

async function seleccionarProveedorAnalisis(id, nombre) {
    const inputBuscar = document.getElementById('buscar_proveedor_analisis');
    const inputId = document.getElementById('proveedor_id_analisis');

    if (inputId) inputId.value = id;
    if (inputBuscar) {
        inputBuscar.value = id ? nombre : '';
        inputBuscar.readOnly = !!id;
        if (id) inputBuscar.classList.add('bg-slate-100', 'cursor-default');
        else inputBuscar.classList.remove('bg-slate-100', 'cursor-default');
    }

    const dropdown = document.getElementById('opciones_proveedor_analisis');
    if (dropdown) dropdown.classList.add('hidden');

    const secFiltros = document.getElementById('sec-filtros-clasificacion');
    const inpDepto = document.getElementById('buscar_depto_analisis');
    const btnImportar = document.getElementById('btn_importar_productos');

    if (typeof limpiarDeptoAnalisis === 'function') limpiarDeptoAnalisis();

    if (!id) {
        if (secFiltros) secFiltros.classList.add('opacity-50', 'pointer-events-none');
        if (inpDepto) inpDepto.disabled = true;
        if (btnImportar) btnImportar.disabled = true;

        if (document.getElementById('prov_contacto')) document.getElementById('prov_contacto').value = '-';
        if (document.getElementById('prov_telefono')) document.getElementById('prov_telefono').value = '-';
        if (document.getElementById('prov_dias_credito')) document.getElementById('prov_dias_credito').value = '-';
        if (document.getElementById('prov_frecuencia')) document.getElementById('prov_frecuencia').value = '-';

        const contEtiquetas = document.getElementById('prov_etiquetas');
        if (contEtiquetas) contEtiquetas.innerHTML = '<span class="text-xs text-slate-400 italic">Sin proveedor seleccionado</span>';
        return;
    }

    if (secFiltros) secFiltros.classList.remove('opacity-50', 'pointer-events-none');
    if (inpDepto) inpDepto.disabled = false;
    if (btnImportar) btnImportar.disabled = false;

    try {
        const respuesta = await fetch(`/api/proveedores/${id}`);
        if (respuesta.ok) {
            const data = await respuesta.json();

            const elemContacto = document.getElementById('prov_contacto');
            const elemTelefono = document.getElementById('prov_telefono');
            const elemCredito = document.getElementById('prov_dias_credito');
            const elemFrecuencia = document.getElementById('prov_frecuencia');

            if (elemContacto) elemContacto.value = data.contacto || '-';
            if (elemTelefono) elemTelefono.value = data.telefono || '-';
            if (elemCredito) elemCredito.value = (data.dias_credito !== undefined && data.dias_credito !== null && data.dias_credito !== '') ? data.dias_credito : '-';
            if (elemFrecuencia) elemFrecuencia.value = data.frecuencia || '-';

            const contEtiquetas = document.getElementById('prov_etiquetas');
            if (contEtiquetas) {
                contEtiquetas.innerHTML = '';
                const etiquetas = data.etiquetas || '';
                if (etiquetas && etiquetas.length > 0) {
                    const lista = typeof etiquetas === 'string' ? etiquetas.split(',') : etiquetas;
                    lista.forEach(tag => {
                        const badge = document.createElement('span');
                        badge.className = 'px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg text-[11px] font-semibold';
                        badge.textContent = String(tag).trim();
                        contEtiquetas.appendChild(badge);
                    });
                } else {
                    contEtiquetas.innerHTML = '<span class="text-xs text-slate-400 italic">Sin etiquetas</span>';
                }
            }
        }
    } catch (error) {
        console.error("Error al obtener los datos del proveedor:", error);
    }

    if (typeof cargarClasificacionProveedor === 'function') {
        cargarClasificacionProveedor(id);
    }
}

function limpiarProveedorAnalisis() {
    seleccionarProveedorAnalisis('', '');
    const inputBuscar = document.getElementById('buscar_proveedor_analisis');
    if (inputBuscar) {
        inputBuscar.value = '';
        inputBuscar.focus();
    }
}

async function ejecutarCalculoSugeridoConSpinner() {
    const btn = document.getElementById('btn-calcular-sugerido');
    const icono = document.getElementById('icono-btn-calcular');
    const texto = document.getElementById('texto-btn-calcular');

    if (!btn) return;

    btn.disabled = true;
    icono.className = 'fa-solid fa-spinner fa-spin';
    texto.textContent = 'Calculado...';

    setTimeout(async () => {
        texto.textContent = 'Cargando a la tabla...';
        try {
            if (typeof calcularSugeridoSedeActual === 'function') {
                await calcularSugeridoSedeActual();
            }
        } catch (e) {
            console.error('Error durante el cálculo:', e);
        } finally {
            setTimeout(() => {
                icono.className = 'fa-solid fa-bolt';
                texto.textContent = 'Calcular Sugerido';
                btn.disabled = false;
            }, 300);
        }
    }, 400);
}

async function cargarClasificacionProveedor(proveedorId) {
    try {
        const res = await fetch(`/api/clasificacion?proveedor_id=${encodeURIComponent(proveedorId)}`);
        datosClasificacionAnalisis = await res.json();
        poblarDepartamentosAnalisis();
        poblarMarcasAnalisis();
    } catch (e) {
        console.error('Error al obtener clasificaciones:', e);
    }
}

function poblarDepartamentosAnalisis() {
    const container = document.getElementById('opciones_depto_analisis');
    const deptos = [...new Set(datosClasificacionAnalisis.map(item => item.departamento))].filter(Boolean);

    let html = `<div onclick="seleccionarDeptoAnalisis('', 'Todos los departamentos')" class="px-4 py-2 text-sm text-slate-400 hover:bg-slate-50 cursor-pointer border-b border-slate-100">Todos los departamentos</div>`;
    deptos.forEach(d => {
        html += `<div onclick="seleccionarDeptoAnalisis('${d}', '${d}')" data-nombre="${d.toLowerCase()}" class="opcion-depto-analisis px-4 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-600 cursor-pointer">${d}</div>`;
    });
    container.innerHTML = html;
}

function seleccionarDeptoAnalisis(val, label) {
    document.getElementById('depto_analisis').value = val;
    document.getElementById('buscar_depto_analisis').value = val ? label : '';
    document.getElementById('opciones_depto_analisis').classList.add('hidden');

    limpiarGrupoAnalisis();

    const inpGrupo = document.getElementById('buscar_grupo_analisis');
    if (val) {
        inpGrupo.disabled = false;
        poblarGruposAnalisis(val);
    } else {
        inpGrupo.disabled = true;
    }
    poblarMarcasAnalisis();
}

function poblarGruposAnalisis(deptoSel) {
    const container = document.getElementById('opciones_grupo_analisis');
    const grupos = [...new Set(datosClasificacionAnalisis.filter(item => item.departamento === deptoSel).map(item => item.grupo))].filter(Boolean);

    let html = `<div onclick="seleccionarGrupoAnalisis('', 'Todos los grupos')" class="px-4 py-2 text-sm text-slate-400 hover:bg-slate-50 cursor-pointer border-b border-slate-100">Todos los grupos</div>`;
    grupos.forEach(g => {
        html += `<div onclick="seleccionarGrupoAnalisis('${g}', '${g}')" data-nombre="${g.toLowerCase()}" class="opcion-grupo-analisis px-4 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-600 cursor-pointer">${g}</div>`;
    });
    container.innerHTML = html;
}

function seleccionarGrupoAnalisis(val, label) {
    document.getElementById('grupo_analisis').value = val;
    document.getElementById('buscar_grupo_analisis').value = val ? label : '';
    document.getElementById('opciones_grupo_analisis').classList.add('hidden');

    limpiarSubgrupoAnalisis();

    const inpSubgrupo = document.getElementById('buscar_subgrupo_analisis');
    if (val) {
        inpSubgrupo.disabled = false;
        poblarSubgruposAnalisis(document.getElementById('depto_analisis').value, val);
    } else {
        inpSubgrupo.disabled = true;
    }
    poblarMarcasAnalisis();
}

function poblarSubgruposAnalisis(deptoSel, grupoSel) {
    const container = document.getElementById('opciones_subgrupo_analisis');
    const subgrupos = [...new Set(datosClasificacionAnalisis.filter(item => item.departamento === deptoSel && item.grupo === grupoSel).map(item => item.subgrupo))].filter(Boolean);

    let html = `<div onclick="seleccionarSubgrupoAnalisis('', 'Todos los subgrupos')" class="px-4 py-2 text-sm text-slate-400 hover:bg-slate-50 cursor-pointer border-b border-slate-100">Todos los subgrupos</div>`;
    subgrupos.forEach(s => {
        html += `<div onclick="seleccionarSubgrupoAnalisis('${s}', '${s}')" data-nombre="${s.toLowerCase()}" class="opcion-subgrupo-analisis px-4 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-600 cursor-pointer">${s}</div>`;
    });
    container.innerHTML = html;
}

function seleccionarSubgrupoAnalisis(val, label) {
    document.getElementById('subgrupo_analisis').value = val;
    document.getElementById('buscar_subgrupo_analisis').value = val ? label : '';
    document.getElementById('opciones_subgrupo_analisis').classList.add('hidden');
    poblarMarcasAnalisis();
}

function poblarMarcasAnalisis() {
    const container = document.getElementById('opciones_marca_analisis');
    if (!container) return;

    const deptoSel = document.getElementById('depto_analisis')?.value || '';
    const grupoSel = document.getElementById('grupo_analisis')?.value || '';
    const subgrupoSel = document.getElementById('subgrupo_analisis')?.value || '';

    let itemsFiltrados = datosClasificacionAnalisis;
    if (deptoSel) itemsFiltrados = itemsFiltrados.filter(item => item.departamento === deptoSel);
    if (grupoSel) itemsFiltrados = itemsFiltrados.filter(item => item.grupo === grupoSel);
    if (subgrupoSel) itemsFiltrados = itemsFiltrados.filter(item => item.subgrupo === subgrupoSel);

    const marcas = [...new Set(itemsFiltrados.map(item => item.marca))].filter(Boolean).sort();

    const marcaActual = document.getElementById('marca_analisis')?.value || '';
    if (marcaActual && !marcas.includes(marcaActual)) {
        limpiarMarcaAnalisis();
    }

    let html = `<div onclick="seleccionarMarcaAnalisis('', 'Todas las marcas')" class="px-4 py-2 text-sm text-slate-400 hover:bg-slate-50 cursor-pointer border-b border-slate-100">Todas las marcas</div>`;
    marcas.forEach(m => {
        html += `<div onclick="seleccionarMarcaAnalisis('${m}', '${m}')" data-nombre="${m.toLowerCase()}" class="opcion-marca-analisis px-4 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-600 cursor-pointer">${m}</div>`;
    });
    container.innerHTML = html;
}

function seleccionarMarcaAnalisis(val, label) {
    document.getElementById('marca_analisis').value = val;
    document.getElementById('buscar_marca_analisis').value = val ? label : '';
    document.getElementById('opciones_marca_analisis').classList.add('hidden');
}

function filtrarMarcasAnalisis() {
    const texto = document.getElementById('buscar_marca_analisis').value.toLowerCase().trim();
    document.querySelectorAll('.opcion-marca-analisis').forEach(op => {
        op.classList.toggle('hidden', !op.getAttribute('data-nombre').includes(texto));
    });
    document.getElementById('opciones_marca_analisis').classList.remove('hidden');
}

function mostrarOpcionesMarcaAnalisis() {
    document.getElementById('opciones_marca_analisis').classList.remove('hidden');
}

function limpiarMarcaAnalisis() {
    document.getElementById('marca_analisis').value = '';
    document.getElementById('buscar_marca_analisis').value = '';
    document.getElementById('opciones_marca_analisis').classList.add('hidden');
}

function filtrarDeptosAnalisis() {
    const texto = document.getElementById('buscar_depto_analisis').value.toLowerCase().trim();
    document.querySelectorAll('.opcion-depto-analisis').forEach(op => {
        op.classList.toggle('hidden', !op.getAttribute('data-nombre').includes(texto));
    });
    document.getElementById('opciones_depto_analisis').classList.remove('hidden');
}
function mostrarOpcionesDeptoAnalisis() {
    document.getElementById('opciones_depto_analisis').classList.remove('hidden');
}

function filtrarGruposAnalisis() {
    const texto = document.getElementById('buscar_grupo_analisis').value.toLowerCase().trim();
    document.querySelectorAll('.opcion-grupo-analisis').forEach(op => {
        op.classList.toggle('hidden', !op.getAttribute('data-nombre').includes(texto));
    });
    document.getElementById('opciones_grupo_analisis').classList.remove('hidden');
}
function mostrarOpcionesGrupoAnalisis() {
    document.getElementById('opciones_grupo_analisis').classList.remove('hidden');
}

function filtrarSubgruposAnalisis() {
    const texto = document.getElementById('buscar_subgrupo_analisis').value.toLowerCase().trim();
    document.querySelectorAll('.opcion-subgrupo-analisis').forEach(op => {
        op.classList.toggle('hidden', !op.getAttribute('data-nombre').includes(texto));
    });
    document.getElementById('opciones_subgrupo_analisis').classList.remove('hidden');
}
function mostrarOpcionesSubgrupoAnalisis() {
    document.getElementById('opciones_subgrupo_analisis').classList.remove('hidden');
}

function limpiarDeptoAnalisis() {
    document.getElementById('depto_analisis').value = '';
    document.getElementById('buscar_depto_analisis').value = '';
    document.getElementById('opciones_depto_analisis').classList.add('hidden');
    limpiarGrupoAnalisis();
    poblarMarcasAnalisis();
}

function limpiarGrupoAnalisis() {
    document.getElementById('grupo_analisis').value = '';
    document.getElementById('buscar_grupo_analisis').value = '';
    document.getElementById('opciones_grupo_analisis').classList.add('hidden');
    limpiarSubgrupoAnalisis();
    poblarMarcasAnalisis();
}

function limpiarSubgrupoAnalisis() {
    document.getElementById('subgrupo_analisis').value = '';
    document.getElementById('buscar_subgrupo_analisis').value = '';
    document.getElementById('opciones_subgrupo_analisis').classList.add('hidden');
    poblarMarcasAnalisis();
}

async function importarProductosAnalisis() {
    const proveedorId = document.getElementById('proveedor_id_analisis').value;
    if (!proveedorId) return;

    const depto = document.getElementById('depto_analisis').value;
    const grupo = document.getElementById('grupo_analisis').value;
    const subgrupo = document.getElementById('subgrupo_analisis').value;
    const marca = document.getElementById('marca_analisis').value;

    const params = new URLSearchParams({
        proveedor_id: proveedorId,
        departamento: depto,
        grupo: grupo,
        subgrupo: subgrupo,
        marca: marca
    });

    try {
        const res = await fetch(`/api/productos/importar-analisis?${params.toString()}`);
        const productos = await res.json();

        if (!Array.isArray(productos) || productos.length === 0) {
            alert('No se encontraron productos para los filtros seleccionados.');
            return;
        }

        const tbody = document.getElementById('filas-tabla-analisis');
        const filasExistentes = Array.from(tbody.querySelectorAll('tr'));

        const filasVacias = filasExistentes.filter(tr => {
            const inpCod = tr.querySelector('.inp-codigo');
            return inpCod && inpCod.value.trim() === '';
        });

        productos.forEach((prod, index) => {
            let tr;
            if (index < filasVacias.length) {
                tr = filasVacias[index];
            } else {
                tr = agregarFilaAnalisis();
            }

            const inpCod = tr.querySelector('.inp-codigo');
            const inpDesc = tr.querySelector('.inp-desc');
            const inpPre = tr.querySelector('.inp-pre');
            const inpCosto = tr.querySelector('.inp-costo');
            const inpEmp = tr.querySelector('.inp-emp');

            inpCod.value = prod.codigo || '';
            inpDesc.value = prod.descripcion || '';
            inpPre.value = prod.unidad_manejo || 1;
            inpCosto.value = (prod.precio || 0).toFixed(2);

            inpPre.dataset.original = prod.unidad_manejo || 1;
            inpCosto.dataset.original = (prod.precio || 0).toFixed(2);

            inpEmp.value = 0;

            bloquearCeldaCodigo(inpCod);
            calcularFila(inpCod);
        });

        totalizarAnalisis();
        if (typeof ejecutarCalculoSugeridosSync === 'function') ejecutarCalculoSugeridosSync();

    } catch (e) {
        console.error('Error al importar productos:', e);
        alert('Ocurrió un error al importar los productos.');
    }
}

function bloquearCeldaCodigo(inputCodigo) {
    if (inputCodigo.value.trim() !== '') {
        inputCodigo.readOnly = true;
        inputCodigo.classList.add('bg-slate-100', 'cursor-default', 'select-none');
        inputCodigo.classList.remove('focus:bg-white', 'cursor-pointer');
    }
}

function desbloquearCeldaCodigo(inputCodigo) {
    if (inputCodigo.readOnly) {
        inputCodigo.readOnly = false;
        inputCodigo.classList.remove('bg-slate-100', 'cursor-default', 'select-none');
        inputCodigo.classList.add('focus:bg-white');
        inputCodigo.focus();
        inputCodigo.select();
    }
}

document.addEventListener('mouseup', () => {
    isArrastrando = false;
});

function iniciarArrastre(input) {
    isArrastrando = true;
    celdaInicio = input;
    actualizarSeleccionRango(input);
}

function arrastrarSobreCelda(input) {
    if (isArrastrando && celdaInicio) {
        window.getSelection()?.removeAllRanges();
        actualizarSeleccionRango(input);
    }
}

function actualizarSeleccionRango(celdaActual) {
    desseleccionarCeldas();
    window.getSelection()?.removeAllRanges();

    const tbody = document.getElementById('filas-tabla-analisis');
    const filas = Array.from(tbody.children);

    const trInicio = celdaInicio.closest('tr');
    const trFin = celdaActual.closest('tr');

    const rowIndexInicio = filas.indexOf(trInicio);
    const rowIndexFin = filas.indexOf(trFin);

    const rMin = Math.min(rowIndexInicio, rowIndexFin);
    const rMax = Math.max(rowIndexInicio, rowIndexFin);

    const tdInicio = celdaInicio.closest('td');
    const tdFin = celdaActual.closest('td');

    const colIndexInicio = Array.from(trInicio.children).indexOf(tdInicio);
    const colIndexFin = Array.from(trFin.children).indexOf(tdFin);

    const cMin = Math.min(colIndexInicio, colIndexFin);
    const cMax = Math.max(colIndexInicio, colIndexFin);

    for (let r = rMin; r <= rMax; r++) {
        const tr = filas[r];
        for (let c = cMin; c <= cMax; c++) {
            const td = tr.children[c];
            const input = td?.querySelector('input');
            if (input) {
                celdasSeleccionadasAnalisis.push(input);
                td.classList.add('bg-blue-100/70');
                if (r === rMin) td.classList.add('border-t-2', 'border-t-blue-600');
                if (r === rMax) td.classList.add('border-b-2', 'border-b-blue-600');
                if (c === cMin) td.classList.add('border-l-2', 'border-l-blue-600');
                if (c === cMax) td.classList.add('border-r-2', 'border-r-blue-600');
            }
        }
    }
}

function desseleccionarCeldas() {
    celdasSeleccionadasAnalisis.forEach(input => {
        const td = input.closest('td');
        if (td) {
            td.classList.remove(
                'bg-blue-100/70',
                'border-t-2', 'border-t-blue-600',
                'border-b-2', 'border-b-blue-600',
                'border-l-2', 'border-l-blue-600',
                'border-r-2', 'border-r-blue-600'
            );
        }
    });
    celdasSeleccionadasAnalisis = [];
}

document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        if (document.activeElement && document.activeElement.tagName === 'INPUT') {
            document.activeElement.blur();
        }
        desseleccionarCeldas();
        return;
    }

    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c' && celdasSeleccionadasAnalisis.length > 0) {
        e.preventDefault();
        const matrizValores = {};

        celdasSeleccionadasAnalisis.forEach(input => {
            const tr = input.closest('tr');
            const tbody = tr.parentElement;
            const rowIndex = Array.from(tbody.children).indexOf(tr);
            const colIndex = Array.from(tr.children).indexOf(input.closest('td'));

            if (!matrizValores[rowIndex]) matrizValores[rowIndex] = {};
            matrizValores[rowIndex][colIndex] = input.value || '';
        });

        const textoCopiar = Object.keys(matrizValores)
            .sort((a, b) => a - b)
            .map(r => {
                return Object.keys(matrizValores[r])
                    .sort((a, b) => a - b)
                    .map(c => matrizValores[r][c])
                    .join('\t');
            })
            .join('\n');

        navigator.clipboard.writeText(textoCopiar);
        return;
    }

    if ((e.key === 'Delete' || e.key === 'Del') && celdasSeleccionadasAnalisis.length > 0) {
        e.preventDefault();

        celdasSeleccionadasAnalisis.forEach(input => {
            const tr = input.closest('tr');

            if (input.classList.contains('inp-codigo')) {
                input.readOnly = false;
                input.value = '';
                input.classList.remove('bg-slate-100', 'cursor-default', 'select-none');
                input.classList.add('focus:bg-white');

                const inpDesc = tr.querySelector('.inp-desc');
                if (inpDesc) inpDesc.value = '';
            } else if (input.classList.contains('inp-inv-emp')) {
                input.value = '0';
                if (typeof recancularFilaConInventario === 'function') recancularFilaConInventario(input);
            } else if (input.classList.contains('inp-emp') || input.classList.contains('inp-uni')) {
                input.value = '0';
                calcularFila(input);
            } else if (input.classList.contains('inp-costo')) {
                input.value = '0.00';
                calcularFila(input);
            } else if (input.classList.contains('inp-pre')) {
                input.value = '1';
                if (typeof recancularFilaConInventario === 'function') recancularFilaConInventario(input);
            }
        });

        desseleccionarCeldas();
        totalizarAnalisis();
    }
});

document.addEventListener('click', function (e) {
    if (!e.target.closest('#tabla-analisis')) {
        desseleccionarCeldas();
    }
});

function asegurarEstructuraTienda(tienda) {
    if (!matrizTiendas[tienda]) {
        matrizTiendas[tienda] = {};
    }
}

function agregarFilaAnalisis() {
    const tbody = document.getElementById('filas-tabla-analisis');
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-blue-50/40 transition text-xs';

    tr.innerHTML = `
        <td class="border border-slate-200 p-0 celda-interactiva relative">
            <input type="text" autocomplete="off" spellcheck="false" class="inp-codigo w-full px-2 py-1.5 border-0 text-xs font-normal uppercase focus:bg-white focus:outline-none bg-transparent"
                onmousedown="iniciarArrastre(this)" onmouseenter="arrastrarSobreCelda(this)"
                ondblclick="desbloquearCeldaCodigo(this)"
                onkeydown="manejarKeyNav(event, this, 'codigo')" onchange="consultarProductoCodigo(this)" onpaste="manejarPegadoCodigo(event, this)">
        </td>
        <td class="border border-slate-200 p-0 celda-interactiva relative">
            <input type="text" readonly tabindex="-1" class="inp-desc w-full px-2 py-1.5 bg-slate-50 text-xs font-normal text-slate-600 focus:outline-none cursor-default border-0"
                onmousedown="iniciarArrastre(this)" onmouseenter="arrastrarSobreCelda(this)">
        </td>
        <td class="border border-slate-200 p-0 celda-interactiva relative">
            <input type="number" step="1" min="1" value="1" class="inp-pre text-center w-full px-2 py-1.5 border-0 text-xs font-normal focus:bg-white focus:outline-none bg-transparent"
                onmousedown="iniciarArrastre(this)" onmouseenter="arrastrarSobreCelda(this)"
                onkeydown="manejarKeyNav(event, this, 'pre')" oninput="if(this.value < 1 && this.value !== '') this.value = 1; if(typeof recancularFilaConInventario === 'function') recancularFilaConInventario(this)" onpaste="manejarPegadoColumna(event, this, 'pre')">
        </td>
        <td class="border border-slate-200 p-0 celda-interactiva relative bg-amber-50/30">
            <input type="number" step="1" min="0" value="0" class="inp-inv-emp text-center w-full px-2 py-1.5 border-0 text-xs font-semibold text-amber-800 focus:bg-white focus:outline-none bg-transparent"
                onmousedown="iniciarArrastre(this)" onmouseenter="arrastrarSobreCelda(this)"
                onkeydown="manejarKeyNav(event, this, 'inv-emp')" oninput="if(this.value < 0) this.value = 0; if(typeof recancularFilaConInventario === 'function') recancularFilaConInventario(this)" onpaste="manejarPegadoColumna(event, this, 'inv-emp')">
        </td>
        <td class="border border-slate-200 p-0 celda-interactiva relative">
            <input type="number" step="1" min="0" value="0" class="inp-emp text-center w-full px-2 py-1.5 border-0 text-xs font-normal focus:bg-white focus:outline-none bg-transparent"
                onmousedown="iniciarArrastre(this)" onmouseenter="arrastrarSobreCelda(this)"
                onkeydown="manejarKeyNav(event, this, 'emp')" oninput="if(this.value < 0) this.value = 0; calcularFila(this)" onpaste="manejarPegadoColumna(event, this, 'emp')">
        </td>
        <td class="border border-slate-200 p-0 celda-interactiva relative">
            <input type="number" step="1" min="0" value="0" class="inp-uni text-center w-full px-2 py-1.5 border-0 text-xs font-normal focus:bg-white focus:outline-none bg-transparent"
                onmousedown="iniciarArrastre(this)" onmouseenter="arrastrarSobreCelda(this)"
                onkeydown="manejarKeyNav(event, this, 'uni')" oninput="if(this.value < 0) this.value = 0; ajustarPorUnidades(this)" onpaste="manejarPegadoColumna(event, this, 'uni')">
        </td>
        <td class="border border-slate-200 p-0 celda-interactiva relative">
            <input type="number" step="0.01" min="0" value="0.00" class="inp-costo text-right w-full px-2 py-1.5 border-0 text-xs font-normal focus:bg-white focus:outline-none bg-transparent"
                onmousedown="iniciarArrastre(this)" onmouseenter="arrastrarSobreCelda(this)"
                onkeydown="manejarKeyNav(event, this, 'costo')" oninput="if(this.value < 0) this.value = 0; calcularFila(this)" onpaste="manejarPegadoColumna(event, this, 'costo')">
        </td>
        <td class="border border-slate-200 px-2 py-1.5 text-right font-normal text-slate-700 bg-slate-50/50">
            <span class="txt-subtotal">$ 0,00</span>
        </td>
        <td class="border border-slate-200 p-0 text-center bg-slate-50/50">
            <button type="button" onclick="eliminarFila(this)" class="w-full h-full text-slate-400 hover:text-rose-600 transition py-1.5">
                <i class="fa-solid fa-trash-can text-xs"></i>
            </button>
        </td>
    `;

    tbody.appendChild(tr);
    return tr;
}

async function manejarPegadoCodigo(e, inputActual) {
    const clipboardData = e.clipboardData || window.clipboardData;
    const pastedData = clipboardData.getData('Text');
    const lineas = pastedData.split(/\r\n|\n|\r/).map(l => l.trim()).filter(l => l.length > 0);

    if (lineas.length <= 1) return;
    e.preventDefault();

    let trActual = inputActual.closest('tr');
    for (const codigo of lineas) {
        if (!trActual) trActual = agregarFilaAnalisis();
        const inpCodigo = trActual.querySelector('.inp-codigo');
        if (inpCodigo) {
            inpCodigo.value = codigo;
            await consultarProductoCodigo(inpCodigo);
        }
        trActual = trActual.nextElementSibling;
    }
}

function manejarPegadoColumna(e, inputActual, tipo) {
    const clipboardData = e.clipboardData || window.clipboardData;
    const pastedData = clipboardData.getData('Text');
    const lineas = pastedData.split(/\r\n|\n|\r/).map(l => l.trim()).filter(l => l.length > 0);

    if (lineas.length <= 1) return;
    e.preventDefault();

    let trActual = inputActual.closest('tr');
    lineas.forEach(valor => {
        if (!trActual) trActual = agregarFilaAnalisis();
        const inputDestino = trActual.querySelector(`.inp-${tipo}`);
        if (inputDestino) {
            const valorLimpio = valor.replace(',', '.');
            inputDestino.value = isNaN(parseFloat(valorLimpio)) ? 0 : valorLimpio;

            if (tipo === 'uni') ajustarPorUnidades(inputDestino);
            else if (tipo === 'inv-emp' && typeof recancularFilaConInventario === 'function') recancularFilaConInventario(inputDestino);
            else calcularFila(inputDestino);
        }
        trActual = trActual.nextElementSibling;
    });
}

async function consultarProductoCodigo(inputCodigo) {
    let codigo = inputCodigo.value.trim();
    const tr = inputCodigo.closest('tr');
    const inpDesc = tr.querySelector('.inp-desc');
    const inpPre = tr.querySelector('.inp-pre');
    const inpCosto = tr.querySelector('.inp-costo');

    if (!codigo) {
        inpDesc.value = '';
        inpCosto.value = '0.00';
        inpPre.value = '1';
        delete inpCosto.dataset.original;
        delete inpPre.dataset.original;
        calcularFila(inputCodigo);
        return;
    }

    if (/^\d+$/.test(codigo)) {
        codigo = codigo.padStart(6, '0');
        inputCodigo.value = codigo;
    }

    try {
        const res = await fetch(`/api/productos/buscar-codigo/${encodeURIComponent(codigo)}`);
        const data = await res.json();

        if (data && data.descripcion) {
            inpDesc.value = data.descripcion;
            inpCosto.value = Number(data.precio || 0).toFixed(2);
            const numManejo = parseInt(data.unidad_manejo);
            if (!isNaN(numManejo) && numManejo > 0) inpPre.value = numManejo;

            inpPre.dataset.original = inpPre.value;
            inpCosto.dataset.original = inpCosto.value;
            bloquearCeldaCodigo(inputCodigo);
        } else {
            inpDesc.value = 'PRODUCTO NO ENCONTRADO';
            inpCosto.value = '0.00';
            inpPre.value = '1';
        }
    } catch (e) {
        inpDesc.value = 'ERROR DE CONEXIÓN';
        inpCosto.value = '0.00';
        inpPre.value = '1';
    }

    calcularFila(inputCodigo);
}

function calcularFila(elem) {
    const tr = elem.closest('tr');
    const pre = parseFloat(tr.querySelector('.inp-pre').value) || 1;
    const emp = parseFloat(tr.querySelector('.inp-emp').value) || 0;
    const costo = parseFloat(tr.querySelector('.inp-costo').value) || 0;

    const uniInput = tr.querySelector('.inp-uni');
    const totalUni = pre * emp;
    uniInput.value = totalUni;

    const subtotal = totalUni * costo;
    tr.querySelector('.txt-subtotal').textContent = `$ ${subtotal.toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    totalizarAnalisis();
}

function ajustarPorUnidades(elem) {
    const tr = elem.closest('tr');
    const pre = parseFloat(tr.querySelector('.inp-pre').value) || 1;
    const uni = parseFloat(tr.querySelector('.inp-uni').value) || 0;
    const costo = parseFloat(tr.querySelector('.inp-costo').value) || 0;

    const empInput = tr.querySelector('.inp-emp');
    empInput.value = pre > 0 ? (uni / pre) : 0;

    const subtotal = uni * costo;
    tr.querySelector('.txt-subtotal').textContent = `$ ${subtotal.toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    totalizarAnalisis();
}

function totalizarAnalisis() {
    let totEmp = 0;
    let totUni = 0;
    let totMonto = 0;

    document.querySelectorAll('#filas-tabla-analisis tr').forEach(tr => {
        const emp = parseFloat(tr.querySelector('.inp-emp')?.value) || 0;
        const uni = parseFloat(tr.querySelector('.inp-uni')?.value) || 0;
        const costo = parseFloat(tr.querySelector('.inp-costo')?.value) || 0;

        totEmp += emp;
        totUni += uni;
        totMonto += (uni * costo);
    });

    document.getElementById('tot-empaques').textContent = totEmp.toLocaleString('es-VE');
    document.getElementById('tot-unidades').textContent = totUni.toLocaleString('es-VE');
    document.getElementById('tot-monto').textContent = `$ ${totMonto.toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function eliminarFila(btn) {
    const tbody = document.getElementById('filas-tabla-analisis');
    const tr = btn.closest('tr');
    const codigoABorrar = tr.querySelector('.inp-codigo')?.value?.trim();

    if (codigoABorrar && typeof matrizTiendas !== 'undefined') {
        for (const sede in matrizTiendas) {
            delete matrizTiendas[sede][codigoABorrar];
        }
    }

    if (tbody.children.length > 1) {
        tr.remove();
        totalizarAnalisis();
    } else {
        tr.querySelectorAll('input').forEach(i => {
            if (i.classList.contains('inp-pre')) i.value = '1';
            else if (i.classList.contains('inp-costo')) i.value = '0.00';
            else i.value = '';
        });
        const subtotalEl = tr.querySelector('.txt-subtotal');
        if (subtotalEl) subtotalEl.textContent = '$ 0,00';
        totalizarAnalisis();
    }
}

function enfocarYSombrearCelda(input) {
    if (!input) return;

    if (input.readOnly) {
        input.focus();
        return;
    }

    input.focus();
    setTimeout(() => {
        input.select();
    }, 0);

    celdaInicio = input;
    actualizarSeleccionRango(input);
}

function manejarKeyNav(e, elem, campoActual) {
    if (e.key === 'F2' && campoActual === 'codigo') {
        e.preventDefault();
        if (typeof abrirModalBuscadorProductos === 'function') abrirModalBuscadorProductos(elem);
        return;
    }
    const tr = elem.closest('tr');
    const tbody = tr.parentElement;
    const filas = Array.from(tbody.children);
    const colIndices = ['codigo', 'pre', 'inv-emp', 'emp', 'uni', 'costo'];

    if ((/^[0-9]$/.test(e.key) || /^Numpad[0-9]$/.test(e.code)) && !e.ctrlKey && !e.altKey && !e.metaKey) {
        const textoSeleccionado = window.getSelection().toString();
        const esSeleccionCompleta = (elem.selectionStart === 0 && elem.selectionEnd === elem.value.length);

        if (esSeleccionCompleta || textoSeleccionado !== '') {
            elem.value = '';
        }
    }

    if (e.key === 'Tab') {
        e.preventDefault();

        let rIdx = filas.indexOf(tr);
        let cIdx = colIndices.indexOf(campoActual);

        if (e.shiftKey) {
            cIdx--;
            if (cIdx < 0) {
                cIdx = colIndices.length - 1;
                rIdx--;
            }
        } else {
            cIdx++;
            if (cIdx >= colIndices.length) {
                cIdx = 0;
                rIdx++;
            }
        }

        if (rIdx >= filas.length) agregarFilaAnalisis();
        rIdx = Math.max(0, rIdx);

        const trDestino = tbody.children[rIdx];
        const campoDestino = colIndices[cIdx];
        const inputDestino = trDestino?.querySelector(`.inp-${campoDestino}`);

        if (inputDestino) {
            if (inputDestino.readOnly) manejarKeyNav(e, inputDestino, campoDestino);
            else enfocarYSombrearCelda(inputDestino);
        }
        return;
    }

    if (e.key === 'Escape') {
        e.preventDefault();
        if (elem.dataset.valorOriginal !== undefined) {
            elem.value = elem.dataset.valorOriginal;
            if (campoActual === 'uni') ajustarPorUnidades(elem);
            else if (['pre', 'emp', 'costo'].includes(campoActual)) calcularFila(elem);
        }
        elem.blur();
        desseleccionarCeldas();
        e.stopPropagation();
        return;
    }

    if (e.key === 'Enter') {
        e.preventDefault();
        elem.blur();

        let siguienteInput = null;

        if (campoActual === 'codigo') {
            consultarProductoCodigo(elem).then(() => {
                siguienteInput = tr.querySelector('.inp-emp');
                enfocarYSombrearCelda(siguienteInput);
            });
            return;
        } else if (campoActual === 'pre') {
            siguienteInput = tr.querySelector('.inp-emp');
        } else if (campoActual === 'inv-emp') {
            let sigTr = tr.nextElementSibling || agregarFilaAnalisis();
            siguienteInput = sigTr.querySelector('.inp-inv-emp');
        } else if (campoActual === 'emp') {
            let sigTr = tr.nextElementSibling || agregarFilaAnalisis();
            siguienteInput = sigTr.querySelector('.inp-emp');
        } else if (campoActual === 'uni') {
            siguienteInput = tr.querySelector('.inp-costo');
        } else if (campoActual === 'costo') {
            let sigTr = tr.nextElementSibling || agregarFilaAnalisis();
            siguienteInput = sigTr.querySelector('.inp-codigo');
        }

        if (siguienteInput) enfocarYSombrearCelda(siguienteInput);
        return;
    }

    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault();

        if (!e.shiftKey && elem.selectionStart !== elem.selectionEnd && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
            return;
        }

        let rIdx = filas.indexOf(tr);
        let cIdx = colIndices.indexOf(campoActual);

        if (e.key === 'ArrowUp') rIdx = Math.max(0, rIdx - 1);
        if (e.key === 'ArrowDown') {
            rIdx++;
            if (rIdx >= filas.length) {
                agregarFilaAnalisis();
                rIdx = tbody.children.length - 1;
            }
        }
        if (e.key === 'ArrowLeft') cIdx = Math.max(0, cIdx - 1);
        if (e.key === 'ArrowRight') cIdx = Math.min(colIndices.length - 1, cIdx + 1);

        const trDestino = tbody.children[rIdx];
        const campoDestino = colIndices[cIdx];
        const inputDestino = trDestino?.querySelector(`.inp-${campoDestino}`);

        if (inputDestino) {
            if (e.shiftKey) {
                if (!celdaInicio) celdaInicio = elem;
                inputDestino.focus();
                actualizarSeleccionRango(inputDestino);
            } else {
                enfocarYSombrearCelda(inputDestino);
            }
        }
    }
}

document.addEventListener('click', (e) => {
    if (!e.target.closest('#combo-proveedor-analisis')) document.getElementById('opciones_proveedor_analisis')?.classList.add('hidden');
    if (!e.target.closest('#combo-tienda-analisis')) document.getElementById('opciones_tienda_analisis')?.classList.add('hidden');
    if (!e.target.closest('#combo-depto-analisis')) document.getElementById('opciones_depto_analisis')?.classList.add('hidden');
    if (!e.target.closest('#combo-grupo-analisis')) document.getElementById('opciones_grupo_analisis')?.classList.add('hidden');
    if (!e.target.closest('#combo-subgrupo-analisis')) document.getElementById('opciones_subgrupo_analisis')?.classList.add('hidden');
    if (!e.target.closest('#combo-marca-analisis')) document.getElementById('opciones_marca_analisis')?.classList.add('hidden');
});

function ordenarTablaAnalisis(colIndex, tipo) {
    const tbody = document.getElementById('filas-tabla-analisis');
    const filas = Array.from(tbody.querySelectorAll('tr'));

    if (colOrdenActual === colIndex) ascOrdenActual = !ascOrdenActual;
    else {
        colOrdenActual = colIndex;
        ascOrdenActual = true;
    }

    document.querySelectorAll('#tabla-analisis thead .th-icon').forEach((icon, idx) => {
        icon.className = 'fa-solid fa-sort text-[10px] opacity-40 th-icon';
        if (idx === colIndex) {
            icon.className = `fa-solid ${ascOrdenActual ? 'fa-sort-up' : 'fa-sort-down'} text-[10px] text-blue-400 opacity-100 th-icon`;
        }
    });

    const obtenerValor = (tr) => {
        const celda = tr.children[colIndex];
        if (!celda) return '';

        const input = celda.querySelector('input');
        if (input) return input.value.trim();

        const spanSubtotal = celda.querySelector('.txt-subtotal');
        if (spanSubtotal) {
            const numStr = spanSubtotal.textContent.replace('$', '').replace(/\./g, '').replace(',', '.').trim();
            return parseFloat(numStr) || 0;
        }

        return celda.textContent.trim();
    };

    filas.sort((a, b) => {
        let valA = obtenerValor(a);
        let valB = obtenerValor(b);

        if (tipo === 'numero' || tipo === 'subtotal') {
            valA = parseFloat(valA) || 0;
            valB = parseFloat(valB) || 0;
            return ascOrdenActual ? valA - valB : valB - valA;
        }

        return ascOrdenActual
            ? String(valA).localeCompare(String(valB))
            : String(valB).localeCompare(String(valA));
    });

    filas.forEach(f => tbody.appendChild(f));
}