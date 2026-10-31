import io  # Manejo de streams de memoria
import math
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
    archivos_xml: List[UploadFile] = File(default=[]),
    access_token: Optional[str] = Cookie(None),
    refresh_token: Optional[str] = Cookie(None)
):
    from datetime import datetime

    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return JSONResponse(status_code=401, content={
            "success": False,
            "mensaje": "Tu sesión venció. Inicia sesión y vuelve a intentar."
        })

    if not archivos_xml or len(archivos_xml) > 20:
        return JSONResponse(status_code=400, content={
            "success": False,
            "mensaje": "Selecciona entre 1 y 20 archivos XML."
        })

    resultado = {
        "success": True,
        "procesados": [],
        "detalles": [],
        "incierto": False,
        "repetidos": 0
    }

    def informar(estado, archivo, numero, motivo):
        resultado["detalles"].append({
            "estado": estado,
            "archivo": archivo,
            "numero_orden": numero,
            "motivo": motivo
        })

    def normalizar(numero):
        numero = str(numero or "").strip()
        return (
            numero.lstrip("0") or "0"
        ) if numero.isdecimal() else numero

    def fecha(valor):
        valor = str(valor or "").strip()

        for formato in (
            "%d/%m/%Y", "%d/%m/%y",
            "%d-%m-%Y", "%d-%m-%y"
        ):
            try:
                return datetime.strptime(valor, formato).date()
            except ValueError:
                pass

        return datetime.fromisoformat(
            valor.replace("Z", "+00:00")
        ).date()

    # Validar el tamaño completo antes de modificar órdenes.
    contenidos, total = [], 0

    for archivo in archivos_xml:
        contenido = await archivo.read(
            4 * 1024 * 1024 - total + 1
        )
        total += len(contenido)

        if total > 4 * 1024 * 1024:
            return JSONResponse(status_code=413, content={
                "success": False,
                "mensaje": (
                    "El lote supera los 4 MB. "
                    "No se realizaron cambios."
                )
            })

        contenidos.append((
            archivo.filename or "Sin nombre",
            contenido
        ))

    pendientes, firmas = {}, set()

    for nombre, contenido in contenidos:
        # Detectar archivos idénticos aunque tengan otro nombre.
        if contenido in firmas:
            informar(
                "Archivo repetido", nombre, "",
                "Omitido: su contenido ya está en este lote."
            )
            continue

        firmas.add(contenido)

        try:
            if not nombre.lower().endswith(".xml") or not contenido:
                raise ValueError(
                    "Selecciona un XML que no esté vacío."
                )

            try:
                texto = contenido.decode("utf-8-sig")
            except UnicodeDecodeError:
                texto = contenido.decode("latin-1")

            if "\x00" in texto or re.search(
                r"<!\s*(DOCTYPE|ENTITY)\b", texto, re.I
            ):
                raise ValueError(
                    "XML no compatible: utiliza UTF-8 o Latin-1, "
                    "sin DTD ni entidades."
                )

            texto = re.sub(
                r"<\?xml[^?]*\?>", "", texto, count=1
            ).strip()

            raiz = ET.fromstring(texto)

            # Admitir nombres con namespaces y diferencias de mayúsculas.
            for nodo in raiz.iter():
                nodo.tag = nodo.tag.rsplit("}", 1)[-1].lower()

            registros = [
                nodo for nodo in raiz.iter()
                if nodo.find("nro_ordendecompra") is not None
            ]

            if not registros:
                raise ValueError(
                    "El archivo no contiene registros "
                    "de recepción compatibles."
                )

        except (ValueError, ET.ParseError) as exc:
            informar("Archivo inválido", nombre, "", str(exc))
            continue

        for reg in registros:
            numero = normalizar(
                reg.findtext("nro_ordendecompra")
            )

            valores = [
                nodo.text
                for nodo in reg.iter("fecharec")
                if (nodo.text or "").strip()
            ]

            try:
                if not numero or not valores:
                    raise ValueError()

                ultima = max(fecha(valor) for valor in valores)

            except (ValueError, TypeError):
                informar(
                    "Registro inválido", nombre, numero,
                    "Falta el número o la fecha de recepción "
                    "no es válida."
                )
                continue

            # Consolidar cada número usando su fecha más reciente.
            anterior = pendientes.get(numero)

            if anterior:
                resultado["repetidos"] += 1

                if ultima <= anterior["fecha"]:
                    continue

            pendientes[numero] = {
                "archivo": nombre,
                "fecha": ultima
            }

    # Consultar todas las páginas para evitar resultados incompletos.
    mapa, inicio = {}, 0

    try:
        while pendientes:
            res = await (
                config.supabase_async.table("ordenes_compra")
                .select(
                    "id, numero_orden, fecha_recepcion, estatus, "
                    "tienda_destino, proveedores(nombre)"
                )
                .eq("usuario_id", user.id)
                .order("id")
                .range(inicio, inicio + 499)
                .execute()
            )

            filas = res.data or []

            if not filas:
                break

            for orden in filas:
                clave = normalizar(orden["numero_orden"])

                if clave in pendientes:
                    mapa.setdefault(clave, []).append(orden)

            inicio += len(filas)

    except Exception:
        return JSONResponse(status_code=503, content={
            "success": False,
            "mensaje": (
                "No se pudieron consultar tus órdenes. "
                "No se realizaron cambios."
            )
        })

    for numero, item in pendientes.items():
        nombre = item["archivo"]
        nueva = item["fecha"]

        # Conservar lo confirmado y detener escrituras tras un fallo incierto.
        if resultado["incierto"]:
            informar(
                "Pendiente", nombre, numero,
                "No se intentó actualizar tras el fallo anterior."
            )
            continue

        coincidencias = mapa.get(numero, [])

        if len(coincidencias) != 1:
            informar(
                "No encontrada"
                if not coincidencias else "Coincidencia ambigua",
                nombre,
                numero,
                "No existe entre tus órdenes."
                if not coincidencias else
                "Varias órdenes comparten el número; "
                "revisa proveedor y tienda."
            )
            continue

        orden = coincidencias[0]
        guardada = orden.get("fecha_recepcion")

        try:
            actual = fecha(guardada) if guardada else None
        except ValueError:
            informar(
                "Registro inválido", nombre, numero,
                "La fecha guardada requiere revisión manual."
            )
            continue

        if actual and nueva < actual:
            informar(
                "Recepción anterior", nombre, numero,
                "Se conservó la fecha más reciente "
                "que ya estaba guardada."
            )
            continue

        if (
            nueva == actual
            and orden.get("estatus") == "Despacho Recibido"
        ):
            informar(
                "Sin cambios", nombre, numero,
                "Esta recepción ya estaba registrada."
            )
            continue

        try:
            consulta = (
                config.supabase_async.table("ordenes_compra")
                .update({
                    "fecha_recepcion": nueva.isoformat(),
                    "estatus": "Despacho Recibido"
                })
                .eq("id", orden["id"])
                .eq("usuario_id", user.id)
            )

            # Evitar sobrescribir cambios realizados desde otra pestaña.
            for campo in ("fecha_recepcion", "estatus"):
                valor = orden.get(campo)

                consulta = (
                    consulta.is_(campo, "null")
                    if valor is None else
                    consulta.eq(campo, valor)
                )

            res = await consulta.select(
                "id, fecha_recepcion, estatus"
            ).execute()

            confirmadas = res.data or []

            if not any(
                fila.get("id") == orden["id"]
                and fila.get("fecha_recepcion") == nueva.isoformat()
                and fila.get("estatus") == "Despacho Recibido"
                for fila in confirmadas
            ):
                informar(
                    "No actualizada", nombre, numero,
                    "No se confirmó el cambio. Revisa permisos "
                    "o cambios desde otra pestaña."
                )
                continue

            proveedor = orden.get("proveedores") or {}

            resultado["procesados"].append({
                "numero_orden": orden["numero_orden"],
                "proveedor": proveedor.get(
                    "nombre", "Sin proveedor"
                ),
                "tienda_destino": (
                    orden.get("tienda_destino") or "Sin tienda"
                ),
                "fecha_recepcion": nueva.strftime("%d/%m/%Y")
            })

        except Exception:
            resultado["incierto"] = True

            informar(
                "Sin confirmar", nombre, numero,
                "Se interrumpió la confirmación. "
                "Comprueba el diario antes de reintentar."
            )

    resultado["total_procesados"] = len(resultado["procesados"])

    return JSONResponse(content=resultado)


