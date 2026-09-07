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
    archivo: UploadFile = File(...),
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    contenido = await archivo.read()
    nombre = archivo.filename.lower()
    filas = []

    if nombre.endswith(".xlsx"):
        df = pd.read_excel(io.BytesIO(contenido))
        for _, r in df.iterrows():
            filas.append({
                "codigo": str(r.get("CodigoDelProducto", "")),
                "descripcion": str(r.get("Descripcion", "")),
                "marca": str(r.get("Marca", "")),
                "departamento": str(r.get("Departamento", "")),
                "grupo": str(r.get("Grupo", "")),
                "subgrupo": str(r.get("SubGrupo", "")),
                "costo": r.get("CostoActual", 0)
            })

    elif nombre.endswith(".xml"):
        root = ET.fromstring(contenido)
        for item in (root.findall(".//Producto") or root):
            filas.append({
                "codigo": item.findtext("CodigoDelProducto", ""),
                "descripcion": item.findtext("Descripcion", ""),
                "marca": item.findtext("Marca", ""),
                "departamento": item.findtext("Departamento", ""),
                "grupo": item.findtext("Grupo", ""),
                "subgrupo": item.findtext("SubGrupo", ""),
                "costo": item.findtext("CostoActual", "0")
            })

    payload = []
    for f in filas:
        raw_cod = f["codigo"].split(".")[0].strip()
        codigo_st = raw_cod.zfill(6) if raw_cod.isdigit() else raw_cod

        desc = f["descripcion"].strip().upper() if f["descripcion"] and f["descripcion"] != "nan" else ""
        marca = f["marca"].strip().upper() if f["marca"] and f["marca"] != "nan" else ""

        costo_raw = f["costo"]
        precio = 0.0
        if pd.notna(costo_raw) and costo_raw != "":
            if isinstance(costo_raw, str):
                c_limpio = costo_raw.replace(".", "").replace(",", ".")
                try:
                    precio = float(c_limpio)
                except ValueError:
                    precio = 0.0
            else:
                try:
                    precio = float(costo_raw)
                except ValueError:
                    precio = 0.0

        if codigo_st and desc:
            payload.append({
                "codigo_st": codigo_st,
                "descripcion": desc,
                "marca": marca,
                "unidad_manejo": "UND",
                "departamento": f["departamento"].strip() if f["departamento"] != "nan" else "",
                "grupo": f["grupo"].strip() if f["grupo"] != "nan" else "",
                "subgrupo": f["subgrupo"].strip() if f["subgrupo"] != "nan" else "",
                "precio": precio
            })

    if payload:
        supabase.table("productos").upsert(
            payload, 
            on_conflict="codigo_st"
        ).execute()

    return RedirectResponse(url="/productos", status_code=303)

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