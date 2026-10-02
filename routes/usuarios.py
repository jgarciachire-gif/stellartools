from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse

import config


router = APIRouter()


# ============================================================
# CONFIGURACIÓN
# ============================================================

TIENDAS_PERMITIDAS = [
    "CENTRO",
    "NAGUANAGUA",
    "ISABELICA",
    "CIUDAD ALIANZA",
    "GARIBALDI",
    "SAN DIEGO",
]


# ============================================================
# SEGURIDAD
# ============================================================

def usuario_es_administrador(request: Request) -> bool:
    """
    Verifica que el usuario autenticado sea administrador.
    """
    perfil = request.session.get("perfil")

    if not isinstance(perfil, dict):
        return False

    return (
        str(
            perfil.get("tipo_usuario", "")
        ).strip().lower()
        == "administrador"
    )


def respuesta_no_autorizado():
    """
    Respuesta estándar para usuarios sin permiso.
    """
    return JSONResponse(
        status_code=403,
        content={
            "ok": False,
            "error": "No tienes permisos para realizar esta acción."
        }
    )


# ============================================================
# VISTA DE ADMINISTRACIÓN
# ============================================================

@router.get("/usuarios")
async def vista_usuarios(request: Request):

    if not usuario_es_administrador(request):
        return respuesta_no_autorizado()

    return config.templates.TemplateResponse(
        request=request,
        name="usuarios.html",
        context={
            "tiendas": TIENDAS_PERMITIDAS
        }
    )


# ============================================================
# CREAR USUARIO
# ============================================================

@router.post("/api/usuarios/crear")
async def crear_usuario(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    nombre_comprador: str = Form(...),
    cargo: str = Form(...),
    tipo_usuario: str = Form(...),
    tienda: str = Form("")
):

    # --------------------------------------------------------
    # SEGURIDAD
    # --------------------------------------------------------

    if not usuario_es_administrador(request):
        return respuesta_no_autorizado()

    # --------------------------------------------------------
    # NORMALIZACIÓN
    # --------------------------------------------------------

    email = email.strip().lower()
    password = password.strip()
    nombre_comprador = nombre_comprador.strip()
    cargo = cargo.strip()
    tipo_usuario = tipo_usuario.strip().lower()
    tienda = tienda.strip().upper()

    # --------------------------------------------------------
    # VALIDACIONES
    # --------------------------------------------------------

    if not email:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "El correo electrónico es obligatorio."
            }
        )

    if not password:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "La contraseña es obligatoria."
            }
        )

    if len(password) < 6:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": (
                    "La contraseña debe tener al menos "
                    "6 caracteres."
                )
            }
        )

    if not nombre_comprador:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "El nombre del usuario es obligatorio."
            }
        )

    if tipo_usuario not in ("normal", "provisional"):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "Tipo de usuario no válido."
            }
        )

    # --------------------------------------------------------
    # TIENDA
    # --------------------------------------------------------

    if tipo_usuario == "normal":
        tienda = None

    else:
        if tienda not in TIENDAS_PERMITIDAS:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "Debes seleccionar una tienda válida."
                }
            )

    usuario_auth = None

    try:

        # ----------------------------------------------------
        # 1. CREAR CUENTA EN SUPABASE AUTH
        # ----------------------------------------------------

        resultado_auth = (
            config.supabase_admin
            .auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True
                }
            )
        )

        usuario_auth = resultado_auth.user

        if not usuario_auth:
            raise RuntimeError(
                "Supabase no devolvió el usuario creado."
            )

        # ----------------------------------------------------
        # 2. CREAR PERFIL
        # ----------------------------------------------------

        perfil = {
            "usuario_id": str(usuario_auth.id),
            "nombre_comprador": nombre_comprador,
            "cargo": cargo,
            "tipo_usuario": tipo_usuario,
            "tienda": tienda
        }

        resultado_perfil = await (
            config.supabase_async
            .table("perfiles")
            .insert(perfil)
            .execute()
        )

        if not resultado_perfil.data:
            raise RuntimeError(
                "No se pudo crear el perfil del usuario."
            )

        return JSONResponse(
            status_code=201,
            content={
                "ok": True,
                "mensaje": "Usuario creado correctamente."
            }
        )

    except Exception as e:

        # ----------------------------------------------------
        # ROLLBACK
        # ----------------------------------------------------
        # Si Auth se creó pero el perfil falló,
        # eliminamos la cuenta para evitar un usuario huérfano.

        if usuario_auth:

            try:
                config.supabase_admin.auth.admin.delete_user(
                    str(usuario_auth.id)
                )
            except Exception:
                pass

        print(
            "ERROR AL CREAR USUARIO:",
            str(e)
        )

        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": (
                    "No se pudo crear el usuario. "
                    "Verifica que el correo no esté "
                    "registrado previamente."
                )
            }
        )