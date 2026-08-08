from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
from datetime import datetime, timedelta, date
from pdf_processor import extraer_datos_oc
import os
import io
import xml.etree.ElementTree as ET
from fastapi import Response, Cookie, Depends
from supabase import create_client, Client

SUPABASE_URL = "https://wrcbuseidkupjndpovdd.supabase.co"
SUPABASE_KEY = "sb_publishable_m6ayEiPYF_dIWiNf-9kRog_j-HbKhwA"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Control de Compras", version="2.0")

def obtener_usuario_actual(access_token: str = Cookie(None)):
    if not access_token:
        return None
    try:
        user_response = supabase.auth.get_user(access_token)
        return user_response.user
    except Exception:
        return None

@app.get("/login")
def vista_login(request: Request):
    token = request.cookies.get("access_token")
    if obtener_usuario_actual(token):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})

@app.post("/registro")
def procesar_registro(email: str = Form(...), password: str = Form(...)):
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        return HTMLResponse("<script>alert('¡Registro exitoso! Ya puedes iniciar sesión con tu correo.'); window.location.href='/login';</script>")
    except Exception as e:
        return HTMLResponse(f"<script>alert('Error al registrar: {str(e)}'); window.history.back();</script>")

@app.post("/login")
def procesar_login(email: str = Form(...), password: str = Form(...)):
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="access_token", 
            value=auth_res.session.access_token, 
            httponly=True, 
            max_age=3600 * 24 * 7
        )
        return response
    except Exception as e:
        return HTMLResponse(f"<script>alert('Credenciales incorrectas o error en el servidor.'); window.history.back();</script>")

@app.get("/logout")
def cerrar_sesion():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


# Configuración de plantillas
templates = Jinja2Templates(directory="templates")
def formato_moneda_latina(valor):
    if valor is None:
        return "0,00"
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

templates.env.filters["moneda"] = formato_moneda_latina


