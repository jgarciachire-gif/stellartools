import os  # Para interactuar con el sistema de archivos y variables de entorno
from dotenv import load_dotenv # Carga las variables guardadas en .env
load_dotenv()
import sys  # Para configurar rutas de inclusión del sistema
import urllib.parse  # Para codificar parámetros en URLs
from fastapi.templating import Jinja2Templates  # Motor de plantillas Jinja2
from fastapi.responses import HTMLResponse, RedirectResponse  # Respuestas HTTP personalizadas
from fastapi import Cookie  # Para inyección de cookies en dependencias
from supabase import create_client, Client, ClientOptions  # Cliente oficial de Supabase
from supabase import create_async_client  # Cliente asíncrono de Supabase
from contextlib import asynccontextmanager, ExitStack
import httpx  # Cliente HTTP independiente.
from supabase import AsyncClientOptions  # Opciones asíncronas correctas.
from contextvars import ContextVar  # Contexto independiente por solicitud.
from supabase_auth.errors import AuthApiError, AuthRetryableError
from postgrest.exceptions import APIError
from fastapi import HTTPException

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
# Clave secreta exclusiva del backend.
# NUNCA debe enviarse al navegador.
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


class ClienteSincronoPorSolicitud:
    # Conserva las importaciones existentes de supabase.
    def __getattr__(self, nombre):
        return getattr(obtener_cliente_sincrono(), nombre)


supabase = ClienteSincronoPorSolicitud()

# ============================================================
# CLIENTE ADMINISTRATIVO DE SUPABASE
# ============================================================
#
# Solo se utiliza desde FastAPI para operaciones administrativas.
# Esta clave NUNCA debe llegar al navegador.
# ============================================================

if not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        "Falta la variable de entorno SUPABASE_SECRET_KEY."
    )

supabase_admin: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
    options=ClientOptions(
        postgrest_client_timeout=SUPABASE_TIMEOUT,
        storage_client_timeout=SUPABASE_TIMEOUT,
    )
)

_sesion_actual = ContextVar("sesion_supabase", default=None)


class SesionTemporalmenteNoDisponible(Exception):
    pass


def obtener_cliente_usuario():
    estado = _sesion_actual.get()
    if estado is None:
        raise RuntimeError("No hay una solicitud activa de Supabase.")
    return estado["cliente"]

def obtener_cliente_sincrono():
    estado = _sesion_actual.get()
    if estado is None:
        raise RuntimeError("No hay una solicitud activa de Supabase.")

    if estado.get("cliente_sincrono") is None:
        # Registra la conexión para cerrarla al finalizar esta solicitud.
        http = estado["salidas"].enter_context(
            httpx.Client(
                timeout=httpx.Timeout(
                    SUPABASE_TIMEOUT,
                    connect=SUPABASE_CONNECT_TIMEOUT,
                )
            )
        )

        cliente = create_client(
            SUPABASE_URL,
            SUPABASE_KEY,
            options=ClientOptions(
                httpx_client=http,
                persist_session=False,
                auto_refresh_token=False,
                postgrest_client_timeout=SUPABASE_TIMEOUT,
                storage_client_timeout=SUPABASE_TIMEOUT,
            ),
        )

        if estado.get("access_token"):
            # Usa el token verificado o renovado por el middleware.
            cliente.postgrest.auth(estado["access_token"])

        estado["cliente_sincrono"] = cliente

    return estado["cliente_sincrono"]

class ClienteAsincronoPorSolicitud:
    # Los módulos existentes reciben el cliente de su solicitud.
    def __getattr__(self, nombre):
        return getattr(obtener_cliente_usuario(), nombre)


supabase_async = ClienteAsincronoPorSolicitud()


async def obtener_supabase_async():
    return obtener_cliente_usuario()

@asynccontextmanager
async def cliente_auth_aislado(persistir_sesion: bool = False):
    # Cada operación recibe un cliente independiente.
    timeout = httpx.Timeout(
        SUPABASE_TIMEOUT,
        connect=SUPABASE_CONNECT_TIMEOUT,
    )

    async with httpx.AsyncClient(timeout=timeout) as http:
        cliente = await create_async_client(
            SUPABASE_URL,
            SUPABASE_KEY,
            options=AsyncClientOptions(
                httpx_client=http,
                persist_session=persistir_sesion,
                auto_refresh_token=False,
                postgrest_client_timeout=SUPABASE_TIMEOUT,
                storage_client_timeout=SUPABASE_TIMEOUT,
            ),
        )

        yield cliente  # La conexión se cierra al salir del bloque.

async def _validar_tokens(cliente, access_token, refresh_token):
    try:
        if access_token:
            try:
                respuesta = await cliente.auth.get_user(access_token)
                if respuesta.user:
                    return respuesta.user, access_token, None

            except AuthApiError as error:
                # Una caída del servicio no debe cerrar la sesión.
                if error.status not in (400, 401, 403, 422):
                    raise SesionTemporalmenteNoDisponible() from error

        if refresh_token:
            try:
                respuesta = await cliente.auth.refresh_session(
                    refresh_token
                )
            except AuthApiError as error:
                if error.status not in (400, 401, 403, 422):
                    raise SesionTemporalmenteNoDisponible() from error
                return None, None, None

            if respuesta.user and respuesta.session:
                return (
                    respuesta.user,
                    respuesta.session.access_token,
                    respuesta.session,
                )

        return None, None, None

    except (httpx.HTTPError, AuthRetryableError) as error:
        raise SesionTemporalmenteNoDisponible() from error

