import json  # Decodificación y codificación de JSON
import traceback  # Trazado detallado de errores de excepción
import math
from typing import Optional  # Tipado para valores nulos/opcionales
from datetime import datetime, timedelta  # Manejo de fechas y diferencias
from fastapi import APIRouter, Request, Form, Cookie, Response  # Controladores de FastAPI
from fastapi.responses import RedirectResponse, JSONResponse  # Formatos de respuesta
import config
from config import templates, obtener_usuario_actual, sanitizar_numero  # Contexto global

router = APIRouter()

@router.get("/ordenes")
async def listar_ordenes(
    request: Request,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res = await (
        config.supabase_async
        .table("ordenes_compra")
        .select(
            "id, numero_orden, proveedor, tienda_destino, "
            "fecha_envio, fecha_recepcion, monto_total, "
            "estatus, proveedor_id, "
            "proveedores(nombre, dias_credito), "
            "detalles_productos(codigo, descripcion, cantidad, "
            "precio_unitario, pre, emp)"
        )
        .eq("usuario_id", user.id)
        .order("fecha_envio", desc=True)
        .execute()
    )
    
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
            
            if tiene_fecha_rec and dias_credito:
                try:
                    f_rec = datetime.strptime(f_rec_raw, "%Y-%m-%d").date()
                    venc_date = f_rec + timedelta(days=int(dias_credito))
                    o['vencimiento_factura_str'] = venc_date.strftime("%d/%m/%Y")
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

@router.post("/ordenes/actualizar/{orden_id}")
async def actualizar_orden(
    orden_id: int, 
    request: Request,
    fecha_envio: str = Form(None), 
    fecha_recepcion: str = Form(None),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        if "application/json" in request.headers.get("accept", "") or request.headers.get("x-requested-with") == "XMLHttpRequest":
            return Response(status_code=401)
        return RedirectResponse(url="/login", status_code=303)

    f_rec = fecha_recepcion if fecha_recepcion else None
    f_env = fecha_envio if fecha_envio else None
    estatus = "Despacho Recibido" if f_rec else "Enviada"

    # Actualizar la OC actual.
    await (
        config.supabase_async
        .table("ordenes_compra")
        .update({
            "estatus": estatus,
            "fecha_envio": f_env,
            "fecha_recepcion": f_rec
        })
        .eq("id", orden_id)
        .eq("usuario_id", user.id)
        .execute()
    )

    if "application/json" in request.headers.get("accept", "") or request.headers.get("x-requested-with") == "XMLHttpRequest":
        vencimiento_str = ""

        if f_rec:
            res_oc = await config.supabase_async.table("ordenes_compra") \
                .select("proveedores(dias_credito)") \
                .eq("id", orden_id) \
                .eq("usuario_id", user.id) \
                .execute()
            
            if res_oc.data:
                oc_info = res_oc.data[0]
                prov_info = oc_info.get("proveedores") or {}
                dias_credito = prov_info.get("dias_credito", 30) or 30

                try:
                    f_rec_date = datetime.strptime(f_rec, "%Y-%m-%d").date()
                    venc_date = f_rec_date + timedelta(days=int(dias_credito))
                    vencimiento_str = venc_date.strftime("%d/%m/%Y")
                except ValueError:
                    pass

        return {
            "status": "ok", 
            "estatus": estatus,
            "vencimiento_factura_str": vencimiento_str
        }

    return RedirectResponse(url="/ordenes", status_code=303)

@router.post("/ordenes/eliminar/{orden_id}")
async def eliminar_orden(
    orden_id: int, 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    await config.supabase_async.table("ordenes_compra") \
        .delete() \
        .eq("id", orden_id) \
        .eq("usuario_id", user.id) \
        .execute()
        
    return RedirectResponse(url="/ordenes", status_code=303)

@router.post("/ordenes/eliminar_masivo")
async def eliminar_ordenes_masivo(
    request: Request, 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        print("[DEBUG ELIMINAR] Error: Usuario no autenticado o token expirado.")
        return JSONResponse(status_code=401, content={"success": False, "message": "No autorizado"})
    
    try:
        data = await request.json()
        raw_ids = data.get("ids", [])
        print(f"[DEBUG ELIMINAR] IDs recibidos desde el cliente: {raw_ids} | Usuario ID: {user.id}")

        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        
        if ids:
            resultado = await config.supabase_async.table("ordenes_compra") \
                .delete() \
                .in_("id", ids) \
                .eq("usuario_id", user.id) \
                .execute()
            print(f"[DEBUG ELIMINAR] Respuesta de Supabase: {resultado}")
            
        return {"success": True, "message": f"{len(ids)} orden(es) eliminada(s)"}
    except Exception as e:
        print(f"[DEBUG ELIMINAR ERROR]:\n{traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

@router.post("/ordenes/crear")
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
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "codigo": "sesion_expirada",
                "mensaje": "Tu sesión venció. Inicia sesión en otra pestaña y vuelve a intentar; conserva esta revisión abierta."
            }
        )

    try:
        # ========================================================
        # 1. NORMALIZAR DATOS
        # ========================================================
        def numero_valido(valor, campo, minimo=0, entero=False):
            try:
                if isinstance(valor, bool):
                    raise ValueError()
                numero = float(str(valor).strip())
            except (ValueError, TypeError):
                raise ValueError(f"{campo}: introduce un número válido.")
            if not math.isfinite(numero) or numero < minimo:
                raise ValueError(f"{campo}: el valor debe ser finito y mayor o igual a {minimo}.")
            if entero and not numero.is_integer():
                raise ValueError(f"{campo}: introduce un número entero.")
            return int(numero) if entero else numero

        monto_total_val = numero_valido(monto_total, "Monto total")
        dias_inv_val = numero_valido(dias_inventario or "15", "Días inventario", 1, entero=True)
        if dias_inv_val > 99:
            raise ValueError("Días inventario: el máximo es 99.")

        f_emision = (
            fecha_emision.strip()
            if fecha_emision and fecha_emision.strip()
            else ""
        )

        f_envio = (
            fecha_envio.strip()
            if fecha_envio and fecha_envio.strip()
            else f_emision
        )

        num_oc = numero_orden.strip()
        prov_nombre = proveedor.strip()
        tienda = tienda_destino.strip()
        if not num_oc or not prov_nombre or not tienda:
            raise ValueError("Completa el número de orden, el proveedor y la tienda destino.")
        try:
            datetime.strptime(f_emision, "%Y-%m-%d")
            datetime.strptime(f_envio, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Revisa las fechas de emisión y envío; deben ser fechas válidas.")

        # ========================================================
        # 2. PARSEAR PRODUCTOS
        # ========================================================
        try:
            productos = (
                json.loads(productos_json)
                if isinstance(productos_json, str)
                else productos_json
            )
        except (ValueError, TypeError):
            raise ValueError("No se pudo leer el detalle de productos. Vuelve a procesar el PDF.")

        if not isinstance(productos, list) or not productos:
            raise ValueError("La orden debe contener al menos un producto. Vuelve a procesar el PDF.")

        productos_rpc = []

        for prod in productos or []:
            if not isinstance(prod, dict):
                raise ValueError("El detalle contiene un producto inválido. Vuelve a procesar el PDF.")
            codigo_raw = (
                prod.get("codigo")
                or prod.get("codigo_producto")
                or prod.get("codigo_st")
            )

            descripcion = (
                prod.get("descripcion")
                or prod.get("nombre_producto")
                or "Sin descripción"
            )

            if not codigo_raw or not str(codigo_raw).strip():
                raise ValueError("Hay un producto sin código. Revisa el PDF original.")
            emp_val = numero_valido(prod.get("empaques", prod.get("emp", 0)), "Empaques", entero=True)
            pre_val = numero_valido(prod.get("unidad_manejo", prod.get("pre", 1)), "Unidad de manejo", 1, entero=True)
            cant_raw = numero_valido(prod.get("cantidad", 0), "Cantidad")

            cant_val = (
                int(emp_val * pre_val)
                if (
                    emp_val > 0
                    and pre_val > 0
                    and cant_raw != (emp_val * pre_val)
                )
                else int(round(cant_raw))
            )

            precio_final = numero_valido(prod.get("precio_unitario", prod.get("precio", 0)), "Precio unitario")

            productos_rpc.append({
                "codigo": str(codigo_raw) if codigo_raw else "",
                "descripcion": descripcion,
                "cantidad": cant_val,
                "precio_unitario": precio_final,
                "pre": pre_val,
                "emp": emp_val
            })

        # ========================================================
        # 3. UNA SOLA LLAMADA A SUPABASE
        # ========================================================
        res = await config.supabase_async.rpc(
            "crear_orden_completa",
            {
                "p_usuario_id": user.id,
                "p_numero_orden": num_oc,
                "p_proveedor": prov_nombre,
                "p_tienda_destino": tienda,
                "p_monto_total": monto_total_val,
                "p_fecha_emision": f_emision,
                "p_fecha_envio": f_envio,
                "p_dias_inventario": dias_inv_val,
                "p_productos": productos_rpc
            }
        ).execute()

        if not res.data:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "mensaje": "No se pudo guardar la orden de compra."
                }
            )

        return JSONResponse(
            content={
                "status": "ok",
                "mensaje": "Orden guardada con éxito."
            }
        )

    except ValueError as e:
        return JSONResponse(status_code=422, content={
            "status": "error", "codigo": "datos_invalidos", "mensaje": str(e)
        })
    except Exception as e:
        mensaje = str(e)

        # Mantener el mensaje de duplicado entendible para el usuario.
        if "ya se encuentra registrada" in mensaje.lower() or getattr(e, "code", None) == "23505":
            return JSONResponse(
                status_code=409,
                content={
                    "status": "error",
                    "codigo": "orden_duplicada",
                    "mensaje": "Esta orden ya está registrada. Comprueba el número de orden, el proveedor y la tienda en el diario antes de volver a guardarla."
                }
            )

        print(
            f"[DEBUG CREAR ORDEN ERROR]:\n"
            f"{traceback.format_exc()}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "codigo": "error_guardado",
                "mensaje": "No se pudo confirmar el guardado. Conserva esta revisión y comprueba el diario antes de reintentar."
            }
        )

@router.get("/ordenes/obtener_detalle/{numero_orden}")
async def obtener_detalle_oc(
    numero_orden: str,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "mensaje": "No autorizado",
                "productos": []
            }
        )

    try:
        # El número de OC se conserva como texto para mantener ceros iniciales.
        numero_orden = numero_orden.strip()

        res = await (
            config.supabase_async
            .table("ordenes_compra")
            .select(
                "id, numero_orden, "
                "detalles_productos("
                "codigo, descripcion, cantidad, "
                "precio_unitario, pre, emp, grupo"
                ")"
            )
            .eq("numero_orden", numero_orden)
            .eq("usuario_id", user.id)
            .limit(1)
            .execute()
        )

        if not res.data:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "mensaje": "Orden no encontrada",
                    "productos": []
                }
            )

        orden = res.data[0]

        detalles = orden.get("detalles_productos") or []

        productos_list = []

        for dp in detalles:
            productos_list.append({
                "codigo": dp.get("codigo") or "-",
                "descripcion": (
                    dp.get("descripcion")
                    or "Sin descripción"
                ),
                "grupo": (
                    dp.get("grupo")
                    or "Sin Grupo"
                ),
                "pre": (
                    dp.get("pre")
                    if dp.get("pre") is not None
                    else 1
                ),
                "emp": (
                    dp.get("emp")
                    if dp.get("emp") is not None
                    else 0
                ),
                "cantidad": dp.get("cantidad") or 0,
                "precio_unitario": float(
                    dp.get("precio_unitario") or 0
                )
            })

        return JSONResponse(
            content={
                "status": "ok",
                "numero_orden": orden.get("numero_orden"),
                "productos": productos_list
            }
        )

    except Exception as e:
        print(
            "[DEBUG DETALLE OC ERROR]:\n"
            f"{traceback.format_exc()}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "mensaje": "Error interno al consultar el detalle de la orden.",
                "productos": []
            }
        )
