import json  # Decodificación y codificación de JSON
import traceback  # Trazado detallado de errores de excepción
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

    res = await config.supabase_async.table("ordenes_compra") \
        .select("*, proveedores(nombre, dias_credito), detalles_productos(*)") \
        .eq("usuario_id", user.id) \
        .order("fecha_envio", desc=True) \
        .execute()
    
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

    await config.supabase_async.table("ordenes_compra").update({
        "estatus": estatus,
        "fecha_envio": f_env,
        "fecha_recepcion": f_rec
    }).eq("id", orden_id).eq("usuario_id", user.id).execute()
    
    if "application/json" in request.headers.get("accept", "") or request.headers.get("x-requested-with") == "XMLHttpRequest":
        vencimiento_str = ""
        alerta_text = ""
        alerta_color = "transparent"

        if f_rec:
            res_oc = await config.supabase_async.table("ordenes_compra") \
                .select("pagada, proveedores(dias_credito)") \
                .eq("id", orden_id) \
                .execute()
            
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

@router.post("/ordenes/pagar/{orden_id}")
async def actualizar_pago(
    orden_id: int, 
    request: Request, 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return {}
    
    data = await request.json()
    estado_pagada = data.get("pagada", False)
    
    await config.supabase_async.table("ordenes_compra") \
        .update({"pagada": estado_pagada}) \
        .eq("id", orden_id) \
        .eq("usuario_id", user.id) \
        .execute()
        
    return {"status": "ok"}

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
        return JSONResponse(status_code=401, content={"status": "error", "mensaje": "No autorizado"})

    try:
        monto_total_val = sanitizar_numero(monto_total)
        dias_inv_val = int(sanitizar_numero(dias_inventario)) if dias_inventario else 15

        f_emision = fecha_emision.strip() if fecha_emision and fecha_emision.strip() else datetime.now().strftime("%Y-%m-%d")
        f_envio = fecha_envio.strip() if fecha_envio and fecha_envio.strip() else f_emision
        
        num_oc = numero_orden.strip()
        if num_oc:
            res_existente = await config.supabase_async.table("ordenes_compra") \
                .select("id") \
                .eq("numero_orden", num_oc) \
                .eq("usuario_id", user.id) \
                .execute()
            if res_existente.data:
                return JSONResponse(status_code=400, content={"status": "error", "mensaje": f"La Orden de Compra N° {num_oc} ya se encuentra registrada."})

        prov_nombre = proveedor.strip()
        res_prov = await config.supabase_async.table("proveedores") \
            .select("id") \
            .eq("nombre", prov_nombre) \
            .execute()
            
        if res_prov.data:
            proveedor_id = res_prov.data[0]["id"]
        else:
            res_ins = await config.supabase_async.table("proveedores") \
                .insert({"nombre": prov_nombre}) \
                .execute()
            if not res_ins.data:
                return JSONResponse(status_code=500, content={"status": "error", "mensaje": "Error al registrar el proveedor en la base de datos."})
            proveedor_id = res_ins.data[0]["id"]

        res_oc = await config.supabase_async.table("ordenes_compra").insert({
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

        detalles_a_insertar = []

        for prod in productos:
            codigo_raw = prod.get("codigo") or prod.get("codigo_producto") or prod.get("codigo_st")
            descripcion = prod.get("descripcion") or prod.get("nombre_producto") or "Sin descripción"

            emp_val = int(float(sanitizar_numero(prod.get("empaques") or prod.get("emp") or 0)))
            pre_val = int(float(sanitizar_numero(prod.get("unidad_manejo") or prod.get("pre") or 1)))

            cant_raw = float(sanitizar_numero(prod.get("cantidad") or 0))
            cant_val = int(emp_val * pre_val) if (emp_val > 0 and pre_val > 0 and cant_raw != (emp_val * pre_val)) else int(round(cant_raw))

            precio_final = float(sanitizar_numero(prod.get("precio_unitario") or prod.get("precio") or 0))

            detalles_a_insertar.append({
                "orden_id": orden_id,
                "codigo": str(codigo_raw) if codigo_raw else "",
                "descripcion": descripcion,
                "cantidad": cant_val,
                "precio_unitario": precio_final,
                "pre": pre_val,
                "emp": emp_val
            })

        if detalles_a_insertar:
            await config.supabase_async.table("detalles_productos").insert(detalles_a_insertar).execute()

        return JSONResponse(content={"status": "ok", "mensaje": "Orden guardada con éxito."})

    except Exception as e:
        print(f"[DEBUG CREAR ORDEN ERROR]:\n{traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"status": "error", "mensaje": str(e)})

@router.get("/ordenes/obtener_detalle/{numero_orden}")
async def obtener_detalle_oc(
    numero_orden: str, 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return {"status": "error", "mensaje": "No autorizado", "productos": []}

    res = await config.supabase_async.table("ordenes_compra") \
        .select("*, detalles_productos(*)") \
        .eq("numero_orden", numero_orden) \
        .eq("usuario_id", user.id) \
        .execute()
    
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