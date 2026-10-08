import os
from fastapi import FastAPI, Request  # Framework principal web
from fastapi.responses import RedirectResponse  # Redirección HTTP para bloqueo de rutas desprotegidas
from fastapi.staticfiles import StaticFiles  # Soporte de archivos estáticos
from starlette.middleware.sessions import SessionMiddleware  # Middleware para manejo de sesiones
from supabase import create_async_client, ClientOptions  # Importa cliente asíncrono y opciones de timeout

# Importación de configuración y utilidades compartidas
import config
from config import SUPABASE_URL, SUPABASE_KEY, supabase, obtener_usuario_actual

# Importación de rutas modulares
from routes import (
    auth,
    dashboard,
    proveedores,
    ordenes,
    escanear,
    productos,
    analisis,
    calendario,
    inventario,
    usuarios
)

# Inicialización de la aplicación FastAPI
app = FastAPI(title="Control de Compras", version="2.0")

app.mount("/static", StaticFiles(directory="static"), name="static")


from fastapi.responses import FileResponse

@app.get("/service-worker.js", include_in_schema=False)
async def service_worker():
    return FileResponse(
        "static/service-worker.js",
        media_type="application/javascript"
    )

@app.on_event("startup")
async def startup_event():
    # Garantiza la preparación de la instancia asíncrona al levantar FastAPI
    await config.obtener_supabase_async()

# Middleware global de autenticación y control de caché
@app.middleware("http")
async def autenticacion_y_cache_middleware(request: Request, call_next):
    # Lista de rutas que se pueden visitar sin iniciar sesión
    rutas_publicas = [
        "/login",
        "/registro",
        "/recuperar-password",
        "/reset-password",
        "/logout"
    ]
    
    path = request.url.path  # Obtiene la ruta actual solicitada por el usuario
    
    user = request.session.get("user")  # Obtiene los datos del usuario en la sesión
    access_token = request.cookies.get("access_token")  # Verifica si existe la cookie del token de acceso
    
    # Evalúa si la URL consultada es pública o corresponde a recursos estáticos
    es_publica = (
        path in rutas_publicas
        or path.startswith("/static/")
        or path.startswith("/.well-known/")
    )
    
    # Si intenta entrar escribiendo la URL a una vista privada sin credenciales, redirige al login
    if not es_publica and not user and not access_token:
        return RedirectResponse(
            url="/login",
            status_code=303
        )


    # ------------------------------------------------------------
    # USUARIO PROVISIONAL
    # ------------------------------------------------------------
    # Los usuarios provisionales solo pueden trabajar
    # directamente en Inventario.
    perfil_sesion = request.session.get("perfil")

    if (
        user
        and not es_publica
        and isinstance(perfil_sesion, dict)
        and str(
            perfil_sesion.get("tipo_usuario", "")
        ).strip().lower() == "provisional"
    ):

        # ------------------------------------------------------------
        # USUARIO PROVISIONAL
        # ------------------------------------------------------------
        # Los usuarios provisionales solo pueden trabajar
        # dentro de Inventario y utilizar las APIs estrictamente
        # necesarias para que esa pantalla funcione.
        # ------------------------------------------------------------

        if (
            user
            and not es_publica
            and isinstance(perfil_sesion, dict)
            and str(
                perfil_sesion.get("tipo_usuario", "")
            ).strip().lower() == "provisional"
        ):

            rutas_provisionales_permitidas = (
                # Pantallas de Inventario.
                "/inventario",

                # Operaciones propias de Inventario.
                "/api/inventario",

                # Buscador F2 compartido.
                "/api/productos/buscar",
                "/api/productos/buscar-codigo",

                # Importador de productos de Inventario.
                "/api/productos/importar-analisis",

                # Datos necesarios para los filtros/importador.
                "/api/proveedores",
                "/api/clasificacion",

                # Recursos del frontend.
                "/static/",
                "/.well-known/",
            )

            def ruta_provisional_permitida(
                ruta: str
            ) -> bool:

                # Recursos con prefijo.
                if ruta.endswith("/"):
                    return (
                        path == ruta
                        or path.startswith(ruta)
                    )

                # Endpoints exactos o con parámetros después.
                return (
                    path == ruta
                    or path.startswith(ruta + "/")
                    or path.startswith(ruta + "?")
                )

            es_ruta_provisional_permitida = any(
                ruta_provisional_permitida(ruta)
                for ruta in rutas_provisionales_permitidas
            )

            if not es_ruta_provisional_permitida:
                return RedirectResponse(
                    url="/inventario",
                    status_code=303
                )

        if not es_ruta_provisional_permitida:
            return RedirectResponse(
                url="/inventario",
                status_code=303
            )


    request.state.user = user
    request.state.perfil = perfil_sesion

    response = await call_next(request)

    # Los recursos estáticos pueden ser reutilizados por el navegador.
    if path.startswith("/static/"):
        response.headers["Cache-Control"] = (
            "public, max-age=86400"
        )
        return response

    # Las páginas privadas siguen sin almacenarse en caché.
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0, private"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response

# 2. DESPUÉS agregamos SessionMiddleware (se ejecutará primero en cada petición)
SECRET_KEY = os.getenv("SECRET_KEY", "clave_secreta_para_sesiones_local")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Registro de rutas modulares
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(proveedores.router)
app.include_router(ordenes.router)
app.include_router(escanear.router)
app.include_router(productos.router)
app.include_router(analisis.router)
app.include_router(calendario.router)
app.include_router(inventario.router)
app.include_router(usuarios.router)