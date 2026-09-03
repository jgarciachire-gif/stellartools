import os
import sys
import io
import re
import socket
import json
import traceback
import urllib.parse
from typing import List, Optional
from datetime import datetime, timedelta, date
import xml.etree.ElementTree as ET

import httpx
import pandas as pd
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Response, Cookie, Depends, status
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from supabase import create_client, Client, ClientOptions
from starlette.middleware.sessions import SessionMiddleware
from pdf_processor import extraer_datos_oc

# ==========================================
# 1. Configuración global y clientes HTTP
# ==========================================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

socket.setdefaulttimeout(30.0)
httpx._config.DEFAULT_TIMEOUT_CONFIG = httpx.Timeout(timeout=60.0, connect=30.0)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wrcbuseidkupjndpovdd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_m6ayEiPYF_dIWiNf-9kRog_j-HbKhwA")

supabase: Client = create_client(
    SUPABASE_URL, 
    SUPABASE_KEY,
    options=ClientOptions(
        postgrest_client_timeout=60,
        storage_client_timeout=60
    )
)

app = FastAPI(title="Control de Compras", version="2.0")
app.add_middleware(SessionMiddleware, secret_key="clave_secreta_para_sesiones")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ==========================================
# 2. Configuración de Plantillas y Filtros
# ==========================================
templates = Jinja2Templates(directory="templates")

def formato_moneda_latina(valor):
    if valor is None:
        return "0,00"
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def limpiar_cantidad(valor):
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    val_limpio = str(valor).replace(",", "").strip()
    try:
        return float(val_limpio)
    except ValueError:
        return 0.0

templates.env.filters["moneda"] = formato_moneda_latina
templates.env.filters["limpiar_cantidad"] = limpiar_cantidad

# ==========================================
# 3. Funciones Helper Globales
# ==========================================
def sanitizar_numero(val):
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    if "." in val_str and "," in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    elif "." in val_str and len(val_str.split(".")[-1]) == 3:
        val_str = val_str.replace(".", "")
    elif "," in val_str:
        val_str = val_str.replace(",", "")
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def limpiar_monto_decimal(valor_str):
    texto = str(valor_str).strip().replace('$', '')
    if ',' in texto and '.' in texto:
        texto = texto.replace(',', '')
    elif ',' in texto:
        texto = texto.replace(',', '.')
    try:
        return round(float(texto), 2)
    except ValueError:
        return 0.0

def obtener_usuario_actual(access_token: str = Cookie(None), refresh_token: str = Cookie(None)):
    if not access_token and not refresh_token:
        return None
    try:
        user_response = supabase.auth.get_user(access_token)
        return user_response.user
    except Exception:
        if refresh_token:
            try:
                res = supabase.auth.refresh_session(refresh_token)
                return res.user if res else None
            except Exception:
                return None
        return None

def script_alerta_error(mensaje: str, redireccionar: str = None) -> HTMLResponse:
    msj_limpio = mensaje.replace("'", "\\'").replace("\n", " ")
    if redireccionar:
        js = f"<script>alert('{msj_limpio}'); window.location.href='{redireccionar}';</script>"
    else:
        js = f"<script>alert('{msj_limpio}'); window.history.back();</script>"
    return HTMLResponse(content=js)

def script_alerta_modal(tipo: str, titulo: str, mensaje: str, redireccionar: str = "/login") -> RedirectResponse:
    msj_enc = urllib.parse.quote(mensaje)
    tit_enc = urllib.parse.quote(titulo)
    return RedirectResponse(url=f"{redireccionar}?msg_tipo={tipo}&msg_titulo={tit_enc}&msg_texto={msj_enc}", status_code=303)

# ==========================================
# 4. Modelos de Datos (Pydantic)
# ==========================================
class ProductoModificado(BaseModel):
    codigo: str
    unidad_manejo: int
    precio: float

# ==========================================
# 5. Endpoints del Sistema
# ==========================================
@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def chrome_devtools_silencer():
    return Response(status_code=204) 

@app.get("/login")
def vista_login(request: Request):
    token = request.cookies.get("access_token")
    if obtener_usuario_actual(token):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={})

@app.post("/registro")
def procesar_registro(email: str = Form(...), password: str = Form(...)):
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        return script_alerta_modal(
            tipo="exito", 
            titulo="¡Registro Exitoso!", 
            mensaje="Hemos enviado un enlace de confirmación a tu correo. Por favor, verifícalo para activar tu cuenta."
        )
    except Exception as e:
        return script_alerta_modal(
            tipo="error", 
            titulo="Error de Registro", 
            mensaje=f"No se pudo crear la cuenta: {str(e)}"
        )

@app.post("/login")
def procesar_login(email: str = Form(...), password: str = Form(...)):
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
        response = RedirectResponse(url="/", status_code=303)
        
        response.set_cookie(
            key="access_token", 
            value=auth_res.session.access_token, 
            httponly=True, 
            secure=False, 
            samesite="lax", 
            max_age=3600 * 24 * 7
        )
        response.set_cookie(
            key="refresh_token", 
            value=auth_res.session.refresh_token, 
            httponly=True, 
            secure=False, 
            samesite="lax", 
            max_age=3600 * 24 * 7
        )
        return response
    except Exception as e:
        print(f"\n[DETALLE ERROR SUPABASE]: {e}\n")
        res_error = script_alerta_modal(
            tipo="error", 
            titulo="Error de Acceso", 
            mensaje=f"Supabase rechazó la entrada: {str(e)}"
        )
        res_error.delete_cookie("access_token")
        res_error.delete_cookie("refresh_token")
        return res_error

