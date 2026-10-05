import io  # Manejo de IO en memoria
import re  # Expresiones regulares
import urllib.parse  # Formateo de URL
import asyncio  # Manejo de concurrencia y reintentos asíncronos
from typing import List, Optional  # Tipado
import xml.etree.ElementTree as ET  # Parseador XML
import pandas as pd  # Lectura de archivos Excel y CSV
from fastapi import APIRouter, Request, Form, UploadFile, File, Cookie  # FastAPI
from fastapi.responses import RedirectResponse, JSONResponse  # Respuestas HTTP
import config
from config import templates, obtener_usuario_actual, script_alerta_modal  # Dependencias globales
from models import CodigosProductosRequest  # Modelo para búsquedas masivas

router = APIRouter()

# Función auxiliar para ejecutar operaciones con reintentos exponenciales asíncronos
async def ejecutar_supabase_con_reintento_async(func, max_reintentos: int = 3, espera_inicial: float = 0.5):
    ultimo_error = None
    for intento in range(max_reintentos):
        try:
            return await func()
        except Exception as e:
            ultimo_error = e
            if intento < max_reintentos - 1:
                tiempo_espera = espera_inicial * (2 ** intento)  # Backoff exponencial
                await asyncio.sleep(tiempo_espera)  # Liberación asíncrona del hilo del servidor
            else:
                raise ultimo_error


