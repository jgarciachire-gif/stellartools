import io  # Manejo de IO en memoria
import re  # Expresiones regulares
import urllib.parse  # Formateo e URL
from typing import Optional  # Tipado
import xml.etree.ElementTree as ET  # Parseador XML
import pandas as pd  # Lectura de archivos Excel
from fastapi import APIRouter, Request, Form, UploadFile, File, Cookie  # FastAPI
from fastapi.responses import RedirectResponse, JSONResponse  # Respuestas HTTP
from config import supabase, templates, obtener_usuario_actual  # Variables globales

router = APIRouter()

@router.get("/productos")
def vista_productos(
    request: Request, 
    query: Optional[str] = None,
    departamento: Optional[str] = None,
    grupo: Optional[str] = None,
    proveedor_id: Optional[int] = None,
    select: Optional[str] = None,
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    busqueda_query = request.query_params.get("q", "")
    tags_query = request.query_params.get("tags", "")
    
    builder = supabase.table("productos").select("*, proveedores(nombre)")

    terminos = []
    if busqueda_query.strip():
        terminos.append(busqueda_query.strip())
    if tags_query.strip():
        terminos.extend([t.strip() for t in tags_query.split(",") if t.strip()])

    for term in terminos:
        term_limpio = re.sub(r'[^\w\s-]', '', term).strip()
        if not term_limpio:
            continue
            
        palabras = term_limpio.split()
        patron_busqueda = f"%{'%'.join(palabras)}%" if palabras else "%"

        res_prov = supabase.table("proveedores").select("id").ilike("nombre", patron_busqueda).execute()
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

    productos_res = builder.order("descripcion", desc=False).range(offset, offset + limit - 1).execute()
    productos = productos_res.data or []

    res_prov = supabase.table("proveedores").select("id, nombre").order("nombre").execute()
    proveedores = res_prov.data if res_prov and res_prov.data else []

    select_id = request.query_params.get("select")
    prov_obj = None

    if select_id:
        try:
            query_id = int(select_id) if str(select_id).isdigit() else select_id
            res_sel = supabase.table("productos").select("*").eq("id", query_id).execute()
            if res_sel.data:
                prov_obj = res_sel.data[0]
        except Exception as e:
            print("Error al obtener producto seleccionado:", e)

    if 'term_limpio' in locals() and term_limpio and term_limpio.isdigit() and productos:
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
def guardar_producto(
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
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
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
        supabase.table("productos").update(payload).eq("id", id).execute()
        prod_id = id
    else:
        res = supabase.table("productos").insert(payload).execute()
        prod_id = res.data[0]["id"] if res and res.data else ""

    redirect_url = f"/productos?select={prod_id}"
    if q.strip():
        redirect_url += f"&q={urllib.parse.quote(q.strip())}"
    if tags.strip():
        redirect_url += f"&tags={urllib.parse.quote(tags.strip())}"

    return RedirectResponse(url=redirect_url, status_code=303)

@router.post("/productos/eliminar/{producto_id}")
def eliminar_producto(producto_id: str, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    supabase.table("productos").delete().eq("id", producto_id).execute()

    return RedirectResponse(url="/productos", status_code=303)

@router.post("/productos/cargar-lista")
async def cargar_lista_productos(
    archivo: UploadFile = File(...), # Archivo subido por el usuario
    access_token: str = Cookie(None) # Token de sesión
):
    user = obtener_usuario_actual(access_token) # Verificar autenticación
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    contenido = await archivo.read() # Leer bytes del archivo
    nombre = archivo.filename.lower() # Nombre en minúsculas para validar extensión
    filas = [] # Almacenará los registros extraídos

    # 1. Extracción de datos desde CSV (detecta automáticamente si está separado por comas ',' o punto y coma ';')
    if nombre.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(contenido), sep=None, engine="python", encoding="utf-8")
        except Exception:
            df = pd.read_csv(io.BytesIO(contenido), sep=None, engine="python", encoding="latin1")

        for _, r in df.iterrows():
            filas.append({
                "codigo": str(r.get("CodigoDelProducto", "")),
                "descripcion": str(r.get("Descripcion", "")),
                "marca": str(r.get("Marca", "")),
                "departamento": str(r.get("Departamento", "")),
                "grupo": str(r.get("Grupo", "")),
                "subgrupo": str(r.get("SubGrupo", "")),
                "costo": r.get("CostoActual", 0),
                "proveedor": str(r.get("Proveedor", ""))
            })

    elif nombre.endswith(".xlsx"):
        df = pd.read_excel(io.BytesIO(contenido)) # Lectura Excel
        for _, r in df.iterrows():
            filas.append({
                "codigo": str(r.get("CodigoDelProducto", "")),
                "descripcion": str(r.get("Descripcion", "")),
                "marca": str(r.get("Marca", "")),
                "departamento": str(r.get("Departamento", "")),
                "grupo": str(r.get("Grupo", "")),
                "subgrupo": str(r.get("SubGrupo", "")),
                "costo": r.get("CostoActual", 0),
                "proveedor": str(r.get("Proveedor", ""))
            })

    elif nombre.endswith(".xml"):
        root = ET.fromstring(contenido) # Lectura XML
        for item in (root.findall(".//Producto") or root):
            filas.append({
                "codigo": item.findtext("CodigoDelProducto", ""),
                "descripcion": item.findtext("Descripcion", ""),
                "marca": item.findtext("Marca", ""),
                "departamento": item.findtext("Departamento", ""),
                "grupo": item.findtext("Grupo", ""),
                "subgrupo": item.findtext("SubGrupo", ""),
                "costo": item.findtext("CostoActual", "0"),
                "proveedor": item.findtext("Proveedor", "")
            })

    # 2. Mapeo de Proveedores (Nombre -> ID en BD)
    res_prov = supabase.table("proveedores").select("id, nombre").execute()
    mapa_proveedores = {p["nombre"].strip().upper(): p["id"] for p in (res_prov.data or []) if p.get("nombre")}

    # 3. Formateo y limpieza de datos de entrada
    codigos_entrada = []
    filas_procesadas = []

    for f in filas:
        raw_cod = f["codigo"].split(".")[0].strip() # Limpiar decimales en código
        codigo_st = raw_cod.zfill(6) if raw_cod.isdigit() else raw_cod # Formatear a 6 dígitos
        
        nombre_prov = f["proveedor"].strip().upper() if f["proveedor"] and f["proveedor"] != "nan" else ""
        prov_id = mapa_proveedores.get(nombre_prov) # Mapear ID del proveedor

        if codigo_st:
            codigos_entrada.append(codigo_st)
            filas_procesadas.append({
                "codigo_st": codigo_st,
                "descripcion": f["descripcion"].strip().upper() if f["descripcion"] and f["descripcion"] != "nan" else "",
                "marca": f["marca"].strip().upper() if f["marca"] and f["marca"] != "nan" else "",
                "departamento": f["departamento"].strip() if f["departamento"] != "nan" else "",
                "grupo": f["grupo"].strip() if f["grupo"] != "nan" else "",
                "subgrupo": f["subgrupo"].strip() if f["subgrupo"] != "nan" else "",
                "costo_raw": f["costo"],
                "proveedor_id": prov_id
            })

    if not filas_procesadas:
        return RedirectResponse(url="/productos", status_code=303)

    # 4. Consulta a BD dividiendo en lotes de 100 para no exceder el límite de URL de Supabase/HTTPX
    prod_existentes_map = {} # Mapa para guardar los productos existentes en BD
    tamanio_lote = 100 # Límite seguro de elementos por consulta HTTP GET

    # Iterar la lista de códigos de entrada en bloques de 100
    for i in range(0, len(codigos_entrada), tamanio_lote):
        lote_codigos = codigos_entrada[i:i + tamanio_lote] # Extraer sublista de 100 códigos
        res_lote = supabase.table("productos").select("*").in_("codigo_st", lote_codigos).execute() # Consultar lote actual
        if res_lote.data: # Si trae registros la consulta
            for p in res_lote.data: # Guardar cada producto en el diccionario general
                prod_existentes_map[p["codigo_st"]] = p

    nuevos_productos = [] # Lista de productos a insertar por primera vez
    actualizaciones_productos = [] # Lista de productos existentes a actualizar

    # 5. Aplicar reglas (completar vacíos, actualizar precio costo o crear nuevo)
    for item in filas_procesadas:
        cod = item["codigo_st"]
        
        # Parsear precio costo a formato decimal
        costo_raw = item["costo_raw"]
        precio_nuevo = 0.0
        if pd.notna(costo_raw) and costo_raw != "":
            if isinstance(costo_raw, str):
                c_limpio = costo_raw.replace(".", "").replace(",", ".")
                try:
                    precio_nuevo = float(c_limpio)
                except ValueError:
                    precio_nuevo = 0.0
            else:
                try:
                    precio_nuevo = float(costo_raw)
                except ValueError:
                    precio_nuevo = 0.0

        if cod in prod_existentes_map:
            # SI EXISTE: Completar datos vacíos en BD y actualizar precio si cambió
            existente = prod_existentes_map[cod]
            cambios = {}

            campos_evaluar = ["descripcion", "marca", "departamento", "grupo", "subgrupo", "proveedor_id"]
            for campo in campos_evaluar:
                valor_bd = existente.get(campo)
                valor_nuevo = item.get(campo)
                if (valor_bd is None or str(valor_bd).strip() == "") and (valor_nuevo is not None and str(valor_nuevo).strip() != ""):
                    cambios[campo] = valor_nuevo

            precio_bd = float(existente.get("precio") or 0.0)
            if precio_nuevo > 0 and precio_nuevo != precio_bd:
                cambios["precio"] = precio_nuevo # Asignar nuevo costo si varió

            if cambios:
                # Mezclar datos existentes con los cambios para enviar el objeto completo
                registro_actualizado = {**existente, **cambios}
                actualizaciones_productos.append(registro_actualizado)

        else:
            # NO EXISTE: Crear producto nuevo
            nuevos_productos.append({
                "codigo_st": cod,
                "descripcion": item["descripcion"],
                "marca": item["marca"],
                "unidad_manejo": "UND",
                "departamento": item["departamento"],
                "grupo": item["grupo"],
                "subgrupo": item["subgrupo"],
                "precio": precio_nuevo,
                "proveedor_id": item["proveedor_id"]
            })

    # 6. Insertar productos nuevos en lotes mostrando progreso en consola
    total_nuevos = len(nuevos_productos) # Total de nuevos a insertar
    if nuevos_productos:
        for i in range(0, total_nuevos, tamanio_lote):
            lote = nuevos_productos[i:i + tamanio_lote] # Sublista de 100
            supabase.table("productos").insert(lote).execute() # Insertar en BD
            print(f"--> [NUEVOS] Procesados {min(i + tamanio_lote, total_nuevos)} de {total_nuevos}") # Ver progreso en terminal de VS Code

    # 7. Actualizar productos existentes en lotes mostrando progreso en consola
    total_actualizados = len(actualizaciones_productos) # Total a actualizar
    if actualizaciones_productos:
        for i in range(0, total_actualizados, tamanio_lote):
            lote = actualizaciones_productos[i:i + tamanio_lote] # Sublista de 100
            supabase.table("productos").upsert(lote, on_conflict="id").execute() # Actualizar en BD
            print(f"--> [ACTUALIZADOS] Procesados {min(i + tamanio_lote, total_actualizados)} de {total_actualizados}") # Ver progreso en terminal

    print(f"SUCCESS: Carga finalizada con éxito. ({total_nuevos} creados, {total_actualizados} actualizados)") # Log final en consola

    # Redireccionar mostrando mensaje flotante de confirmación en el navegador
    from config import script_alerta_modal # Helper de mensajes del sistema
    msj = f"Proceso finalizado: {total_nuevos} productos creados y {total_actualizados} actualizados."
    return script_alerta_modal("exito", "Carga Completada", msj, "/productos")

@router.get("/api/productos/buscar-codigo/{codigo}")
def buscar_producto_por_codigo(codigo: str, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return JSONResponse(status_code=401, content={"encontrado": False})

    codigo_limpio = codigo.strip()
    res = supabase.table("productos").select("*").eq("codigo_st", codigo_limpio).execute()
    
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