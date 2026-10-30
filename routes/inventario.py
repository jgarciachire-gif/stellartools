from fastapi import (
    APIRouter,
    Request,
    Cookie,
    Form,
    HTTPException,
    Query
)
from fastapi.responses import (
    RedirectResponse,
    JSONResponse
)

import config
from config import templates, obtener_usuario_actual
from uuid import UUID, uuid4
import re


router = APIRouter()

# ============================================================
# PERFIL Y PERMISOS DE INVENTARIO
# ============================================================

def obtener_perfil_inventario(request: Request):
    """
    Obtiene el perfil cargado durante el inicio de sesión.
    """
    perfil = request.session.get("perfil")

    if not isinstance(perfil, dict):
        return None

    return perfil


def es_usuario_provisional(perfil: dict) -> bool:
    """
    Determina si el usuario tiene acceso limitado por tienda.
    """
    return (
        str(
            perfil.get("tipo_usuario", "")
        ).strip().lower()
        == "provisional"
    )


def obtener_tienda_provisional(perfil: dict):
    """
    Devuelve la tienda asignada al usuario provisional.
    """
    tienda = str(
        perfil.get("tienda", "")
    ).strip()

    return tienda or None


# ============================================================
# API PARA IMPORTAR INVENTARIOS EN ANÁLISIS DE PEDIDO
# ============================================================

@router.get("/api/analisis/inventarios")
async def listar_inventarios_para_analisis(
    request: Request,
    tienda: str = "",
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    """Lista inventarios completados permitidos para el usuario."""

    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return JSONResponse(
            status_code=401,
            content={"ok": False, "error": "No autorizado."}
        )

    try:
        perfil = obtener_perfil_inventario(request)
        tienda_solicitada = str(tienda or "").strip()
        es_provisional = (
            perfil and es_usuario_provisional(perfil)
        )

        if es_provisional:
            tienda_asignada = obtener_tienda_provisional(perfil)

            if not tienda_asignada:
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": "El usuario provisional no tiene una tienda asignada."
                    }
                )

            if (
                tienda_solicitada
                and tienda_solicitada.casefold()
                != tienda_asignada.casefold()
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": "No tienes permiso para consultar esa tienda."
                    }
                )

            tienda_solicitada = tienda_asignada

        consulta = (
            config.supabase_async
            .table("inventarios")
            .select(
                "id, nombre, realizado_por, tienda, "
                "estado, created_at, updated_at"
            )
            .eq("estado", "completado")
        )

        if tienda_solicitada:
            consulta = consulta.eq("tienda", tienda_solicitada)

        respuesta = await consulta.order(
            "updated_at",
            desc=True
        ).execute()

        return {
            "ok": True,
            "inventarios": respuesta.data or []
        }

    except Exception as e:
        print(
            "ERROR EN /api/analisis/inventarios: "
            f"{str(e)}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "No se pudieron consultar los inventarios."
            }
        )


@router.get("/api/analisis/inventarios/{inventario_id}")
async def obtener_detalle_inventario_para_analisis(
    request: Request,
    inventario_id: int,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    """Devuelve el detalle de un inventario completado autorizado."""

    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return JSONResponse(
            status_code=401,
            content={"ok": False, "error": "No autorizado."}
        )

    try:
        respuesta = await (
            config.supabase_async
            .table("inventarios")
            .select(
                "id, nombre, realizado_por, tienda, "
                "estado, created_at, updated_at"
            )
            .eq("id", inventario_id)
            .eq("estado", "completado")
            .maybe_single()
            .execute()
        )

        inventario = respuesta.data

        if not inventario:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": "El inventario no existe o no está completado."
                }
            )

        perfil = obtener_perfil_inventario(request)

        if perfil and es_usuario_provisional(perfil):
            tienda_asignada = obtener_tienda_provisional(perfil)

            if (
                not tienda_asignada
                or str(inventario.get("tienda", "")).strip().casefold()
                != tienda_asignada.casefold()
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": "No tienes permiso para consultar ese inventario."
                    }
                )

        respuesta_detalle = await (
            config.supabase_async
            .table("inventarios_detalle")
            .select("codigo, descripcion, cantidad, orden")
            .eq("inventario_id", inventario_id)
            .order("orden", desc=False)
            .execute()
        )

        return {
            "ok": True,
            "inventario": inventario,
            "productos": respuesta_detalle.data or []
        }

    except Exception as e:
        print(
            "ERROR EN "
            f"/api/analisis/inventarios/{inventario_id}: {str(e)}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "No se pudo consultar el detalle del inventario."
            }
        )


# ============================================================
# BIBLIOTECA DE INVENTARIOS
# ============================================================


