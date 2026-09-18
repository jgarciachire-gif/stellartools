import csv
import io 
from typing import List, Optional  # Anotaciones de tipos
from fastapi import APIRouter, File, UploadFile, Request, Cookie, HTTPException  # Componentes FastAPI
from fastapi.responses import RedirectResponse
import config
from config import templates, obtener_usuario_actual  # Dependencias globales
from models import (
    ProductoModificado,
    CodigosVentasRequest,
    GuardarAnalisisRequest
)  # Modelos de validación para las API
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
    # Verifica que exista una sesión válida.
    user = await obtener_usuario_actual(access_token, refresh_token)

    # Si no hay usuario o proveedor, no consulta la BD.
    if not user or not proveedor_id:
        return []

    # PostgreSQL devuelve directamente combinaciones únicas.
    res = await config.supabase_async.rpc(
        "obtener_clasificacion_proveedor",
        {
            "p_proveedor_id": proveedor_id
        }
    ).execute()

    # Devuelve únicamente las combinaciones necesarias para los combos.
    return res.data or []

@router.get("/api/productos/importar-analisis")
async def api_importar_productos_analisis(
    proveedor_id: Optional[int] = None,
    departamento: Optional[str] = "",
    grupo: Optional[str] = "",
    subgrupo: Optional[str] = "",
    marca: Optional[str] = "",
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Valida al usuario antes de consultar productos.
    user = await obtener_usuario_actual(access_token, refresh_token)

    # Evita consultas incompletas.
    if not user or not proveedor_id:
        return []

    # Solicita únicamente las columnas utilizadas por Análisis de Pedido.
    query = (
        config.supabase_async
        .table("productos")
        .select("codigo_st, descripcion, unidad_manejo, precio")
        .eq("proveedor_id", proveedor_id)
    )

    # Aplica el filtro de departamento cuando exista.
    if departamento and departamento.strip():
        query = query.eq("departamento", departamento.strip())

    # Aplica el filtro de grupo cuando exista.
    if grupo and grupo.strip():
        query = query.eq("grupo", grupo.strip())

    # Aplica el filtro de subgrupo cuando exista.
    if subgrupo and subgrupo.strip():
        query = query.eq("subgrupo", subgrupo.strip())

    # Aplica el filtro de marca cuando exista.
    if marca and marca.strip():
        query = query.eq("marca", marca.strip())

    productos = []
    bloque = 1000
    inicio = 0

    # Mantiene soporte para más de 1000 registros.
    while True:
        res = await query.range(
            inicio,
            inicio + bloque - 1
        ).execute()

        datos = res.data or []

        # Finaliza cuando no existan más filas.
        if not datos:
            break

        # Acumula únicamente las columnas solicitadas.
        productos.extend(datos)

        # Si llegó menos del bloque, ya terminamos.
        if len(datos) < bloque:
            break

        # Continúa con el siguiente bloque.
        inicio += bloque

    # Devuelve exactamente lo que necesita la tabla HTML.
    return [
        {
            "codigo": p.get("codigo_st") or "",
            "descripcion": p.get("descripcion") or "",
            "unidad_manejo": p.get("unidad_manejo") or "1",
            "precio": float(p.get("precio") or 0.0)
        }
        for p in productos
    ]

# Actualiza en una sola operación los productos modificados desde Análisis.
@router.post("/api/productos/actualizar-analisis")
async def actualizar_productos_desde_analisis(
    productos: List[ProductoModificado],
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Valida la sesión antes de modificar datos.
    user = await obtener_usuario_actual(access_token, refresh_token)

    # Bloquea usuarios no autenticados.
    if not user:
        raise HTTPException(
            status_code=401,
            detail="No autorizado"
        )

    # Evita una llamada innecesaria cuando no existen cambios.
    if not productos:
        return {
            "status": "success",
            "mensaje": "Sin cambios que procesar"
        }

    try:
        # Usa un diccionario para evitar códigos duplicados.
        productos_unicos = {}

        # Normaliza el payload recibido.
        for producto in productos:
            codigo = str(producto.codigo or "").strip()

            # Ignora códigos vacíos o inválidos.
            if not codigo or codigo.lower() in {"null", "undefined"}:
                continue

            # Conserva el último cambio recibido para ese código.
            productos_unicos[codigo] = {
                "codigo": codigo,
                "unidad_manejo": str(
                    producto.unidad_manejo or 1
                ),
                "precio": float(producto.precio or 0)
            }

        # Convierte el diccionario nuevamente a lista.
        payload_rpc = list(productos_unicos.values())

        # Evita payloads exageradamente grandes.
        if len(payload_rpc) > 2000:
            raise HTTPException(
                status_code=400,
                detail="No se permiten más de 2000 productos por actualización."
            )

        # Actualiza todos los registros dentro de PostgreSQL.
        res = await config.supabase_async.rpc(
            "actualizar_productos_analisis",
            {
                "p_productos": payload_rpc
            }
        ).execute()

        # PostgreSQL devuelve la cantidad de registros actualizados.
        actualizados = int(res.data or 0)

        return {
            "status": "success",
            "actualizados": actualizados,
            "mensaje": f"{actualizados} productos actualizados correctamente"
        }

    except HTTPException:
        # Mantiene intactos los códigos HTTP generados arriba.
        raise

    except Exception as e:
        # Registra el error para depuración local/Vercel.
        print(
            f"ERROR EN /api/productos/actualizar-analisis: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al actualizar productos."
        )


# ============================================================
# CARGA MASIVA DE VENTAS CSV
# ============================================================
@router.post("/analisis/cargar-ventas-csv")
async def cargar_ventas_csv(
    file: UploadFile = File(...),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Valida sesión antes de escribir ventas.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    # Bloquea usuarios no autenticados.
    if not user:
        raise HTTPException(
            status_code=401,
            detail="No autorizado"
        )

    # Valida el nombre del archivo.
    nombre = (file.filename or "").lower()

    if not nombre.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="El archivo debe ser formato .csv"
        )

    try:
        # Lee el archivo una sola vez.
        content = await file.read()

        # Protege el endpoint frente a archivos excesivamente grandes.
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="El archivo CSV supera el límite de 15 MB."
            )

        # Abre CSV respetando UTF-8 con BOM.
        stream = io.StringIO(
            content.decode("utf-8-sig")
        )

        # Crea el lector de filas.
        reader = csv.DictReader(stream)

        registros = []

        # Procesa cada fila del CSV.
        for row in reader:
            row_clean = {
                k.strip().lower(): v.strip()
                for k, v in row.items()
                if k
            }

            # Normaliza sede y código.
            sede = row_clean.get("sede", "").upper()
            codigo = row_clean.get("codigo", "").upper()

            # Busca la columna de demanda disponible.
            demanda_raw = (
                row_clean.get("demanda_diaria")
                or row_clean.get("demanda diaria")
                or row_clean.get("demanda")
                or "0"
            )

            # Normaliza separador decimal.
            demanda_str = demanda_raw.replace(",", ".")

            # Descarta filas sin sede/código.
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

        # Valida el contenido antes de tocar la BD.
        if not registros:
            raise HTTPException(
                status_code=400,
                detail="No se encontraron registros válidos en el CSV"
            )

        # Realiza un único UPSERT masivo.
        await (
            config.supabase_async
            .table("ventas_stellar")
            .upsert(
                registros,
                on_conflict="sede,codigo"
            )
            .execute()
        )

        return {
            "status": "ok",
            "procesados": len(registros)
        }

    except HTTPException:
        # Mantiene los códigos 400/413 originales.
        raise

    except Exception as e:
        # Devuelve un error controlado al frontend.
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando CSV: {str(e)}"
        )


