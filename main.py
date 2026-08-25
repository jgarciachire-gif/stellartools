import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Response, Cookie, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional
import pandas as pd
from datetime import datetime, timedelta, date
from pdf_processor import extraer_datos_oc
import os
import io
import xml.etree.ElementTree as ET
import json
from fastapi import Form
from supabase import create_client, Client
import traceback


SUPABASE_URL = "https://wrcbuseidkupjndpovdd.supabase.co"
SUPABASE_KEY = "sb_publishable_m6ayEiPYF_dIWiNf-9kRog_j-HbKhwA"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="Control de Compras", version="2.0")
# Silencia las peticiones automáticas de Chrome DevTools para evitar falsos logs 404
@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def chrome_devtools_silencer():
    return Response(status_code=204) # Retorna 204 No Content sin generar alertas en servidor

def obtener_usuario_actual(access_token: str = Cookie(None)):
    if not access_token:
        return None
    try:
        user_response = supabase.auth.get_user(access_token)
        return user_response.user
    except Exception:
        return None

def script_alerta_error(mensaje: str, redireccionar: str = None) -> HTMLResponse:
    
    msj_limpio = mensaje.replace("'", "\\'").replace("\n", " ")
    if redireccionar:
        js = f"<script>alert('{msj_limpio}'); window.location.href='{redireccionar}';</script>"
    else:
        js = f"<script>alert('{msj_limpio}'); window.history.back();</script>"
    return HTMLResponse(content=js)

def script_alerta_modal(tipo: str, titulo: str, mensaje: str, redireccionar: str = "/login") -> RedirectResponse:
    import urllib.parse
    msj_enc = urllib.parse.quote(mensaje)
    tit_enc = urllib.parse.quote(titulo)
    return RedirectResponse(url=f"{redireccionar}?msg_tipo={tipo}&msg_titulo={tit_enc}&msg_texto={msj_enc}", status_code=303)

@app.get("/login")
def vista_login(request: Request):
    token = request.cookies.get("access_token")
    if obtener_usuario_actual(token):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})

@app.post("/registro")
def procesar_registro(email: str = Form(...), password: str = Form(...)):
    try:
        # Supabase envía automáticamente el correo de confirmación
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
        return script_alerta_modal(
            tipo="error", 
            titulo="Error de Acceso", 
            mensaje="Credenciales incorrectas o correo no verificado aún."
        )