@router.get("/inventario")
async def vista_inventario(
    request: Request,
    page: int = 1,
    q: str = "",
    tags: list[str] = Query(default=[]),
    tienda: str = "",
    realizado_por: str = "",
    estado: str = "",
    fecha_desde: str = "",
    fecha_hasta: str = "",
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Verifica la sesión del usuario.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    try:
        perfil = obtener_perfil_inventario(request)
        es_provisional = (
            perfil
            and es_usuario_provisional(perfil)
        )

        # Normaliza los filtros recibidos.
        q = q.strip()[:150]
        tienda = tienda.strip()[:150]
        realizado_por = realizado_por.strip()[:150]
        estado = estado.strip().lower()
        # Limitar cantidad y longitud de los criterios recibidos.
        tags = [
            str(valor).strip()[:150]
            for valor in tags[:12]
            if str(valor).strip()
        ]

        estados_validos = {
            "borrador",
            "completado"
        }

        if estado not in estados_validos:
            estado = ""

        # Comprueba que las fechas tengan formato válido.
        from datetime import date

        if fecha_desde:
            try:
                fecha_desde = date.fromisoformat(
                    fecha_desde
                ).isoformat()
            except ValueError:
                fecha_desde = ""

        if fecha_hasta:
            try:
                fecha_hasta = date.fromisoformat(
                    fecha_hasta
                ).isoformat()
            except ValueError:
                fecha_hasta = ""

        if (
            fecha_desde
            and fecha_hasta
            and fecha_desde > fecha_hasta
        ):
            fecha_desde, fecha_hasta = (
                fecha_hasta,
                fecha_desde
            )

        # Los usuarios provisionales solo ven su tienda.
        tienda_provisional = None

        if es_provisional:
            tienda_provisional = (
                obtener_tienda_provisional(perfil)
            )

            if not tienda_provisional:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "El usuario provisional no tiene "
                        "una tienda asignada."
                    )
                )

        # Construye los filtros en el servidor.
        def aplicar_filtros(consulta):
            if es_provisional:
                consulta = consulta.eq(
                    "tienda",
                    tienda_provisional
                )
            elif tienda:
                consulta = consulta.eq(
                    "tienda",
                    tienda
                )

            if realizado_por:
                consulta = consulta.ilike(
                    "realizado_por",
                    f"%{realizado_por}%"
                )

            if estado:
                consulta = consulta.ilike(
                    "estado",
                    estado
                )

            if fecha_desde:
                consulta = consulta.gte(
                    "created_at",
                    f"{fecha_desde}T00:00:00"
                )

            
            if fecha_hasta:
                from datetime import timedelta

                dia_siguiente = (
                    date.fromisoformat(fecha_hasta)
                    + timedelta(days=1)
                )

                consulta = consulta.lt(
                    "created_at",
                    f"{dia_siguiente.isoformat()}T00:00:00"
                )


            # Cada criterio coincide con algún campo; entre criterios se exige AND.
            for valor in tags + ([q] if q else []):
                termino = re.sub(r"[^\w\s\-]", " ", valor, flags=re.UNICODE).strip()
                if not termino:
                    continue
                consulta = consulta.or_(
                    f"nombre.ilike.%{termino}%,"
                    f"tienda.ilike.%{termino}%,"
                    f"realizado_por.ilike.%{termino}%,"
                    f"estado.ilike.%{termino}%"
                )

            return consulta

        # Cuenta en la base de datos solo los resultados filtrados.
        consulta_total = aplicar_filtros(
            config.supabase_async
            .table("inventarios")
            .select("id", count="exact", head=True)
        )

        res_total = await consulta_total.execute()
        total_inventarios = res_total.count or 0

        registros_por_pagina = 15
        total_paginas = max(
            1,
            (
                total_inventarios
                + registros_por_pagina
                - 1
            ) // registros_por_pagina
        )

        try:
            pagina_actual = max(int(page), 1)
        except (TypeError, ValueError):
            pagina_actual = 1

        pagina_actual = min(
            pagina_actual,
            total_paginas
        )

        offset = (
            pagina_actual - 1
        ) * registros_por_pagina

        limite = (
            offset
            + registros_por_pagina
            - 1
        )

        # Obtiene solo los resultados de la página solicitada.
        consulta = aplicar_filtros(
            config.supabase_async
            .table("inventarios")
            .select(
                "id, nombre, realizado_por, tienda, "
                "estado, created_at, updated_at"
            )
        )

        res = await (
            consulta
            .order("created_at", desc=True)
            .range(offset, limite)
            .execute()
        )

        return templates.TemplateResponse(
            request=request,
            name="inventario.html",
            context={
                "inventarios": res.data or [],
                "perfil": perfil,
                "es_provisional": es_provisional,
                "pagina_actual": pagina_actual,
                "total_paginas": total_paginas,
                "total_inventarios": total_inventarios,
                "filtro_q": q,
                "filtro_tags": tags,
                "filtro_tienda": tienda,
                "filtro_realizado_por": realizado_por,
                "filtro_estado": estado,
                "filtro_fecha_desde": fecha_desde,
                "filtro_fecha_hasta": fecha_hasta
            }
        )

    except HTTPException:
        raise

    except Exception as e:
        print(
            f"ERROR EN /inventario: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Error al cargar la biblioteca de inventarios."
            )
        )



# ============================================================
# FORMULARIO NUEVO INVENTARIO
# ============================================================

@router.get("/inventario/nuevo")
async def vista_nuevo_inventario(
    request: Request,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Obtiene el usuario autenticado.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="inventario_nuevo.html"
    )


# ============================================================
# CREAR INVENTARIO
# ============================================================

