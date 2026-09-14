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
from routes import auth, dashboard, proveedores, ordenes, escanear, productos, analisis, calendario

# Inicialización de la aplicación FastAPI
app = FastAPI(title="Control de Compras", version="2.0")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    # Garantiza la preparación de la instancia asíncrona al levantar FastAPI
    await config.obtener_supabase_async()

# Middleware global de autenticación y control de caché
@app.middleware("http")
async def autenticacion_y_cache_middleware(request: Request, call_next):
    # Lista de rutas que se pueden visitar sin iniciar sesión
    rutas_publicas = ["/login", "/registro", "/recuperar-password", "/reset-password"]
    
    path = request.url.path  # Obtiene la ruta actual solicitada por el usuario
    
    user = request.session.get("user")  # Obtiene los datos del usuario en la sesión
    access_token = request.cookies.get("access_token")  # Verifica si existe la cookie del token de acceso
    
    # Evalúa si la URL consultada es pública o corresponde a recursos estáticos
    es_publica = any(path.startswith(r) for r in rutas_publicas) or path.startswith("/static") or path.startswith("/.well-known")
    
    # Si intenta entrar escribiendo la URL a una vista privada sin credenciales, redirige al login
    if not es_publica and not user and not access_token:
        return RedirectResponse(url="/login", status_code=303)

    request.state.user = user  # Asigna el usuario al estado de la petición actual
    request.state.perfil = request.session.get("perfil")  # Asigna el perfil al estado de la petición

    response = await call_next(request)  # Procesa la vista correspondiente

    # Fuerza al navegador a no guardar copia de la página en memoria para anular el botón "Atrás"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"  # Prohíbe el almacenamiento local
    response.headers["Pragma"] = "no-cache"  # Compatibilidad con navegadores HTTP/1.0
    response.headers["Expires"] = "0"  # Expira el contenido inmediatamente

    return response  # Devuelve la respuesta final

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