@app.post("/recuperar-password")
def enviar_recuperacion(request: Request, email: str = Form(...)):
    try:
        redirect_to = str(request.url_for("vista_reset_password"))
        supabase.auth.reset_password_for_email(email, {"redirect_to": redirect_to})
        return script_alerta_modal(
            tipo="exito", 
            titulo="Correo Enviado", 
            mensaje="Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."
        )
    except Exception as e:
        return script_alerta_modal(
            tipo="error", 
            titulo="Error", 
            mensaje=f"No se pudo procesar la solicitud: {str(e)}"
        )

@app.get("/reset-password")
def vista_reset_password(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"reset_mode": True})

@app.post("/reset-password")
def procesar_reset_password(access_token: str = Cookie(None), nueva_password: str = Form(...)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return script_alerta_modal(tipo="error", titulo="Sesión Expirada", mensaje="El enlace de recuperación ha expirado o es inválido.")
    try:
        supabase.auth.update_user({"password": nueva_password})
        return script_alerta_modal(tipo="exito", titulo="Contraseña Actualizada", mensaje="Tu clave se ha cambiado con éxito. Puedes iniciar sesión.")
    except Exception as e:
        return script_alerta_modal(tipo="error", titulo="Error", mensaje=f"Error al actualizar la contraseña: {str(e)}")

@app.get("/logout")
def cerrar_sesion():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response

@app.middleware("http")
async def cargar_perfil_middleware(request: Request, call_next):
    request.state.perfil = None
    access_token = request.cookies.get("access_token")
    
    if access_token:
        user = obtener_usuario_actual(access_token)  
        if user:
            res = supabase.table("perfiles").select("*").eq("usuario_id", user.id).maybe_single().execute()
            request.state.perfil = res.data if res and res.data else None  
            
    response = await call_next(request)
    return response
  
@app.get("/")
@app.get("/aplicaciones") 
def vista_aplicaciones(
    request: Request, 
    access_token: str = Cookie(None), 
    refresh_token: str = Cookie(None)
): 
    user = obtener_usuario_actual(access_token, refresh_token) 
    if not user: 
        return RedirectResponse(url="/login", status_code=303) 
    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.get("/dashboard")
@app.get("/inicio") 
def dashboard(
    request: Request, 
    access_token: str = Cookie(None),  
    refresh_token: str = Cookie(None)  
):
    user = obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)  

    res_oc = supabase.table("ordenes_compra").select("*, proveedores(nombre)").eq("usuario_id", user.id).order("id", desc=False).execute()
    
    proveedores_desglose = {}
    hoy = datetime.now().date()  
    if res_oc.data:
        agrupado = {}
        for row in res_oc.data:
            prov_obj = row.get("proveedores")
            if isinstance(prov_obj, dict) and prov_obj.get("nombre"):
                prov = prov_obj.get("nombre")
            elif isinstance(prov_obj, list) and len(prov_obj) > 0 and isinstance(prov_obj[0], dict):
                prov = prov_obj[0].get("nombre")
            else:
                prov = row.get('proveedor') or "Sin Proveedor"

            tienda = row.get('tienda_destino') or "Sin Tienda Asignada"
            
            key = (prov, tienda)
            if key not in agrupado:
                agrupado[key] = []
            agrupado[key].append(row) 

        for (prov, tienda), lista_ocs in agrupado.items():
            if prov not in proveedores_desglose:
                proveedores_desglose[prov] = {}

            ocs_recibidas = []
            ocs_enviadas = []
            
            for oc in lista_ocs:
                f_rec_raw = str(oc.get('fecha_recepcion') or "").strip()
                tiene_fecha_rec = f_rec_raw != "" and f_rec_raw.lower() not in ['none', 'nan', 'nat', 'null']
                if tiene_fecha_rec:
                    ocs_recibidas.append(oc)
                else:
                    ocs_enviadas.append(oc)

            if ocs_recibidas:
                oc_seleccionada = ocs_recibidas[-1]
                hay_nueva_enviada = any(oc.get('id', 0) > oc_seleccionada.get('id', 0) for oc in ocs_enviadas)
                
                if hay_nueva_enviada:
                    estatus_oc = "Nueva OC enviada"
                else:
                    estatus_oc = "Despacho Recibido"
            else:
                oc_seleccionada = ocs_enviadas[-1]
                estatus_oc = "Enviada"

            f_rec_raw = str(oc_seleccionada.get('fecha_recepcion') or "").strip()
            tiene_fecha_rec = f_rec_raw != "" and f_rec_raw.lower() not in ['none', 'nan', 'nat', 'null']
            dias_inv_totales = int(oc_seleccionada.get('dias_inventario') or 15)

            if tiene_fecha_rec:
                try:
                    f_rec = datetime.strptime(f_rec_raw, "%Y-%m-%d").date()
                    f_rec_str = f_rec.strftime("%d/%m/%Y")
                    fecha_agotamiento = f_rec + timedelta(days=dias_inv_totales)
                    dias_restantes = (fecha_agotamiento - hoy).days
                    
                    if dias_restantes <= 0:
                        estatus_inv = "Reponer inventario"
                        color_inv = "text-red-700 bg-red-100"
                        dias_mostrar = f"Vencido hace {abs(dias_restantes)}d"
                    elif dias_restantes <= 2:
                        estatus_inv = "Próximo a Agotar"
                        color_inv = "text-amber-700 bg-amber-100"
                        dias_mostrar = f"Quedan {dias_restantes}d"
                    else:
                        estatus_inv = "Stock OK"
                        color_inv = "text-emerald-700 bg-emerald-100"
                        dias_mostrar = f"Quedan {dias_restantes}d"
                except ValueError:
                    f_rec_str = f_rec_raw
                    estatus_inv = "Error de Fecha"
                    color_inv = "text-slate-600 bg-slate-100"
                    dias_mostrar = f"{dias_inv_totales} totales"
            else:
                f_rec_str = "-"
                estatus_inv = "Esperando Recepción"
                color_inv = "text-blue-700 bg-blue-100"
                dias_mostrar = "Sin iniciar"

            if estatus_oc in ["Despacho Recibido", "Stock OK"]:
                color_oc = "text-emerald-700 bg-emerald-100"
            elif estatus_oc == "Nueva OC enviada":
                color_oc = "text-blue-700 bg-blue-100"
            else:
                color_oc = "text-slate-700 bg-slate-100"

            proveedores_desglose[prov][tienda] = {
                "ultima_oc": oc_seleccionada.get('numero_orden'),
                "fecha_recepcion": f_rec_str,
                "estatus_oc": estatus_oc,
                "color_oc": color_oc,
                "dias_inventario": dias_mostrar,
                "estatus_inv": estatus_inv,
                "color_inv": color_inv
            }

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "proveedores_desglose": proveedores_desglose
    })