@router.post("/inventario/crear")
async def crear_inventario(
    request: Request,
    nombre: str = Form(...),
    realizado_por: str = Form(...),
    tienda: str = Form(...),
    clave_creacion: str = Form(...),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Obtiene el usuario real desde la sesión.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="No autorizado."
        )

    # Limpieza básica de datos recibidos.
    nombre = nombre.strip()
    realizado_por = realizado_por.strip()
    tienda = tienda.strip()

    # ----------------------------------------------------
    # SEGURIDAD DE TIENDA
    # ----------------------------------------------------

    perfil = obtener_perfil_inventario(request)

    if perfil and es_usuario_provisional(perfil):

        tienda_provisional = obtener_tienda_provisional(
            perfil
        )

        if not tienda_provisional:
            raise HTTPException(
                status_code=403,
                detail=(
                    "El usuario provisional "
                    "no tiene una tienda asignada."
                )
            )

        # La tienda enviada por el navegador NO se utiliza.
        # El backend impone la tienda asignada al usuario.
        tienda = tienda_provisional

    # Validaciones obligatorias.
    if not nombre:
        raise HTTPException(
            status_code=400,
            detail="El nombre de la lista es obligatorio."
        )

    if not realizado_por:
        raise HTTPException(
            status_code=400,
            detail="El campo 'Realizado por' es obligatorio."
        )

    if not tienda:
        raise HTTPException(
            status_code=400,
            detail="La tienda es obligatoria."
        )

    
    # Validar que la clave recibida sea un UUID válido.
    try:
        clave_creacion = str(
            UUID(clave_creacion.strip())
        )
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="La clave de creación no es válida."
        )

    
    try:
        
                # Buscar si el usuario ya creó este inventario.
        res_existente = await (
            config.supabase_async
            .table("inventarios")
            .select("id")
            .eq("clave_creacion", clave_creacion)
            .eq("usuario_creador_id", str(user.id))
            .limit(1)  # Evita usar maybe_single().
            .execute()
        )

        # Tratar los resultados como una lista.
        inventarios_existentes = (
            res_existente.data or []
            if res_existente is not None
            else []
        )

        # Reutilizar el inventario si ya existe.
        if inventarios_existentes:
            return RedirectResponse(
                url=(
                    f"/inventario/"
                    f"{inventarios_existentes[0]['id']}?nuevo=1"
                ),
                status_code=303
            )

        # El usuario creador se obtiene del token,
        # nunca del formulario ni de JavaScript.
        payload = {
            "nombre": nombre,
            "realizado_por": realizado_por,
            "tienda": tienda,
            "estado": "borrador",
            "usuario_creador_id": str(user.id),
            "clave_creacion": clave_creacion
        }

        res = await (
            config.supabase_async
            .table("inventarios")
            .insert(payload)
            .select(
                "id, nombre, realizado_por, tienda, "
                "estado, created_at, updated_at"
            )
            .execute()
        )

        inventarios_creados = res.data or []

        if not inventarios_creados:
            raise HTTPException(
                status_code=500,
                detail="No se pudo crear el inventario."
            )

        inventario = inventarios_creados[0]

        if not inventario:
            raise HTTPException(
                status_code=500,
                detail="No se pudo crear el inventario."
            )

        return RedirectResponse(
            url=f"/inventario/{inventario['id']}?nuevo=1",
            status_code=303
        )
    except HTTPException:
        raise

    

    try:
        # Comprobar si la solicitud ya creó el inventario.
        res_existente = await (
            config.supabase_async
            .table("inventarios")
            .select("id")
            .eq("clave_creacion", clave_creacion)
            .eq("usuario_creador_id", str(user.id))
            .limit(1)
            .execute()
        )

        inventarios_existentes = (
            res_existente.data or []
            if res_existente is not None
            else []
        )

        # Si existe, abrir el documento original.
        if inventarios_existentes:
            return RedirectResponse(
                url=(
                    f"/inventario/"
                    f"{inventarios_existentes[0]['id']}?nuevo=1"
                ),
                status_code=303
            )

        # El usuario se obtiene de la sesión validada.
        payload = {
            "nombre": nombre,
            "realizado_por": realizado_por,
            "tienda": tienda,
            "estado": "borrador",
            "usuario_creador_id": str(user.id),
            "clave_creacion": clave_creacion
        }

        res = await (
            config.supabase_async
            .table("inventarios")
            .insert(payload)
            .select("id")
            .execute()
        )

        inventarios_creados = res.data or []

        if not inventarios_creados:
            raise HTTPException(
                status_code=500,
                detail="No se pudo crear el inventario."
            )

        inventario_id_creado = inventarios_creados[0]["id"]

        return RedirectResponse(
            url=f"/inventario/{inventario_id_creado}?nuevo=1",
            status_code=303
        )

    except HTTPException:
        raise

    except Exception as e:
        print(
            "ERROR AL CREAR INVENTARIO: "
            f"{str(e)}"
        )

        # Recuperar el documento si la inserción se confirmó,
        # pero la respuesta de la solicitud falló.
        try:
            res_existente = await (
                config.supabase_async
                .table("inventarios")
                .select("id")
                .eq("clave_creacion", clave_creacion)
                .eq("usuario_creador_id", str(user.id))
                .limit(1)
                .execute()
            )

            inventarios_existentes = (
                res_existente.data or []
                if res_existente is not None
                else []
            )

            if inventarios_existentes:
                return RedirectResponse(
                    url=(
                        f"/inventario/"
                        f"{inventarios_existentes[0]['id']}?nuevo=1"
                    ),
                    status_code=303
                )

        except Exception as error_busqueda:
            print(
                "ERROR AL RECUPERAR INVENTARIO: "
                f"{str(error_busqueda)}"
            )

        raise HTTPException(
            status_code=500,
            detail="No se pudo crear el inventario."
        )


# ============================================================
# VALIDAR PRODUCTOS PARA INVENTARIOS MULTITIENDA
# ============================================================

@router.post("/api/inventarios/multitienda/validar-productos")
async def validar_productos_multitienda(
    request: Request,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Validar sesión.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": "No autorizado."
            }
        )


    perfil = obtener_perfil_inventario(request)

    tipo_usuario = str(
        (perfil or {}).get("tipo_usuario", "")
    ).strip().lower()

    
    if tipo_usuario not in {"normal", "administrador"}:
        return JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "error": (
                    "No tienes permisos para utilizar "
                    "esta función."
                )
            }
        )



    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "El formato de los datos no es válido."
            }
        )

    # Evitar errores si el JSON no es un objeto.
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "El formato de los datos no es válido."
            }
        )

    codigos_recibidos = payload.get("codigos", [])


    if not isinstance(codigos_recibidos, list):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "La lista de códigos no es válida."
            }
        )

    # Limitar el tamaño de la solicitud.
    if len(codigos_recibidos) > 500:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Puedes validar hasta 500 códigos por solicitud."
            }
        )

    # Limpiar códigos y eliminar duplicados conservando el orden.
    codigos = list(dict.fromkeys(
        str(codigo).strip()
        for codigo in codigos_recibidos
        if codigo is not None and str(codigo).strip()
    ))

    if not codigos:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Introduce al menos un código de producto."
            }
        )

    try:
        respuesta = await (
            config.supabase_async
            .table("productos")
            .select("codigo_st, descripcion")
            .in_("codigo_st", codigos)
            .execute()
        )

        productos_encontrados = respuesta.data or []

        # Comparar como texto para preservar los códigos.
        productos_por_codigo = {
            str(producto["codigo_st"]): {
                "codigo": str(producto["codigo_st"]),
                "descripcion": producto.get("descripcion") or ""
            }
            for producto in productos_encontrados
        }

        productos_validos = [
            productos_por_codigo[codigo]
            for codigo in codigos
            if codigo in productos_por_codigo
        ]

        codigos_no_encontrados = [
            codigo
            for codigo in codigos
            if codigo not in productos_por_codigo
        ]

        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "productos": productos_validos,
                "codigos_no_encontrados": codigos_no_encontrados,
                "total_validos": len(productos_validos),
                "total_no_encontrados": len(
                    codigos_no_encontrados
                )
            }
        )

    except Exception as e:
        print(
            "ERROR EN VALIDACIÓN DE PRODUCTOS MULTITIENDA: "
            f"{str(e)}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "No se pudieron validar los productos."
            }
        )


