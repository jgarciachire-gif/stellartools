import io  # Manejo de streams de memoria
import re  # Expresiones regulares para extracción
from typing import List  # Definición de tipos
import xml.etree.ElementTree as ET  # Parseador XML
from fastapi import APIRouter, Request, File, UploadFile, Cookie  # FastAPI
from fastapi.responses import RedirectResponse, JSONResponse  # Respuestas HTTP
from fastapi.concurrency import run_in_threadpool  # Ejecución asíncrona de funciones bloqueantes
from pdf_processor import extraer_datos_oc  # Función externa de análisis PDF
from config import supabase, templates, obtener_usuario_actual, sanitizar_numero, script_alerta_error  # Entorno global

router = APIRouter()

@router.post("/recepciones/procesar-xml")
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

@router.get("/escanear")
def vista_escanear(request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="escanear.html", context={"lista_datos": None})

@router.post("/escanear/procesar")
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
        datos_extraidos = await run_in_threadpool(extraer_datos_oc, pdf_en_memoria)
        
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