import os  # Para interactuar con el sistema de archivos y variables de entorno
import sys  # Para configurar rutas de inclusión del sistema
import socket  # Para configurar timeouts de red
import urllib.parse  # Para codificar parámetros en URLs
import httpx  # Cliente HTTP con soporte de timeout
from fastapi.templating import Jinja2Templates  # Motor de plantillas Jinja2
from fastapi.responses import HTMLResponse, RedirectResponse  # Respuestas HTTP personalizadas
from fastapi import Cookie  # Para inyección de cookies en dependencias
from supabase import create_client, Client, ClientOptions  # Cliente oficial de Supabase
from supabase import create_async_client  # Cliente asíncrono de Supabase

# Ajuste de rutas globales del sistema
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configuración de timeouts globales de red
socket.setdefaulttimeout(30.0)
httpx._config.DEFAULT_TIMEOUT_CONFIG = httpx.Timeout(timeout=60.0, connect=30.0)

# Credenciales y cliente de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wrcbuseidkupjndpovdd.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_m6ayEiPYF_dIWiNf-9kRog_j-HbKhwA")

supabase: Client = create_client(
    SUPABASE_URL, 
    SUPABASE_KEY,
    options=ClientOptions(
        postgrest_client_timeout=60,
        storage_client_timeout=60
    )
)
supabase_async = None  # Instancia asíncrona global

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

def obtener_usuario_actual(access_token: str = Cookie(None), refresh_token: str = Cookie(None)):
    if not access_token and not refresh_token:
        return None
    try:
        user_response = supabase.auth.get_user(access_token)
        return user_response.user
    except Exception:
        if refresh_token:
            try:
                res = supabase.auth.refresh_session(refresh_token)
                return res.user if res else None
            except Exception:
                return None
        return None

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