@asynccontextmanager
async def sesion_supabase(request):
    async with cliente_auth_aislado() as cliente:
        estado = {
            "cliente": cliente,
            "user": None,
            "renovada": None,
            "borrar_cookies": False,
            "access_token": None,
            "refresh_token": None,
            "cliente_sincrono": None,
            "salidas": ExitStack(),
        }
        contexto = _sesion_actual.set(estado)

        try:
            # Estas operaciones administran sus propias cookies.
            omitir = (
                request.url.path in {
                    "/logout", "/recuperar-password", "/reset-password"
                }
                or (
                    request.url.path == "/login"
                    and request.method == "POST"
                )
            )

            if not omitir:
                access = request.cookies.get("access_token")
                refresh = request.cookies.get("refresh_token")

                user, token, renovada = await _validar_tokens(
                    cliente, access, refresh
                )

                # Descarta la identidad y el perfil guardados anteriormente.
                request.session.pop("user", None)
                request.session.pop("perfil", None)

                if user:
                    # Todas las consultas de este cliente usan este JWT.
                    cliente.postgrest.auth(token)

                    try:
                        resultado = await (
                            cliente.table("perfiles")
                            .select(
                                "usuario_id, nombre_comprador, cargo, "
                                "tipo_usuario, tienda"
                            )
                            .eq("usuario_id", user.id)
                            .maybe_single()
                            .execute()
                        )
                    except (APIError, httpx.HTTPError) as error:
                        raise SesionTemporalmenteNoDisponible() from error

                    perfil = resultado.data if resultado else None

                    permitido = (
                        isinstance(perfil, dict)
                        and perfil.get("tipo_usuario")
                        in {"administrador", "normal", "provisional"}
                        and (
                            perfil.get("tipo_usuario") != "provisional"
                            or bool(str(perfil.get("tienda") or "").strip())
                        )
                    )

                    if permitido:
                        estado["user"] = user
                        estado["renovada"] = renovada
                        estado["access_token"] = token
                        estado["refresh_token"] = (
                            renovada.refresh_token if renovada else refresh
                        )

                        request.session["user"] = {
                            "id": user.id,
                            "email": user.email,
                        }
                        request.session["perfil"] = perfil

                estado["borrar_cookies"] = bool(
                    (access or refresh) and estado["user"] is None
                )

            yield estado

        finally:
            try:
                estado["salidas"].close()  # Cierra conexiones síncronas.
            finally:
                _sesion_actual.reset(contexto)

async def obtener_usuario_actual(
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    # La sesión ya fue verificada por el middleware.
    estado = _sesion_actual.get()
    return estado["user"] if estado is not None else None
async def exigir_permiso_backend(
    tipos_permitidos: tuple[str, ...] = ("normal", "administrador"),
):
    # Usa exclusivamente la identidad verificada de esta solicitud.
    estado = _sesion_actual.get()
    user = estado.get("user") if estado else None

    if user is None:
        raise HTTPException(status_code=401, detail="No autorizado")

    try:
        # Comprueba el permiso actual antes de usar el cliente privilegiado.
        resultado = await (
            estado["cliente"]
            .table("perfiles")
            .select("usuario_id, tipo_usuario")
            .eq("usuario_id", str(user.id))
            .maybe_single()
            .execute()
        )
    except (APIError, httpx.HTTPError) as error:
        raise HTTPException(
            status_code=503,
            detail="No se pudieron verificar los permisos. Reintenta.",
        ) from error

    perfil = resultado.data if resultado else None

    if (
        not isinstance(perfil, dict)
        or str(perfil.get("usuario_id")) != str(user.id)
        or perfil.get("tipo_usuario") not in tipos_permitidos
    ):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos.",
        )

    return user
# Configuración del motor de plantillas HTML
# Configuración del motor de plantillas HTML
# Configuración del motor de plantillas HTML
templates = Jinja2Templates(directory="templates")


# ============================================================
# VERSIONADO AUTOMÁTICO DE RECURSOS ESTÁTICOS
# ============================================================

import time


ASSET_VERSION = (
    os.getenv("VERCEL_GIT_COMMIT_SHA")
    or os.getenv("ASSET_VERSION")
    or str(int(time.time()))
)


def asset_url(path: str) -> str:
    """
    Genera la URL de un recurso estático con su versión.

    Ejemplo:
        asset_url("js/calendario.js")

    devuelve:
        /static/js/calendario.js?v=<version>
    """

    path = str(path).lstrip("/")

    return f"/static/{path}?v={ASSET_VERSION}"


# Hace la función disponible directamente desde cualquier
# plantilla Jinja2.
templates.env.globals["asset_url"] = asset_url

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