@router.get("/productos")
async def vista_productos(
    request: Request, 
    query: Optional[str] = None,
    departamento: Optional[str] = None,
    grupo: Optional[str] = None,
    proveedor_id: Optional[int] = None,
    select: Optional[str] = None,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    busqueda_query = request.query_params.get("q", "")
    tags_query = request.query_params.get("tags", "")
    
    builder = config.supabase_async.table("productos").select("*, proveedores(nombre)")

    terminos = []
    if busqueda_query.strip():
        terminos.append(busqueda_query.strip())
    if tags_query.strip():
        terminos.extend([t.strip() for t in tags_query.split(",") if t.strip()])

    term_limpio = None
    for term in terminos:
        term_limpio = re.sub(r'[^\w\s-]', '', term).strip()
        if not term_limpio:
            continue
            
        palabras = term_limpio.split()
        patron_busqueda = f"%{'%'.join(palabras)}%" if palabras else "%"

        # Consulta asíncrona de proveedores con reintentos sin bloqueo
        query_prov = config.supabase_async.table("proveedores").select("id").ilike("nombre", patron_busqueda)
        res_prov = await ejecutar_supabase_con_reintento_async(lambda: query_prov.execute())
        ids_prov = [str(p["id"]) for p in res_prov.data] if res_prov.data else []

        condiciones = [
            f"codigo_st.ilike.{patron_busqueda}",
            f"codigo_ean.ilike.{patron_busqueda}",
            f"descripcion.ilike.{patron_busqueda}",
            f"marca.ilike.{patron_busqueda}",
            f"departamento.ilike.{patron_busqueda}",
            f"grupo.ilike.{patron_busqueda}"
        ]

        if term_limpio.isdigit():
            val_num = int(term_limpio)
            condiciones.append(f"proveedor_id.eq.{val_num}")

        if ids_prov:
            for pid in ids_prov:
                condiciones.append(f"proveedor_id.eq.{pid}")

        condicion_or = ",".join(condiciones)
        builder = builder.or_(condicion_or)

    page = int(request.query_params.get("page", 1))
    limit = 50
    offset = (page - 1) * limit

    # Consulta paginada asíncrona
    productos_res = await ejecutar_supabase_con_reintento_async(
        lambda: builder.order("descripcion", desc=False).range(offset, offset + limit - 1).execute()
    )
    productos = productos_res.data or []

    res_prov = await config.supabase_async.table("proveedores").select("id, nombre").order("nombre").execute()
    proveedores = res_prov.data if res_prov and res_prov.data else []

    select_id = request.query_params.get("select")
    prov_obj = None

    if select_id:
        try:
            query_id = int(select_id) if str(select_id).isdigit() else select_id
            res_sel = await config.supabase_async.table("productos").select("*").eq("id", query_id).execute()
            if res_sel.data:
                prov_obj = res_sel.data[0]
        except Exception as e:
            print("Error al obtener producto seleccionado:", e)

    if term_limpio and term_limpio.isdigit() and productos:
        def evaluar_prioridad(prod):
            cod_st = str(prod.get("codigo_st", "") or "")
            if cod_st == term_limpio:
                return 0
            elif cod_st.startswith(term_limpio):
                return 1
            elif term_limpio in cod_st:
                return 2
            return 3

        productos.sort(key=evaluar_prioridad)

    return templates.TemplateResponse(
        request=request,
        name="productos.html",
        context={
            "productos": productos,
            "prov_obj": prov_obj,
            "proveedores": proveedores
        }
    )


@router.post("/productos/guardar")
async def guardar_producto(
    id: Optional[str] = Form(None),
    codigo_st: str = Form(...),
    codigo_ean: Optional[str] = Form(None),
    unidad_manejo: str = Form(...),
    descripcion: str = Form(...),
    precio: float = Form(0.0),
    departamento: str = Form(...),
    grupo: str = Form(...),
    subgrupo: str = Form(...),
    proveedor_id: Optional[str] = Form(None),
    marca: str = Form(""),
    q: str = Form(""), 
    tags: str = Form(""),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    codigo_st_fmt = codigo_st.strip().zfill(6) if codigo_st.strip().isdigit() else codigo_st.strip()
    payload = {
        "codigo_st": codigo_st_fmt,
        "codigo_ean": codigo_ean or None,
        "unidad_manejo": unidad_manejo,
        "descripcion": descripcion,
        "precio": precio,
        "departamento": departamento,
        "grupo": grupo,
        "subgrupo": subgrupo,
        "proveedor_id": int(proveedor_id) if proveedor_id and proveedor_id.isdigit() else None,
        "marca": marca.strip(),
    }

    if id:
        await config.supabase_async.table("productos").update(payload).eq("id", id).execute()
        prod_id = id
    else:
        res = await config.supabase_async.table("productos").insert(payload).execute()
        prod_id = res.data[0]["id"] if res and res.data else ""

    redirect_url = f"/productos?select={prod_id}"
    if q.strip():
        redirect_url += f"&q={urllib.parse.quote(q.strip())}"
    if tags.strip():
        redirect_url += f"&tags={urllib.parse.quote(tags.strip())}"

    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/productos/eliminar/{producto_id}")
async def eliminar_producto(
    producto_id: str, 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    await config.supabase_async.table("productos").delete().eq("id", producto_id).execute()

    return RedirectResponse(url="/productos", status_code=303)


def validar_columnas_producto(columnas):
    requeridas = {
        "CodigoDelProducto",
        "CodigoEAN",
        "Descripcion",
        "UnidadManejo",
        "CostoActual",
        "Departamento",
        "Grupo",
        "SubGrupo",
        "Proveedor",
        "Marca"
    }

    disponibles = {
        str(col).replace("\ufeff", "").strip()
        for col in columnas
    }

    faltantes = sorted(requeridas - disponibles)

    if faltantes:
        return (
            False,
            "Faltan columnas requeridas: "
            + ", ".join(faltantes)
        )

    return True, ""

def texto_valor(valor):
    """Convierte un valor del archivo en texto limpio."""
    if valor is None or pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto.lower() == "nan":
        return ""

    return texto


def convertir_codigo(valor):
    """Normaliza CodigoDelProducto a 6 dígitos cuando es numérico."""
    texto = texto_valor(valor)

    if not texto:
        return ""

    # Excel puede entregar códigos numéricos como 123456.0
    if re.fullmatch(r"\d+\.0", texto):
        texto = texto[:-2]

    return texto.zfill(6) if texto.isdigit() else texto


def convertir_unidad_manejo(valor):
    """Convierte UnidadManejo en entero positivo."""
    texto = texto_valor(valor)

    if not texto:
        return None

    try:
        numero = float(texto.replace(",", "."))

        if not numero.is_integer() or numero <= 0:
            return None

        return int(numero)

    except (ValueError, TypeError):
        return None


def convertir_precio(valor):
    """Convierte CostoActual soportando formatos 12.50, 12,50 y 1.234,56."""
    texto = texto_valor(valor)

    if not texto:
        return 0.0

    try:
        # Si viene con punto y coma, asumimos formato 1.234,56
        if "." in texto and "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

        # Si solo tiene coma, asumimos decimal 12,50
        elif "," in texto:
            texto = texto.replace(",", ".")

        # Si solo tiene punto, se conserva como decimal: 12.50

        return float(texto)

    except (ValueError, TypeError):
        return 0.0

@router.post("/productos/cargar-lista")
async def cargar_lista_productos(
    archivo: UploadFile = File(...),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    contenido = await archivo.read()
    nombre = archivo.filename.lower()
    filas = []

    # 1. Extracción de datos según extensión
    if nombre.endswith(".csv"):
        try:
            df = pd.read_csv(
                io.BytesIO(contenido),
                sep=None,
                engine="python",
                encoding="utf-8"
            )
        except Exception:
            df = pd.read_csv(
                io.BytesIO(contenido),
                sep=None,
                engine="python",
                encoding="latin1"
            )

        # Normalizar encabezados SIEMPRE, independientemente
        # de la codificación utilizada.
        df.columns = [
            str(col).replace("\ufeff", "").strip()
            for col in df.columns
        ]

        columnas_validas, mensaje_columnas = validar_columnas_producto(
            df.columns
        )

        if not columnas_validas:
            return script_alerta_modal(
                "error",
                "Formato de archivo incorrecto",
                mensaje_columnas,
                "/productos"
            )

        for _, r in df.iterrows():
            filas.append({
                "codigo": r.get("CodigoDelProducto", ""),
                "codigo_ean": r.get("CodigoEAN", ""),
                "descripcion": r.get("Descripcion", ""),
                "unidad_manejo": r.get("UnidadManejo", ""),
                "marca": r.get("Marca", ""),
                "departamento": r.get("Departamento", ""),
                "grupo": r.get("Grupo", ""),
                "subgrupo": r.get("SubGrupo", ""),
                "costo": r.get("CostoActual", 0),
                "proveedor": r.get("Proveedor", "")
            })


    elif nombre.endswith(".xlsx"):
        df = pd.read_excel(io.BytesIO(contenido))

        # Normalizar encabezados.
        df.columns = [
            str(col).replace("\ufeff", "").strip()
            for col in df.columns
        ]

        columnas_validas, mensaje_columnas = validar_columnas_producto(
            df.columns
        )

        if not columnas_validas:
            return script_alerta_modal(
                "error",
                "Formato de archivo incorrecto",
                mensaje_columnas,
                "/productos"
            )

        for _, r in df.iterrows():
            filas.append({
                "codigo": r.get("CodigoDelProducto", ""),
                "codigo_ean": r.get("CodigoEAN", ""),
                "descripcion": r.get("Descripcion", ""),
                "unidad_manejo": r.get("UnidadManejo", ""),
                "marca": r.get("Marca", ""),
                "departamento": r.get("Departamento", ""),
                "grupo": r.get("Grupo", ""),
                "subgrupo": r.get("SubGrupo", ""),
                "costo": r.get("CostoActual", 0),
                "proveedor": r.get("Proveedor", "")
            })


    elif nombre.endswith(".xml"):
        root = ET.fromstring(contenido)

        for item in (root.findall(".//Producto") or root):
            filas.append({
                "codigo": item.findtext("CodigoDelProducto", ""),
                "codigo_ean": item.findtext("CodigoEAN", ""),
                "descripcion": item.findtext("Descripcion", ""),
                "unidad_manejo": item.findtext("UnidadManejo", ""),
                "marca": item.findtext("Marca", ""),
                "departamento": item.findtext("Departamento", ""),
                "grupo": item.findtext("Grupo", ""),
                "subgrupo": item.findtext("SubGrupo", ""),
                "costo": item.findtext("CostoActual", "0"),
                "proveedor": item.findtext("Proveedor", "")
            })


    else:
        return script_alerta_modal(
            "error",
            "Formato no compatible",
            "El archivo debe ser CSV, XLSX o XML.",
            "/productos"
        )

    # 2. Mapeo asíncrono de proveedores
    res_prov = await config.supabase_async.table("proveedores").select("id, nombre").execute()
    mapa_proveedores = {p["nombre"].strip().upper(): p["id"] for p in (res_prov.data or []) if p.get("nombre")}

    # 3. Formateo y limpieza de datos
    filas_procesadas = []
    errores_filas = []

    for numero_fila, f in enumerate(filas, start=2):

        codigo_st = convertir_codigo(f["codigo"])

        if not codigo_st:
            errores_filas.append(
                f"Fila {numero_fila}: CodigoDelProducto vacío."
            )
            continue

        unidad_manejo = convertir_unidad_manejo(
            f["unidad_manejo"]
        )

        if unidad_manejo is None:
            errores_filas.append(
                f"Fila {numero_fila}: UnidadManejo inválida "
                f"para el producto {codigo_st}."
            )
            continue

        nombre_prov = texto_valor(
            f["proveedor"]
        ).upper()

        prov_id = mapa_proveedores.get(nombre_prov)

        filas_procesadas.append({
            "codigo_st": codigo_st,
            "codigo_ean": texto_valor(f["codigo_ean"]),
            "descripcion": texto_valor(
                f["descripcion"]
            ).upper(),
            "unidad_manejo": unidad_manejo,
            "marca": texto_valor(
                f["marca"]
            ).upper(),
            "departamento": texto_valor(
                f["departamento"]
            ),
            "grupo": texto_valor(
                f["grupo"]
            ),
            "subgrupo": texto_valor(
                f["subgrupo"]
            ),
            "costo_raw": f["costo"],
            "proveedor_id": prov_id
        })


    if not filas_procesadas:
        mensaje = (
            "No se encontraron productos válidos para importar."
        )

        if errores_filas:
            mensaje += "\n\n" + "\n".join(errores_filas[:10])

        return script_alerta_modal(
            "error",
            "No se pudo procesar el archivo",
            mensaje,
            "/productos"
        )

    

    # ============================================================
    # 4. PREPARAR DATOS PARA IMPORTACIÓN MASIVA
    # ============================================================

    productos_importacion = []

    for item in filas_procesadas:

        precio_nuevo = convertir_precio(
            item["costo_raw"]
        )

        productos_importacion.append({
            "codigo_st": item["codigo_st"],
            "codigo_ean": item["codigo_ean"],
            "descripcion": item["descripcion"],
            "unidad_manejo": item["unidad_manejo"],
            "marca": item["marca"],
            "departamento": item["departamento"],
            "grupo": item["grupo"],
            "subgrupo": item["subgrupo"],
            "proveedor_id": item["proveedor_id"],
            "precio_nuevo": precio_nuevo
        })


    # ============================================================
    # 5. UNA SOLA OPERACIÓN EN SUPABASE
    # ============================================================

    if productos_importacion:

        try:
            res_importacion = await (
                ejecutar_supabase_con_reintento_async(
                    lambda: config.supabase_async.rpc(
                        "importar_productos_masivo",
                        {
                            "p_productos": productos_importacion
                        }
                    ).execute()
                )
            )

            resultado = res_importacion.data or {}

            total_nuevos = int(
                resultado.get("creados", 0)
            )

            total_actualizados = int(
                resultado.get("actualizados", 0)
            )

            total_sin_cambios = int(
                resultado.get("sin_cambios", 0)
            )

        except Exception as e:
            print(
                "ERROR EN IMPORTACIÓN MASIVA DE PRODUCTOS:",
                repr(e)
            )

            return script_alerta_modal(
                "error",
                "Error al cargar productos",
                "No fue posible completar la importación. "
                "Revise el formato del archivo y vuelva a intentarlo.",
                "/productos"
            )

    else:
        total_nuevos = 0
        total_actualizados = 0
        total_sin_cambios = 0


    # ============================================================
    # 6. MENSAJE DE CONFIRMACIÓN
    # ============================================================

    from config import script_alerta_modal

    msj = (
        f"Proceso finalizado: "
        f"{total_nuevos} productos creados, "
        f"{total_actualizados} actualizados y "
        f"{total_sin_cambios} sin cambios."
    )

    return script_alerta_modal(
        "exito",
        "Carga Completada",
        msj,
        "/productos"
    )

# Endpoint asíncrono para buscar productos por coincidencia parcial en la descripción
@router.get("/api/productos/buscar")
async def buscar_productos(
    q: Optional[str] = "",
    tags: Optional[str] = "",
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    """
    Buscador flexible utilizado por F2 en Análisis.

    Replica la lógica de búsqueda de /productos:

    - Código ST
    - Código EAN
    - Descripción
    - Marca
    - Departamento
    - Grupo
    - Subgrupo
    - Proveedor
    - Múltiples términos mediante badges
    """

    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return []

    # ---------------------------------------------------------
    # Construir lista de términos.
    # q se mantiene compatible con llamadas anteriores.
    # ---------------------------------------------------------

    terminos = []

    if q and q.strip():
        terminos.append(q.strip())

    if tags and tags.strip():
        terminos.extend(
            t.strip()
            for t in tags.split(',')
            if t.strip()
        )

    if not terminos:
        return []

    # Evitar términos duplicados
    terminos_unicos = []

    vistos = set()

    for termino in terminos:

        clave = termino.lower()

        if clave not in vistos:
            vistos.add(clave)
            terminos_unicos.append(termino)

    # ---------------------------------------------------------
    # Consulta base
    # ---------------------------------------------------------

    builder = (
        config.supabase_async
        .table("productos")
        .select(
            "codigo_st, "
            "codigo_ean, "
            "descripcion, "
            "marca, "
            "departamento, "
            "grupo, "
            "subgrupo, "
            "precio, "
            "unidad_manejo, "
            "proveedor_id"
        )
    )

    # ---------------------------------------------------------
    # Cada badge funciona como filtro acumulativo.
    #
    # Ejemplo:
    #   COCA
    #   COLA
    #
    # obliga a que ambos términos participen.
    # ---------------------------------------------------------

    for termino in terminos_unicos:

        termino_limpio = re.sub(
            r'[^\w\s-]',
            '',
            termino
        ).strip()

        if not termino_limpio:
            continue

        palabras = termino_limpio.split()

        patron_busqueda = (
            f"%{'%'.join(palabras)}%"
        )

        # -----------------------------------------------------
        # Buscar proveedores usando el término COMPLETO.
        #
        # "COCA COLA" -> %coca%cola%
        #
        # No se busca "coca" y "cola" por separado.
        # -----------------------------------------------------

        query_prov = (
            config.supabase_async
            .table("proveedores")
            .select("id")
            .ilike(
                "nombre",
                patron_busqueda
            )
        )

        res_prov = await (
            ejecutar_supabase_con_reintento_async(
                lambda:
                query_prov.execute()
            )
        )

        ids_prov = [
            str(p["id"])
            for p in (res_prov.data or [])
            if p.get("id") is not None
        ]

        # -----------------------------------------------------
        # Campos del producto
        # -----------------------------------------------------

        condiciones = [
            f"codigo_st.ilike.{patron_busqueda}",
            f"codigo_ean.ilike.{patron_busqueda}",
            f"descripcion.ilike.{patron_busqueda}",
            f"marca.ilike.{patron_busqueda}",
            f"departamento.ilike.{patron_busqueda}",
            f"grupo.ilike.{patron_busqueda}",
            f"subgrupo.ilike.{patron_busqueda}",
        ]

        # Coincidencia por proveedor
        for proveedor_id in ids_prov:
            condiciones.append(
                f"proveedor_id.eq.{proveedor_id}"
            )

        builder = builder.or_(
            ",".join(condiciones)
        )

    # ---------------------------------------------------------
    # Resultados
    # ---------------------------------------------------------

    res = await (
        ejecutar_supabase_con_reintento_async(
            lambda:
            builder
            .order(
                "descripcion",
                desc=False
            )
            .limit(30)
            .execute()
        )
    )

    # ---------------------------------------------------------
    # Estructura que necesita el modal
    # ---------------------------------------------------------

    return [
        {
            "codigo":
                producto.get("codigo_st") or "",

            "descripcion":
                producto.get("descripcion") or "",

            "precio":
                float(
                    producto.get("precio") or 0
                ),

            "unidad_manejo":
                producto.get(
                    "unidad_manejo"
                ) or 1,

            "departamento":
                producto.get(
                    "departamento"
                ) or "",

            "grupo":
                producto.get(
                    "grupo"
                ) or "",

            "subgrupo":
                producto.get(
                    "subgrupo"
                ) or "",
        }
        for producto in (res.data or [])
    ]

@router.post("/api/productos/buscar-lote")
async def buscar_productos_por_codigo_lote(
    payload: CodigosProductosRequest,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Verifica la sesión.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    # Bloquea usuarios no autenticados.
    if not user:
        raise JSONResponse(
            status_code=401,
            content={"error": "No autorizado"}
        )

    # Normaliza y deduplica códigos.
    codigos = list(dict.fromkeys(
        str(codigo).strip()
        for codigo in payload.codigos
        if str(codigo).strip()
    ))

    # Evita una consulta vacía.
    if not codigos:
        return []

    try:
        # Busca todos los códigos en una sola operación.
        res = await (
            config.supabase_async
            .table("productos")
            .select(
                "codigo_st, descripcion, precio, unidad_manejo"
            )
            .in_("codigo_st", codigos)
            .execute()
        )

        # Devuelve solamente las columnas usadas por Análisis.
        return [
            {
                "codigo_st": producto.get("codigo_st") or "",
                "descripcion": producto.get("descripcion") or "",
                "precio": float(
                    producto.get("precio") or 0.0
                ),
                "unidad_manejo": producto.get(
                    "unidad_manejo"
                ) or "1"
            }
            for producto in (res.data or [])
        ]

    except Exception as e:
        # Registra el fallo.
        print(
            f"ERROR EN /api/productos/buscar-lote: {str(e)}"
        )

        raise JSONResponse(
            status_code=500,
            content={"error": "Error al consultar productos"}
        )

@router.get("/api/productos/buscar-codigo/{codigo}")
async def buscar_producto_por_codigo(
    codigo: str, 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return JSONResponse(status_code=401, content={"encontrado": False})

    codigo_limpio = codigo.strip()
    res = await (
    config.supabase_async
    .table("productos")
    .select("codigo_st, descripcion, precio, unidad_manejo")
    .eq("codigo_st", codigo_limpio)
    .execute()
)
    
    if res.data and len(res.data) > 0:
        prod = res.data[0]
        return {
            "encontrado": True,
            "codigo_st": prod.get("codigo_st", ""),
            "descripcion": prod.get("descripcion", ""),
            "precio": float(prod.get("precio") or 0.0),
            "unidad_manejo": prod.get("unidad_manejo", "1")
        }
    
    return {"encontrado": False}
