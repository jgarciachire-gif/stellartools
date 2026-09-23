from datetime import date, timedelta  # Maneja fechas sin depender de la zona horaria del navegador
from fastapi import APIRouter, Request, Cookie, Query, HTTPException  # Agrega parámetros y validaciones HTTP
from fastapi.responses import HTMLResponse, JSONResponse  # Importa respuestas HTML y JSON
import config
from config import templates, obtener_usuario_actual

router = APIRouter()

@router.get("/calendario", response_class=HTMLResponse)
async def ver_calendario(request: Request):
    proveedores = []
    try:
        client = await config.obtener_supabase_async()

        res = await (
            client
            .table("proveedores")
            .select("id, nombre, dias_despacho")
            .order("nombre")
            .execute()
        )
        proveedores = res.data if res.data else []
    except Exception:
        proveedores = []

    return templates.TemplateResponse(
        request=request,
        name="calendario.html",
        context={"proveedores_db": proveedores}
    )

@router.get("/api/calendario")
async def listar_eventos_calendario(
    inicio: date = Query(...),  # Primer día solicitado
    fin: date = Query(...),  # Último día solicitado
    access_token: str = Cookie(None),  # Token de sesión actual
    refresh_token: str = Cookie(None)  # Token para renovar sesión si corresponde
):
    user = await obtener_usuario_actual(access_token, refresh_token)  # Valida autenticación
    if not user:
        return JSONResponse(status_code=401, content={"error": "No autorizado"})

    # Evita consultas excesivamente grandes desde el navegador
    if fin < inicio:
        raise HTTPException(status_code=400, detail="El rango de fechas es inválido")

    if (fin - inicio).days > 62:
        raise HTTPException(status_code=400, detail="El rango máximo permitido es de 62 días")

    client = await config.obtener_supabase_async()

    # Solo recuperamos las columnas necesarias para generar eventos.
    res = await (
        client
        .table("programacion_reposicion")
        .select(
            "id, proveedor, departamento, grupo, "
            "nombre_comprador, usuario_id, fecha_inicio, frecuencia"
        )
        .lte("fecha_inicio", fin.isoformat())
        .gt("frecuencia", 0)
        .execute()
    )

    eventos = []  # Lista final de ocurrencias del calendario

    for programacion in res.data or []:
        try:
            fecha_inicio = date.fromisoformat(str(programacion["fecha_inicio"]))
            frecuencia = int(programacion["frecuencia"])
        except (TypeError, ValueError):
            continue  # Ignora registros históricos corruptos sin romper el calendario

        if frecuencia <= 0:
            continue  # Protección adicional contra frecuencias inválidas

        # Encuentra la primera ocurrencia que cae dentro del rango solicitado
        fecha_candidata = max(inicio, fecha_inicio)
        dias_desde_inicio = (fecha_candidata - fecha_inicio).days

        # Salta directamente a la próxima fecha válida de la recurrencia
        ajuste = (-dias_desde_inicio) % frecuencia
        fecha_evento = fecha_candidata + timedelta(days=ajuste)

        while fecha_evento <= fin:
            eventos.append({
                "clave": f"{programacion['id']}-{fecha_evento.isoformat()}",
                "id": programacion["id"],
                "fecha": fecha_evento.isoformat(),
                "proveedor": programacion.get("proveedor") or "Sin proveedor",
                "departamento": programacion.get("departamento") or "Sin Depto.",
                "grupo": programacion.get("grupo") or "TODOS LOS GRUPOS",
                "usuarioNombre": (
                    programacion.get("nombre_comprador")
                    or "Usuario Desconocido"
                ),
                "frecuencia": frecuencia,
                # El servidor determina el propietario real, no el navegador
                "esCreador": str(programacion.get("usuario_id")) == str(user.id)
            })

            fecha_evento += timedelta(days=frecuencia)  # Avanza a la siguiente ocurrencia

    # Ordena para que el frontend reciba datos estables y predecibles
    eventos.sort(key=lambda item: (
        item["fecha"],
        item["proveedor"].lower(),
        item["usuarioNombre"].lower()
    ))

    return eventos

@router.get("/api/programaciones")
async def listar_programaciones_api(access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)  # Valida la sesión activa
    if not user:
        return JSONResponse(status_code=401, content={"error": "No autorizado"})

    # Devuelve solo los campos que realmente necesita el calendario
    res = (
        supabase.table("programacion_reposicion")
        .select(
            "id, proveedor, departamento, grupo, "
            "nombre_comprador, usuario_id, fecha_inicio, frecuencia"
        )
        .order("proveedor")
        .execute()
    )

    return res.data if res and res.data else []

