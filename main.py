from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Response, Cookie, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List
import pandas as pd
from datetime import datetime, timedelta, date
from pdf_processor import extraer_datos_oc
import os
import io
import xml.etree.ElementTree as ET
import json
from supabase import create_client, Client
import traceback

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

def script_alerta_error(mensaje: str, redireccionar: str = None) -> HTMLResponse:
    
    msj_limpio = mensaje.replace("'", "\\'").replace("\n", " ")
    if redireccionar:
        js = f"<script>alert('{msj_limpio}'); window.location.href='{redireccionar}';</script>"
    else:
        js = f"<script>alert('{msj_limpio}'); window.history.back();</script>"
    return HTMLResponse(content=js)

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
        
        return script_alerta_error("¡Registro exitoso! Ya puedes iniciar sesión con tu correo.", redireccionar="/login")
    except Exception as e:
        
        return script_alerta_error(f"Error al registrar: {str(e)}")

@app.post("/login")
def procesar_login(email: str = Form(...), password: str = Form(...)):
    try:
        # Autentica al usuario contra Supabase
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
        # Sanitiza la alerta en caso de credenciales incorrectas o fallo de conexión
        return script_alerta_error("Credenciales incorrectas o error en el servidor.")

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
                        f_rec_str = f_rec.strftime("%d/%m/%Y") # Formato dd/mm/aaaa para la vista
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
                        f_rec_str = f_rec_raw
                        estatus_inv = "Error de Fecha"
                        color_inv = "text-slate-600 bg-slate-100"
                        dias_mostrar = f"{dias_inv_totales} totales"
                else:
                    f_rec_str = "-"
                    estatus_inv = "Esperando Recepción"
                    color_inv = "text-blue-700 bg-blue-100"
                    dias_mostrar = "Sin iniciar"

                proveedores_desglose[prov][tienda] = {
                    "ultima_oc": row.get('numero_orden'),
                    "fecha_recepcion": f_rec_str, # Asigna la fecha formateada dd/mm/aaaa
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
            
            o['estatus'] = 'Recibido' if tiene_fecha_rec else 'Enviada'
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
                    elif dias_restantes <= 5:
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
    estatus = "Recibido" if f_rec else "Enviada"

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
        return {"status": "error", "mensaje": "No autorizado"}
    
    data = await request.json()
    ids = data.get("ids", [])
    
    if ids:
        supabase.table("ordenes_compra").delete().in_("id", ids).eq("usuario_id", user.id).execute()
        
    return {"status": "ok"}

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
# --- MÓDULO DE PERFIL DE COMPRADOR Y CATEGORÍAS ---

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

@app.post("/proveedores/guardar")
def guardar_proveedor(
    id: int = Form(None), 
    codigo: str = Form(""), 
    nombre: str = Form(...), 
    dias_credito: int = Form(30), 
    dias_despacho: int = Form(3), 
    contacto: str = Form(""), 
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    redirect_url = "/proveedores"

    if id:
        supabase.table("proveedores").update({
            "codigo": codigo,
            "nombre": nombre,
            "dias_credito": dias_credito,
            "dias_despacho": dias_despacho,
            "contacto": contacto
        }).eq("id", id).execute()
        
        redirect_url = f"/proveedores?select={id}"
    else:
        try:
            res = supabase.table("proveedores").insert({
                "codigo": codigo,
                "nombre": nombre,
                "dias_credito": dias_credito,
                "dias_despacho": dias_despacho,
                "contacto": contacto,
                "dias_inventario": 15
            }).execute()
            
            if res.data and len(res.data) > 0:
                nuevo_id = res.data[0]['id']
                redirect_url = f"/proveedores?select={nuevo_id}"
                
        except Exception as e:
            print(f"Error al guardar proveedor: {e}") 
            
    return RedirectResponse(url=redirect_url, status_code=303)

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

@app.post("/recepciones/procesar-xml")
async def procesar_recepciones_xml(
    request: Request,
    archivo_xml: UploadFile = File(...), 
    access_token: str = Cookie(None)
):
    # Validar sesión activa del usuario
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    contenido = await archivo_xml.read()
    
    try:
        arbol = ET.fromstring(contenido) # Parsear XML
        procesados_exito = [] # Lista de diccionarios procesados
        no_encontrados = []   # Lista de strings

        registros = arbol.findall('.//Registro')
        if not registros:
            registros = arbol.findall('.//*')

        for reg in registros:
            nro_oc_raw = (reg.findtext('Nro_OrdenDeCompra') or reg.findtext('nro_ordendecompra') or "").strip()
            fechas_nodos = reg.findall('.//FechaREC') or reg.findall('.//fecharec')
            fecha_rec_raw = (fechas_nodos[-1].text or "").strip() if fechas_nodos else ""

            nro_oc_limpio = str(nro_oc_raw.lstrip('0'))

            if nro_oc_limpio and fecha_rec_raw:
                import re  # Importación rápida para saneamiento de texto
                
                # Normalizar fecha YYYY-MM-DD limpiando textos extraños como horas o sufijos
                fecha_formateada = None
                dia, mes, anio = "", "", ""
                
                # Busca un patrón tipo DD/MM/YYYY o DD/MM/YY al inicio de la cadena
                coincidencia = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', str(fecha_rec_raw))
                if coincidencia:
                    dia = coincidencia.group(1).zfill(2)
                    mes = coincidencia.group(2).zfill(2)
                    anio_raw = coincidencia.group(3)
                    anio = anio_raw if len(anio_raw) == 4 else f"20{anio_raw}"
                    fecha_formateada = f"{anio}-{mes}-{dia}"
                else:
                    # Si no viene con barras, intenta extraer el formato YYYY-MM-DD
                    coincidencia_iso = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', str(fecha_rec_raw))
                    if coincidencia_iso:
                        anio = coincidencia_iso.group(1)
                        mes = coincidencia_iso.group(2).zfill(2)
                        dia = coincidencia_iso.group(3).zfill(2)
                        fecha_formateada = f"{anio}-{mes}-{dia}"

                # Si no se pudo sanitizar una fecha válida, se omite este registro para evitar romper la BD
                if not fecha_formateada:
                    no_encontrados.append(nro_oc_limpio)
                    continue

                # Consultar en Supabase
                res_oc = supabase.table("ordenes_compra").select("id, numero_orden, proveedor").ilike("numero_orden", f"%{nro_oc_limpio}").eq("usuario_id", user.id).execute()

                if res_oc.data and len(res_oc.data) > 0:
                    orden = res_oc.data[0]
                    orden_id = orden["id"]
                    num_orden_str = str(orden.get("numero_orden", ""))
                    prov_str = str(orden.get("proveedor", "N/A"))

                    # Actualizar fecha de recepción y estatus en Supabase
                    supabase.table("ordenes_compra").update({
                        "fecha_recepcion": fecha_formateada,
                        "estatus": "Recibido"
                    }).eq("id", orden_id).execute()
                    
                    # Formato de presentación para la tabla
                    fecha_mostrar = f"{dia}/{mes}/{anio}" if (dia and mes and anio) else fecha_formateada

                    # Insertar un diccionario estricto con valores de cadena
                    procesados_exito.append({
                        "numero_orden": num_orden_str,
                        "proveedor": prov_str,
                        "fecha_recepcion": str(fecha_mostrar)
                    })
                else:
                    no_encontrados.append(nro_oc_limpio)

        contexto = {
            "request": request,
            "procesados": procesados_exito,
            "no_encontrados": no_encontrados,
            "total_procesados": int(len(procesados_exito)),
            "total_no_encontrados": int(len(no_encontrados))
        }

        
        # Retornar vista HTML indicando explicitamente el nombre de la plantilla y el contexto
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
        return script_alerta_error("El archivo XML subido no tiene un formato correcto.", redireccionar="/escanear")
    except Exception as e:
        # Extrae la última línea del error para mostrarla directamente en el alert
        error_msg = str(e).replace("'", "").replace('"', '').replace("\n", " ")
        print(f"⚠️ ERROR XML VERCEL: {traceback.format_exc()}")
        
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
    user = obtener_usuario_actual(access_token)
    if not user:
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
        
        # Buscar la Frecuencia de Despacho registrada del proveedor en Supabase
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