@app.post("/recuperar-password")
def enviar_recuperacion(request: Request, email: str = Form(...)):
    try:
        # Define la URL de retorno apuntando al endpoint de reset
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
    return templates.TemplateResponse(request, "login.html", {"reset_mode": True})

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

    # Obtenemos las OCs ordenadas por ID ascendente para evaluar su orden cronológico de registro
    res_oc = supabase.table("ordenes_compra").select("*, proveedores(nombre)").eq("usuario_id", user.id).order("id", desc=False).execute()
    
    proveedores_desglose = {}
    hoy = datetime.now().date()

    if res_oc.data:
        # Agrupar todas las órdenes por proveedor y tienda
        agrupado = {}
        for row in res_oc.data:
            prov_obj = row.get("proveedores")
            prov = prov_obj["nombre"] if prov_obj else (row.get('proveedor') or "Sin Proveedor")
            tienda = row.get('tienda_destino') or "Sin Tienda Asignada"
            
            key = (prov, tienda)
            if key not in agrupado:
                agrupado[key] = []
            agrupado[key].append(row)

        # Procesar la selección de la OC principal a mostrar por cada (Proveedor, Tienda)
        for (prov, tienda), lista_ocs in agrupado.items():
            if prov not in proveedores_desglose:
                proveedores_desglose[prov] = {}

            # 1. Separar OCs con recepción y OCs solo enviadas
            ocs_recibidas = []
            ocs_enviadas = []
            
            for oc in lista_ocs:
                f_rec_raw = str(oc.get('fecha_recepcion') or "").strip()
                tiene_fecha_rec = f_rec_raw != "" and f_rec_raw.lower() not in ['none', 'nan', 'nat', 'null']
                if tiene_fecha_rec:
                    ocs_recibidas.append(oc)
                else:
                    ocs_enviadas.append(oc)

            # Determinamos la OC activa a mostrar según prioridad:
            # - Si hay nueva OC enviada, la anterior con recepción cambia su estatus visible a "Nueva OC enviada"
            # - La última OC recibida se mantiene en pantalla hasta que la nueva OC cambie a "Despacho Recibido"
            if ocs_recibidas:
                oc_seleccionada = ocs_recibidas[-1] # La última recibida
                if ocs_enviadas:
                    # Existe una nueva OC en estatus "Enviada" posterior a la última recibida
                    estatus_oc = "Nueva OC enviada"
                else:
                    estatus_oc = "Despacho Recibido"
            else:
                # No hay recepciones registradas aún para esta tienda/proveedor
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

    return templates.TemplateResponse(request, "dashboard.html", {
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
            
    return templates.TemplateResponse(request, "ordenes.html", {"ordenes_agrupadas": ordenes_agrupadas})

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
    
    # Respuesta asíncrona para evitar recargar la página y mantener el filtro activo
    if "application/json" in request.headers.get("accept", "") or request.headers.get("x-requested-with") == "XMLHttpRequest":
        return {"status": "ok", "estatus": estatus}

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
            # Ejecuta la eliminación en Supabase
            resultado = supabase.table("ordenes_compra").delete().in_("id", ids).eq("usuario_id", user.id).execute()
            print(f"[DEBUG ELIMINAR] Respuesta de Supabase: {resultado}")
            
        return {"success": True, "message": f"{len(ids)} orden(es) eliminada(s)"}
    except Exception as e:
        print(f"[DEBUG ELIMINAR ERROR]:\n{traceback.format_exc()}") # Imprime la traza completa del error en la terminal
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# Modifica el endpoint GET de proveedores para incluir etiquetas y trazabilidad
@app.get("/proveedores")
def vista_proveedores(request: Request, select: int = None, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Obtenemos lista de proveedores
    res = supabase.table("proveedores").select("*").order("nombre").execute()
    proveedores = res.data if res and res.data else []

    # Obtenemos la lista global de categorías/etiquetas disponibles para autocompletar o asignar
    res_cats = supabase.table("categorias").select("*").eq("usuario_id", user.id).order("nombre").execute()
    categorias_disponibles = res_cats.data if res_cats and res_cats.data else []

    prov_obj = None
    if select:
        res_sel = supabase.table("proveedores").select("*").eq("id", select).maybe_single().execute()
        if res_sel and res_sel.data:
            prov_obj = res_sel.data

    return templates.TemplateResponse(request, "proveedores.html", {
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

# Endpoint para generar y descargar el reporte de proveedores en formato XML
@app.get("/proveedores/exportar-xml")
def exportar_proveedores_xml(request: Request, access_token: str = Cookie(None)): # Define la ruta GET y obtiene el token de sesión
    user = obtener_usuario_actual(access_token) # Valida el usuario autenticado
    if not user: # Redirige si la sesión expiró o no existe
        return RedirectResponse(url="/login", status_code=303) # Redirección limpia al login

    res = supabase.table("proveedores").select("*").order("nombre").execute() # Consulta todos los proveedores de la base de datos
    proveedores = res.data if res and res.data else [] # Extrae el listado de proveedores

    root = ET.Element("Proveedores") # Crea el nodo raíz principal del documento XML
    for p in proveedores: # Itera sobre cada registro de proveedor
        item = ET.SubElement(root, "Proveedor") # Subnodo individual por cada proveedor
        ET.SubElement(item, "Codigo").text = str(p.get("codigo") or "") # Agrega nodo Código
        ET.SubElement(item, "Nombre").text = str(p.get("nombre") or "") # Agrega nodo Nombre / Razón Social
        ET.SubElement(item, "Contacto").text = str(p.get("contacto") or "") # Agrega nodo Contacto / Atención
        ET.SubElement(item, "Telefono").text = str(p.get("telefono") or "") # Agrega nodo Teléfono
        ET.SubElement(item, "Email").text = str(p.get("email") or "") # Agrega nodo Correo Electrónico
        ET.SubElement(item, "DiasCredito").text = str(p.get("dias_credito") if p.get("dias_credito") is not None else 0) # Agrega Días de Crédito
        ET.SubElement(item, "FrecuenciaPedidos").text = str(p.get("dias_despacho") if p.get("dias_despacho") is not None else 3) # Agrega Frecuencia de Pedidos
        
        cats = p.get("categorias") or [] # Obtiene la lista de categorías o asigna lista vacía
        if isinstance(cats, list): # Verifica si es una lista
            cats_str = ", ".join([str(c) for c in cats]) # Une las etiquetas separadas por coma en una sola celda/texto
        else:
            cats_str = str(cats) # Convierte a texto si ya venía como string
        ET.SubElement(item, "Categorias").text = cats_str # Agrega nodo Categorías / Etiquetas unificadas

    xml_data = ET.tostring(root, encoding="utf-8", method="xml") # Genera el contenido XML en bytes codificados
    
    return Response( # Devuelve la respuesta para la descarga del archivo en el navegador
        content=xml_data, # Contenido binario del XML
        media_type="application/xml", # Cabecera MIME type XML
        headers={"Content-Disposition": "attachment; filename=proveedores.xml"} # Fuerza la descarga con el nombre proveedores.xml
    )

@app.get("/perfil")
def vista_perfil(request: Request, access_token: str = Cookie(None)):
    # Valida la sesión activa del usuario
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Consulta el perfil usando el método .maybe_single() para evitar errores si no existe el registro
    res_perfil = supabase.table("perfiles").select("*").eq("usuario_id", user.id).maybe_single().execute()
    perfil = res_perfil.data if res_perfil and res_perfil.data else {"nombre_comprador": "", "cargo": ""}

    # Consulta las categorías asignadas
    res_cats = supabase.table("categorias").select("*").eq("usuario_id", user.id).order("nombre").execute()
    categorias = res_cats.data if res_cats and res_cats.data else []

    return templates.TemplateResponse(request, "perfil.html", {
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
    # Valida la sesión
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Verifica si el perfil ya existe para actualizarlo o crearlo
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
    # Valida la sesión activa del usuario
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        # Actualiza la clave del usuario autenticado directamente en Supabase Auth
        supabase.auth.update_user({"password": nueva_password})
        return script_alerta_error("¡Contraseña actualizada con éxito!", redireccionar="/perfil")
    except Exception as e:
        return script_alerta_error(f"Error al cambiar contraseña: {str(e)}")
    
@app.post("/perfil/categorias/crear")
def crear_categoria(nombre: str = Form(...), access_token: str = Cookie(None)):
    # Valida la sesión
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Inserta nueva etiqueta si el nombre no está vacío
    if nombre.strip():
        supabase.table("categorias").insert({
            "usuario_id": user.id,
            "nombre": nombre.strip()
        }).execute()

    return RedirectResponse(url="/perfil", status_code=303)
@app.post("/perfil/categorias/actualizar/{cat_id}") # Ruta POST para modificar una categoría específica
def actualizar_categoria(cat_id: int, nombre: str = Form(...), access_token: str = Cookie(None)): # Recibe ID de la categoría y nuevo nombre
    user = obtener_usuario_actual(access_token) # Verifica la sesión del usuario
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if nombre.strip(): # Valida que el texto no esté vacío
        supabase.table("categorias").update({"nombre": nombre.strip()}).eq("id", cat_id).eq("usuario_id", user.id).execute() # Actualiza el nombre asegurando propiedad del usuario

    return RedirectResponse(url="/perfil", status_code=303) # Redirige de vuelta a la vista de perfil

@app.post("/perfil/categorias/eliminar/{cat_id}")
def eliminar_categoria(cat_id: int, access_token: str = Cookie(None)):
    # Valida la sesión y restringe eliminación solo a registros propios
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    supabase.table("categorias").delete().eq("id", cat_id).eq("usuario_id", user.id).execute()

    return RedirectResponse(url="/perfil", status_code=303)


# Colocar en main.py antes de @app.post("/proveedores/eliminar/{prov_id}")
@app.post("/proveedores/guardar")
def guardar_proveedor(
    id: Optional[str] = Form(None), # Recibe el ID como texto opcional para evitar error 422 si viene ""
    codigo: str = Form(""), # Código de proveedor opcional
    nombre: Optional[str] = Form(""), # Recibe el nombre como opcional para evitar rechazos 422 si llega vacío
    contacto: str = Form(""), # Contacto de atención opcional
    telefono: str = Form(""), # Teléfono opcional
    email: str = Form(""), # Correo electrónico opcional
    dias_credito: Optional[str] = Form("0"), # Días de crédito recibidos como texto seguro
    dias_despacho: Optional[str] = Form("3"), # Días de despacho recibidos como texto seguro
    categorias: str = Form("[]"), # Arreglo de etiquetas en formato JSON
    access_token: str = Cookie(None) # Token de autenticación del usuario
):
    # Verifica la sesión activa del usuario
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Convierte el ID de texto a entero solo si contiene un número válido
    prov_id = int(id) if id and id.strip().isdigit() else None

    # Convierte los campos numéricos de forma segura evitando excepciones
    credito_num = int(dias_credito) if dias_credito and dias_credito.strip().isdigit() else 0
    despacho_num = int(dias_despacho) if dias_despacho and dias_despacho.strip().isdigit() else 3

    # Decodifica la cadena JSON de categorías
    try:
        lista_categorias = json.loads(categorias)
    except Exception:
        lista_categorias = []

    # Genera la traza de auditoría con fecha actual y correo del usuario
    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    usuario_str = user.email if user and hasattr(user, 'email') else "Usuario"
    historial_mod = f"Última modificación hecha por {usuario_str} el {fecha_actual}."

    # Estructura de datos limpia y saneada para Supabase
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

    # Si prov_id tiene un entero válido, actualiza; de lo contrario, inserta nuevo registro
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
        # Intenta eliminar directamente el registro
        res = supabase.table("proveedores").delete().eq("id", prov_id).execute()
        if not res.data:
            return script_alerta_error("No se pudo eliminar el proveedor. Es posible que ya no exista.", redireccionar="/proveedores")
    except Exception as e:
        # Manejo de restricción por Clave Foránea en Base de Datos
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
                    import re
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

                    res_oc = supabase.table("ordenes_compra").select("id, numero_orden, proveedor, tienda_destino").ilike("numero_orden", f"%{nro_oc_limpio}").eq("usuario_id", user.id).execute()

                    if res_oc.data and len(res_oc.data) > 0:
                        orden = res_oc.data[0]
                        orden_id = orden["id"]
                        num_orden_str = str(orden.get("numero_orden", ""))
                        prov_str = str(orden.get("proveedor", "N/A"))
                        tienda_str = str(orden.get("tienda_destino", "N/A"))

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
            request,
            "resumen_xml.html",
            {
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
    return templates.TemplateResponse(request, "escanear.html", {"lista_datos": None})

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

    return templates.TemplateResponse(request, "escanear.html", {
        "lista_datos": lista_datos
    })

@app.post("/ordenes/crear")
def crear_orden_manual(
    numero_orden: str = Form(...),
    proveedor: str = Form(...),
    tienda_destino: str = Form(...),
    monto_total: float = Form(0.0),
    fecha_emision: str = Form(...),
    dias_inventario: int = Form(...),
    fecha_envio: str = Form(""),
    productos_json: str = Form("[]"),
    ajax: bool = Form(False),
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user:
        if ajax: return {"status": "error", "mensaje": "No autorizado"}
        return RedirectResponse(url="/login", status_code=303)

    res_existe = supabase.table("ordenes_compra").select("id").eq("numero_orden", numero_orden).eq("usuario_id", user.id).execute()
    if res_existe.data and len(res_existe.data) > 0:
        if ajax:
            return {"status": "error", "mensaje": f"La Orden N° {numero_orden} ya está registrada."}
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

    res_insert = supabase.table("ordenes_compra").insert({
        "usuario_id": user.id,
        "numero_orden": numero_orden,
        "proveedor_id": prov_id,
        "proveedor": proveedor,
        "tienda_destino": tienda_destino,
        "fecha_emision": fecha_emision,
        "fecha_envio": fecha_envio if fecha_envio else None,
        "monto_total": monto_total,
        "estatus": "Enviada",
        "dias_inventario": dias_inventario
    }).execute()

    if res_insert.data and res_insert.data[0].get("id"):
        nueva_oc_id = res_insert.data[0]["id"]
        try:
            lista_prods = json.loads(productos_json)
            for p in lista_prods:
                supabase.table("detalles_productos").insert({
                    "orden_id": nueva_oc_id,
                    "codigo": p.get("codigo"),
                    "descripcion": p.get("descripcion"),
                    "cantidad": p.get("cantidad"),
                    "precio_unitario": p.get("precio_unitario")
                }).execute()
        except Exception:
            pass
            
    if ajax:
        return {"status": "ok", "mensaje": "Orden guardada con éxito"}
        
    return RedirectResponse(url="/ordenes", status_code=303)

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
    # Valida la sesión activa del usuario
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    busqueda_query = request.query_params.get("q", "")
    tags_query = request.query_params.get("tags", "")
    
    # Inicializa la consulta trayendo los productos y su relación con proveedores
    builder = supabase.table("productos").select("*, proveedores(nombre)")

    # Recopila los términos de búsqueda ingresados
    terminos = []
    if busqueda_query.strip():
        terminos.append(busqueda_query.strip())
    if tags_query.strip():
        terminos.extend([t.strip() for t in tags_query.split(",") if t.strip()])

    # Aplica los filtros acumulativos por cada término
    for term in terminos:
        palabras = term.strip().split()
        patron_busqueda = f"%{'%'.join(palabras)}%" if palabras else "%"

        # Consulta IDs de proveedores coincidentes
        res_prov = supabase.table("proveedores").select("id").ilike("nombre", patron_busqueda).execute()
        ids_prov = [str(p["id"]) for p in res_prov.data] if res_prov.data else []

        # Lista de condiciones OR en la tabla productos
        condiciones = [
            f"codigo_st.ilike.{patron_busqueda}",
            f"codigo_ean.ilike.{patron_busqueda}",
            f"descripcion.ilike.{patron_busqueda}",
            f"marca.ilike.{patron_busqueda}",
            f"departamento.ilike.{patron_busqueda}",
            f"grupo.ilike.{patron_busqueda}"
        ]

        # Filtra por la columna foránea correcta 'proveedor_id' si se hallaron proveedores
        if ids_prov:
            for pid in ids_prov:
                condiciones.append(f"proveedor_id.eq.{pid}")

        # Encadena la condición OR al builder actual sin reiniciar la consulta
        condicion_or = ",".join(condiciones) # Une las condiciones de texto y proveedor
        builder = builder.or_(condicion_or)

    # Limitar a 200 resultados activos para mantener fluidez visual
    productos_res = builder.order("descripcion", desc=False).limit(200).execute()
    productos = productos_res.data or []

    # Cargar lista de proveedores para la selección
    res_prov = supabase.table("proveedores").select("id, nombre").order("nombre").execute()
    proveedores = res_prov.data if res_prov and res_prov.data else []

    # Obtener el producto seleccionado si existe el parámetro select
    select_id = request.query_params.get("select")
    prov_obj = None

    if select_id:
        try:
            # Convierte a int si es numérico para coincidir con el tipo int8 de Supabase
            query_id = int(select_id) if str(select_id).isdigit() else select_id
            res_sel = supabase.table("productos").select("*").eq("id", query_id).execute()
            if res_sel.data:
                prov_obj = res_sel.data[0]
        except Exception as e:
            print("Error al obtener producto seleccionado:", e)

    # 2. Retornar la plantilla asegurando la clave 'prov_obj'
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
    # Verificar usuario autenticado solo por seguridad
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Estructura de datos global (sin usuario_id)
    payload = {
        "codigo_st": codigo_st,
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

    # Actualizar o insertar sin filtrar por usuario
    if id:
        supabase.table("productos").update(payload).eq("id", id).execute()
        prod_id = id
    else:
        res = supabase.table("productos").insert(payload).execute()
        prod_id = res.data[0]["id"] if res and res.data else ""

    import urllib.parse
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

    # Eliminar producto por su ID de manera global
    supabase.table("productos").delete().eq("id", producto_id).execute()

    return RedirectResponse(url="/productos", status_code=303)

@app.post("/productos/cargar-lista")
async def cargar_lista_productos(
    archivo: UploadFile = File(...),
    access_token: str = Cookie(None)
):
    # Validar autenticación de usuario
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    contenido = await archivo.read()
    nombre = archivo.filename.lower()
    filas = []

    # 1. Lectura si el archivo es un Excel (.xlsx)
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

    # 2. Lectura si el archivo es XML (.xml)
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

    # 3. Formateo de datos
    payload = []
    for f in filas:
        raw_cod = f["codigo"].split(".")[0].strip()
        codigo_st = raw_cod.zfill(6) if raw_cod.isdigit() else raw_cod

        desc = f["descripcion"].strip().upper() if f["descripcion"] and f["descripcion"] != "nan" else ""
        marca = f["marca"].strip().upper() if f["marca"] and f["marca"] != "nan" else ""
        nombre_final = f"{desc} {marca}".strip() if marca else desc

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

    # Upsert global usando solo codigo_st como conflicto
    if payload:
        supabase.table("productos").upsert(
            payload, 
            on_conflict="codigo_st"
        ).execute()

    return RedirectResponse(url="/productos", status_code=303)