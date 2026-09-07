import csv
import io 
from typing import List, Optional  # Anotaciones de tipos
from fastapi import APIRouter,File, UploadFile, Request, Cookie, HTTPException  # Componentes FastAPI
from config import supabase, templates, obtener_usuario_actual  # Dependencias globales
from models import ProductoModificado  # Modelo Pydantic

router = APIRouter()

@router.get("/analisis-pedido")
def vista_analisis_pedido(request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res_prov = supabase.table("proveedores").select("id, nombre").order("nombre").execute()
    proveedores = res_prov.data if res_prov and res_prov.data else []

    return templates.TemplateResponse(request=request, name="analisis_pedido.html", context={
        "proveedores": proveedores
    })

@router.get("/api/clasificacion")
def api_obtener_clasificacion(
    proveedor_id: Optional[int] = None, 
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user or not proveedor_id:
        return []

    res = supabase.table("productos").select("departamento, grupo, subgrupo").eq("proveedor_id", proveedor_id).execute()
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
def api_importar_productos_analisis(
    proveedor_id: Optional[int] = None,
    departamento: Optional[str] = "",
    grupo: Optional[str] = "",
    subgrupo: Optional[str] = "",
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
    if not user or not proveedor_id:
        return []

    # Prepara la consulta base filtrada por proveedor
    query = supabase.table("productos").select("*").eq("proveedor_id", proveedor_id)

    # Aplica filtros opcionales de clasificación
    if departamento and departamento.strip():
        query = query.eq("departamento", departamento.strip())
    if grupo and grupo.strip():
        query = query.eq("grupo", grupo.strip())
    if subgrupo and subgrupo.strip():
        query = query.eq("subgrupo", subgrupo.strip())

    productos = []  # Lista final para almacenar todos los productos
    bloque = 1000  # Tamaño del lote por cada consulta
    inicio = 0  # Posición inicial del rango

    # Ciclo para recuperar todos los productos superando el límite de 1000
    while True:
        # Pide un rango de registros específico a Supabase
        res = query.range(inicio, inicio + bloque - 1).execute()
        datos = res.data or []  # Extrae la lista de filas

        if not datos:  # Si no retorna registros, finaliza el bucle
            break

        productos.extend(datos)  # Acumula los registros traídos

        if len(datos) < bloque:  # Si el lote vino incompleto, es la última página
            break

        inicio += bloque  # Avanza la ventana de lectura al siguiente bloque

    return [
        {
            "codigo": p.get("codigo_st") or p.get("codigo", ""),
            "descripcion": p.get("descripcion", ""),
            "unidad_manejo": p.get("unidad_manejo") or "1",
            "precio": float(p.get("precio") or 0.0)
        }
        for p in productos
    ]

@router.post("/api/productos/actualizar-analisis")
def actualizar_productos_desde_analisis(productos: List[ProductoModificado], access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    for prod in productos:
        supabase.table("productos").update({
            "unidad_manejo": prod.unidad_manejo,
            "precio": prod.precio
        }).eq("codigo_st", prod.codigo).execute()
    
    return {"status": "success", "mensaje": "Productos actualizados correctamente"}

# RUTA 1: Endpoint para recibir el archivo CSV y procesar el UPSERT en Supabase
@router.post("/analisis/cargar-ventas-csv")
async def cargar_ventas_csv(file: UploadFile = File(...)):
    # Validar extensión del archivo
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="El archivo debe ser formato .csv")

    try:
        # Leer el contenido del archivo subido en memoria
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

        # Ejecutar UPSERT masivo en Supabase basado en la clave única (sede, codigo)
        res = supabase.table("ventas_stellar").upsert(registros, on_conflict="sede,codigo").execute()

        return {"status": "ok", "procesados": len(registros)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando CSV: {str(e)}")


# RUTA 2: Endpoint para consultar todas las ventas guardadas en Supabase con paginación
@router.get("/analisis/obtener-ventas-stellar")
async def obtener_ventas_stellar():
    try:
        todos_los_registros = []  # Acumulador de todas las ventas
        bloque = 1000  # Tamaño máximo por petición en Supabase
        inicio = 0  # Índice de inicio para el rango

        # Ciclo iterativo para consultar lotes de 1000 en 1000
        while True:
            # Obtiene el bloque de ventas desde la posición 'inicio' hasta 'inicio + 999'
            res = supabase.table("ventas_stellar").select("sede, codigo, demanda_diaria").range(inicio, inicio + bloque - 1).execute()
            datos = res.data or []  # Extrae los datos devueltos

            if not datos:  # Si no hay datos devueltos, detiene el ciclo
                break

            todos_los_registros.extend(datos)  # Concatena los registros recuperados

            if len(datos) < bloque:  # Si trajo menos del límite del bloque, ya no hay más filas
                break

            inicio += bloque  # Incrementa el indicador de inicio para la siguiente página

        return {"status": "ok", "data": todos_los_registros}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar ventas: {str(e)}")