# ============================================================
# CONSULTA DE VENTAS SOLO PARA CÓDIGOS NECESARIOS
# ============================================================
@router.post("/analisis/obtener-ventas-stellar")
async def obtener_ventas_stellar(
    payload: CodigosVentasRequest,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Valida al usuario antes de consultar ventas.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    # Bloquea consultas anónimas.
    if not user:
        raise HTTPException(
            status_code=401,
            detail="No autorizado"
        )

    # Normaliza y elimina códigos duplicados.
    codigos = list(dict.fromkeys(
        str(codigo).strip()
        for codigo in payload.codigos
        if str(codigo).strip()
    ))

    # Si no hay códigos, evita una consulta a Supabase.
    if not codigos:
        return {
            "status": "ok",
            "data": []
        }

    try:
        # Consulta únicamente ventas de los productos visibles.
        res = await (
            config.supabase_async
            .table("ventas_stellar")
            .select("sede, codigo, demanda_diaria")
            .in_("codigo", codigos)
            .execute()
        )

        return {
            "status": "ok",
            "data": res.data or []
        }

    except Exception as e:
        # Devuelve un error controlado.
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar ventas: {str(e)}"
        )


# ============================================================
# GUARDADO TRANSACCIONAL DEL ANÁLISIS
# ============================================================
@router.post("/analisis/guardar-pedido")
async def guardar_analisis_pedido(
    payload: GuardarAnalisisRequest,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Obtiene el usuario real desde la cookie.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    # No acepta el usuario desde JavaScript.
    if not user:
        raise HTTPException(
            status_code=401,
            detail="No autorizado"
        )

    # Evita guardar pedidos vacíos.
    if not payload.detalles:
        raise HTTPException(
            status_code=400,
            detail="No existen detalles para guardar."
        )

    # Convierte los modelos Pydantic al formato JSON esperado por PostgreSQL.
    detalles = [
        detalle.model_dump()
        for detalle in payload.detalles
    ]

    try:
        # Ejecuta todo el guardado dentro de una función PostgreSQL.
        res = await config.supabase_async.rpc(
            "guardar_analisis_pedido",
            {
                "p_usuario_id": str(user.id),
                "p_proveedor_id": payload.proveedor_id,
                "p_dias_cobertura": payload.dias_cobertura,
                "p_detalles": detalles
            }
        ).execute()

        # Recupera la respuesta de la función.
        resultado = res.data or {}

        return {
            "status": "ok",
            "analisis_id": resultado.get("analisis_id")
        }

    except Exception as e:
        # Registra el error internamente.
        print(
            f"ERROR EN /analisis/guardar-pedido: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al guardar el análisis."
        )


# ============================================================
# CARGA DEL ÚLTIMO PEDIDO EN UNA SOLA PETICIÓN HTTP
# ============================================================
@router.get("/analisis/ultimo-pedido")
async def obtener_ultimo_pedido(
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Obtiene el usuario real desde la sesión.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    # Bloquea usuarios no autenticados.
    if not user:
        raise HTTPException(
            status_code=401,
            detail="No autorizado"
        )

    try:
        # Consulta únicamente la última cabecera del usuario.
        res_analisis = await (
            config.supabase_async
            .table("analisis_pedidos")
            .select(
                "id, proveedor_id, dias_cobertura, updated_at, proveedores(nombre)"
            )
            .eq("usuario_id", str(user.id))
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )

        # Si no existe ningún pedido, termina aquí.
        if not res_analisis.data:
            return {
                "status": "ok",
                "encontrado": False
            }

        # Convierte la primera fila en diccionario independiente.
        analisis = dict(res_analisis.data[0])

        # Extrae la información relacionada del proveedor.
        proveedor = analisis.pop("proveedores", None) or {}

        # Normaliza la relación por si Supabase la devuelve como lista.
        if isinstance(proveedor, list):
            proveedor = proveedor[0] if proveedor else {}

        # Consulta todos los detalles en un solo viaje.
        res_detalles = await (
            config.supabase_async
            .table("analisis_pedidos_detalle")
            .select(
                "sede, codigo, sugerido, pedido_final"
            )
            .eq("analisis_id", analisis["id"])
            .execute()
        )

        # Obtiene detalles o lista vacía.
        detalles = res_detalles.data or []

        # Extrae códigos únicos para la consulta de productos.
        codigos = list(dict.fromkeys(
            str(item.get("codigo")).strip()
            for item in detalles
            if item.get("codigo")
        ))

        productos = []

        # Consulta productos solamente si existen códigos.
        if codigos:
            res_productos = await (
                config.supabase_async
                .table("productos")
                .select(
                    "codigo_st, descripcion, precio, unidad_manejo"
                )
                .in_("codigo_st", codigos)
                .execute()
            )

            productos = res_productos.data or []

        # Devuelve todo lo necesario en una sola respuesta HTTP.
        return {
            "status": "ok",
            "encontrado": True,
            "analisis": analisis,
            "proveedor": proveedor,
            "detalles": detalles,
            "productos": productos
        }

    except Exception as e:
        # Registra error para depuración.
        print(
            f"ERROR EN /analisis/ultimo-pedido: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al cargar el último pedido."
        )