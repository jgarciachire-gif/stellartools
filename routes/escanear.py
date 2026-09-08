import io  # Manejo de streams de memoria
import re  # Expresiones regulares para extracción
from typing import List, Optional  # Definición de tipos
import xml.etree.ElementTree as ET  # Parseador XML
from fastapi import APIRouter, Request, File, UploadFile, Cookie  # FastAPI
from fastapi.responses import RedirectResponse, JSONResponse  # Respuestas HTTP
from fastapi.concurrency import run_in_threadpool  # Ejecución asíncrona de funciones bloqueantes
from pdf_processor import extraer_datos_oc  # Función externa de análisis PDF
import config
from config import templates, obtener_usuario_actual, sanitizar_numero, script_alerta_error  # Entorno global

router = APIRouter()

@router.get("/escanear")
async def vista_escanear(
    request: Request, 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="escanear.html", context={"lista_datos": None})


@router.post("/recepciones/procesar-xml")
async def procesar_recepciones_xml(
    request: Request,
    archivos_xml: List[UploadFile] = File(default=[]), # Permite recibir listas vacías sin lanzar error 422 de validación
    access_token: Optional[str] = Cookie(None), # Evita fallos de validación si la cookie no está presente
    refresh_token: Optional[str] = Cookie(None)
):
    es_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")
    # Validar sesión activa del usuario
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        if es_ajax:
            return JSONResponse(status_code=401, content={"success": False, "mensaje": "Sesión expirada."})
        return RedirectResponse(url="/login", status_code=303)

    # Validar manualmente si se enviaron archivos en la petición
    if not archivos_xml:
        if es_ajax:
            return JSONResponse(status_code=400, content={"success": False, "mensaje": "No se enviaron archivos XML."})
        return script_alerta_error("No se adjuntó ningún archivo XML", redireccionar="/escanear")

    procesados_exito = []
    no_encontrados = []

    try:
        items_a_procesar = []
        # Bucle de depuración para verificar qué archivos llegan en la consola
        for archivo_xml in archivos_xml:
            # Leer los bytes del archivo enviado por la petición
            contenido_bytes = await archivo_xml.read()
            # Imprimir en la terminal el nombre del archivo y cuántos bytes mide
            print(f"--> Archivo recibido: {archivo_xml.filename} | Tamaño: {len(contenido_bytes)} bytes")
            # Reposicionar el puntero de lectura al inicio para no dejar el archivo vacío
            await archivo_xml.seek(0)

        # 1. Parsear archivos XML con decodificación tolerante
        for archivo_xml in archivos_xml:
            if not archivo_xml.filename:
                continue
                
            contenido_bytes = await archivo_xml.read()
            if not contenido_bytes:
                continue

            try:
                # Decodificar manejando UTF-8 BOM y encodings alternativos de ERPs
                try:
                    contenido_str = contenido_bytes.decode('utf-8-sig')
                except UnicodeDecodeError:
                    contenido_str = contenido_bytes.decode('latin-1', errors='ignore')

                # Eliminar la declaración XML si interfiere con el string de Python
                contenido_str = re.sub(r'<\?xml[^\?]*\?>', '', contenido_str, count=1).strip()
                arbol = ET.fromstring(contenido_str)
            except Exception:
                no_encontrados.append(archivo_xml.filename)
                continue

            registros = arbol.findall('.//Registro')
            if not registros:
                registros = arbol.findall('.//*')

            for reg in registros:
                nro_oc_raw = (reg.findtext('Nro_OrdenDeCompra') or reg.findtext('nro_ordendecompra') or "").strip()
                fechas_nodos = reg.findall('.//FechaREC') or reg.findall('.//fecharec')
                fecha_rec_raw = (fechas_nodos[-1].text or "").strip() if fechas_nodos else ""

                nro_oc_limpio = str(nro_oc_raw.lstrip('0')) if nro_oc_raw.lstrip('0') else nro_oc_raw

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

                    items_a_procesar.append({
                        "nro_oc_limpio": nro_oc_limpio,
                        "fecha_formateada": fecha_formateada,
                        "dia": dia,
                        "mes": mes,
                        "anio": anio
                    })

        # 2. Consultar órdenes de compra únicamente pertenecientes al usuario actual
        res_ocs = await config.supabase_async.table("ordenes_compra") \
            .select("id, numero_orden, tienda_destino, proveedores(nombre)") \
            .eq("usuario_id", user.id) \
            .execute()

        ordenes_db = res_ocs.data or []
        
        mapa_ordenes = {}
        for o in ordenes_db:
            num_raw = str(o.get("numero_orden") or "").strip()
            num_str = num_raw.lstrip('0') if num_raw.lstrip('0') else num_raw
            mapa_ordenes[num_str] = o

        actualizaciones_payload = []

        for item in items_a_procesar:
            nro = item["nro_oc_limpio"]
            if nro in mapa_ordenes:
                orden = mapa_ordenes[nro]
                orden_id = orden["id"]
                num_orden_str = str(orden.get("numero_orden") or "")
                
                # Obtener nombre del proveedor desde la tabla relacionada
                prov_obj = orden.get("proveedores")
                prov_str = prov_obj.get("nombre") if isinstance(prov_obj, dict) else str(orden.get("proveedor") or "Sin Proveedor")
                tienda_str = str(orden.get("tienda_destino") or "Sin Tienda")

                actualizaciones_payload.append({
                    "id": orden_id,
                    "fecha_recepcion": item["fecha_formateada"],
                    "estatus": item["estatus"] if "estatus" in item else "Despacho Recibido"
                })

                dia, mes, anio = item["dia"], item["mes"], item["anio"]
                fecha_mostrar = f"{dia}/{mes}/{anio}" if (dia and mes and anio) else item["fecha_formateada"]

                procesados_exito.append({
                    "numero_orden": num_orden_str,
                    "proveedor": prov_str,
                    "tienda_destino": tienda_str,
                    "fecha_recepcion": str(fecha_mostrar)
                })
            else:
                no_encontrados.append(nro)

        # 3. Actualizar registros asegurando pertenencia al usuario actual
        for item_act in actualizaciones_payload:
            await config.supabase_async.table("ordenes_compra") \
                .update({
                    "fecha_recepcion": item_act["fecha_recepcion"],
                    "estatus": item_act["estatus"]
                }) \
                .eq("id", item_act["id"]) \
                .eq("usuario_id", user.id) \
                .execute()

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
                "request": request,
                "procesados": procesados_exito,
                "no_encontrados": no_encontrados,
                "total_procesados": len(procesados_exito),
                "total_no_encontrados": len(no_encontrados)
            }
        )

    except Exception as e:
        import traceback
        # Imprimir la traza completa del error en la consola de Uvicorn para ver el archivo y linea exactos
        print("\n================ ERROR AL PROCESAR XML ================")
        traceback.print_exc()
        print("========================================================\n")
        
        # Limpiar mensaje de error para evitar fallos de formato
        error_msg = str(e).replace("'", "").replace('"', '').replace("\n", " ")
        
        # Retornar respuesta JSON con el error explícito sin romper la app
        return JSONResponse(
            status_code=500, 
            content={"success": False, "mensaje": f"Error interno en servidor: {error_msg}"}
        )


