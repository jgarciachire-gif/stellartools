from datetime import datetime, timedelta  # Manejo de fechas y duraciones
from fastapi import APIRouter, Request, Cookie  # Tipos de FastAPI para consultas HTTP
from fastapi.responses import RedirectResponse  # Respuestas de redirección
from config import supabase, templates, obtener_usuario_actual  # Dependencias del sistema

router = APIRouter()

@router.get("/")
@router.get("/aplicaciones") 
def vista_aplicaciones(
    request: Request, 
    access_token: str = Cookie(None), 
    refresh_token: str = Cookie(None)
): 
    user = obtener_usuario_actual(access_token, refresh_token) 
    if not user: 
        return RedirectResponse(url="/login", status_code=303) 
    return templates.TemplateResponse(request=request, name="index.html", context={})

@router.get("/dashboard")
@router.get("/inicio") 
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