# ============================================================
# CREAR INVENTARIOS PARA VARIAS TIENDAS
# ============================================================

@router.post("/api/inventarios/multitienda/crear")
async def crear_inventarios_multitienda(
    request: Request,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Solo normales y administradores pueden crear inventarios multitienda.
    user = await config.exigir_permiso_backend()

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": "No autorizado."
            }
        )

    perfil = obtener_perfil_inventario(request)

    tipo_usuario = str(
        (perfil or {}).get("tipo_usuario", "")
    ).strip().lower()

    
    if tipo_usuario not in {"normal", "administrador"}:
        return JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "error": (
                    "No tienes permisos para utilizar "
                    "esta función."
                )
            }
        )


    # Leer los datos enviados por el navegador.
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "El formato de los datos no es válido."
            }
        )

    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "El formato de los datos no es válido."
            }
        )

    nombre = str(payload.get("nombre", "")).strip()
    realizado_por = str(
        payload.get("realizado_por", "")
    ).strip()

    tiendas = payload.get("tiendas")
    codigos_recibidos = payload.get("codigos")

    tiendas_permitidas = {
        "CENTRO",
        "NAGUANAGUA",
        "ISABELICA",
        "CIUDAD ALIANZA",
        "GARIBALDI",
        "SAN DIEGO"
    }

    # Validar nombre y responsable.
    if not nombre or not realizado_por:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": (
                    "Indica el nombre del inventario "
                    "y la persona responsable."
                )
            }
        )

    # Validar tiendas seleccionadas.
    if (
        not isinstance(tiendas, list)
        or not tiendas
        or len(tiendas) > len(tiendas_permitidas)
    ):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Selecciona al menos una tienda válida."
            }
        )

    tiendas_limpias = [
        str(tienda).strip().upper()
        for tienda in tiendas
        if isinstance(tienda, str)
    ]

    if (
        len(tiendas_limpias) != len(tiendas)
        or len(set(tiendas_limpias)) != len(tiendas_limpias)
        or any(
            tienda not in tiendas_permitidas
            for tienda in tiendas_limpias
        )
    ):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": (
                    "Hay tiendas inválidas o repetidas "
                    "en la selección."
                )
            }
        )

    # Validar la lista de productos.
    if (
        not isinstance(codigos_recibidos, list)
        or not codigos_recibidos
        or len(codigos_recibidos) > 500
    ):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": (
                    "Introduce entre 1 y 500 códigos de producto."
                )
            }
        )

    if any(
        not isinstance(codigo, (str, int))
        or isinstance(codigo, bool)
        or not str(codigo).strip()
        for codigo in codigos_recibidos
    ):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "La lista contiene códigos inválidos."
            }
        )

    codigos = list(dict.fromkeys(
        str(codigo).strip()
        for codigo in codigos_recibidos
    ))

    # Limitar los campos de texto.
    if len(nombre) > 150 or len(realizado_por) > 150:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": (
                    "El nombre y el responsable "
                    "no pueden superar 150 caracteres."
                )
            }
        )

    try:
        # Confirmar que todos los códigos existen.
        respuesta_productos = await (
            config.supabase_async
            .table("productos")
            .select("codigo_st")
            .in_("codigo_st", codigos)
            .execute()
        )

        codigos_existentes = {
            str(producto["codigo_st"])
            for producto in (respuesta_productos.data or [])
        }

        codigos_invalidos = [
            codigo
            for codigo in codigos
            if codigo not in codigos_existentes
        ]

        if codigos_invalidos:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": (
                        "Hay códigos que no existen "
                        "en el catálogo de productos."
                    ),
                    "codigos_no_encontrados": codigos_invalidos
                }
            )

        
        # Recibir claves estables para permitir reintentos seguros.
        claves_recibidas = payload.get("claves")

        if (
            not isinstance(claves_recibidas, list)
            or len(claves_recibidas) != len(tiendas_limpias)
        ):
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": (
                        "Las claves de operación no son válidas."
                    )
                }
            )

        try:
            claves = [
                str(UUID(str(clave)))
                for clave in claves_recibidas
            ]
        except (ValueError, TypeError, AttributeError):
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "Una o más claves UUID son inválidas."
                }
            )

        if len(set(claves)) != len(claves):
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "Las claves de operación deben ser únicas."
                }
            )


        # La función SQL inserta todos los documentos
        # dentro de una sola transacción.
        respuesta = config.supabase_admin.rpc(
            "crear_inventarios_multitienda",
            {
                "p_user_id": str(user.id),
                "p_nombre": nombre,
                "p_realizado_por": realizado_por,
                "p_tiendas": tiendas_limpias,
                "p_codigos": codigos,
                "p_claves": claves
            }
        ).execute()

        resultado = respuesta.data

        if isinstance(resultado, str):
            import json
            resultado = json.loads(resultado)

        if isinstance(resultado, dict):
            resultado = resultado.get("inventarios", resultado)

        if not isinstance(resultado, list):
            raise ValueError(
                "La función SQL devolvió un resultado inesperado."
            )

        # No informar éxito si faltan documentos.
        if len(resultado) != len(tiendas_limpias):
            raise ValueError(
                "La cantidad de inventarios creados no coincide."
            )

        return JSONResponse(
            status_code=201,
            content={
                "ok": True,
                "mensaje": (
                    f"Se crearon {len(resultado)} inventarios."
                ),
                "inventarios": resultado
            }
        )

    except Exception as e:
        print(
            "ERROR AL CREAR INVENTARIOS MULTITIENDA: "
            f"{str(e)}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": (
                    "No se pudieron crear los inventarios. "
                    "Verifica los datos e inténtalo nuevamente."
                )
            }
        )