@app.get("/")
def dashboard(request: Request):
    token = request.cookies.get("access_token")
    user = obtener_usuario_actual(token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res_oc = supabase.table("ordenes_compra").select("*, proveedores(nombre)").eq("usuario_id", user.id).order("id", desc=True).execute()
    
    proveedores_desglose = {}
    hoy = datetime.now().date()

    if res_oc.data:
        for row in res_oc.data:
            prov_obj = row.get("proveedores")
            prov = prov_obj["nombre"] if prov_obj else (row.get('proveedor') or "Sin Proveedor")
            tienda = row.get('tienda_destino') or "Sin Tienda Asignada"
            
            if prov not in proveedores_desglose:
                proveedores_desglose[prov] = {}
            
            if tienda not in proveedores_desglose[prov]:
                f_rec_raw = str(row.get('fecha_recepcion') or "").strip()
                tiene_fecha_rec = f_rec_raw != "" and f_rec_raw.lower() not in ['none', 'nan', 'nat', 'null']
                
                estatus_oc = "Recibido" if tiene_fecha_rec else "Enviada"
                dias_inv_totales = int(row.get('dias_inventario') or 15)
                
                if tiene_fecha_rec:
                    try:
                        f_rec = datetime.strptime(f_rec_raw, "%Y-%m-%d").date()
                        fecha_agotamiento = f_rec + timedelta(days=dias_inv_totales)
                        dias_restantes = (fecha_agotamiento - hoy).days
                        
                        if dias_restantes <= 0:
                            estatus_inv = "Reponer inventario"
                            color_inv = "text-red-700 bg-red-100"
                            dias_mostrar = f"Vencido hace {abs(dias_restantes)}d"
                        elif dias_restantes <= 5:
                            estatus_inv = "Próximo a Agotar"
                            color_inv = "text-amber-700 bg-amber-100"
                            dias_mostrar = f"Quedan {dias_restantes}d"
                        else:
                            estatus_inv = "Stock OK"
                            color_inv = "text-emerald-700 bg-emerald-100"
                            dias_mostrar = f"Quedan {dias_restantes}d"
                    except ValueError:
                        estatus_inv = "Error de Fecha"
                        color_inv = "text-slate-600 bg-slate-100"
                        dias_mostrar = f"{dias_inv_totales} totales"
                else:
                    estatus_inv = "Esperando Recepción"
                    color_inv = "text-blue-700 bg-blue-100"
                    dias_mostrar = "Sin iniciar"

                proveedores_desglose[prov][tienda] = {
                    "ultima_oc": row.get('numero_orden'),
                    "fecha_recepcion": row.get('fecha_recepcion') or "-",
                    "estatus_oc": estatus_oc,
                    "dias_inventario": dias_mostrar,
                    "estatus_inv": estatus_inv,
                    "color_inv": color_inv
                }

    return templates.TemplateResponse(request, "dashboard.html", {
        "proveedores_desglose": proveedores_desglose
    })

@app.get("/ordenes")
def listar_ordenes(request: Request):
    token = request.cookies.get("access_token")
    user = obtener_usuario_actual(token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res = supabase.table("ordenes_compra").select("*, proveedores(nombre, dias_credito)").eq("usuario_id", user.id).order("fecha_emision", desc=True).execute()
    
    hoy = datetime.now().date()
    meses_espanol = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    ordenes_agrupadas = {}
    
    if res.data:
        for row in res.data:
            o = row.copy()
            prov_obj = o.get("proveedores")
            
            if prov_obj:
                o['proveedor'] = prov_obj.get("nombre")
                dias_credito = prov_obj.get("dias_credito")
            else:
                dias_credito = 30

            f_rec_raw = str(o.get('fecha_recepcion') or "").strip()
            tiene_fecha_rec = f_rec_raw != "" and f_rec_raw.lower() not in ['none', 'nan', 'nat', 'null']
            
            o['estatus'] = 'Recibido' if tiene_fecha_rec else 'Enviada'
            o['vencimiento_factura_str'] = ""
            o['alerta_text'] = ""
            o['alerta_color'] = "transparent"
            o['pagada'] = o.get('pagada', False) # Obtenemos el valor de la base de datos
            
            if tiene_fecha_rec and dias_credito:
                try:
                    f_rec = datetime.strptime(f_rec_raw, "%Y-%m-%d").date()
                    venc_date = f_rec + timedelta(days=int(dias_credito))
                    o['vencimiento_factura_str'] = venc_date.strftime("%d/%m/%Y")
                    dias_restantes = (venc_date - hoy).days
                    
                    if dias_restantes < 0:
                        o['alerta_text'] = f"Vencido ({abs(dias_restantes)}d)"
                        o['alerta_color'] = "bg-red-500"
                    elif dias_restantes <= 5:
                        o['alerta_text'] = f"Por vencer ({dias_restantes}d)"
                        o['alerta_color'] = "bg-yellow-400"
                    else:
                        o['alerta_text'] = "Vigente"
                        o['alerta_color'] = "bg-green-500"
                except ValueError:
                    pass
            
            # Agrupación por Mes y Año
            fecha_emision_raw = str(o.get('fecha_emision') or "").strip()
            if fecha_emision_raw:
                try:
                    dt = datetime.strptime(fecha_emision_raw, "%Y-%m-%d")
                    mes_anio = f"{meses_espanol[dt.month - 1]} {dt.year}"
                except ValueError:
                    mes_anio = "Fecha Inválida"
            else:
                mes_anio = "Sin Fecha"
                
            if mes_anio not in ordenes_agrupadas:
                ordenes_agrupadas[mes_anio] = []
            ordenes_agrupadas[mes_anio].append(o)
            
    return templates.TemplateResponse(request, "ordenes.html", {"ordenes_agrupadas": ordenes_agrupadas})

@app.post("/ordenes/actualizar/{orden_id}")
def actualizar_orden(
    orden_id: int, 
    fecha_envio: str = Form(None), 
    fecha_recepcion: str = Form(None),
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    f_rec = fecha_recepcion if fecha_recepcion else None
    f_env = fecha_envio if fecha_envio else None
    estatus = "Recibido" if f_rec else "Enviada"

    supabase.table("ordenes_compra").update({
        "estatus": estatus,
        "fecha_envio": f_env,
        "fecha_recepcion": f_rec
    }).eq("id", orden_id).eq("usuario_id", user.id).execute()
    
    return RedirectResponse(url="/ordenes", status_code=303)
@app.post("/ordenes/pagar/{orden_id}")
async def actualizar_pago(orden_id: int, request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return {}
    
    data = await request.json()
    estado_pagada = data.get("pagada", False)
    
    # Actualizamos el valor en Supabase
    supabase.table("ordenes_compra").update({"pagada": estado_pagada}).eq("id", orden_id).eq("usuario_id", user.id).execute()
    return {"status": "ok"}

@app.post("/ordenes/eliminar/{orden_id}")
def eliminar_orden(orden_id: int, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    supabase.table("ordenes_compra").delete().eq("id", orden_id).eq("usuario_id", user.id).execute()
    return RedirectResponse(url="/ordenes", status_code=303)

@app.get("/proveedores")
def gestionar_proveedores(request: Request, buscar: str = "", select: int = None, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    query = supabase.table("proveedores").select("*").order("nombre", desc=False)
    if buscar:
        query = query.ilike("nombre", f"%{buscar}%")
    
    res = query.execute()
    proveedores = res.data if res.data else []
    
    prov_obj = next((p for p in proveedores if p["id"] == select), None) if select else None
    
    return templates.TemplateResponse(request, "proveedores.html", {
        "proveedores": proveedores, 
        "busqueda": buscar,
        "prov_obj": prov_obj
    })

@app.post("/proveedores/importar-xml")
async def importar_proveedores_xml(archivo_xml: UploadFile = File(...), access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    contenido = await archivo_xml.read()
    try:
        arbol = ET.fromstring(contenido)
        # Apuntamos a 'Registro', 'Descripcion' y 'Codigo' según la estructura de tu XML
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

@app.post("/proveedores/guardar")
def guardar_proveedor(id: int = Form(None), codigo: str = Form(""), nombre: str = Form(...), dias_credito: int = Form(30), contacto: str = Form(""), access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if id:
        supabase.table("proveedores").update({
            "codigo": codigo,
            "nombre": nombre,
            "dias_credito": dias_credito,
            "contacto": contacto
        }).eq("id", id).execute()
    else:
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

@app.post("/proveedores/eliminar/{prov_id}")
def eliminar_proveedor(prov_id: int, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        supabase.table("proveedores").delete().eq("id", prov_id).execute()
    except Exception:
        pass
    return RedirectResponse(url="/proveedores", status_code=303)

@app.get("/escanear")
def vista_escanear(request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request, "escanear.html", {"datos": None})

@app.post("/escanear/procesar")
async def procesar_pdf(request: Request, archivo_pdf: UploadFile = File(...), access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    contenido_bytes = await archivo_pdf.read()
    pdf_en_memoria = io.BytesIO(contenido_bytes)
    datos_extraidos = extraer_datos_oc(pdf_en_memoria)
    
    if not datos_extraidos:
        datos_extraidos = {
            "numero_orden": "",
            "proveedor": "",
            "tienda_destino": "",
            "fecha_emision": "",
            "monto_total": 0.0
        }
    
    return templates.TemplateResponse(request, "escanear.html", {
        "datos": datos_extraidos
    })

@app.post("/ordenes/crear")
def crear_orden_manual(
    numero_orden: str = Form(...),
    proveedor: str = Form(...),
    tienda_destino: str = Form(...),
    monto_total: float = Form(0.0),
    fecha_emision: str = Form(...),
    dias_inventario: int = Form(...),
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res_existe = supabase.table("ordenes_compra").select("id").eq("numero_orden", numero_orden).eq("usuario_id", user.id).execute()
    if res_existe.data and len(res_existe.data) > 0:
        alerta_js = f"<script>alert('Cuidado: La Orden de Compra N° {numero_orden} ya fue registrada.'); window.history.back();</script>"
        return HTMLResponse(content=alerta_js)

    res_p = supabase.table("proveedores").select("id").ilike("nombre", proveedor.strip()).execute()
    if res_p.data and len(res_p.data) > 0:
        prov_id = res_p.data[0]['id']
    else:
        res_ins_p = supabase.table("proveedores").insert({
            "nombre": proveedor.strip(),
            "dias_credito": 30,
            "dias_despacho": 3,
            "dias_inventario": 15
        }).execute()
        prov_id = res_ins_p.data[0]['id'] if res_ins_p.data else None

    supabase.table("ordenes_compra").insert({
        "usuario_id": user.id,
        "numero_orden": numero_orden,
        "proveedor_id": prov_id,
        "proveedor": proveedor,
        "tienda_destino": tienda_destino,
        "fecha_emision": fecha_emision,
        "monto_total": monto_total,
        "estatus": "Enviada",
        "dias_inventario": dias_inventario
    }).execute()
    
    return RedirectResponse(url="/ordenes", status_code=303)