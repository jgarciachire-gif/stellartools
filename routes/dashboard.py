# dashboard.py

from datetime import datetime, timedelta, timezone
import hashlib
import json
from fastapi import APIRouter, Request, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
import config
from config import templates, obtener_usuario_actual

router = APIRouter()


@router.get("/api/notificaciones/reposicion")
async def notificaciones_reposicion(
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return JSONResponse({"detalle": "Tu sesión ha vencido. Inicia sesión nuevamente."}, status_code=401,
                            headers={"Cache-Control": "no-store"})
    desglose = await obtener_desglose_reposicion(user.id)
    notificaciones = construir_notificaciones_reposicion(desglose)
    return JSONResponse({"notificaciones": notificaciones,
                         "total": len(notificaciones)},
                        headers={"Cache-Control": "no-store"})


def construir_notificaciones_reposicion(desglose):
    avisos = []
    estados = {"Próximo a Agotar", "Reponer inventario"}
    for proveedor, grupos in desglose.items():
        tiendas = {}
        for grupo, registros in grupos.items():
            for tienda, registro in registros.items():
                estado = registro['estatus_inv']
                if estado not in estados:
                    continue
                clave = (tienda, estado, registro['dias_inventario'])
                detalle = tiendas.setdefault(clave, {
                    "tienda": tienda, "estatus": estado,
                    "dias_inventario": registro['dias_inventario'], "grupos": []
                })
                detalle['grupos'].append(grupo)
        if not tiendas:
            continue
        detalles = list(tiendas.values())
        for detalle in detalles:
            detalle['grupos'].sort(key=str.casefold)
            detalle['mostrar_grupos'] = sum(d['tienda'] == detalle['tienda'] for d in detalles) > 1
        detalles.sort(key=lambda d: (d['estatus'] != 'Reponer inventario', d['tienda'].casefold(), d['grupos']))
        estados_proveedor = sorted(
            (grupo, tienda, registro['estatus_inv'], registro.get('id_oc'))
            for grupo, registros in grupos.items() for tienda, registro in registros.items()
        )
        version = hashlib.sha256(json.dumps(estados_proveedor, ensure_ascii=False).encode('utf-8')).hexdigest()
        avisos.append({"proveedor": proveedor, "tiendas": detalles, "version_estado": version})
    avisos.sort(key=lambda a: (not any(t['estatus'] == 'Reponer inventario' for t in a['tiendas']),
                              a['proveedor'].casefold()))
    return avisos


@router.get("/")
@router.get("/aplicaciones") 
async def vista_aplicaciones(
    request: Request, 
    access_token: str = Cookie(None), 
    refresh_token: str = Cookie(None)
): 
    user = await obtener_usuario_actual(access_token, refresh_token) 
    if not user: 
        return RedirectResponse(url="/login", status_code=303) 
    return templates.TemplateResponse(request=request, name="index.html", context={})

@router.get("/dashboard")
@router.get("/inicio") 
async def dashboard(
    request: Request, 
    access_token: str = Cookie(None),  
    refresh_token: str = Cookie(None)  
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)  

    proveedores_desglose = await obtener_desglose_reposicion(user.id)

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "proveedores_desglose": proveedores_desglose
    })


async def obtener_desglose_reposicion(usuario_id):
    ordenes = []
    offset = 0
    while True:
        respuesta = await (
            config.supabase_async.table("ordenes_compra")
            .select("id, proveedor, tienda_destino, numero_orden, fecha_recepcion, "
                    "dias_inventario, proveedores(nombre), detalles_productos(grupo)")
            .eq("usuario_id", usuario_id)
            .order("id", desc=False)
            .range(offset, offset + 999)
            .execute()
        )
        lote = respuesta.data or []
        ordenes.extend(lote)
        if len(lote) < 1000:
            break
        offset += 1000
    return construir_desglose_reposicion(ordenes)