# ============================================================
# ABRIR INVENTARIO
# ============================================================

@router.get("/inventario/{inventario_id}")
async def vista_inventario_detalle(
    request: Request,
    inventario_id: int,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    try:
        # ----------------------------------------------------
        # CABECERA DEL INVENTARIO
        # ----------------------------------------------------

        res_inventario = await (
            config.supabase_async
            .table("inventarios")
            .select(
                "id, nombre, realizado_por, tienda, "
                "estado, usuario_creador_id, "
                "created_at, updated_at"
            )
            .eq("id", inventario_id)
            .execute()
        )

        inventarios = res_inventario.data or []

        if not inventarios:
            return RedirectResponse(
                url="/inventario",
                status_code=303
            )

        inventario = inventarios[0]

        # ----------------------------------------------------
        # SEGURIDAD POR TIENDA
        # ----------------------------------------------------

        perfil = obtener_perfil_inventario(request)

        if perfil and es_usuario_provisional(perfil):

            tienda_provisional = obtener_tienda_provisional(
                perfil
            )

            if not tienda_provisional:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "El usuario provisional "
                        "no tiene una tienda asignada."
                    )
                )

            if (
                str(inventario.get("tienda", "")).strip()
                != tienda_provisional
            ):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "No tienes permiso para acceder "
                        "a este inventario."
                    )
                )


        # ----------------------------------------------------
        # DETALLE
        # ----------------------------------------------------

        res_detalle = await (
            config.supabase_async
            .table("inventarios_detalle")
            .select(
                "id, inventario_id, codigo, "
                "descripcion, cantidad, "
                "cantidad_almacen, "
                "cantidad_piso_ventas, orden"
            )
            .eq("inventario_id", inventario_id)
            .order("orden", desc=False)
            .execute()
        )

        productos = res_detalle.data or []

        es_creador_inventario = (
            str(
                inventario.get(
                    "usuario_creador_id"
                )
            )
            == str(user.id)
        )

        return templates.TemplateResponse(
            request=request,
            name="inventario_nuevo.html",
            context={
                "inventario": inventario,
                "productos": productos,
                "perfil": perfil,
                "es_provisional": (
                    perfil
                    and es_usuario_provisional(perfil)
                ),
                "es_creador_inventario": es_creador_inventario
            }
        )



    except HTTPException:
        raise

    except Exception as e:
        print(
            f"ERROR EN /inventario/{inventario_id}: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al cargar el inventario."
        )


# ============================================================
# REABRIR INVENTARIO COMPLETADO
# ============================================================

@router.post("/api/inventario/{inventario_id}/reabrir")
async def reabrir_inventario(
    request: Request,
    inventario_id: int,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Validar la sesión del usuario.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": "No autorizado."
            }
        )

   
    # Obtener el tipo de usuario desde el perfil actual.
    perfil = obtener_perfil_inventario(request)

    tipo_usuario = str(
        perfil.get("tipo_usuario", "")
        if isinstance(perfil, dict)
        else ""
    ).strip().lower()

    # Permitir la reapertura a usuarios normales y administradores.
    tipos_autorizados = {
        "normal",
        "administrador",
    }

    if tipo_usuario not in tipos_autorizados:
        return JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "error": (
                    "Tu tipo de usuario no tiene permiso "
                    "para reabrir inventarios completados."
                )
            }
        )


    try:
        # Cambiar el estado solo si sigue completado.
        resultado = await (
            config.supabase_async
            .table("inventarios")
            .update({
                "estado": "borrador"
            })
            .eq("id", inventario_id)
            .eq("estado", "completado")
            .select("id")
            .execute()
        )

        inventarios_actualizados = (
            resultado.data or []
        )

        # Evitar cambios si el documento no existe
        # o ya no está completado.
        if not inventarios_actualizados:
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": (
                        "El inventario no existe o "
                        "ya no está completado."
                    )
                }
            )

        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "estado": "borrador"
            }
        )

    except Exception as e:
        print(
            "ERROR AL REABRIR INVENTARIO: "
            f"{str(e)}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "No se pudo reabrir el inventario."
            }
        )


# ============================================================
# GUARDAR INVENTARIO
# ============================================================