@router.post("/api/programaciones")
async def crear_programacion_api(
    request: Request,
    access_token: str = Cookie(None)
):
    # Verifica que exista una sesión válida
    user = await obtener_usuario_actual(access_token)

    # Rechaza la operación si no hay usuario autenticado
    if not user:
        return JSONResponse(
            status_code=401,
            content={"error": "No autorizado"}
        )

    # Lee el cuerpo JSON enviado desde el calendario
    try:
        datos = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "La solicitud no contiene un JSON válido"}
        )

    # Obtiene el ID real del usuario autenticado
    user_id = str(user.id)

    # Obtiene el perfil guardado en la sesión
    perfil = request.session.get("perfil") or {}

    # Nunca confía en el nombre de comprador enviado por JavaScript
    nombre_comprador = (
        perfil.get("nombre_comprador")
        or getattr(user, "email", None)
        or "Usuario Sistema"
    )

    # Obtiene el ID del proveedor seleccionado
    proveedor_id_raw = datos.get("proveedor_id")

    # Valida que realmente se haya seleccionado un proveedor
    if not proveedor_id_raw:
        return JSONResponse(
            status_code=400,
            content={"error": "Debe seleccionar un proveedor"}
        )

    # Convierte el ID del proveedor a entero
    try:
        proveedor_id = int(proveedor_id_raw)
    except (TypeError, ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": "El proveedor seleccionado no es válido"}
        )

    client = await config.obtener_supabase_async()

    # Solo recuperamos las columnas necesarias para generar eventos.
    res = await (
        client
        .table("proveedores")
        .select("id, nombre")
        .eq("id", proveedor_id)
        .maybe_single()
        .execute()
    )

    # Valida que el proveedor siga existiendo
    if not proveedor_res or not proveedor_res.data:
        return JSONResponse(
            status_code=404,
            content={"error": "El proveedor seleccionado no existe"}
        )

    # Usa el nombre almacenado en la base de datos
    proveedor_nombre = proveedor_res.data["nombre"]

    # Normaliza departamento y grupo
    dep_nuevo = str(datos.get("departamento") or "").strip()
    grupo_nuevo = str(datos.get("grupo") or "").strip()

    # Obtiene y valida la fecha inicial
    fecha_inicio_raw = str(datos.get("fechaInicio") or "").strip()

    try:
        fecha_inicio = date.fromisoformat(fecha_inicio_raw)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": "La fecha de inicio no es válida"}
        )

    # Obtiene y valida la frecuencia
    frecuencia_raw = datos.get("frecuencia")

    try:
        frecuencia = int(frecuencia_raw)
    except (TypeError, ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": "La frecuencia debe ser un número entero"}
        )

    # Impide frecuencias imposibles o excesivas
    if frecuencia < 1 or frecuencia > 365:
        return JSONResponse(
            status_code=400,
            content={"error": "La frecuencia debe estar entre 1 y 365 días"}
        )

    client = await config.obtener_supabase_async()

    # Solo recuperamos las columnas necesarias para generar eventos.
    res = await (
        client
        .table("programacion_reposicion")
        .select(
            "id, proveedor, departamento, grupo, "
            "nombre_comprador, usuario_id, fecha_inicio, frecuencia"
        )
        .eq("usuario_id", user_id)
        .eq("proveedor", proveedor_nombre)
        .maybe_single()
        .execute()
    )

    # Si ya existe, conserva el comportamiento actual de actualizarla
    if existente and existente.data:

        # Divide textos separados por coma para evitar duplicados
        def fusionar_textos(valor_existente, valor_nuevo):
            existentes = [
                item.strip()
                for item in str(valor_existente or "").split(",")
                if item.strip()
            ]

            nuevos = [
                item.strip()
                for item in str(valor_nuevo or "").split(",")
                if item.strip()
            ]

            unificados = existentes + [
                item for item in nuevos
                if item not in existentes
            ]

            return ", ".join(unificados)

        # Une las categorías nuevas con las ya guardadas
        dep_final = fusionar_textos(
            existente.data.get("departamento"),
            dep_nuevo
        )

        grupo_final = fusionar_textos(
            existente.data.get("grupo"),
            grupo_nuevo
        )

        # Prepara la actualización
        payload_update = {
            "departamento": dep_final,
            "grupo": grupo_final,
            "fecha_inicio": fecha_inicio.isoformat(),
            "frecuencia": frecuencia,
            "nombre_comprador": nombre_comprador
        }

        # Actualiza únicamente el registro encontrado
        res = (
            supabase.table("programacion_reposicion")
            .update(payload_update)
            .eq("id", existente.data["id"])
            .eq("usuario_id", user_id)
            .execute()
        )

    else:
        # Prepara una nueva programación
        payload_insert = {
            "proveedor": proveedor_nombre,
            "departamento": dep_nuevo,
            "grupo": grupo_nuevo,
            "fecha_inicio": fecha_inicio.isoformat(),
            "frecuencia": frecuencia,
            "usuario_id": user_id,
            "nombre_comprador": nombre_comprador
        }

        # Inserta la nueva programación
        res = (
            supabase.table("programacion_reposicion")
            .insert(payload_insert)
            .execute()
        )

    # Devuelve el registro recién creado o actualizado
    if res and res.data:
        return res.data[0]

    # Informa si Supabase no devolvió el registro
    return JSONResponse(
        status_code=400,
        content={"error": "No se pudo guardar la programación"}
    )

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