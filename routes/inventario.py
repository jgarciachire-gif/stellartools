from fastapi import (
    APIRouter,
    Request,
    Cookie,
    Form,
    HTTPException
)
from fastapi.responses import (
    RedirectResponse,
    JSONResponse
)

import config
from config import templates, obtener_usuario_actual


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
# BIBLIOTECA DE INVENTARIOS
# ============================================================

@router.get("/inventario")
async def vista_inventario(
    request: Request,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
):
    # Obtiene el usuario real desde la sesión.
    user = await obtener_usuario_actual(
        access_token,
        refresh_token
    )

    # Bloquea el acceso si la sesión no es válida.
    if not user:
        return RedirectResponse(
            url="/login",
            status_code=303
        )

    try:
        perfil = obtener_perfil_inventario(request)

        consulta = (
            config.supabase_async
            .table("inventarios")
            .select(
                "id, nombre, realizado_por, tienda, "
                "estado, created_at, updated_at"
            )
        )

        # Los usuarios provisionales solo ven
        # inventarios de su tienda asignada.
        if perfil and es_usuario_provisional(perfil):
            tienda_provisional = obtener_tienda_provisional(perfil)

            if not tienda_provisional:
                raise HTTPException(
                    status_code=403,
                    detail="El usuario provisional no tiene una tienda asignada."
                )

            consulta = consulta.eq(
                "tienda",
                tienda_provisional
            )

        res = await (
            consulta
            .order(
                "created_at",
                desc=True
            )
            .execute()
        )

        inventarios = res.data or []

        return templates.TemplateResponse(
            request=request,
            name="inventario.html",
            context={
                "inventarios": inventarios,
                "perfil": perfil,
                "es_provisional": (
                    perfil
                    and es_usuario_provisional(perfil)
                )
            }
        )

    except Exception as e:
        print(
            f"ERROR EN /inventario: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al cargar la biblioteca de inventarios."
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

    if not clave_creacion:
        raise HTTPException(
            status_code=400,
            detail="No se pudo validar la solicitud de creación."
        )
    
    try:
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

    except Exception as e:
        print(
            f"ERROR EN /inventario/crear: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Error al crear el inventario."
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
                "descripcion, cantidad, orden"
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
                "es_creador_inventario": es_creador_inventario,
                "es_provisional": (
                    perfil
                    and es_usuario_provisional(perfil)
                )
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

    provisional_solo_cantidades = False

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
        # el Provisional únicamente puede modificar cantidades.
        if not es_creador_inventario:
            provisional_solo_cantidades = True

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
    # Solo pueden cambiar sus cantidades.

    productos_originales = []

    if provisional_solo_cantidades:

        res_detalle_original = await (
            config.supabase_async
            .table("inventarios_detalle")
            .select(
                "codigo, descripcion, orden, cantidad"
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
        # Cantidad
        # --------------------------------------------

        cantidad_raw = producto.get(
            "cantidad",
            0
        )

        try:
            cantidad = float(
                str(cantidad_raw)
                .replace(",", ".")
            )
        except (
            ValueError,
            TypeError
        ):
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error":
                        f"Cantidad inválida para {codigo}."
                }
            )

        # No se permiten negativos.
        if cantidad < 0:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error":
                        f"La cantidad de {codigo} "
                        "no puede ser negativa."
                }
            )

        # No se permiten infinitos / NaN.
        if not cantidad == cantidad:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error":
                        f"Cantidad inválida para {codigo}."
                }
            )

        # Máximo 3 decimales.
        cantidad_3 = round(
            cantidad,
            3
        )

        if abs(
            cantidad - cantidad_3
        ) > 0.0000001:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error":
                        f"La cantidad de {codigo} "
                        "admite máximo 3 decimales."
                }
            )

        productos_limpios.append({
            "codigo": codigo,
            "descripcion": descripcion,
            "cantidad": cantidad_3
        })
    # --------------------------------------------------------
    # 4.5. PROTEGER LA ESTRUCTURA DEL INVENTARIO
    # --------------------------------------------------------

    if provisional_solo_cantidades:

        codigos_recibidos = {
            producto["codigo"]
            for producto in productos_limpios
        }

        # No puede agregar ni eliminar productos.
        if codigos_recibidos != codigos_originales:

            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": (
                        "No puedes agregar ni eliminar "
                        "productos de una lista creada "
                        "por otro usuario."
                    )
                }
            )

        cantidades_por_codigo = {
            producto["codigo"]: producto["cantidad"]
            for producto in productos_limpios
        }

        # Reconstruimos la lista usando la estructura
        # que realmente existe en la base de datos.
        #
        # De esta manera el navegador tampoco puede
        # modificar descripción ni orden.

        productos_limpios = []

        for producto_original in productos_originales:

            codigo_original = str(
                producto_original.get(
                    "codigo",
                    ""
                )
            ).strip()

            productos_limpios.append({
                "codigo": codigo_original,
                "descripcion": str(
                    producto_original.get(
                        "descripcion",
                        ""
                    )
                ).strip(),
                "cantidad": cantidades_por_codigo[
                    codigo_original
                ]
            })

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