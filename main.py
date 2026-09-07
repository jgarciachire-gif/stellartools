from fastapi import FastAPI, Request  # Framework principal web
from fastapi.staticfiles import StaticFiles  # Soporte de archivos estáticos
from starlette.middleware.sessions import SessionMiddleware  # Middleware para manejo de sesiones
from supabase import create_async_client  # Cliente asíncrono Supabase

# Importación de configuración y utilidades compartidas
import config
from config import SUPABASE_URL, SUPABASE_KEY, supabase, obtener_usuario_actual

# Importación de rutas modulares
from routes import auth, dashboard, proveedores, ordenes, escanear, productos, analisis

# Inicialización de la aplicación FastAPI
app = FastAPI(title="Control de Compras", version="2.0")

# Middlewares principales
app.add_middleware(SessionMiddleware, secret_key="clave_secreta_para_sesiones")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    config.supabase_async = await create_async_client(SUPABASE_URL, SUPABASE_KEY)

@app.middleware("http")
async def cargar_perfil_middleware(request: Request, call_next):
    request.state.perfil = None
    access_token = request.cookies.get("access_token")
    
    if access_token:
        user = obtener_usuario_actual(access_token)  
        if user:
            res = supabase.table("perfiles").select("*").eq("usuario_id", user.id).maybe_single().execute()
            request.state.perfil = res.data if res and res.data else None  
            
    response = await call_next(request)

    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response

# Registro de rutas modulares
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(proveedores.router)
app.include_router(ordenes.router)
app.include_router(escanear.router)
app.include_router(productos.router)
app.include_router(analisis.router)