@app.get("/ordenes")
def listar_ordenes(request: Request):
    token = request.cookies.get("access_token")
    user = obtener_usuario_actual(token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res = supabase.table("ordenes_compra").select("*, proveedores(nombre, dias_credito), detalles_productos(*)").eq("usuario_id", user.id).order("fecha_envio", desc=True).execute()
    
    hoy = datetime.now().date()
    meses_espanol = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    ordenes_agrupadas = {}
    
    if res.data:
        for row in res.data:
            o = row.copy()
            
            dp_raw = o.get("detalles_productos")
            if isinstance(dp_raw, str):
                try:
                    o['detalles_productos'] = json.loads(dp_raw)
                except (json.JSONDecodeError, TypeError):
                    o['detalles_productos'] = []
            elif not isinstance(dp_raw, list):
                o['detalles_productos'] = []
            
            prov_obj = o.get("proveedores")
            if prov_obj:
                o['proveedor'] = prov_obj.get("nombre")
                dias_credito = prov_obj.get("dias_credito")
            else:
                dias_credito = 30

            f_rec_raw = str(o.get('fecha_recepcion') or "").strip()
            tiene_fecha_rec = f_rec_raw != "" and f_rec_raw.lower() not in ['none', 'nan', 'nat', 'null']
            
            o['estatus'] = 'Despacho Recibido' if tiene_fecha_rec else 'Enviada'
            o['vencimiento_factura_str'] = ""
            o['alerta_text'] = ""
            o['alerta_color'] = "transparent"
            o['pagada'] = o.get('pagada', False)
            
            if tiene_fecha_rec and dias_credito:
                try:
                    f_rec = datetime.strptime(f_rec_raw, "%Y-%m-%d").date()
                    venc_date = f_rec + timedelta(days=int(dias_credito))
                    o['vencimiento_factura_str'] = venc_date.strftime("%d/%m/%Y")
                    dias_restantes = (venc_date - hoy).days
                    
                    if dias_restantes < 0:
                        o['alerta_text'] = f"Vencido ({abs(dias_restantes)}d)"
                        o['alerta_color'] = "bg-red-500"
                    elif dias_restantes <= 3:
                        o['alerta_text'] = f"Por vencer ({dias_restantes}d)"
                        o['alerta_color'] = "bg-yellow-400"
                    else:
                        o['alerta_text'] = "Vigente"
                        o['alerta_color'] = "bg-green-500"
                except ValueError:
                    pass
            
            fecha_agrupar_raw = str(o.get('fecha_envio') or "").strip()
            if fecha_agrupar_raw and fecha_agrupar_raw.lower() not in ['none', 'nan', 'nat', 'null']:
                try:
                    dt = datetime.strptime(fecha_agrupar_raw, "%Y-%m-%d")
                    mes_anio = f"{meses_espanol[dt.month - 1]} {dt.year}"
                except ValueError:
                    mes_anio = "Fecha Inválida"
            else:
                mes_anio = "Sin Fecha de Envío (Pendiente)"
                
            if mes_anio not in ordenes_agrupadas:
                ordenes_agrupadas[mes_anio] = []
            ordenes_agrupadas[mes_anio].append(o)
            
    return templates.TemplateResponse(request=request, name="ordenes.html", context={"ordenes_agrupadas": ordenes_agrupadas})

@app.post("/ordenes/actualizar/{orden_id}")
async def actualizar_orden(
    orden_id: int, 
    request: Request,
    fecha_envio: str = Form(None), 
    fecha_recepcion: str = Form(None),
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user:
        if "application/json" in request.headers.get("accept", "") or request.headers.get("x-requested-with") == "XMLHttpRequest":
            return Response(status_code=401)
        return RedirectResponse(url="/login", status_code=303)

    f_rec = fecha_recepcion if fecha_recepcion else None
    f_env = fecha_envio if fecha_envio else None
    estatus = "Despacho Recibido" if f_rec else "Enviada"

    supabase.table("ordenes_compra").update({
        "estatus": estatus,
        "fecha_envio": f_env,
        "fecha_recepcion": f_rec
    }).eq("id", orden_id).eq("usuario_id", user.id).execute()
    
    if "application/json" in request.headers.get("accept", "") or request.headers.get("x-requested-with") == "XMLHttpRequest":
        vencimiento_str = ""
        alerta_text = ""
        alerta_color = "transparent"

        if f_rec:
            res_oc = supabase.table("ordenes_compra").select("pagada, proveedores(dias_credito)").eq("id", orden_id).execute()
            if res_oc.data:
                oc_info = res_oc.data[0]
                prov_info = oc_info.get("proveedores") or {}
                dias_credito = prov_info.get("dias_credito", 30) or 30

                try:
                    hoy = datetime.now().date()
                    f_rec_date = datetime.strptime(f_rec, "%Y-%m-%d").date()
                    venc_date = f_rec_date + timedelta(days=int(dias_credito))
                    vencimiento_str = venc_date.strftime("%d/%m/%Y")
                    dias_restantes = (venc_date - hoy).days

                    if dias_restantes < 0:
                        alerta_text = f"Vencido ({abs(dias_restantes)}d)"
                        alerta_color = "bg-red-500"
                    elif dias_restantes <= 3:
                        alerta_text = f"Por vencer ({dias_restantes}d)"
                        alerta_color = "bg-yellow-400"
                    else:
                        alerta_text = "Vigente"
                        alerta_color = "bg-green-500"
                except ValueError:
                    pass

        return {
            "status": "ok", 
            "estatus": estatus,
            "vencimiento_factura_str": vencimiento_str,
            "alerta_text": alerta_text,
            "alerta_color": alerta_color
        }

    return RedirectResponse(url="/ordenes", status_code=303)

@app.post("/ordenes/pagar/{orden_id}")
async def actualizar_pago(orden_id: int, request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return {}
    
    data = await request.json()
    estado_pagada = data.get("pagada", False)
    
    supabase.table("ordenes_compra").update({"pagada": estado_pagada}).eq("id", orden_id).eq("usuario_id", user.id).execute()
    return {"status": "ok"}

@app.post("/ordenes/eliminar/{orden_id}")
def eliminar_orden(orden_id: int, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    supabase.table("ordenes_compra").delete().eq("id", orden_id).eq("usuario_id", user.id).execute()
    return RedirectResponse(url="/ordenes", status_code=303)

@app.post("/ordenes/eliminar_masivo")
async def eliminar_ordenes_masivo(request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        print("[DEBUG ELIMINAR] Error: Usuario no autenticado o token expirado.")
        return JSONResponse(status_code=401, content={"success": False, "message": "No autorizado"})
    
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        print(f"[DEBUG ELIMINAR] IDs recibidos desde el cliente: {raw_ids} | Usuario ID: {user.id}")

        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        
        if ids:
            resultado = supabase.table("ordenes_compra").delete().in_("id", ids).eq("usuario_id", user.id).execute()
            print(f"[DEBUG ELIMINAR] Respuesta de Supabase: {resultado}")
            
        return {"success": True, "message": f"{len(ids)} orden(es) eliminada(s)"}
    except Exception as e:
        print(f"[DEBUG ELIMINAR ERROR]:\n{traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

@app.get("/proveedores")
def vista_proveedores(request: Request, select: int = None, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
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
    
@app.post("/proveedores/importar-xml")
async def importar_proveedores_xml(archivo_xml: UploadFile = File(...), access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
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

@app.get("/proveedores/exportar-xml")
def exportar_proveedores_xml(request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
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

@app.get("/perfil")
def vista_perfil(request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res_perfil = supabase.table("perfiles").select("*").eq("usuario_id", user.id).maybe_single().execute()
    perfil = res_perfil.data if res_perfil and res_perfil.data else {"nombre_comprador": "", "cargo": ""}

    res_cats = supabase.table("categorias").select("*").eq("usuario_id", user.id).order("nombre").execute()
    categorias = res_cats.data if res_cats and res_cats.data else []

    return templates.TemplateResponse(request=request, name="perfil.html", context={
        "user": user,
        "perfil": perfil,
        "categorias": categorias
    })

@app.post("/perfil/guardar")
def guardar_perfil(
    nombre_comprador: str = Form(""),
    cargo: str = Form(""),
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res = supabase.table("perfiles").select("id").eq("usuario_id", user.id).execute()
    
    if res.data:
        supabase.table("perfiles").update({
            "nombre_comprador": nombre_comprador,
            "cargo": cargo
        }).eq("usuario_id", user.id).execute()
    else:
        supabase.table("perfiles").insert({
            "usuario_id": user.id,
            "nombre_comprador": nombre_comprador,
            "cargo": cargo
        }).execute()

    return RedirectResponse(url="/perfil", status_code=303)

@app.post("/perfil/cambiar-clave")
def cambiar_clave(nueva_password: str = Form(...), access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        supabase.auth.update_user({"password": nueva_password})
        return script_alerta_error("¡Contraseña actualizada con éxito!", redireccionar="/perfil")
    except Exception as e:
        return script_alerta_error(f"Error al cambiar contraseña: {str(e)}")
    
@app.post("/perfil/categorias/crear")
def crear_categoria(nombre: str = Form(...), access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if nombre.strip():
        supabase.table("categorias").insert({
            "usuario_id": user.id,
            "nombre": nombre.strip()
        }).execute()

    return RedirectResponse(url="/perfil", status_code=303)

@app.post("/perfil/categorias/actualizar/{cat_id}")
def actualizar_categoria(cat_id: int, nombre: str = Form(...), access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if nombre.strip():
        supabase.table("categorias").update({"nombre": nombre.strip()}).eq("id", cat_id).eq("usuario_id", user.id).execute()

    return RedirectResponse(url="/perfil", status_code=303)

@app.post("/perfil/categorias/eliminar/{cat_id}")
def eliminar_categoria(cat_id: int, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    supabase.table("categorias").delete().eq("id", cat_id).eq("usuario_id", user.id).execute()

    return RedirectResponse(url="/perfil", status_code=303)

@app.post("/proveedores/guardar")
def guardar_proveedor(
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
    user = obtener_usuario_actual(access_token)
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

@app.post("/proveedores/eliminar/{prov_id}")
def eliminar_proveedor(prov_id: int, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        res = supabase.table("proveedores").delete().eq("id", prov_id).execute()
        if not res.data:
            return script_alerta_error("No se pudo eliminar el proveedor. Es posible que ya no exista.", redireccionar="/proveedores")
    except Exception:
        return script_alerta_error("No se puede eliminar el proveedor porque tiene Órdenes de Compra asociadas a su registro.", redireccionar=f"/proveedores?select={prov_id}")

    return RedirectResponse(url="/proveedores", status_code=303)

@app.post("/recepciones/procesar-xml")
async def procesar_recepciones_xml(
    request: Request,
    archivos_xml: List[UploadFile] = File(...), 
    access_token: str = Cookie(None)
):
    es_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")
    user = obtener_usuario_actual(access_token)
    
    if not user:
        if es_ajax:
            return JSONResponse(status_code=401, content={"success": False, "mensaje": "No autorizado"})
        return RedirectResponse(url="/login", status_code=303)

    procesados_exito = []
    no_encontrados = []

    try:
        for archivo_xml in archivos_xml:
            if not archivo_xml.filename:
                continue
                
            contenido = await archivo_xml.read()
            if not contenido:
                continue

            arbol = ET.fromstring(contenido)
            registros = arbol.findall('.//Registro')
            if not registros:
                registros = arbol.findall('.//*')

            for reg in registros:
                nro_oc_raw = (reg.findtext('Nro_OrdenDeCompra') or reg.findtext('nro_ordendecompra') or "").strip()
                fechas_nodos = reg.findall('.//FechaREC') or reg.findall('.//fecharec')
                fecha_rec_raw = (fechas_nodos[-1].text or "").strip() if fechas_nodos else ""

                nro_oc_limpio = str(nro_oc_raw.lstrip('0'))

                if nro_oc_limpio and fecha_rec_raw:
                    fecha_formateada = None
                    dia, mes, anio = "", "", ""
                    
                    coincidencia = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', str(fecha_rec_raw))
                    if coincidencia:
                        dia = coincidencia.group(1).zfill(2)
                        mes = coincidencia.group(2).zfill(2)
                        anio_raw = coincidencia.group(3)
                        anio = anio_raw if len(anio_raw) == 4 else f"20{anio_raw}"
                        fecha_formateada = f"{anio}-{mes}-{dia}"
                    else:
                        coincidencia_iso = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', str(fecha_rec_raw))
                        if coincidencia_iso:
                            anio = coincidencia_iso.group(1)
                            mes = coincidencia_iso.group(2).zfill(2)
                            dia = coincidencia_iso.group(3).zfill(2)
                            fecha_formateada = f"{anio}-{mes}-{dia}"

                    if not fecha_formateada:
                        no_encontrados.append(nro_oc_limpio)
                        continue

                    res_oc = supabase.table("ordenes_compra") \
                        .select("id, numero_orden, proveedor, tienda_destino, proveedores(nombre)") \
                        .ilike("numero_orden", f"%{nro_oc_limpio}") \
                        .eq("usuario_id", user.id) \
                        .execute()

                    if res_oc.data and len(res_oc.data) > 0:
                        orden = res_oc.data[0]
                        orden_id = orden["id"]
                        num_orden_str = str(orden.get("numero_orden") or "")
                        
                        prov_obj = orden.get("proveedores")
                        if isinstance(prov_obj, dict) and prov_obj.get("nombre"):
                            prov_str = prov_obj.get("nombre")
                        elif orden.get("proveedor"):
                            prov_str = orden.get("proveedor")
                        else:
                            prov_str = "Sin Proveedor"

                        tienda_str = str(orden.get("tienda_destino") or "Sin Tienda")

                        supabase.table("ordenes_compra").update({
                            "fecha_recepcion": fecha_formateada,
                            "estatus": "Despacho Recibido"
                        }).eq("id", orden_id).execute()
                        
                        fecha_mostrar = f"{dia}/{mes}/{anio}" if (dia and mes and anio) else fecha_formateada

                        procesados_exito.append({
                            "numero_orden": num_orden_str,
                            "proveedor": prov_str,
                            "tienda_destino": tienda_str,
                            "fecha_recepcion": str(fecha_mostrar)
                        })
                    else:
                        no_encontrados.append(nro_oc_limpio)

        if es_ajax:
            return JSONResponse(content={
                "success": True,
                "procesados": procesados_exito,
                "no_encontrados": no_encontrados,
                "total_procesados": len(procesados_exito),
                "total_no_encontrados": len(no_encontrados)
            })

        return templates.TemplateResponse(
            request=request,
            name="resumen_xml.html",
            context={
                "procesados": procesados_exito,
                "no_encontrados": no_encontrados,
                "total_procesados": len(procesados_exito),
                "total_no_encontrados": len(no_encontrados)
            }
        )

    except ET.ParseError:
        if es_ajax:
            return JSONResponse(status_code=400, content={"success": False, "mensaje": "Uno de los archivos XML no tiene un formato válido."})
        return script_alerta_error("Uno de los archivos XML subidos no tiene un formato correcto.", redireccionar="/escanear")
    except Exception as e:
        error_msg = str(e).replace("'", "").replace('"', '').replace("\n", " ")
        if es_ajax:
            return JSONResponse(status_code=500, content={"success": False, "mensaje": f"Error: {error_msg}"})
        return script_alerta_error(f"Error procesando XML en servidor: {error_msg}", redireccionar="/escanear")
    
@app.get("/escanear")
def vista_escanear(request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="escanear.html", context={"lista_datos": None})

@app.post("/escanear/procesar")
async def procesar_pdf(
    request: Request, 
    archivos_pdf: List[UploadFile] = File(...), 
    access_token: str = Cookie(None)
):
    es_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")
    
    user = obtener_usuario_actual(access_token)
    if not user:
        if es_ajax:
            return JSONResponse(status_code=401, content={"success": False, "mensaje": "Sesión expirada. Por favor, inicia sesión nuevamente."})
        return RedirectResponse(url="/login", status_code=303)

    lista_datos = []
    for archivo in archivos_pdf:
        if not archivo.filename:
            continue
        contenido_bytes = await archivo.read()
        pdf_en_memoria = io.BytesIO(contenido_bytes)
        datos_extraidos = extraer_datos_oc(pdf_en_memoria)
        
        prods_procesados = []
        monto_calculado_total = 0.0
        
        for p in datos_extraidos.get("productos", []):
            cod_st = str(p.get("codigo", "")).strip()
            desc = p.get("descripcion", "")
        
            match_extra = re.search(r'^(.*?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)$', desc)
            if match_extra:
                desc = match_extra.group(1).strip()
                p["descripcion"] = desc
                p["pre"] = int(float(match_extra.group(2)))
                p["emp"] = int(float(match_extra.group(3)))
                p["empaques"] = p["emp"]

            emp = p.get("emp", 0)
            pre = p.get("pre", 1)

            if emp > 0 and pre > 0:
                cant = int(emp * pre)
            else:
                cant = int(round(sanitizar_numero(p.get("cantidad", 0))))

            precio_unitario = float(p.get("precio_unitario") or 0.0)
            
            res_p = supabase.table("productos").select("descripcion, precio").eq("codigo_st", cod_st).execute()
            if res_p.data and len(res_p.data) > 0:
                desc = res_p.data[0].get("descripcion") or desc
                if precio_unitario == 0.0:
                    precio_unitario = float(res_p.data[0].get("precio") or 0.0)
            
            subtotal = round(cant * precio_unitario, 2)
            monto_calculado_total += subtotal

            prods_procesados.append({
                "codigo": cod_st,
                "codigo_producto": cod_st,
                "descripcion": desc,
                "pre": pre,
                "unidad_manejo": pre,
                "emp": emp,
                "empaques": emp,
                "cantidad": cant,
                "precio_unitario": precio_unitario,
                "subtotal": subtotal
            })
        
        datos_extraidos["productos"] = prods_procesados
        if monto_calculado_total > 0 and datos_extraidos.get("monto_total", 0.0) == 0.0:
            datos_extraidos["monto_total"] = monto_calculado_total
        if not datos_extraidos:
            datos_extraidos = {
                "numero_orden": "",
                "proveedor": "",
                "tienda_destino": "",
                "fecha_emision": "",
                "fecha_envio": "",
                "monto_total": 0.0
            }
        
        prov_nombre = (datos_extraidos.get("proveedor") or "").strip()
        frecuencia_sugerida = 15
        if prov_nombre:
            try:
                res_p = supabase.table("proveedores").select("dias_despacho").ilike("nombre", prov_nombre).execute()
                if res_p.data and len(res_p.data) > 0 and res_p.data[0].get("dias_despacho") is not None:
                    frecuencia_sugerida = res_p.data[0]["dias_despacho"]
            except Exception:
                pass

        datos_extraidos["dias_despacho"] = frecuencia_sugerida
        datos_extraidos["nombre_archivo"] = archivo.filename
        lista_datos.append(datos_extraidos)

    if es_ajax:
        return JSONResponse(content={"success": True, "ordenes": lista_datos})

    return templates.TemplateResponse(request=request, name="escanear.html", context={"lista_datos": lista_datos})

@app.post("/ordenes/crear")
async def crear_orden(
    request: Request,
    numero_orden: str = Form(""),
    proveedor: str = Form(""),
    tienda_destino: str = Form(""),
    monto_total: Optional[str] = Form("0"),
    fecha_emision: Optional[str] = Form(None),
    fecha_envio: Optional[str] = Form(None),
    dias_inventario: Optional[str] = Form("15"),
    productos_json: str = Form("[]"),
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "mensaje": "No autorizado"})

    try:
        monto_total_val = sanitizar_numero(monto_total)
        dias_inv_val = int(sanitizar_numero(dias_inventario)) if dias_inventario else 15

        f_emision = fecha_emision.strip() if fecha_emision and fecha_emision.strip() else datetime.now().strftime("%Y-%m-%d")
        f_envio = fecha_envio.strip() if fecha_envio and fecha_envio.strip() else f_emision
        
        num_oc = numero_orden.strip()
        if num_oc:
            res_existente = supabase.table("ordenes_compra").select("id").eq("numero_orden", num_oc).eq("usuario_id", user.id).execute()
            if res_existente.data:
                return JSONResponse(status_code=400, content={"status": "error", "mensaje": f"La Orden de Compra N° {num_oc} ya se encuentra registrada."})

        prov_nombre = proveedor.strip()
        res_prov = supabase.table("proveedores").select("id").eq("nombre", prov_nombre).execute()
        if res_prov.data:
            proveedor_id = res_prov.data[0]["id"]
        else:
            res_ins = supabase.table("proveedores").insert({"nombre": prov_nombre}).execute()
            if not res_ins.data:
                return JSONResponse(status_code=500, content={"status": "error", "mensaje": "Error al registrar el proveedor en la base de datos."})
            proveedor_id = res_ins.data[0]["id"]

        res_oc = supabase.table("ordenes_compra").insert({
            "usuario_id": user.id,
            "numero_orden": numero_orden.strip(),
            "proveedor_id": proveedor_id,
            "tienda_destino": tienda_destino.strip(),
            "monto_total": monto_total_val,
            "fecha_emision": f_emision,
            "fecha_envio": f_envio,
            "dias_inventario": dias_inv_val,
            "estatus": "Enviada"
        }).execute()

        if not res_oc.data:
            return JSONResponse(status_code=500, content={"status": "error", "mensaje": "No se pudo guardar la orden de compra."})

        orden_id = res_oc.data[0]["id"]

        try:
            productos = json.loads(productos_json) if isinstance(productos_json, str) else productos_json
        except Exception:
            productos = []

        for prod in productos:
            print(f"[DEBUG BD] Payload recibido del producto: {prod}")
            
            codigo_raw = prod.get("codigo") or prod.get("codigo_producto") or prod.get("codigo_st")
            descripcion = prod.get("descripcion") or prod.get("nombre_producto") or "Sin descripción"

            candidatos_precio = []
            for key in ["precio_unitario", "precio", "costo_unitario", "costo", "precio_nuevo"]:
                val = prod.get(key)
                if val is not None:
                    try:
                        val_float = float(sanitizar_numero(val))
                        if val_float > 0 and val_float not in candidatos_precio:
                            candidatos_precio.append(val_float)
                    except (ValueError, TypeError):
                        pass

            precio_extraido = candidatos_precio[0] if candidatos_precio else 0.0

            if codigo_raw:
                codigo = str(codigo_raw).strip()
                if codigo.isdigit():
                    codigo = codigo.zfill(6)
                codigo_sin_ceros = codigo.lstrip("0")

                res_prod = supabase.table("productos").select("id, codigo_st, precio").eq("codigo_st", codigo).execute()
                if not res_prod.data and codigo != codigo_sin_ceros:
                    res_prod = supabase.table("productos").select("id, codigo_st, precio").eq("codigo_st", codigo_sin_ceros).execute()

                if res_prod.data:
                    prod_db = res_prod.data[0]
                    target_codigo = prod_db["codigo_st"]
                    precio_db = float(prod_db.get("precio") or 0.0)

                    precio_nuevo_detectado = None
                    for c in candidatos_precio:
                        if abs(c - precio_db) > 0.001:
                            precio_nuevo_detectado = c
                            break

                    if precio_nuevo_detectado is not None:
                        precio_extraido = precio_nuevo_detectado
                        supabase.table("productos").update({"precio": precio_extraido}).eq("codigo_st", target_codigo).execute()
                        print(f"[DEBUG BD] ¡PRECIO ACTUALIZADO EN BD! Código '{target_codigo}': Antes {precio_db} -> Ahora {precio_extraido}")
                    else:
                        print(f"[DEBUG BD] Código '{target_codigo}': Sin cambios de precio (BD: {precio_db} | Candidatos: {candidatos_precio})")
                else:
                    print(f"[DEBUG BD] Código '{codigo}' no existía en catálogo. Insertando...")
                    supabase.table("productos").insert({
                        "codigo_st": codigo,
                        "descripcion": descripcion,
                        "precio": precio_extraido
                    }).execute()

            emp_val = int(float(sanitizar_numero(prod.get("empaques") or prod.get("emp") or 0)))
            pre_val = int(float(sanitizar_numero(prod.get("unidad_manejo") or prod.get("pre") or 1)))

            cant_raw = float(sanitizar_numero(prod.get("cantidad") or 0))
            if emp_val > 0 and pre_val > 0 and cant_raw != (emp_val * pre_val):
                cant_val = int(emp_val * pre_val)
            else:
                cant_val = int(round(cant_raw))

            precio_final = precio_extraido if precio_extraido > 0 else float(sanitizar_numero(prod.get("precio_unitario") or 0))

            supabase.table("detalles_productos").insert({
                "orden_id": orden_id,
                "codigo": str(codigo_raw) if codigo_raw else "",
                "descripcion": descripcion,
                "cantidad": cant_val,
                "precio_unitario": precio_final,
                "pre": pre_val,
                "emp": emp_val
            }).execute()

        return JSONResponse(content={"status": "ok", "mensaje": "Orden guardada y precios actualizados."})

    except Exception as e:
        print(f"[DEBUG CREAR ORDEN ERROR]:\n{traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"status": "error", "mensaje": str(e)})

@app.get("/productos")
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

        # Incluir códigos ST y EAN dentro de las búsquedas por coincidencia parcial de texto
        condiciones = [
            f"codigo_st.ilike.{patron_busqueda}",   # Búsqueda parcial en código ST
            f"codigo_ean.ilike.{patron_busqueda}",  # Búsqueda parcial en código EAN
            f"descripcion.ilike.{patron_busqueda}", # Búsqueda parcial en descripción
            f"marca.ilike.{patron_busqueda}",       # Búsqueda parcial en marca
            f"departamento.ilike.{patron_busqueda}", # Búsqueda parcial en departamento
            f"grupo.ilike.{patron_busqueda}"        # Búsqueda parcial en grupo
        ]

        # Mantener la consulta exacta de ID numérico únicamente para el ID de proveedor
        if term_limpio.isdigit():
            val_num = int(term_limpio)  # Conversión a entero
            condiciones.append(f"proveedor_id.eq.{val_num}")  # Filtro por ID de proveedor

        if ids_prov:
            for pid in ids_prov:
                condiciones.append(f"proveedor_id.eq.{pid}")

        condicion_or = ",".join(condiciones)
        builder = builder.or_(condicion_or)

    productos_res = builder.order("descripcion", desc=False).limit(200).execute()
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
                cod_st = str(prod.get("codigo_st", "") or "")  # Convertir el codigo_st a texto de forma segura
                if cod_st == term_limpio:
                    return 0  # Coincidencia exacta (máxima prioridad)
                elif cod_st.startswith(term_limpio):
                    return 1  # El código comienza con los números ingresados
                elif term_limpio in cod_st:
                    return 2  # El código contiene los números ingresados
                return 3  # Coincidencia en descripción o demás campos (menor prioridad)

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

@app.post("/productos/guardar")
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

@app.post("/productos/eliminar/{producto_id}")
def eliminar_producto(producto_id: str, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    supabase.table("productos").delete().eq("id", producto_id).execute()

    return RedirectResponse(url="/productos", status_code=303)

@app.post("/productos/cargar-lista")
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

@app.get("/analisis-pedido")
def vista_analisis_pedido(request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res_prov = supabase.table("proveedores").select("id, nombre").order("nombre").execute()
    proveedores = res_prov.data if res_prov and res_prov.data else []

    return templates.TemplateResponse(request=request, name="analisis_pedido.html", context={
        "proveedores": proveedores
    })

@app.get("/api/productos/buscar-codigo/{codigo}")
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

@app.get("/api/clasificacion")
def api_obtener_clasificacion(
    proveedor_id: Optional[int] = None, 
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user or not proveedor_id:
        return []

    res = supabase.table("productos").select("departamento, grupo, subgrupo").eq("proveedor_id", proveedor_id).execute()
    productos = res.data or []

    resultado = []
    vistos = set()
    for p in productos:
        depto = p.get("departamento") or ""
        grupo = p.get("grupo") or ""
        subgrupo = p.get("subgrupo") or ""
        
        clave = (depto, grupo, subgrupo)
        if clave not in vistos:
            vistos.add(clave)
            resultado.append({
                "departamento": depto,
                "grupo": grupo,
                "subgrupo": subgrupo
            })

    return resultado

@app.get("/api/productos/importar-analisis")
def api_importar_productos_analisis(
    proveedor_id: Optional[int] = None,
    departamento: Optional[str] = "",
    grupo: Optional[str] = "",
    subgrupo: Optional[str] = "",
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user or not proveedor_id:
        return []

    query = supabase.table("productos").select("*").eq("proveedor_id", proveedor_id)

    if departamento and departamento.strip():
        query = query.eq("departamento", departamento.strip())
    if grupo and grupo.strip():
        query = query.eq("grupo", grupo.strip())
    if subgrupo and subgrupo.strip():
        query = query.eq("subgrupo", subgrupo.strip())

    res = query.execute()
    productos = res.data or []

    return [
        {
            "codigo": p.get("codigo_st") or p.get("codigo", ""),
            "descripcion": p.get("descripcion", ""),
            "unidad_manejo": p.get("unidad_manejo") or "1",
            "precio": float(p.get("precio") or 0.0)
        }
        for p in productos
    ]

@app.get("/ordenes/obtener_detalle/{numero_orden}")
async def obtener_detalle_oc(numero_orden: str, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return {"status": "error", "mensaje": "No autorizado", "productos": []}

    res = supabase.table("ordenes_compra").select("*, detalles_productos(*)").eq("numero_orden", numero_orden).eq("usuario_id", user.id).execute()
    
    if not res.data:
        return {"status": "error", "mensaje": "Orden no encontrada", "productos": []}
    
    orden = res.data[0]
    detalles = orden.get("detalles_productos") or []
    
    productos_list = []
    for dp in detalles:
        productos_list.append({
            "codigo": dp.get("codigo") or dp.get("codigo_producto") or "-",
            "descripcion": dp.get("descripcion") or dp.get("nombre_producto") or "Sin descripción",
            "pre": dp.get("pre") if dp.get("pre") is not None else dp.get("unidad_manejo", 1),
            "emp": dp.get("emp") if dp.get("emp") is not None else dp.get("empaques", 0),
            "cantidad": dp.get("cantidad", 0),
            "precio_unitario": float(dp.get("precio_unitario") or 0.0)
        })
            
    return {
        "status": "ok",
        "numero_orden": orden.get("numero_orden"),
        "productos": productos_list
    }

@app.post("/api/productos/actualizar-analisis")
def actualizar_productos_desde_analisis(productos: List[ProductoModificado], access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    for prod in productos:
        supabase.table("productos").update({
            "unidad_manejo": prod.unidad_manejo,
            "precio": prod.precio
        }).eq("codigo_st", prod.codigo).execute()
    
    return {"status": "success", "mensaje": "Productos actualizados correctamente"}