from fastapi import APIRouter, Request, Form, Cookie, Response  # Componentes web FastAPI
from fastapi.responses import RedirectResponse  # Redirecciones HTTP
from config import supabase, templates, obtener_usuario_actual, script_alerta_modal, script_alerta_error  # Importación de contexto global

router = APIRouter()

@router.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def chrome_devtools_silencer():
    return Response(status_code=204)

@router.get("/login")
def vista_login(request: Request):
    access_token = request.cookies.get("access_token")
    refresh_token = request.cookies.get("refresh_token")
    
    if not access_token and not refresh_token:
        return templates.TemplateResponse(request=request, name="login.html", context={})

    if obtener_usuario_actual(access_token, refresh_token):
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(request=request, name="login.html", context={})

@router.post("/registro")
def procesar_registro(email: str = Form(...), password: str = Form(...)):
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        return script_alerta_modal(
            tipo="exito", 
            titulo="¡Registro Exitoso!", 
            mensaje="Hemos enviado un enlace de confirmación a tu correo. Por favor, verifícalo para activar tu cuenta."
        )
    except Exception as e:
        return script_alerta_modal(
            tipo="error", 
            titulo="Error de Registro", 
            mensaje=f"No se pudo crear la cuenta: {str(e)}"
        )

@router.post("/login")
def procesar_login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
        user = auth_res.user
        
        # Consultamos el perfil una sola vez durante el inicio de sesión
        res_perfil = supabase.table("perfiles").select("*").eq("usuario_id", user.id).maybe_single().execute()
        perfil_data = res_perfil.data if res_perfil and res_perfil.data else None

        # Guardamos los datos de usuario y perfil en la sesión cifrada
        request.session["user"] = {"id": user.id, "email": user.email}
        request.session["perfil"] = perfil_data

        response = RedirectResponse(url="/", status_code=303)
        
        response.set_cookie(
            key="access_token", 
            value=auth_res.session.access_token, 
            httponly=True, 
            secure=False, 
            samesite="lax", 
            max_age=3600 * 24 * 7
        )
        response.set_cookie(
            key="refresh_token", 
            value=auth_res.session.refresh_token, 
            httponly=True, 
            secure=False, 
            samesite="lax", 
            max_age=3600 * 24 * 7
        )
        return response
    except Exception as e:
        print(f"\n[DETALLE ERROR SUPABASE]: {e}\n")
        res_error = script_alerta_modal(
            tipo="error", 
            titulo="Error de Acceso", 
            mensaje=f"Supabase rechazó la entrada: {str(e)}"
        )
        res_error.delete_cookie("access_token")
        res_error.delete_cookie("refresh_token")
        request.session.clear()
        return res_error

@router.post("/recuperar-password")
def enviar_recuperacion(request: Request, email: str = Form(...)):
    try:
        redirect_to = str(request.url_for("vista_reset_password"))
        supabase.auth.reset_password_for_email(email, {"redirect_to": redirect_to})
        return script_alerta_modal(
            tipo="exito", 
            titulo="Correo Enviado", 
            mensaje="Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."
        )
    except Exception as e:
        return script_alerta_modal(
            tipo="error", 
            titulo="Error", 
            mensaje=f"No se pudo procesar la solicitud: {str(e)}"
        )

@router.get("/reset-password")
def vista_reset_password(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"reset_mode": True})

@router.post("/reset-password")
def procesar_reset_password(access_token: str = Cookie(None), nueva_password: str = Form(...)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return script_alerta_modal(tipo="error", titulo="Sesión Expirada", mensaje="El enlace de recuperación ha expirado o es inválido.")
    try:
        supabase.auth.update_user({"password": nueva_password})
        return script_alerta_modal(tipo="exito", titulo="Contraseña Actualizada", mensaje="Tu clave se ha cambiado con éxito. Puedes iniciar sesión.")
    except Exception as e:
        return script_alerta_modal(tipo="error", titulo="Error", mensaje=f"Error al actualizar la contraseña: {str(e)}")

@router.get("/logout")
def cerrar_sesion(request: Request):
    request.session.clear()
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response

@router.get("/perfil")
def vista_perfil(request: Request, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res_perfil = supabase.table("perfiles").select("*").eq("usuario_id", user.id).maybe_single().execute()
    perfil = res_perfil.data if res_perfil and res_perfil.data else {"nombre_comprador": "", "cargo": ""}

    res_cats = supabase.table("categorias").select("*").eq("usuario_id", user.id).order("nombre").execute()
    categorias = res_cats.data if res_cats and res_cats.data else []

    return templates.TemplateResponse(request=request, name="perfil.html", context={
        "user": user,
        "perfil": perfil,
        "categorias": categorias
    })

@router.post("/perfil/guardar")
def guardar_perfil(
    nombre_comprador: str = Form(""),
    cargo: str = Form(""),
    access_token: str = Cookie(None)
):
    user = obtener_usuario_actual(access_token)
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

@router.post("/perfil/cambiar-clave")
def cambiar_clave(nueva_password: str = Form(...), access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        supabase.auth.update_user({"password": nueva_password})
        return script_alerta_error("¡Contraseña actualizada con éxito!", redireccionar="/perfil")
    except Exception as e:
        return script_alerta_error(f"Error al cambiar contraseña: {str(e)}")

@router.post("/perfil/categorias/crear")
def crear_categoria(nombre: str = Form(...), access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if nombre.strip():
        supabase.table("categorias").insert({
            "usuario_id": user.id,
            "nombre": nombre.strip()
        }).execute()

    return RedirectResponse(url="/perfil", status_code=303)

@router.post("/perfil/categorias/actualizar/{cat_id}")
def actualizar_categoria(cat_id: int, nombre: str = Form(...), access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if nombre.strip():
        supabase.table("categorias").update({"nombre": nombre.strip()}).eq("id", cat_id).eq("usuario_id", user.id).execute()

    return RedirectResponse(url="/perfil", status_code=303)

@router.post("/perfil/categorias/eliminar/{cat_id}")
def eliminar_categoria(cat_id: int, access_token: str = Cookie(None)):
    user = obtener_usuario_actual(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    supabase.table("categorias").delete().eq("id", cat_id).eq("usuario_id", user.id).execute()

    return RedirectResponse(url="/perfil", status_code=303)