def construir_desglose_reposicion(ordenes, hoy=None):
    proveedores_desglose = {}
    hoy = hoy or datetime.now(timezone(timedelta(hours=-4))).date()

    if ordenes:
        agrupado = {}

        # =========================================================
        # AGRUPACIÓN: PROVEEDOR + GRUPO + TIENDA
        # =========================================================
        for row in ordenes:
            prov_obj = row.get("proveedores")

            if isinstance(prov_obj, dict) and prov_obj.get("nombre"):
                prov = prov_obj.get("nombre")
            elif (
                isinstance(prov_obj, list)
                and len(prov_obj) > 0
                and isinstance(prov_obj[0], dict)
            ):
                prov = prov_obj[0].get("nombre") or row.get("proveedor") or "Sin Proveedor"
            else:
                prov = row.get("proveedor") or "Sin Proveedor"

            tienda = row.get("tienda_destino") or "Sin Tienda Asignada"

            detalles = row.get("detalles_productos") or []

            # Una misma OC puede pertenecer a varios grupos.
            grupos = {
                str(detalle.get("grupo") or "Sin Grupo").strip() or "Sin Grupo"
                for detalle in detalles
            }

            # Compatibilidad con OCs antiguas sin detalles/grupo.
            if not grupos:
                grupos = {"Sin Grupo"}

            for grupo in grupos:
                key = (prov, grupo, tienda)

                if key not in agrupado:
                    agrupado[key] = []

                agrupado[key].append(row)

        # =========================================================
        # CALCULAR ESTADO PARA CADA
        # PROVEEDOR + GRUPO + TIENDA
        # =========================================================
        for (prov, grupo, tienda), lista_ocs in agrupado.items():

            if prov not in proveedores_desglose:
                proveedores_desglose[prov] = {}

            if grupo not in proveedores_desglose[prov]:
                proveedores_desglose[prov][grupo] = {}

            ocs_recibidas = []
            ocs_enviadas = []

            for oc in lista_ocs:
                f_rec_raw = str(
                    oc.get("fecha_recepcion") or ""
                ).strip()

                tiene_fecha_rec = (
                    f_rec_raw != ""
                    and f_rec_raw.lower()
                    not in ["none", "nan", "nat", "null"]
                )

                if tiene_fecha_rec:
                    ocs_recibidas.append(oc)
                else:
                    ocs_enviadas.append(oc)

            if ocs_recibidas:
                oc_seleccionada = ocs_recibidas[-1]

                hay_nueva_enviada = any(
                    oc.get("id", 0) > oc_seleccionada.get("id", 0)
                    for oc in ocs_enviadas
                )

                estatus_oc = (
                    "Nueva OC enviada"
                    if hay_nueva_enviada
                    else "Despacho Recibido"
                )
            elif ocs_enviadas:
                oc_seleccionada = ocs_enviadas[-1]
                estatus_oc = "Enviada"
            else:
                continue

            f_rec_raw = str(
                oc_seleccionada.get("fecha_recepcion") or ""
            ).strip()

            tiene_fecha_rec = (
                f_rec_raw != ""
                and f_rec_raw.lower()
                not in ["none", "nan", "nat", "null"]
            )

            valor_dias = oc_seleccionada.get("dias_inventario")
            try:
                dias_inv_totales = int(valor_dias) if valor_dias not in (None, '') else 15
            except (ValueError, TypeError):
                dias_inv_totales = 15

            if tiene_fecha_rec:
                try:
                    f_rec = datetime.strptime(
                        f_rec_raw,
                        "%Y-%m-%d"
                    ).date()

                    f_rec_str = f_rec.strftime("%d/%m/%Y")

                    fecha_agotamiento = (
                        f_rec + timedelta(days=dias_inv_totales)
                    )

                    dias_restantes = (
                        fecha_agotamiento - hoy
                    ).days

                    if dias_restantes <= 0:
                        estatus_inv = "Reponer inventario"
                        color_inv = "text-red-700 bg-red-100"
                        dias_mostrar = (
                            f"Vencido hace {abs(dias_restantes)}d"
                        )

                    elif dias_restantes <= 2:
                        estatus_inv = "Próximo a Agotar"
                        color_inv = "text-amber-700 bg-amber-100"
                        dias_mostrar = (
                            f"Quedan {dias_restantes}d"
                        )

                    else:
                        estatus_inv = "Stock OK"
                        color_inv = "text-emerald-700 bg-emerald-100"
                        dias_mostrar = (
                            f"Quedan {dias_restantes}d"
                        )

                except ValueError:
                    f_rec_str = f_rec_raw
                    estatus_inv = "Error de Fecha"
                    color_inv = "text-slate-600 bg-slate-100"
                    dias_mostrar = (
                        f"{dias_inv_totales} totales"
                    )

            else:
                f_rec_str = "-"
                estatus_inv = "Esperando Recepción"
                color_inv = "text-blue-700 bg-blue-100"
                dias_mostrar = "Sin iniciar"

            if estatus_oc in [
                "Despacho Recibido",
                "Stock OK"
            ]:
                color_oc = "text-emerald-700 bg-emerald-100"

            elif estatus_oc == "Nueva OC enviada":
                color_oc = "text-blue-700 bg-blue-100"

            else:
                color_oc = "text-slate-700 bg-slate-100"

            proveedores_desglose[prov][grupo][tienda] = {
                "id_oc": oc_seleccionada.get("id"),
                "grupo": grupo,
                "ultima_oc": oc_seleccionada.get("numero_orden"),
                "fecha_recepcion": f_rec_str,
                "estatus_oc": estatus_oc,
                "color_oc": color_oc,
                "dias_inventario": dias_mostrar,
                "estatus_inv": estatus_inv,
                "color_inv": color_inv
            }

    return proveedores_desglose