@router.post("/api/inventario/{inventario_id}/guardar")
async def guardar_inventario(
    request: Request,
    inventario_id: int,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # --------------------------------------------------------
    # 1. VALIDAR SESIÓN
    # --------------------------------------------------------

    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": "No autorizado."
            }
        )

    # --------------------------------------------------------
    # 2. LEER PAYLOAD
    # --------------------------------------------------------

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Datos de inventario inválidos."
            }
        )

    estado = str(
        payload.get("estado", "")
    ).strip().lower()

    productos = payload.get(
        "productos",
        []
    )

    # --------------------------------------------------------
    # 2.5. VERIFICAR ESTADO ACTUAL DEL INVENTARIO
    # --------------------------------------------------------

    res_actual = await (
        config.supabase_async
        .table("inventarios")
        .select(
            "id, estado, tienda, usuario_creador_id"
        )
        .eq("id", inventario_id)
        .maybe_single()
        .execute()
    )

    inventario_actual = res_actual.data

    if not inventario_actual:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": "Inventario no encontrado."
            }
        )
    # ----------------------------------------------------
    # SEGURIDAD PARA USUARIOS PROVISIONALES
    # ----------------------------------------------------

    perfil = obtener_perfil_inventario(request)

    es_provisional = (
        perfil
        and es_usuario_provisional(perfil)
    )

    es_creador_inventario = (
        str(
            inventario_actual.get(
                "usuario_creador_id"
            )
        )
        == str(user.id)
    )

    provisional_proteger_productos = False

    if es_provisional:

        tienda_provisional = obtener_tienda_provisional(
            perfil
        )

        if not tienda_provisional:
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": (
                        "El usuario provisional "
                        "no tiene una tienda asignada."
                    )
                }
            )

        # El inventario debe pertenecer a su tienda.
        if (
            str(
                inventario_actual.get("tienda", "")
            ).strip()
            != tienda_provisional
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": (
                        "No tienes permiso para modificar "
                        "este inventario."
                    )
                }
            )

        # Si el documento fue creado por otro usuario,
        # el Provisional puede modificar cantidades y agregar productos,
        # pero debe conservar los productos existentes.
        if not es_creador_inventario:
            provisional_proteger_productos = True

    # Un inventario completado queda cerrado.
    if inventario_actual.get("estado") == "completado":
        return JSONResponse(
            status_code=409,
            content={
                "ok": False,
                "error":
                    "El inventario ya está completado "
                    "y no puede modificarse."
            }
        )
        
    # --------------------------------------------------------
    # 3. VALIDACIONES BÁSICAS
    # --------------------------------------------------------

    if estado not in {
        "borrador",
        "completado"
    }:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Estado de inventario no válido."
            }
        )

    # --------------------------------------------------------
    # 3.5. ESTRUCTURA ORIGINAL PARA PROVISIONAL
    # --------------------------------------------------------
    #
    # Si el Provisional está trabajando sobre una lista
    # creada por otro usuario, los productos existentes
    # son intocables.
    #
    # Pueden cambiar sus cantidades y agregar productos nuevos.

    productos_originales = []

    if provisional_proteger_productos:

        res_detalle_original = await (
            config.supabase_async
            .table("inventarios_detalle")
            .select(
                "codigo, descripcion, orden, cantidad, "
                "cantidad_almacen, cantidad_piso_ventas"
            )
            .eq(
                "inventario_id",
                inventario_id
            )
            .order(
                "orden",
                desc=False
            )
            .execute()
        )

        productos_originales = (
            res_detalle_original.data or []
        )

        codigos_originales = {
            str(producto.get("codigo", "")).strip()
            for producto in productos_originales
        }

    # --------------------------------------------------------
    # 4. VALIDAR CADA PRODUCTO EN BACKEND
    # --------------------------------------------------------

    productos_limpios = []
    codigos_vistos = set()

    for producto in productos:

        if not isinstance(producto, dict):
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "Producto inválido."
                }
            )

        codigo = str(
            producto.get("codigo", "")
        ).strip()

        descripcion = str(
            producto.get("descripcion", "")
        ).strip()

        if not codigo:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "Existe un producto sin código."
                }
            )

        # Evita duplicados incluso si alguien
        # manipula el navegador.
        if codigo in codigos_vistos:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error":
                        f"El código {codigo} está repetido."
                }
            )

        codigos_vistos.add(codigo)

        # --------------------------------------------
        # Cantidades por ubicación
        # --------------------------------------------

        zonas = producto.get("zonas")

        # Compatibilidad con el formato anterior.
        if not isinstance(zonas, dict):
            zonas = {}

        cantidad_almacen_raw = zonas.get(
            "almacen",
            producto.get("cantidad_almacen",
                         producto.get("cantidad", 0))
        )

        cantidad_piso_raw = zonas.get(
            "piso_ventas",
            producto.get("cantidad_piso_ventas", 0)
        )

        def validar_cantidad_ubicacion(valor, ubicacion):
            # Convierte la cantidad a número.
            try:
                cantidad = float(
                    str(valor).replace(",", ".")
                )
            except (ValueError, TypeError):
                raise ValueError(
                    f"Cantidad inválida para {codigo} "
                    f"en {ubicacion}."
                )

            # Rechaza valores negativos, infinitos y NaN.
            import math

            if not math.isfinite(cantidad) or cantidad < 0:
                raise ValueError(
                    f"La cantidad de {codigo} en "
                    f"{ubicacion} debe ser un número "
                    "finito mayor o igual a cero."
                )

            # Conserva la precisión máxima admitida.
            cantidad_redondeada = round(cantidad, 3)

            if abs(cantidad - cantidad_redondeada) > 0.0000001:
                raise ValueError(
                    f"La cantidad de {codigo} en "
                    f"{ubicacion} admite máximo 3 decimales."
                )

            return cantidad_redondeada

        # Valida ambas cantidades independientemente.
        try:
            cantidad_almacen = validar_cantidad_ubicacion(
                cantidad_almacen_raw,
                "Almacén"
            )

            cantidad_piso_ventas = validar_cantidad_ubicacion(
                cantidad_piso_raw,
                "Piso de Ventas"
            )

        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": str(error)
                }
            )

        # Mantiene la cantidad general por compatibilidad.
        productos_limpios.append({
            "codigo": codigo,
            "descripcion": descripcion,
            "cantidad": cantidad_almacen,
            "cantidad_almacen": cantidad_almacen,
            "cantidad_piso_ventas": cantidad_piso_ventas,
            "zonas": {
                "almacen": cantidad_almacen,
                "piso_ventas": cantidad_piso_ventas
            }
        })
        
    # --------------------------------------------------------
    # 4.5. PROTEGER LA ESTRUCTURA DEL INVENTARIO
    # --------------------------------------------------------

    if provisional_proteger_productos:

        codigos_recibidos = {
            producto["codigo"]
            for producto in productos_limpios
        }

        # Puede agregar productos, pero debe conservar todos los originales.
        if not codigos_originales.issubset(codigos_recibidos):

            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": (
                        "No puedes eliminar ni reemplazar "
                        "productos de una lista creada "
                        "por otro usuario."
                    )
                }
            )

        cantidades_por_codigo = {
            producto["codigo"]: {
                "cantidad_almacen": producto["cantidad_almacen"],
                "cantidad_piso_ventas": producto["cantidad_piso_ventas"]
            }
            for producto in productos_limpios
        }

        # Reconstruimos la lista usando la estructura
        # que realmente existe en la base de datos.
        #
        # El usuario provisional puede modificar las
        # cantidades, pero no el código, la descripción
        # ni el orden de los productos.

        productos_nuevos = [
            producto
            for producto in productos_limpios
            if producto["codigo"] not in codigos_originales
        ]

        productos_limpios = []

        for producto_original in productos_originales:

            codigo_original = str(
                producto_original.get(
                    "codigo",
                    ""
                )
            ).strip()

            cantidades = cantidades_por_codigo[
                codigo_original
            ]

            cantidad_almacen = cantidades[
                "cantidad_almacen"
            ]

            cantidad_piso_ventas = cantidades[
                "cantidad_piso_ventas"
            ]

            productos_limpios.append({
                "codigo": codigo_original,
                "descripcion": str(
                    producto_original.get(
                        "descripcion",
                        ""
                    )
                ).strip(),
                "cantidad": cantidad_almacen,
                "cantidad_almacen": cantidad_almacen,
                "cantidad_piso_ventas": cantidad_piso_ventas,
                "zonas": {
                    "almacen": cantidad_almacen,
                    "piso_ventas": cantidad_piso_ventas
                }
            })

        # Agrega los nuevos al final, conservando el orden de los originales.
        productos_limpios.extend(productos_nuevos)

    # --------------------------------------------------------
    # 5. GUARDAR TODO EN UNA SOLA OPERACIÓN
    # --------------------------------------------------------

    try:

        resultado = await (
            config.supabase_async
            .rpc(
                "guardar_inventario_completo",
                {
                    "p_inventario_id": inventario_id,
                    "p_estado": estado,
                    "p_productos": productos_limpios
                }
            )
            .execute()
        )

        data = resultado.data

        if isinstance(data, list):
            data = data[0] if data else {}

        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "estado": estado,
                "total_productos":
                    len(productos_limpios),
                "resultado": data or {}
            }
        )

    except Exception as e:

        print(
            "ERROR EN "
            f"/api/inventario/{inventario_id}/guardar: "
            f"{str(e)}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error":
                    "No se pudo guardar el inventario."
            }
        )

