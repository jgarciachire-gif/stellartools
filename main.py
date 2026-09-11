import os
from fastapi import FastAPI, Request  # Framework principal web
from fastapi.staticfiles import StaticFiles  # Soporte de archivos estáticos
from starlette.middleware.sessions import SessionMiddleware  # Middleware para manejo de sesiones
from supabase import create_async_client  # Cliente asíncrono Supabase

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
    config.supabase_async = await create_async_client(SUPABASE_URL, SUPABASE_KEY)

# 1. PRIMERO declaramos el middleware del perfil
@app.middleware("http")
async def cargar_perfil_middleware(request: Request, call_next):
    # Leemos la sesión en memoria local (0 llamadas a Supabase/Red)
    request.state.user = request.session.get("user")
    request.state.perfil = request.session.get("perfil")

    response = await call_next(request)

    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
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