@router.post("/escanear/procesar")
async def procesar_pdf(
    request: Request, 
    archivos_pdf: List[UploadFile] = File(default=[]),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    es_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")
    
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        if es_ajax:
            return JSONResponse(status_code=401, content={"success": False, "mensaje": "Sesión expirada. Por favor, inicia sesión nuevamente."})
        return RedirectResponse(url="/login", status_code=303)

    def error_carga(mensaje, status_code=400):
        return JSONResponse(status_code=status_code, content={
            "success": False, "mensaje": mensaje, "ordenes": [], "errores": []
        })

    if not archivos_pdf:
        return error_carga("Selecciona al menos un archivo PDF.")
    if len(archivos_pdf) > 20:
        return error_carga("Puedes procesar hasta 20 archivos por carga.")

    # Limitar la lectura también en el servidor, antes de iniciar la extracción.
    limite_bytes = 4 * 1024 * 1024
    total_bytes = 0
    contenidos = []
    for archivo in archivos_pdf:
        contenido = await archivo.read(limite_bytes - total_bytes + 1)
        total_bytes += len(contenido)
        if total_bytes > limite_bytes:
            return error_carga("Los archivos superan los 4 MB permitidos en total.", 413)
        contenidos.append((archivo.filename or "Sin nombre", contenido))

    # 1. Un archivo inválido no impide revisar los demás.
    errores = []
    advertencias = []
    archivos_extraidos = []
    todos_codigos_st = set()
    todos_proveedores = set()

    for nombre, contenido_bytes in contenidos:
        if not nombre.lower().endswith(".pdf") or not contenido_bytes:
            errores.append({"archivo": nombre, "mensaje": "Selecciona un PDF que no esté vacío."})
            continue
        if b"%PDF-" not in contenido_bytes[:1024]:
            errores.append({"archivo": nombre, "mensaje": "El contenido del archivo no corresponde a un PDF."})
            continue
        try:
            datos_extraidos = await run_in_threadpool(extraer_datos_oc, io.BytesIO(contenido_bytes))
            if datos_extraidos.get("error_extraccion"):
                raise ValueError(datos_extraidos["error_extraccion"])
            if not datos_extraidos.get("productos"):
                raise ValueError("No se detectaron productos. Usa un PDF con texto seleccionable y el formato de orden de compra compatible.")
        except Exception as exc:
            mensaje = str(exc) if isinstance(exc, ValueError) else "No se pudo leer el PDF. Comprueba que no esté dañado ni protegido."
            errores.append({"archivo": nombre, "mensaje": mensaje})
            continue
        
        for p in datos_extraidos.get("productos", []):
            cod_st = str(p.get("codigo", "")).strip()
            if cod_st:
                todos_codigos_st.add(cod_st)

        prov_nombre = (datos_extraidos.get("proveedor") or "").strip()
        if prov_nombre:
            todos_proveedores.add(prov_nombre)

        archivos_extraidos.append((nombre, datos_extraidos))

    # 2. Consultar Productos y Proveedores de forma masiva (solo 2 peticiones globales)
    mapa_productos = {}
    try:
        if todos_codigos_st:
            res_p = await config.supabase_async.table("productos") \
                .select("codigo_st, descripcion, precio") \
                .in_("codigo_st", list(todos_codigos_st)) \
                .execute()
            if res_p.data:
                for prod in res_p.data:
                    mapa_productos[prod["codigo_st"]] = prod
    except Exception:
        advertencias.append("No se pudo consultar el catálogo de productos. Se conservan los datos del PDF; revísalos antes de guardar.")

    mapa_proveedores = {}
    try:
        if todos_proveedores:
            res_prov = await config.supabase_async.table("proveedores") \
                .select("nombre, dias_despacho") \
                .execute()
            if res_prov.data:
                for prov in res_prov.data:
                    mapa_proveedores[prov["nombre"].strip().lower()] = prov.get("dias_despacho")
    except Exception:
        advertencias.append("No se pudieron consultar los días de despacho. Revisa los días inventario sugeridos.")

    # 3. Cruzar datos en memoria local
    lista_datos = []
    def completar_datos(filename, datos_extraidos):
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
            producto_encontrado = cod_st in mapa_productos
            if producto_encontrado:
                prod_db = mapa_productos[cod_st]
                desc = prod_db.get("descripcion") or desc
                if precio_unitario == 0.0:
                    precio_unitario = float(prod_db.get("precio") or 0.0)

            subtotal = round(cant * precio_unitario, 2)
            if cant < 0 or precio_unitario < 0 or not math.isfinite(subtotal):
                raise ValueError("Cantidad o precio inválidos.")
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
                "subtotal": subtotal,
                "encontrado_en_bd": producto_encontrado,
                "estado_producto": "encontrado" if producto_encontrado else "no_encontrado",
                "mensaje_catalogo": "" if producto_encontrado else "Producto no encontrado en catálogo"
            })

        datos_extraidos["productos"] = prods_procesados
        monto_pdf = float(datos_extraidos.get("monto_total") or 0)
        if not math.isfinite(monto_pdf) or monto_pdf < 0:
            raise ValueError("Monto total inválido.")
        datos_extraidos["monto_total"] = monto_pdf or monto_calculado_total

        prov_nombre = (datos_extraidos.get("proveedor") or "").strip()
        frecuencia_sugerida = mapa_proveedores.get(prov_nombre.lower(), 15) if prov_nombre else 15

        datos_extraidos["dias_despacho"] = frecuencia_sugerida
        datos_extraidos["nombre_archivo"] = filename
        return datos_extraidos

    for filename, datos_extraidos in archivos_extraidos:
        try:
            lista_datos.append(completar_datos(filename, datos_extraidos))
        except Exception:
            errores.append({"archivo": filename, "mensaje": "No se pudieron preparar los datos de esta orden. Revisa las cantidades y precios en el PDF original."})

    if es_ajax:
        return JSONResponse(status_code=200 if lista_datos else 422, content={
            "success": bool(lista_datos),
            "mensaje": f"{len(lista_datos)} orden(es) listas para revisar; {len(errores)} archivo(s) no procesados.",
            "ordenes": lista_datos, "errores": errores, "advertencias": advertencias
        })

    return templates.TemplateResponse(request=request, name="escanear.html", context={"lista_datos": lista_datos})