# ============================================================
# DESCARTAR BORRADOR NUEVO
# ============================================================

@router.delete("/api/inventario/{inventario_id}/descartar")
async def descartar_inventario_nuevo(
    request: Request,  # Necesario para consultar el perfil de la solicitud.
    inventario_id: int,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    # --------------------------------------------------------
    # 1. VALIDAR SESIÓN
    # --------------------------------------------------------

    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": "No autorizado."
            }
        )


    # --------------------------------------------------------
    # 2. BUSCAR EL BORRADOR
    # --------------------------------------------------------

    try:

        res = await (
            config.supabase_async
            .table("inventarios")
            .select(
                "id, estado, tienda, usuario_creador_id"
            )
            .eq("id", inventario_id)
            .maybe_single()
            .execute()
        )

        inventario = res.data

        if not inventario:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error":
                        "Inventario no encontrado."
                }
            )

        # ----------------------------------------------------
        # SEGURIDAD POR TIENDA
        # ----------------------------------------------------

        perfil = obtener_perfil_inventario(request)

        if perfil and es_usuario_provisional(perfil):

            tienda_provisional = obtener_tienda_provisional(
                perfil
            )

            if not tienda_provisional:
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": (
                            "El usuario provisional "
                            "no tiene una tienda asignada."
                        )
                    }
                )

            if (
                str(inventario.get("tienda", "")).strip()
                != tienda_provisional
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": (
                            "No tienes permiso para "
                            "descartar este inventario."
                        )
                    }
                )

        # ----------------------------------------------------
        # 3. SEGURIDAD
        # ----------------------------------------------------
        # Solo se puede descartar un borrador creado
        # por el usuario actual.

        if str(
            inventario.get(
                "usuario_creador_id"
            )
        ) != str(user.id):

            return JSONResponse(
                
                status_code=403,
                content={
                    "ok": False,
                    "error":
                        "No tienes permiso para descartar este inventario."
                }
            )

        
        # ----------------------------------------------------
        # 4. SOLO SE PUEDEN DESCARTAR BORRADORES
        # ----------------------------------------------------

        if (
            str(
                inventario.get("estado")
            ).strip().lower()
            != "borrador"
        ):

            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error":
                        "Solo se pueden descartar inventarios en borrador."
                }
            )


        # ----------------------------------------------------
        # 5. ELIMINAR
        # ----------------------------------------------------
        # inventarios_detalle tiene ON DELETE CASCADE,
        # por lo que sus productos se eliminan
        # automáticamente.

        await (
            config.supabase_async
            .table("inventarios")
            .delete()
            .eq("id", inventario_id)
            .eq(
                "usuario_creador_id",
                str(user.id)
            )
            .eq(
                "estado",
                "borrador"
            )
            .execute()
        )


        return JSONResponse(
            status_code=200,
            content={
                "ok": True
            }
        )


    except Exception as e:

        print(
            "ERROR EN "
            f"/api/inventario/{inventario_id}/descartar: "
            f"{str(e)}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error":
                    "No se pudo descartar el documento."
            }
        )

# ============================================================
# ELIMINAR INVENTARIO COMPLETO
# ============================================================

