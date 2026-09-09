import csv
import io 
from typing import List, Optional  # Anotaciones de tipos
from fastapi import APIRouter, File, UploadFile, Request, Cookie, HTTPException  # Componentes FastAPI
from fastapi.responses import RedirectResponse
import config
from config import templates, obtener_usuario_actual  # Dependencias globales
from models import ProductoModificado  # Modelo Pydantic

router = APIRouter()

@router.get("/analisis-pedido")
async def vista_analisis_pedido(
    request: Request, 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res_prov = await config.supabase_async.table("proveedores") \
        .select("id, nombre") \
        .order("nombre") \
        .execute()
        
    proveedores = res_prov.data if res_prov and res_prov.data else []

    return templates.TemplateResponse(request=request, name="analisis_pedido.html", context={
        "proveedores": proveedores
    })


@router.get("/api/clasificacion")
async def api_obtener_clasificacion(
    proveedor_id: Optional[int] = None, 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user or not proveedor_id:
        return []

    res = await config.supabase_async.table("productos") \
        .select("departamento, grupo, subgrupo") \
        .eq("proveedor_id", proveedor_id) \
        .execute()
        
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


@router.get("/api/productos/importar-analisis")
async def api_importar_productos_analisis(
    proveedor_id: Optional[int] = None,
    departamento: Optional[str] = "",
    grupo: Optional[str] = "",
    subgrupo: Optional[str] = "",
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user or not proveedor_id:
        return []

    # Prepara la consulta base filtrada por proveedor
    query = config.supabase_async.table("productos").select("*").eq("proveedor_id", proveedor_id)

    # Aplica filtros opcionales de clasificación
    if departamento and departamento.strip():
        query = query.eq("departamento", departamento.strip())
    if grupo and grupo.strip():
        query = query.eq("grupo", grupo.strip())
    if subgrupo and subgrupo.strip():
        query = query.eq("subgrupo", subgrupo.strip())

    productos = []
    bloque = 1000
    inicio = 0

    # Lectura asíncrona por bloques superando el límite de 1000 registros
    while True:
        res = await query.range(inicio, inicio + bloque - 1).execute()
        datos = res.data or []

        if not datos:
            break

        productos.extend(datos)

        if len(datos) < bloque:
            break

        inicio += bloque

    return [
        {
            "codigo": p.get("codigo_st") or p.get("codigo", ""),
            "descripcion": p.get("descripcion", ""),
            "unidad_manejo": p.get("unidad_manejo") or "1",
            "precio": float(p.get("precio") or 0.0)
        }
        for p in productos
    ]


# RUTA OPTIMIZADA: Procesa miles de cambios en 1 solo viaje a la base de datos
@router.post("/api/productos/actualizar-analisis")
async def actualizar_productos_desde_analisis(
    productos: List[ProductoModificado], 
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not productos:
        return {"status": "success", "mensaje": "Sin cambios que procesar"}

# 1. Filtra y limpia los productos asignando valores por defecto a columnas NOT NULL de PostgreSQL
    payload_actualizacion = []
    for prod in productos:
        codigo_limpio = str(prod.codigo).strip() if prod.codigo else ""
        
        # Ignora registros vacíos o no válidos
        if not codigo_limpio or codigo_limpio.lower() == "null":
            continue

        # Extrae atributos opcionales evitando enviar nulos a la BD
        descripcion_valida = str(getattr(prod, "descripcion", "") or "").strip()
        departamento_valido = str(getattr(prod, "departamento", "") or "").strip()
        grupo_valido = str(getattr(prod, "grupo", "") or "").strip()
        subgrupo_valido = str(getattr(prod, "subgrupo", "") or "").strip()

        payload_actualizacion.append({
            "codigo_st": codigo_limpio,
            "descripcion": descripcion_valida,    # Evita error NOT NULL en descripcion
            "departamento": departamento_valido, # Evita error NOT NULL en departamento
            "grupo": grupo_valido,               # Evita error NOT NULL si la columna exige valor
            "subgrupo": subgrupo_valido,         # Evita error NOT NULL si la columna exige valor
            "unidad_manejo": str(prod.unidad_manejo or "1").strip(),
            "precio": float(prod.precio) if prod.precio is not None else 0.0
        })
    try:
        # 2. Ejecución asíncrona masiva en 1 sola consulta HTTP/PostgreSQL
        await config.supabase_async.table("productos") \
            .upsert(payload_actualizacion, on_conflict="codigo_st") \
            .execute()
        
        return {
            "status": "success", 
            "mensaje": f"{len(payload_actualizacion)} productos actualizados correctamente"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en actualización masiva: {str(e)}")


# Endpoint asíncrono para carga masiva de Ventas CSV
@router.post("/analisis/cargar-ventas-csv")
async def cargar_ventas_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="El archivo debe ser formato .csv")

    try:
        content = await file.read()
        stream = io.StringIO(content.decode("utf-8-sig"))
        reader = csv.DictReader(stream)

        registros = []
        for row in reader:
            row_clean = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            
            sede = row_clean.get("sede", "").upper()
            codigo = row_clean.get("codigo", "").upper()
            
            demanda_raw = (
                row_clean.get("demanda_diaria") or 
                row_clean.get("demanda diaria") or 
                row_clean.get("demanda") or 
                "0"
            )
            demanda_str = demanda_raw.replace(",", ".")

            if sede and codigo:
                try:
                    demanda_val = float(demanda_str)
                except ValueError:
                    demanda_val = 0.0

                registros.append({
                    "sede": sede,
                    "codigo": codigo,
                    "demanda_diaria": demanda_val
                })

        if not registros:
            raise HTTPException(status_code=400, detail="No se encontraron registros válidos en el CSV")

        # UPSERT masivo asíncrono en Supabase
        await config.supabase_async.table("ventas_stellar") \
            .upsert(registros, on_conflict="sede,codigo") \
            .execute()

        return {"status": "ok", "procesados": len(registros)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando CSV: {str(e)}")


# Endpoint asíncrono para consultar ventas
@router.get("/analisis/obtener-ventas-stellar")
async def obtener_ventas_stellar():
    try:
        todos_los_registros = []
        bloque = 1000
        inicio = 0

        while True:
            res = await config.supabase_async.table("ventas_stellar") \
                .select("sede, codigo, demanda_diaria") \
                .range(inicio, inicio + bloque - 1) \
                .execute()
                
            datos = res.data or []

            if not datos:
                break

            todos_los_registros.extend(datos)

            if len(datos) < bloque:
                break

            inicio += bloque

        return {"status": "ok", "data": todos_los_registros}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar ventas: {str(e)}")