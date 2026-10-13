import os
from fastapi import APIRouter, Request, Form, Cookie, Response  # Componentes web FastAPI
from fastapi.responses import RedirectResponse  # Redirecciones HTTP
import traceback
import config  # Importa el módulo de configuración para acceder al cliente asíncrono
from config import supabase, templates, obtener_usuario_actual, script_alerta_modal, script_alerta_error  # Importación de contexto global

router = APIRouter()

# En local HTTP permanece false; en Vercel puedes activarlo con COOKIE_SECURE=true.
COOKIE_SECURE = (
    os.getenv("COOKIE_SECURE", "false").lower()
    == "true"
)

@router.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def chrome_devtools_silencer():
    return Response(status_code=204)

# Convertimos la función a async y agregamos los parámetros de cookies
@router.get("/login")
async def vista_login(request: Request, access_token: str = Cookie(None), refresh_token: str = Cookie(None)):
    if not access_token and not refresh_token:
        return templates.TemplateResponse(request=request, name="login.html", context={})

    # Esperamos la respuesta asíncrona para validar la sesión del usuario
    user = await obtener_usuario_actual(access_token, refresh_token)
    if user:
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(request=request, name="login.html", context={})

@router.post("/login")
async def procesar_login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        # Obtiene el cliente asíncrono resuelto
        client_async = await config.obtener_supabase_async()
        
        # Inicio de sesión asíncrono
        auth_res = await client_async.auth.sign_in_with_password({"email": email.strip(), "password": password})
        user = auth_res.user
        
        # Consulta de perfil asíncrona
        res_perfil = await (
            client_async
            .table("perfiles")
            .select(
                "usuario_id, nombre_comprador, cargo, "
                "tipo_usuario, tienda"
            )
            .eq("usuario_id", user.id)
            .maybe_single()
            .execute()
        )
        perfil_data = res_perfil.data if res_perfil and res_perfil.data else None

        # Almacenamiento en sesión cifrada
        request.session["user"] = {"id": user.id, "email": user.email}
        request.session["perfil"] = perfil_data

        # Los usuarios provisionales entran
        # directamente a la biblioteca de inventarios.
        es_provisional = (
            isinstance(perfil_data, dict)
            and str(
                perfil_data.get("tipo_usuario", "")
            ).strip().lower() == "provisional"
        )

        ruta_inicio = (
            "/inventario"
            if es_provisional
            else "/"
        )

        response = RedirectResponse(
            url=ruta_inicio,
            status_code=303
        )
        
        # Asignación de cookies de autenticación
        response.set_cookie(
            key="access_token", 
            value=auth_res.session.access_token, 
            httponly=True, 
            secure=COOKIE_SECURE, 
            samesite="lax", 
            max_age=3600 * 24 * 7
        )
        response.set_cookie(
            key="refresh_token", 
            value=auth_res.session.refresh_token, 
            httponly=True, 
            secure=COOKIE_SECURE, 
            samesite="lax", 
            max_age=3600 * 24 * 7
        )
        return response
    except Exception as e:
        print("\n================ DETALLE EXACTO DEL ERROR ================")
        traceback.print_exc()  # Muestra en la terminal el archivo, la línea exacta y la causa del fallo
        print("==========================================================\n")
        
        res_error = script_alerta_modal(
            tipo="error", 
            titulo="Error de Acceso", 
            mensaje=f"Supabase rechazó la entrada: {str(e)}"
        )
        res_error.delete_cookie("access_token")
        res_error.delete_cookie("refresh_token")
        request.session.clear()
        return res_error
        

# Envía el correo de recuperación de contraseña.
@router.post("/recuperar-password")
def enviar_recuperacion(
    request: Request,
    email: str = Form(...)
):
    try:
        # Usa el dominio configurado para producción, no el host de la petición.
        base_url = (
            os.getenv("APP_BASE_URL")
            or os.getenv("VERCEL_PROJECT_PRODUCTION_URL")
            or os.getenv("VERCEL_URL")
        )

        if not base_url:
            raise RuntimeError(
                "Falta configurar APP_BASE_URL en el entorno."
            )

        # Vercel puede entregar el dominio sin https://.
        if not base_url.startswith(("https://", "http://")):
            base_url = f"https://{base_url}"

        # Evita una barra doble al construir la URL.
        redirect_to = f"{base_url.rstrip('/')}/reset-password"

        # Solicita a Supabase el envío del enlace.
        config.supabase.auth.reset_password_for_email(
            email.strip(),
            {"redirect_to": redirect_to}
        )

        # No revela si el correo existe en el sistema.
        return script_alerta_modal(
            tipo="exito",
            titulo="Solicitud procesada",
            mensaje=(
                "Si el correo está registrado, recibirás "
                "un enlace para restablecer tu contraseña."
            )
        )

    except Exception:
        # No mostrar al usuario detalles internos del servidor.
        print("ERROR AL SOLICITAR RECUPERACIÓN DE CONTRASEÑA")

        return script_alerta_modal(
            tipo="error",
            titulo="No se pudo procesar",
            mensaje=(
                "No pudimos enviar la solicitud. "
                "Inténtalo nuevamente más tarde."
            )
        )


# Muestra la pantalla para establecer una nueva contraseña.
@router.get("/reset-password", name="vista_reset_password")
def vista_reset_password(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"reset_mode": True}
    )