@router.delete("/api/inventario/{inventario_id}")
async def eliminar_inventario(
    request: Request,
    inventario_id: int,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):

    # --------------------------------------------------------
    # 1. VALIDAR SESIÓN
    # --------------------------------------------------------

    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": "No autorizado."
            }
        )

    # --------------------------------------------------------
    # 2. VERIFICAR EXISTENCIA
    # --------------------------------------------------------

    try:

        res = await (
            config.supabase_async
            .table("inventarios")
            .select(
                "id, estado, tienda, usuario_creador_id"
            )
            .eq("id", inventario_id)
            .maybe_single()
            .execute()
        )

        inventario = res.data

        if not inventario:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error":
                        "Inventario no encontrado."
                }
            )

        # ----------------------------------------------------
        # SEGURIDAD PARA USUARIOS PROVISIONALES
        # ----------------------------------------------------

        perfil = obtener_perfil_inventario(request)

        if perfil and es_usuario_provisional(perfil):

            tienda_provisional = obtener_tienda_provisional(
                perfil
            )

            if not tienda_provisional:
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": (
                            "El usuario provisional "
                            "no tiene una tienda asignada."
                        )
                    }
                )

            # Solo puede eliminar documentos de su tienda.
            if (
                str(inventario.get("tienda", "")).strip()
                != tienda_provisional
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": (
                            "No tienes permiso para "
                            "eliminar este inventario."
                        )
                    }
                )

            # Solo puede eliminar sus propios documentos.
            if (
                str(inventario.get("usuario_creador_id"))
                != str(user.id)
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": (
                            "Solo puedes eliminar tus "
                            "propios inventarios."
                        )
                    }
                )

            # Los usuarios provisionales solo pueden
            # eliminar documentos en borrador.
            if (
                str(inventario.get("estado", "")).strip().lower()
                != "borrador"
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": (
                            "Los inventarios completados "
                            "no se pueden eliminar."
                        )
                    }
                )   


        # ----------------------------------------------------
        # 3. ELIMINAR CABECERA
        # ----------------------------------------------------
        #
        # inventarios_detalle tiene ON DELETE CASCADE,
        # por lo que sus productos se eliminan
        # automáticamente.

        await (
            config.supabase_async
            .table("inventarios")
            .delete()
            .eq("id", inventario_id)
            .execute()
        )

        return JSONResponse(
            status_code=200,
            content={
                "ok": True
            }
        )

    except Exception as e:

        print(
            "ERROR EN "
            f"/api/inventario/{inventario_id}: "
            f"{str(e)}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error":
                    "No se pudo eliminar el inventario."
            }
        )
    
# ============================================================
# ELIMINAR VARIOS INVENTARIOS
# ============================================================

@router.post("/api/inventarios/eliminar-masivo")
async def eliminar_inventarios_masivo(
    request: Request,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # 1. Validar sesión.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": "No autorizado."
            }
        )

    # 2. Validar los identificadores recibidos.
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "La solicitud no contiene datos válidos."
            }
        )

    ids_recibidos = (
        payload.get("ids")
        if isinstance(payload, dict)
        else None
    )

    if (
        not isinstance(ids_recibidos, list)
        or not ids_recibidos
        or len(ids_recibidos) > 100
    ):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": (
                    "Selecciona entre 1 y 100 inventarios."
                )
            }
        )

    # Aceptar IDs enteros o cadenas numéricas positivas.
    ids = []

    for valor in ids_recibidos:
        if isinstance(valor, bool):
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "Hay identificadores inválidos."
                }
            )

        try:
            texto_id = str(valor).strip()

            if not texto_id.isdigit() or int(texto_id) <= 0:
                raise ValueError

            ids.append(int(texto_id))

        except (TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "Hay identificadores inválidos."
                }
            )

    # Eliminar IDs repetidos.
    ids = list(dict.fromkeys(ids))

    try:
        # 3. Consultar todos los inventarios seleccionados.
        resultado = await (
            config.supabase_async
            .table("inventarios")
            .select(
                "id, estado, tienda, usuario_creador_id"
            )
            .in_("id", ids)
            .execute()
        )

        inventarios = resultado.data or []
        encontrados = {int(inv["id"]) for inv in inventarios}

        if encontrados != set(ids):
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": (
                        "Uno o más inventarios no existen. "
                        "No se eliminó ninguno."
                    )
                }
            )

        # 4. Aplicar las restricciones de usuarios provisionales.
        perfil = obtener_perfil_inventario(request)

        if perfil and es_usuario_provisional(perfil):
            tienda_provisional = obtener_tienda_provisional(
                perfil
            )

            if not tienda_provisional:
                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error": (
                            "El usuario provisional "
                            "no tiene una tienda asignada."
                        )
                    }
                )

            for inventario in inventarios:
                if (
                    str(inventario.get("tienda", "")).strip()
                    != tienda_provisional
                ):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "ok": False,
                            "error": (
                                "No tienes permiso para eliminar "
                                "uno o más inventarios."
                            )
                        }
                    )

                if (
                    str(inventario.get("usuario_creador_id"))
                    != str(user.id)
                ):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "ok": False,
                            "error": (
                                "Solo puedes eliminar tus "
                                "propios inventarios."
                            )
                        }
                    )

                if (
                    str(inventario.get("estado", "")).strip().lower()
                    != "borrador"
                ):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "ok": False,
                            "error": (
                                "Los usuarios provisionales "
                                "solo pueden eliminar borradores."
                            )
                        }
                    )

        # 5. Eliminar solo después de validar todos los registros.
        eliminacion = await (
            config.supabase_async
            .table("inventarios")
            .delete()
            .in_("id", ids)
            .select("id")
            .execute()
        )

        ids_eliminados = {
            int(inv["id"])
            for inv in (eliminacion.data or [])
        }

        if ids_eliminados != set(ids):
            print(
                "ADVERTENCIA: eliminación múltiple incompleta. "
                f"Solicitados={ids}; eliminados="
                f"{sorted(ids_eliminados)}"
            )

            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": (
                        "No se pudo confirmar la eliminación "
                        "de todos los inventarios."
                    ),
                    "eliminados": sorted(ids_eliminados)
                }
            )

        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "eliminados": sorted(ids_eliminados),
                "cantidad": len(ids_eliminados)
            }
        )

    except Exception as e:
        print(
            "ERROR EN /api/inventarios/eliminar-masivo: "
            f"{str(e)}"
        )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": (
                    "No se pudieron eliminar los inventarios."
                )
            }
        )
