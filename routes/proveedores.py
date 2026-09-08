import json  # Manejo de formatos JSON
from typing import Optional  # Anotaciones de tipos opcionales
import xml.etree.ElementTree as ET  # Procesamiento de archivos XML
from datetime import datetime  # Fechas
from fastapi import APIRouter, Request, Form, UploadFile, File, Cookie  # Dependencias FastAPI
from fastapi.responses import RedirectResponse, HTMLResponse, Response  # Tipos de respuesta
from config import supabase, templates, obtener_usuario_actual, script_alerta_error  # Entorno global

router = APIRouter()

@router.get("/proveedores")
async def vista_proveedores(request: Request, select: int = None, access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res = supabase.table("proveedores").select("*").order("nombre").execute()
    proveedores = res.data if res and res.data else []

    res_cats = supabase.table("categorias").select("*").eq("usuario_id", user.id).order("nombre").execute()
    categorias_disponibles = res_cats.data if res_cats and res_cats.data else []

    prov_obj = None
    if select:
        res_sel = supabase.table("proveedores").select("*").eq("id", select).maybe_single().execute()
        if res_sel and res_sel.data:
            prov_obj = res_sel.data

    return templates.TemplateResponse(request=request, name="proveedores.html", context={
        "proveedores": proveedores,
        "prov_obj": prov_obj,
        "categorias_disponibles": categorias_disponibles
    })
    
@router.post("/proveedores/importar-xml")
async def importar_proveedores_xml(archivo_xml: UploadFile = File(...), access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    contenido = await archivo_xml.read()
    try:
        arbol = ET.fromstring(contenido)
        for prov in arbol.findall('.//Registro'):
            nombre = prov.findtext('Descripcion')
            codigo = prov.findtext('Codigo', default="")
            contacto = "" 
            dias_credito = 30
            
            if nombre:
                try:
                    supabase.table("proveedores").insert({
                        "codigo": codigo,
                        "nombre": nombre,
                        "dias_credito": dias_credito,
                        "contacto": contacto,
                        "dias_despacho": 3,
                        "dias_inventario": 15
                    }).execute()
                except Exception:
                    pass 
                    
        return RedirectResponse(url="/proveedores", status_code=303)
    except ET.ParseError:
        return HTMLResponse("<script>alert('Error: El archivo XML no tiene un formato válido.'); window.location.href='/proveedores';</script>")

@router.get("/proveedores/exportar-xml")
async def exportar_proveedores_xml(request: Request, access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res = supabase.table("proveedores").select("*").order("nombre").execute()
    proveedores = res.data if res and res.data else []

    root = ET.Element("Proveedores")
    for p in proveedores:
        item = ET.SubElement(root, "Proveedor")
        ET.SubElement(item, "Codigo").text = str(p.get("codigo") or "")
        ET.SubElement(item, "Nombre").text = str(p.get("nombre") or "")
        ET.SubElement(item, "Contacto").text = str(p.get("contacto") or "")
        ET.SubElement(item, "Telefono").text = str(p.get("telefono") or "")
        ET.SubElement(item, "Email").text = str(p.get("email") or "")
        ET.SubElement(item, "DiasCredito").text = str(p.get("dias_credito") if p.get("dias_credito") is not None else 0)
        ET.SubElement(item, "FrecuenciaPedidos").text = str(p.get("dias_despacho") if p.get("dias_despacho") is not None else 3)
        
        cats = p.get("categorias") or []
        if isinstance(cats, list):
            cats_str = ", ".join([str(c) for c in cats])
        else:
            cats_str = str(cats)
        ET.SubElement(item, "Categorias").text = cats_str

    xml_data = ET.tostring(root, encoding="utf-8", method="xml")
    
    return Response(
        content=xml_data,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=proveedores.xml"}
    )

@router.post("/proveedores/guardar")
async def guardar_proveedor(
    id: Optional[str] = Form(None),
    codigo: str = Form(""),
    nombre: Optional[str] = Form(""),
    contacto: str = Form(""),
    telefono: str = Form(""),
    email: str = Form(""),
    dias_credito: Optional[str] = Form("0"),
    dias_despacho: Optional[str] = Form("3"),
    categorias: str = Form("[]"),
    access_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    prov_id = int(id) if id and id.strip().isdigit() else None

    credito_num = int(dias_credito) if dias_credito and dias_credito.strip().isdigit() else 0
    despacho_num = int(dias_despacho) if dias_despacho and dias_despacho.strip().isdigit() else 3

    try:
        lista_categorias = json.loads(categorias)
    except Exception:
        lista_categorias = []

    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    usuario_str = user.email if user and hasattr(user, 'email') else "Usuario"
    historial_mod = f"Última modificación hecha por {usuario_str} el {fecha_actual}."

    datos_payload = {
        "codigo": codigo,
        "nombre": nombre,
        "contacto": contacto,
        "telefono": telefono,
        "email": email,
        "dias_credito": credito_num,
        "dias_despacho": despacho_num,
        "categorias": lista_categorias,
        "ultima_modificacion": historial_mod
    }

    if prov_id:
        supabase.table("proveedores").update(datos_payload).eq("id", prov_id).execute()
        redirect_url = f"/proveedores?select={prov_id}"
    else:
        datos_payload["dias_inventario"] = 15
        res = supabase.table("proveedores").insert(datos_payload).execute()
        if res.data and len(res.data) > 0:
            nuevo_id = res.data[0]['id']
            redirect_url = f"/proveedores?select={nuevo_id}"
        else:
            redirect_url = "/proveedores"
            
    return RedirectResponse(url=redirect_url, status_code=303)

@router.post("/proveedores/eliminar/{prov_id}")
async def eliminar_proveedor(prov_id: int, access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        res = supabase.table("proveedores").delete().eq("id", prov_id).execute()
        if not res.data:
            return script_alerta_error("No se pudo eliminar el proveedor. Es posible que ya no exista.", redireccionar="/proveedores")
    except Exception:
        return script_alerta_error("No se puede eliminar el proveedor porque tiene Órdenes de Compra asociadas a su registro.", redireccionar=f"/proveedores?select={prov_id}")

    return RedirectResponse(url="/proveedores", status_code=303)