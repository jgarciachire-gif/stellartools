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
        # La biblioteca es GLOBAL:
        # todos los usuarios autenticados pueden visualizar
        # los inventarios creados.
        res = await (
            config.supabase_async
            .table("inventarios")
            .select(
                "id, nombre, realizado_por, tienda, "
                "estado, created_at, updated_at"
            )
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
                "inventarios": inventarios
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
    nombre: str = Form(...),
    realizado_por: str = Form(...),
    tienda: str = Form(...),
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

    try:
        # El usuario creador se obtiene del token,
        # nunca del formulario ni de JavaScript.
        payload = {
            "nombre": nombre,
            "realizado_por": realizado_por,
            "tienda": tienda,
            "estado": "borrador",
            "usuario_creador_id": str(user.id)
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

        # Por ahora regresamos a la biblioteca.
        # En el siguiente paso este ID abrirá directamente
        # el documento recién creado.
        # Abrir directamente el Borrador recién creado.
        return RedirectResponse(
            url=f"/inventario/{inventario['id']}",
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
                "estado, created_at, updated_at"
            )
            .eq("id", inventario_id)
            .execute()
        )

        inventarios = res_inventario.data or []

        if not inventarios:
            raise HTTPException(
                status_code=404,
                detail="Inventario no encontrado."
            )

        inventario = inventarios[0]

        if not inventario:
            raise HTTPException(
                status_code=404,
                detail="Inventario no encontrado."
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

        return templates.TemplateResponse(
            request=request,
            name="inventario_nuevo.html",
            context={
                "inventario": inventario,
                "productos": productos
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
        .select("id, estado")
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

    if not isinstance(productos, list):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "La lista de productos no es válida."
            }
        )

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
# ELIMINAR INVENTARIO COMPLETO
# ============================================================

@router.delete("/api/inventario/{inventario_id}")
async def eliminar_inventario(
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
            .select("id, estado")
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