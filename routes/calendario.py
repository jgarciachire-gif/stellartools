from fastapi import APIRouter, Request, Cookie  # Importa dependencias requeridas
from fastapi.responses import HTMLResponse, JSONResponse  # Importa respuestas HTML y JSON
import config
from config import supabase, templates, obtener_usuario_actual  # Funciones globales de configuración

router = APIRouter()

@router.get("/calendario", response_class=HTMLResponse)
async def ver_calendario(request: Request):
    proveedores = []
    try:
        res = supabase.table("proveedores").select("id, nombre, dias_despacho").order("nombre").execute()
        proveedores = res.data if res.data else []
    except Exception:
        proveedores = []

    return templates.TemplateResponse(
        request=request,
        name="calendario.html",
        context={"proveedores_db": proveedores}
    )

@router.get("/api/programaciones")
async def listar_programaciones_api(access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return JSONResponse(status_code=401, content={"error": "No autorizado"})

    # Obtiene todas las columnas incluyendo usuario_id, nombre_comprador, departamento y grupo
    res = supabase.table("programacion_reposicion").select("*").execute()
    return res.data if res and res.data else []

@router.post("/api/programaciones")
async def crear_programacion_api(request: Request, access_token: str = Cookie(None)):
    # 1. Verifica autenticación del usuario en sesión
    user = await obtener_usuario_actual(access_token)
    if not user:
        return JSONResponse(status_code=401, content={"error": "No autorizado"})

    datos = await request.json()
    user_id = str(user.id) if user and hasattr(user, "id") and user.id else None
    nombre_comprador = datos.get("nombre_comprador") or getattr(user, "email", "Usuario Sistema")
    proveedor_nombre = str(datos.get("proveedor", ""))

    dep_nuevo = str(datos.get("departamento") or "").strip() or "Sin Depto."
    grupo_nuevo = str(datos.get("grupo") or "").strip() or "Todos los Grupos"

    # 2. Crea un registro único e independiente con su propio ID para evitar sobreescribir o borrar otros agendamientos
    payload_insert = {
        "proveedor": proveedor_nombre,
        "departamento": dep_nuevo,
        "grupo": grupo_nuevo,
        "fecha_inicio": datos.get("fechaInicio"),
        "frecuencia": int(datos.get("frecuencia", 1)),
        "usuario_id": user_id,
        "nombre_comprador": nombre_comprador
    }
    res = supabase.table("programacion_reposicion").insert(payload_insert).execute()

    return res.data[0] if res and res.data else JSONResponse({"error": "No se pudo guardar"}, status_code=400)

@router.delete("/api/programaciones/{prog_id}")
async def eliminar_programacion_api(prog_id: int, access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return JSONResponse(status_code=401, content={"error": "No autorizado"})

    # Valida que la eliminación solo afecte registros creados por el usuario activo (usuario_id)
    res = supabase.table("programacion_reposicion").delete().eq("id", prog_id).eq("usuario_id", user.id).execute()
    
    if not res.data:
        return JSONResponse({"error": "No tienes permiso para eliminar este registro o no existe"}, status_code=403)

    return {"ok": True}