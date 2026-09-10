import csv
import io 
from typing import List, Optional  # Anotaciones de tipos
from fastapi import APIRouter, File, UploadFile, Request, Cookie, HTTPException  # Componentes FastAPI
from fastapi.responses import RedirectResponse
import config
from config import templates, obtener_usuario_actual  # Dependencias globales
from models import ProductoModificado  # Modelo Pydantic
import asyncio
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

    # Consulta agregando el campo marca
    res = await config.supabase_async.table("productos") \
        .select("departamento, grupo, subgrupo, marca") \
        .eq("proveedor_id", proveedor_id) \
        .execute()
        
    productos = res.data or []

    resultado = []
    vistos = set()
    for p in productos:
        depto = p.get("departamento") or ""
        grupo = p.get("grupo") or ""
        subgrupo = p.get("subgrupo") or ""
        marca = p.get("marca") or ""
        
        # Incluye la marca en la tupla de unicidad
        clave = (depto, grupo, subgrupo, marca)
        if clave not in vistos:
            vistos.add(clave)
            resultado.append({
                "departamento": depto,
                "grupo": grupo,
                "subgrupo": subgrupo,
                "marca": marca
            })

    return resultado

@router.get("/api/productos/importar-analisis")
async def api_importar_productos_analisis(
    proveedor_id: Optional[int] = None,
    departamento: Optional[str] = "",
    grupo: Optional[str] = "",
    subgrupo: Optional[str] = "",
    marca: Optional[str] = "",  # Nuevo parámetro para filtrar por marca
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
    if marca and marca.strip():
        query = query.eq("marca", marca.strip())  # Filtra exactamente por la marca seleccionada

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


# RUTA OPTIMIZADA: Compara con la BD y actualiza únicamente los campos modificados
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

    try:
        # 1. Filtra los códigos válidos recibidos desde la plantilla
        codigos = [str(prod.codigo).strip() for prod in productos if prod.codigo and str(prod.codigo).strip().lower() != "null"]
        if not codigos:
            return {"status": "success", "mensaje": "No hay códigos válidos para procesar"}

        # 2. Consulta los datos actuales en la base de datos para comparar
        res = await config.supabase_async.table("productos") \
            .select("codigo_st, unidad_manejo, precio") \
            .in_("codigo_st", codigos) \
            .execute()

        # Mapea los registros existentes por su código de producto
        db_map = {item["codigo_st"]: item for item in (res.data or [])}

        tareas = []
        for prod in productos:
            codigo = str(prod.codigo).strip() if prod.codigo else ""
            if not codigo or codigo not in db_map:
                continue

            db_prod = db_map[codigo]
            campos_a_actualizar = {}

            # Verifica unidad_manejo: actualiza si en BD está vacío/nulo o si es diferente
            db_um = str(db_prod.get("unidad_manejo") or "").strip()
            nuevo_um = str(prod.unidad_manejo or "1").strip()
            if not db_um or db_um != nuevo_um:
                campos_a_actualizar["unidad_manejo"] = nuevo_um

            # Verifica precio: actualiza si el valor difiere del guardado en la BD
            if prod.precio is not None:
                db_precio = float(db_prod.get("precio") or 0.0)
                nuevo_precio = float(prod.precio)
                if abs(db_precio - nuevo_precio) > 0.0001:  # Compara la diferencia decimal
                    campos_a_actualizar["precio"] = nuevo_precio

            # Agrega la consulta UPDATE solo si se detectaron diferencias
            if campos_a_actualizar:
                tarea = config.supabase_async.table("productos") \
                    .update(campos_a_actualizar) \
                    .eq("codigo_st", codigo) \
                    .execute()
                tareas.append(tarea)

        if not tareas:
            return {"status": "success", "mensaje": "No se detectaron cambios con respecto a la base de datos"}

        # 3. Ejecuta las actualizaciones necesarias en paralelo
        await asyncio.gather(*tareas)

        return {
            "status": "success", 
            "mensaje": f"{len(tareas)} productos actualizados correctamente"
        }
    except Exception as e:
        print(f"❌ ERROR EN /api/productos/actualizar-analisis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar productos: {str(e)}")


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