# Actualiza la contraseña usando la sesión del enlace de recuperación.
@router.post("/reset-password")
def procesar_reset_password(
    access_token: str = Form(...),
    refresh_token: str = Form(...),
    nueva_password: str = Form(...)
):
    access_token = access_token.strip()
    refresh_token = refresh_token.strip()

    # Validación básica adicional en el servidor.
    if not access_token or not refresh_token:
        return script_alerta_modal(
            tipo="error",
            titulo="Enlace inválido",
            mensaje=(
                "El enlace no contiene una sesión válida. "
                "Solicita uno nuevo."
            )
        )

    if len(nueva_password) < 6:
        return script_alerta_modal(
            tipo="error",
            titulo="Contraseña demasiado corta",
            mensaje="La contraseña debe tener al menos 6 caracteres."
        )

    try:
        # Crea un cliente independiente para esta solicitud.
        cliente_reset = config.create_client(
            config.SUPABASE_URL,
            config.SUPABASE_KEY
        )

        # Establece la sesión recibida desde el enlace.
        cliente_reset.auth.set_session(
            access_token,
            refresh_token
        )

        # Supabase valida la sesión antes de actualizar la contraseña.
        cliente_reset.auth.update_user({
            "password": nueva_password
        })

        # Tras el éxito, vuelve al inicio de sesión.
        return script_alerta_modal(
            tipo="exito",
            titulo="Contraseña actualizada",
            mensaje=(
                "Tu contraseña se actualizó correctamente. "
                "Ya puedes iniciar sesión."
            )
        )

    except Exception as e:
        # Registra el tipo de error sin imprimir tokens ni contraseñas.
        print(
            "ERROR AL ACTUALIZAR CONTRASEÑA: "
            f"{type(e).__name__}"
        )

        return script_alerta_modal(
            tipo="error",
            titulo="No se pudo actualizar",
            mensaje=(
                "El enlace puede haber caducado o ser inválido. "
                "Solicita un nuevo correo de recuperación."
            )
        )

# Cierre de sesión y limpieza de rastro en navegador
@router.get("/logout")
def cerrar_sesion(request: Request):
    request.session.clear()  # Elimina todos los datos guardados en la sesión del servidor
    response = RedirectResponse(url="/login", status_code=303)  # Prepara la redirección a la vista de login
    
    # Forzado de eliminación de las cookies de autenticación en todo el dominio
    response.delete_cookie(key="access_token", path="/", httponly=True)  # Borra cookie de acceso
    response.delete_cookie(key="refresh_token", path="/", httponly=True)  # Borra cookie de refresco
    
    # Encabezados anti-caché aplicados a la respuesta del cierre de sesión
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"  # Impide guardar el estado anterior
    response.headers["Pragma"] = "no-cache"  # Encabezado secundario para denegar almacenamiento
    response.headers["Expires"] = "0"  # Expiración instantánea
    
    return response  # Retorna la redirección limpia hacia el login

# Definición asíncrona para la vista principal del perfil
@router.get("/perfil")
async def vista_perfil(request: Request, access_token: str = Cookie(None)):
    # Esperamos el objeto usuario real devuelto por la corrutina
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Consulta a la tabla perfiles usando la ID del usuario ya resuelta
    res_perfil = supabase.table("perfiles").select("*").eq("usuario_id", user.id).maybe_single().execute()
    perfil = res_perfil.data if res_perfil and res_perfil.data else {"nombre_comprador": "", "cargo": ""}

    # Consulta de categorías creadas por el usuario activo
    res_cats = supabase.table("categorias").select("*").eq("usuario_id", user.id).order("nombre").execute()
    categorias = res_cats.data if res_cats and res_cats.data else []

    return templates.TemplateResponse(request=request, name="perfil.html", context={
        "user": user,
        "perfil": perfil,
        "categorias": categorias
    })

# Guardar información personal del perfil
@router.post("/perfil/guardar")
async def guardar_perfil(
    nombre_comprador: str = Form(""),
    cargo: str = Form(""),
    access_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res = supabase.table("perfiles").select("id").eq("usuario_id", user.id).execute()
    
    if res.data:
        supabase.table("perfiles").update({
            "nombre_comprador": nombre_comprador,
            "cargo": cargo
        }).eq("usuario_id", user.id).execute()
    else:
        supabase.table("perfiles").insert({
            "usuario_id": user.id,
            "nombre_comprador": nombre_comprador,
            "cargo": cargo
        }).execute()

    return RedirectResponse(url="/perfil", status_code=303)

# Cambio de contraseña desde la vista de perfil
@router.post("/perfil/cambiar-clave")
async def cambiar_clave(nueva_password: str = Form(...), access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        supabase.auth.update_user({"password": nueva_password})
        return script_alerta_error("¡Contraseña actualizada con éxito!", redireccionar="/perfil")
    except Exception as e:
        return script_alerta_error(f"Error al cambiar contraseña: {str(e)}")

# Creación de nueva categoría
@router.post("/perfil/categorias/crear")
async def crear_categoria(nombre: str = Form(...), access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if nombre.strip():
        supabase.table("categorias").insert({
            "usuario_id": user.id,
            "nombre": nombre.strip()
        }).execute()

    return RedirectResponse(url="/perfil", status_code=303)

# Actualización de categoría existente
@router.post("/perfil/categorias/actualizar/{cat_id}")
async def actualizar_categoria(cat_id: int, nombre: str = Form(...), access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if nombre.strip():
        supabase.table("categorias").update({"nombre": nombre.strip()}).eq("id", cat_id).eq("usuario_id", user.id).execute()

    return RedirectResponse(url="/perfil", status_code=303)

# Eliminación de categoría
@router.post("/perfil/categorias/eliminar/{cat_id}")
async def eliminar_categoria(cat_id: int, access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    supabase.table("categorias").delete().eq("id", cat_id).eq("usuario_id", user.id).execute()

    return RedirectResponse(url="/perfil", status_code=303)