@router.post("/escanear/procesar")
async def procesar_pdf(
    request: Request, 
    archivos_pdf: List[UploadFile] = File(...), 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    es_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")
    
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        if es_ajax:
            return JSONResponse(status_code=401, content={"success": False, "mensaje": "Sesión expirada. Por favor, inicia sesión nuevamente."})
        return RedirectResponse(url="/login", status_code=303)

    # 1. Extraer datos de todos los PDFs primero
    archivos_extraidos = []
    todos_codigos_st = set()
    todos_proveedores = set()

    for archivo in archivos_pdf:
        if not archivo.filename:
            continue
        contenido_bytes = await archivo.read()
        pdf_en_memoria = io.BytesIO(contenido_bytes)
        datos_extraidos = await run_in_threadpool(extraer_datos_oc, pdf_en_memoria)
        
        for p in datos_extraidos.get("productos", []):
            cod_st = str(p.get("codigo", "")).strip()
            if cod_st:
                todos_codigos_st.add(cod_st)

        prov_nombre = (datos_extraidos.get("proveedor") or "").strip()
        if prov_nombre:
            todos_proveedores.add(prov_nombre)

        archivos_extraidos.append((archivo.filename, datos_extraidos))

    # 2. Consultar Productos y Proveedores de forma masiva (solo 2 peticiones globales)
    mapa_productos = {}
    if todos_codigos_st:
        res_p = await config.supabase_async.table("productos") \
            .select("codigo_st, descripcion, precio") \
            .in_("codigo_st", list(todos_codigos_st)) \
            .execute()
        if res_p.data:
            for prod in res_p.data:
                mapa_productos[prod["codigo_st"]] = prod

    mapa_proveedores = {}
    if todos_proveedores:
        res_prov = await config.supabase_async.table("proveedores") \
            .select("nombre, dias_despacho") \
            .execute()
        if res_prov.data:
            for prov in res_prov.data:
                mapa_proveedores[prov["nombre"].strip().lower()] = prov.get("dias_despacho")

    # 3. Cruzar datos en memoria local
    lista_datos = []
    for filename, datos_extraidos in archivos_extraidos:
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

            # Cruce veloz en memoria local
            if cod_st in mapa_productos:
                prod_db = mapa_productos[cod_st]
                desc = prod_db.get("descripcion") or desc
                if precio_unitario == 0.0:
                    precio_unitario = float(prod_db.get("precio") or 0.0)

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
        frecuencia_sugerida = mapa_proveedores.get(prov_nombre.lower(), 15) if prov_nombre else 15

        datos_extraidos["dias_despacho"] = frecuencia_sugerida
        datos_extraidos["nombre_archivo"] = filename
        lista_datos.append(datos_extraidos)

    if es_ajax:
        return JSONResponse(content={"success": True, "ordenes": lista_datos})

    return templates.TemplateResponse(request=request, name="escanear.html", context={"lista_datos": lista_datos})