import os  # Para interactuar con el sistema de archivos y variables de entorno
import sys  # Para configurar rutas de inclusión del sistema
import urllib.parse  # Para codificar parámetros en URLs
from fastapi.templating import Jinja2Templates  # Motor de plantillas Jinja2
from fastapi.responses import HTMLResponse, RedirectResponse  # Respuestas HTTP personalizadas
from fastapi import Cookie  # Para inyección de cookies en dependencias
from supabase import create_client, Client, ClientOptions  # Cliente oficial de Supabase
from supabase import create_async_client  # Cliente asíncrono de Supabase

# Ajuste de rutas globales del sistema
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# TIMEOUTS DE SUPABASE
# ============================================================

SUPABASE_TIMEOUT = float(os.getenv("SUPABASE_TIMEOUT", "20"))
SUPABASE_CONNECT_TIMEOUT = float(
    os.getenv("SUPABASE_CONNECT_TIMEOUT", "5")
)

# Credenciales y cliente de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wrcbuseidkupjndpovdd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_m6ayEiPYF_dIWiNf-9kRog_j-HbKhwA")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(
        postgrest_client_timeout=SUPABASE_TIMEOUT,
        storage_client_timeout=SUPABASE_TIMEOUT,
    )
)
# Adaptador de almacenamiento en memoria 100% asíncrono para el cliente de Supabase Auth
class AsyncMemoryStorage:
    def __init__(self):
        self._storage = {}  # Diccionario interno de almacenamiento temporal

    async def get_item(self, key: str):
        return self._storage.get(key)  # Recuperación asíncrona del token

    async def set_item(self, key: str, value: str):
        self._storage[key] = value  # Guardado asíncrono del token

    async def remove_item(self, key: str):
        self._storage.pop(key, None)  # Eliminación asíncrona requerida por GoTrue

supabase_async = None  # Instancia asíncrona global

async def obtener_supabase_async():
    global supabase_async
    # Inicialización asíncrona inyectando AsyncMemoryStorage para solucionar el error NoneType en await
    if supabase_async is None:
        supabase_async = await create_async_client(
            SUPABASE_URL, 
            SUPABASE_KEY,
            options=ClientOptions(
                storage=AsyncMemoryStorage(),

                # Evita mantener solicitudes lentas abiertas indefinidamente.
                postgrest_client_timeout=SUPABASE_TIMEOUT,

                # Mantiene el mismo límite para Storage.
                storage_client_timeout=SUPABASE_TIMEOUT,
            )
        )
    return supabase_async

async def obtener_usuario_actual(
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    # No hay ninguna sesión que validar.
    if not access_token:
        return None
    try:
        # Obtiene el cliente asíncrono inicializado para validar la cookie de sesión
        client = await obtener_supabase_async()
        user_response = await client.auth.get_user(access_token)
        return user_response.user
    except Exception:
        if refresh_token:
            try:
                client = await obtener_supabase_async()
                res = await client.auth.refresh_session(refresh_token)
                return res.user if res else None
            except Exception:
                return None
        return None

# Configuración del motor de plantillas HTML
templates = Jinja2Templates(directory="templates")

# Filtros para plantillas Jinja2
def formato_moneda_latina(valor):
    if valor is None:
        return "0,00"
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def limpiar_cantidad(valor):
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    val_limpio = str(valor).replace(",", "").strip()
    try:
        return float(val_limpio)
    except ValueError:
        return 0.0

templates.env.filters["moneda"] = formato_moneda_latina
templates.env.filters["limpiar_cantidad"] = limpiar_cantidad

# Funciones auxiliares globales
def sanitizar_numero(val):
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    if "." in val_str and "," in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    elif "." in val_str and len(val_str.split(".")[-1]) == 3:
        val_str = val_str.replace(".", "")
    elif "," in val_str:
        val_str = val_str.replace(",", "")
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def limpiar_monto_decimal(valor_str):
    texto = str(valor_str).strip().replace('$', '')
    if ',' in texto and '.' in texto:
        texto = texto.replace(',', '')
    elif ',' in texto:
        texto = texto.replace(',', '.')
    try:
        return round(float(texto), 2)
    except ValueError:
        return 0.0

def script_alerta_error(mensaje: str, redireccionar: str = None) -> HTMLResponse:
    msj_limpio = mensaje.replace("'", "\\'").replace("\n", " ")
    if redireccionar:
        js = f"<script>alert('{msj_limpio}'); window.location.href='{redireccionar}';</script>"
    else:
        js = f"<script>alert('{msj_limpio}'); window.history.back();</script>"
    return HTMLResponse(content=js)

def script_alerta_modal(tipo: str, titulo: str, mensaje: str, redireccionar: str = "/login") -> RedirectResponse:
    msj_enc = urllib.parse.quote(mensaje)
    tit_enc = urllib.parse.quote(titulo)
    return RedirectResponse(url=f"{redireccionar}?msg_tipo={tipo}&msg_titulo={tit_enc}&msg_texto={msj_enc}", status_code=303)