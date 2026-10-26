import csv
import io
from typing import List, Optional  # Anotaciones de tipos
from fastapi import (
    APIRouter,
    File,
    UploadFile,
    Request,
    Cookie,
    HTTPException,
)  # Componentes FastAPI
from fastapi.responses import RedirectResponse
import config
from config import templates, obtener_usuario_actual  # Dependencias globales
from models import (
    ProductoModificado,
    CodigosVentasRequest,
    GuardarAnalisisRequest,
)  # Modelos de validación para las API

router = APIRouter()

import asyncio
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo  # Fecha actual de Venezuela.
from decimal import Decimal, InvalidOperation

from fastapi import Query

# ============================================================
# NORMALIZACIÓN DEL KARDEX DE VENTAS
# ============================================================


def _normalizar_cabecera_kardex(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))

    texto = "".join(
        caracter for caracter in texto if not unicodedata.combining(caracter)
    )

    return texto.strip().lower().replace(" ", "_").replace("-", "_")


def _normalizar_codigo_kardex(valor):
    codigo = str(valor or "").strip().upper()

    # Evita códigos numéricos convertidos a texto decimal
    # por algunos programas de hojas de cálculo.
    if codigo.endswith(".0") and codigo[:-2].isdigit():
        codigo = codigo[:-2]

    if not codigo:
        return ""

    # Completa hasta seis dígitos sin truncar códigos largos.
    if codigo.isdigit():
        return codigo.zfill(6)

    return codigo


def _parsear_fecha_kardex(valor):
    texto = str(valor or "").strip()

    formatos = (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%y",
        "%Y-%m-%d %H:%M:%S",
    )

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue

    # Admite fechas ISO con hora y zona horaria.
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parsear_cantidad_kardex(valor):
    texto = str(valor or "").strip()

    if not texto:
        return Decimal("0")

    texto = texto.replace(" ", "")

    # Formato del Kardex: punto para miles y coma decimal.
    # Ejemplos:
    # 38,025      -> 38.025
    # 25,56       -> 25.56
    # 1.234,567   -> 1234.567
    # 1.234.567   -> 1234567

    if "," in texto:
        if texto.count(",") != 1:
            raise ValueError(f"Cantidad no válida: {valor}")

        parte_entera, parte_decimal = texto.split(",")

        if not parte_entera or not parte_decimal:
            raise ValueError(f"Cantidad no válida: {valor}")

        if "." in parte_entera:
            grupos = parte_entera.split(".")

            if (
                not grupos[0].isdigit()
                or not 1 <= len(grupos[0]) <= 3
                or any(not grupo.isdigit() or len(grupo) != 3 for grupo in grupos[1:])
            ):
                raise ValueError(f"Cantidad no válida: {valor}")

            parte_entera = "".join(grupos)

        elif not parte_entera.isdigit():
            raise ValueError(f"Cantidad no válida: {valor}")

        if not parte_decimal.isdigit():
            raise ValueError(f"Cantidad no válida: {valor}")

        texto = f"{parte_entera}.{parte_decimal}"

    elif "." in texto:
        grupos = texto.split(".")

        if (
            len(grupos) > 1
            and all(grupo.isdigit() for grupo in grupos)
            and all(len(grupo) == 3 for grupo in grupos[1:])
            and 1 <= len(grupos[0]) <= 3
        ):
            texto = "".join(grupos)

    try:
        cantidad = Decimal(texto)
    except InvalidOperation:
        raise ValueError(f"Cantidad no válida: {valor}")

    if not cantidad.is_finite() or cantidad < 0:
        raise ValueError(f"Cantidad negativa o no válida: {valor}")

    return cantidad


@router.get("/analisis-pedido")
async def vista_analisis_pedido(
    request: Request,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    user = await obtener_usuario_actual(access_token, refresh_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    res_prov = (
        await config.supabase_async.table("proveedores")
        .select("id, nombre")
        .order("nombre")
        .execute()
    )

    proveedores = res_prov.data if res_prov and res_prov.data else []

    return templates.TemplateResponse(
        request=request,
        name="analisis_pedido.html",
        context={"proveedores": proveedores},
    )


@router.get("/api/clasificacion")
async def api_obtener_clasificacion(
    proveedor_id: Optional[int] = None,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    # Verifica que exista una sesión válida.
    user = await obtener_usuario_actual(access_token, refresh_token)

    if not user:
        return []

    # =========================================================
    # CLASIFICACIÓN POR PROVEEDOR
    # =========================================================
    if proveedor_id:

        res = await config.supabase_async.rpc(
            "obtener_clasificacion_proveedor", {"p_proveedor_id": proveedor_id}
        ).execute()

        return res.data or []

    # =========================================================
    # CLASIFICACIÓN GLOBAL
    # =========================================================
    # Se utiliza cuando Inventario no tiene proveedor
    # seleccionado. Solo se cargan los campos necesarios
    # para construir los filtros.
    query = config.supabase_async.table("productos").select(
        "departamento, grupo, subgrupo, marca"
    )

    registros = []
    bloque = 1000
    inicio = 0

    # PostgreSQL/Supabase puede limitar cada respuesta.
    # Recorremos los productos por bloques.
    while True:

        res = await query.range(inicio, inicio + bloque - 1).execute()

        datos = res.data or []

        if not datos:
            break

        registros.extend(datos)

        if len(datos) < bloque:
            break

        inicio += bloque

    # Elimina combinaciones completamente duplicadas
    # para no enviar información innecesaria al navegador.
    unicos = []
    vistos = set()

    for item in registros:

        clave = (
            item.get("departamento") or "",
            item.get("grupo") or "",
            item.get("subgrupo") or "",
            item.get("marca") or "",
        )

        if clave in vistos:
            continue

        vistos.add(clave)
        unicos.append(item)

    return unicos


@router.get("/api/productos/importar-analisis")
async def api_importar_productos_analisis(
    proveedor_id: Optional[int] = None,
    departamento: Optional[str] = "",
    grupo: Optional[str] = "",
    subgrupo: Optional[str] = "",
    marca: Optional[str] = "",
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    # Valida al usuario antes de consultar productos.
    user = await obtener_usuario_actual(access_token, refresh_token)

    # =========================================================
    # VALIDAR SESIÓN
    # =========================================================

    if not user:
        return []

    # =========================================================
    # EVITAR UNA IMPORTACIÓN GLOBAL SIN FILTROS
    # =========================================================
    # Sin proveedor, debe existir al menos una clasificación.
    # Esto evita que un clic accidental intente cargar toda
    # la base de productos.
    hay_filtro_clasificacion = any(
        valor and valor.strip() for valor in (departamento, grupo, subgrupo, marca)
    )

    if not proveedor_id and not hay_filtro_clasificacion:
        return []

    # =========================================================
    # CONSULTA DE PRODUCTOS
    # =========================================================

    query = config.supabase_async.table("productos").select(
        "codigo_st, descripcion, " "unidad_manejo, precio"
    )

    # Si existe proveedor, mantenemos exactamente
    # el comportamiento anterior.
    if proveedor_id:
        query = query.eq("proveedor_id", proveedor_id)

    # Aplica el filtro de departamento cuando exista.
    if departamento and departamento.strip():
        query = query.eq("departamento", departamento.strip())

    # Aplica el filtro de grupo cuando exista.
    if grupo and grupo.strip():
        query = query.eq("grupo", grupo.strip())

    # Aplica el filtro de subgrupo cuando exista.
    if subgrupo and subgrupo.strip():
        query = query.eq("subgrupo", subgrupo.strip())

    # Aplica el filtro de marca cuando exista.
    if marca and marca.strip():
        query = query.eq("marca", marca.strip())

    productos = []
    bloque = 1000
    inicio = 0

    # Mantiene soporte para más de 1000 registros.
    while True:
        res = await query.range(inicio, inicio + bloque - 1).execute()

        datos = res.data or []

        # Finaliza cuando no existan más filas.
        if not datos:
            break

        # Acumula únicamente las columnas solicitadas.
        productos.extend(datos)

        # Si llegó menos del bloque, ya terminamos.
        if len(datos) < bloque:
            break

        # Continúa con el siguiente bloque.
        inicio += bloque

    # Devuelve exactamente lo que necesita la tabla HTML.
    return [
        {
            "codigo": p.get("codigo_st") or "",
            "descripcion": p.get("descripcion") or "",
            "unidad_manejo": p.get("unidad_manejo") or "1",
            "precio": float(p.get("precio") or 0.0),
        }
        for p in productos
    ]


# Actualiza en una sola operación los productos modificados desde Análisis.
@router.post("/api/productos/actualizar-analisis")
async def actualizar_productos_desde_analisis(
    productos: List[ProductoModificado],
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    # Valida la sesión antes de modificar datos.
    user = await obtener_usuario_actual(access_token, refresh_token)

    # Bloquea usuarios no autenticados.
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    # Evita una llamada innecesaria cuando no existen cambios.
    if not productos:
        return {"status": "success", "mensaje": "Sin cambios que procesar"}

    try:
        # Usa un diccionario para evitar códigos duplicados.
        productos_unicos = {}

        # Normaliza el payload recibido.
        for producto in productos:
            codigo = str(producto.codigo or "").strip()

            # Ignora códigos vacíos o inválidos.
            if not codigo or codigo.lower() in {"null", "undefined"}:
                continue

            # Conserva el último cambio recibido para ese código.
            productos_unicos[codigo] = {
                "codigo": codigo,
                "unidad_manejo": str(producto.unidad_manejo or 1),
                "precio": float(producto.precio or 0),
            }

        # Convierte el diccionario nuevamente a lista.
        payload_rpc = list(productos_unicos.values())

        # Evita payloads exageradamente grandes.
        if len(payload_rpc) > 2000:
            raise HTTPException(
                status_code=400,
                detail="No se permiten más de 2000 productos por actualización.",
            )

        # Actualiza todos los registros dentro de PostgreSQL.
        res = await config.supabase_async.rpc(
            "actualizar_productos_analisis", {"p_productos": payload_rpc}
        ).execute()

        # PostgreSQL devuelve la cantidad de registros actualizados.
        actualizados = int(res.data or 0)

        return {
            "status": "success",
            "actualizados": actualizados,
            "mensaje": f"{actualizados} productos actualizados correctamente",
        }

    except HTTPException:
        # Mantiene intactos los códigos HTTP generados arriba.
        raise

    except Exception as e:
        # Registra el error para depuración local/Vercel.
        print(f"ERROR EN /api/productos/actualizar-analisis: {str(e)}")

        raise HTTPException(status_code=500, detail="Error al actualizar productos.")


# ============================================================
# CARGA MASIVA DE VENTAS CSV
# ============================================================
@router.post("/analisis/cargar-ventas-csv")
async def cargar_ventas_csv(
    file: UploadFile = File(...),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    # Valida sesión antes de escribir ventas.
    user = await obtener_usuario_actual(access_token, refresh_token)

    # Bloquea usuarios no autenticados.
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    # Valida el nombre del archivo.
    nombre = (file.filename or "").lower()

    if not nombre.endswith(".csv"):
        raise HTTPException(status_code=400, detail="El archivo debe ser formato .csv")

    try:
        # Lee el archivo una sola vez.
        content = await file.read()

        # Protege el endpoint frente a archivos excesivamente grandes.
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(
                status_code=413, detail="El archivo CSV supera el límite de 15 MB."
            )

        # Abre CSV respetando UTF-8 con BOM.
        stream = io.StringIO(content.decode("utf-8-sig"))

        # Crea el lector de filas.
        reader = csv.DictReader(stream)

        registros = []

        # Procesa cada fila del CSV.
        for row in reader:
            row_clean = {k.strip().lower(): v.strip() for k, v in row.items() if k}

            # Normaliza sede y código.
            sede = row_clean.get("sede", "").upper()
            codigo = row_clean.get("codigo", "").upper()

            # Busca la columna de demanda disponible.
            demanda_raw = (
                row_clean.get("demanda_diaria")
                or row_clean.get("demanda diaria")
                or row_clean.get("demanda")
                or "0"
            )

            # Normaliza separador decimal.
            demanda_str = demanda_raw.replace(",", ".")

            # Descarta filas sin sede/código.
            if sede and codigo:
                try:
                    demanda_val = float(demanda_str)
                except ValueError:
                    demanda_val = 0.0

                registros.append(
                    {"sede": sede, "codigo": codigo, "demanda_diaria": demanda_val}
                )

        # Valida el contenido antes de tocar la BD.
        if not registros:
            raise HTTPException(
                status_code=400, detail="No se encontraron registros válidos en el CSV"
            )

        # Realiza un único UPSERT masivo.
        await (
            config.supabase_async.table("ventas_stellar")
            .upsert(registros, on_conflict="sede,codigo")
            .execute()
        )

        return {"status": "ok", "procesados": len(registros)}

    except HTTPException:
        # Mantiene los códigos 400/413 originales.
        raise

    except Exception as e:
        # Devuelve un error controlado al frontend.
        raise HTTPException(status_code=500, detail=f"Error procesando CSV: {str(e)}")


# ============================================================
# CONSULTA DE VENTAS SOLO PARA CÓDIGOS NECESARIOS
# ============================================================
@router.post("/analisis/obtener-ventas-stellar")
async def obtener_ventas_stellar(
    payload: CodigosVentasRequest,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    # Valida al usuario antes de consultar ventas.
    user = await obtener_usuario_actual(access_token, refresh_token)

    # Bloquea consultas anónimas.
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    # Normaliza y elimina códigos duplicados.
    codigos = list(
        dict.fromkeys(
            str(codigo).strip() for codigo in payload.codigos if str(codigo).strip()
        )
    )

    # Si no hay códigos, evita una consulta a Supabase.
    if not codigos:
        return {"status": "ok", "data": []}

    try:
        # Consulta únicamente ventas de los productos visibles.
        res = await (
            config.supabase_async.table("ventas_stellar")
            .select("sede, codigo, demanda_diaria")
            .in_("codigo", codigos)
            .execute()
        )

        return {"status": "ok", "data": res.data or []}

    except Exception as e:
        # Devuelve un error controlado.
        raise HTTPException(
            status_code=500, detail=f"Error al consultar ventas: {str(e)}"
        )


# ============================================================
# IMPORTACIÓN DEL KARDEX HISTÓRICO DE VENTAS
# ============================================================


@router.post("/analisis/cargar-kardex-ventas")
async def cargar_kardex_ventas(
    file: UploadFile = File(...),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    user = await obtener_usuario_actual(access_token, refresh_token)

    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(
            status_code=400, detail="El archivo debe estar en formato CSV."
        )

    try:
        contenido = await file.read()

        if len(contenido) > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=413, detail="El archivo supera el límite de 50 MB."
            )

        # Detecta las codificaciones habituales de los CSV exportados.
        # Prioriza UTF-8 y luego prueba las codificaciones de Windows.
        texto = None

        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                texto = contenido.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if texto is None:
            raise HTTPException(
                status_code=400,
                detail="No se pudo leer la codificación del archivo CSV.",
            )

        # El kardex puede utilizar coma o punto y coma.
        try:
            dialecto = csv.Sniffer().sniff(texto[:8192], delimiters=";,\t")
        except csv.Error:
            dialecto = csv.excel
            dialecto.delimiter = ";"

        lector = csv.DictReader(io.StringIO(texto), dialect=dialecto)

        if not lector.fieldnames:
            raise HTTPException(
                status_code=400, detail="El CSV no contiene encabezados."
            )

        # Normaliza los nombres de las columnas.
        columnas = {
            _normalizar_cabecera_kardex(nombre): nombre
            for nombre in lector.fieldnames
            if nombre
        }

        def buscar_columna(*alternativas):
            for alternativa in alternativas:
                nombre_real = columnas.get(alternativa)

                if nombre_real:
                    return nombre_real

            return None

        col_sede = buscar_columna("sede", "tienda")

        col_codigo = buscar_columna("codigo", "cod_producto", "codigo_producto")

        col_documento = buscar_columna("documento", "nro_documento", "numero_documento")

        col_movimiento = buscar_columna("movimiento", "tipo_movimiento")

        col_descargos = buscar_columna("descargos", "descargo")

        col_fecha = buscar_columna(
            "fecha", "fecha_movimiento", "fecha_documento", "fecha_venta"
        )

        requeridas = {
            "Sede/Tienda": col_sede,
            "Codigo": col_codigo,
            "Documento": col_documento,
            "Movimiento": col_movimiento,
            "Descargos": col_descargos,
            "Fecha": col_fecha,
        }

        faltantes = [nombre for nombre, columna in requeridas.items() if not columna]

        if faltantes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Faltan columnas necesarias en el kardex: " + ", ".join(faltantes)
                ),
            )

        # Consolida líneas repetidas del mismo producto
        # dentro de la misma transacción y fecha.
        acumulados = {}
        filas_venta = 0
        filas_ignoradas = 0

        for numero_fila, fila in enumerate(lector, start=2):
            movimiento = str(fila.get(col_movimiento) or "").strip().upper()

            # Solo se admiten ventas.
            if movimiento != "VEN":
                filas_ignoradas += 1
                continue

            sede = str(fila.get(col_sede) or "").strip().upper()

            codigo = _normalizar_codigo_kardex(fila.get(col_codigo))

            documento = str(fila.get(col_documento) or "").strip()

            fecha_venta = _parsear_fecha_kardex(fila.get(col_fecha))

            try:
                cantidad = _parsear_cantidad_kardex(fila.get(col_descargos))
            except ValueError as error:
                raise HTTPException(
                    status_code=400, detail=(f"Fila {numero_fila}: {error}")
                )

            if not sede or not codigo or not documento or fecha_venta is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Fila "
                        f"{numero_fila}: falta sede, código, "
                        "documento o fecha válida."
                    ),
                )

            # Las filas con cantidad cero no aportan demanda.
            if cantidad == 0:
                filas_ignoradas += 1
                continue

            clave = (sede, fecha_venta.isoformat(), documento, codigo)

            if clave not in acumulados:
                acumulados[clave] = {
                    "sede": sede,
                    "codigo": codigo,
                    "fecha_venta": fecha_venta.isoformat(),
                    "documento": documento,
                    "descargos": cantidad,
                }
            else:
                acumulados[clave]["descargos"] += cantidad

            filas_venta += 1

        if not acumulados:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se encontraron ventas VEN válidas " "con cantidad positiva."
                ),
            )

        registros = []

        for registro in acumulados.values():
            registro["descargos"] = float(registro["descargos"])
            registros.append(registro)

        # Se utiliza el cliente administrativo síncrono
        # fuera del event loop de FastAPI.
        # El upsert evita duplicados en cargas repetidas.
        tamanio_lote = 500
        procesados = 0

        def guardar_lote(lote):
            return (
                config.supabase_admin.table("ventas_kardex")
                .upsert(lote, on_conflict=("sede,fecha_venta,documento,codigo"))
                .execute()
            )

        for inicio in range(0, len(registros), tamanio_lote):
            lote = registros[inicio : inicio + tamanio_lote]

            await asyncio.to_thread(guardar_lote, lote)

            procesados += len(lote)

        return {
            "status": "ok",
            "filas_venta": filas_venta,
            "registros_consolidados": procesados,
            "filas_ignoradas": filas_ignoradas,
        }

    except HTTPException:
        raise

    except Exception as error:
        print("ERROR AL IMPORTAR KARDEX DE VENTAS:", str(error))

        raise HTTPException(
            status_code=500,
            detail=(
                "No se pudo importar el kardex. " "Revisa el registro del servidor."
            ),
        )


# ============================================================
# COBERTURA DE FECHAS DISPONIBLES DEL KARDEX
# ============================================================


@router.get("/analisis/cobertura-kardex")
async def obtener_cobertura_kardex(
    access_token: str = Cookie(None), refresh_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token, refresh_token)

    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    try:

        def consultar():
            return config.supabase_admin.rpc("obtener_cobertura_kardex", {}).execute()

        respuesta = await asyncio.to_thread(consultar)

        return {"status": "ok", "data": respuesta.data or []}

    except Exception as error:
        print("ERROR AL CONSULTAR COBERTURA DEL KARDEX:", str(error))

        raise HTTPException(
            status_code=500, detail="No se pudo consultar la cobertura del kardex."
        )


# ============================================================
# MESES CON VENTAS DISPONIBLES PARA COMPARACIÓN
# ============================================================

@router.get("/analisis/meses-kardex")
async def consultar_meses_kardex(
    sede: str,
    anio: int,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    user = await obtener_usuario_actual(access_token, refresh_token)

    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    sede_normalizada = sede.strip().upper()

    if not sede_normalizada or len(sede_normalizada) > 80:
        raise HTTPException(
            status_code=400,
            detail="Sede inválida."
        )

    if anio < 2000 or anio > date.today().year:
        raise HTTPException(
            status_code=400,
            detail="Año fuera del rango permitido."
        )

    try:
        def consultar():
            return config.supabase_admin.rpc(
                "obtener_meses_disponibles_kardex",
                {
                    "p_sede": sede_normalizada,
                    "p_anio": anio,
                },
            ).execute()

        respuesta = await asyncio.to_thread(consultar)

        return {
            "status": "ok",
            "sede": sede_normalizada,
            "anio": anio,
            "data": respuesta.data or [],
        }

    except Exception as error:
        print("ERROR AL CONSULTAR MESES DEL KARDEX:", str(error))

        raise HTTPException(
            status_code=500,
            detail="No se pudieron consultar los meses del Kardex."
        )

# ============================================================
# TOOLTIP DE VENTAS: CUATRO SEMANAS COMPLETAS
# ============================================================

MESES_TOOLTIP = (
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
)


def preparar_semanas_tooltip(filas):
    semanas = []

    for numero, fila in enumerate(filas, start=1):
        inicio = date.fromisoformat(fila["fecha_inicio"])

        # El jueves identifica el mes con más días en esa semana.
        mes = (inicio + timedelta(days=3)).month

        semanas.append({
            "etiqueta": f"{MESES_TOOLTIP[mes - 1]} {numero}",
            "inicio": fila["fecha_inicio"],
            "fin": fila["fecha_fin"],
            "unidades": float(fila["unidades_vendidas"]),
            "puesto": 0,
        })

    # En empate gana la semana más reciente.
    mejores = sorted(
        range(len(semanas)),
        key=lambda i: (
            Decimal(str(filas[i]["unidades_vendidas"])),
            semanas[i]["inicio"],
        ),
        reverse=True,
    )[:2]

    for puesto, indice in enumerate(mejores, start=1):
        # Una semana sin ventas no recibe indicador.
        if semanas[indice]["unidades"] > 0:
            semanas[indice]["puesto"] = puesto

    demanda = sum(
        (
            Decimal(str(filas[i]["unidades_vendidas"]))
            for i in mejores
        ),
        Decimal("0"),
    ) / Decimal("14")

    return semanas, float(demanda)


@router.get("/analisis/ventas-semanales-tooltip")
async def obtener_ventas_semanales_tooltip(
    codigo: str = Query(..., min_length=1, max_length=100),
    sede: str = Query(..., min_length=1, max_length=100),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    user = await obtener_usuario_actual(access_token, refresh_token)

    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    codigo = _normalizar_codigo_kardex(codigo)
    sede = sede.strip().upper()

    if sede in ("ALIANZA", "C. ALIANZA"):
        sede = "CIUDAD ALIANZA"

    if not codigo or not sede:
        raise HTTPException(
            status_code=400,
            detail="Código y sede obligatorios.",
        )

    # Excluye siempre la semana que está en curso.
    hoy = datetime.now(ZoneInfo("America/Caracas")).date()
    lunes = hoy - timedelta(days=hoy.weekday())

    try:
        def consultar():
            return config.supabase_admin.rpc(
                "obtener_ventas_semanales_tooltip",
                {
                    "p_codigo": codigo,
                    "p_sede": sede,
                    "p_lunes_actual": lunes.isoformat(),
                },
            ).execute()

        respuesta = await asyncio.to_thread(consultar)
        filas = respuesta.data or []

        if len(filas) != 4:
            raise ValueError(
                "La consulta semanal debe devolver cuatro intervalos."
            )

        semanas, demanda = preparar_semanas_tooltip(filas)

        return {
            "status": "ok",
            "semanas": semanas,
            "demanda_diaria": demanda,
        }

    except Exception as error:
        print("ERROR EN TOOLTIP DE VENTAS:", str(error))

        raise HTTPException(
            status_code=500,
            detail="No se pudieron consultar las ventas.",
        )

# ============================================================
# DEMANDA CALCULADA A PARTIR DEL KARDEX
# ============================================================


@router.get("/analisis/demanda-kardex")
async def obtener_demanda_kardex(
    fecha_inicio: date,
    fecha_fin: date,
    
    codigos: Optional[List[str]] = Query(None),
    modo: str = Query("ventas"),
    access_token: str = Cookie(None),

    refresh_token: str = Cookie(None),
):
    user = await obtener_usuario_actual(access_token, refresh_token)

    if modo not in ("ventas", "intervalo"):
        raise HTTPException(
            status_code=400,
            detail="Modo de cálculo de demanda inválido."
        )

    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    if fecha_inicio > fecha_fin:
        raise HTTPException(
            status_code=400,
            detail=("La fecha inicial no puede ser posterior " "a la fecha final."),
        )

    if not codigos:
        raise HTTPException(
            status_code=400, detail="Debes enviar al menos un código de producto."
        )

    codigos_normalizados = None

    if codigos:
        codigos_normalizados = list(
            dict.fromkeys(
                _normalizar_codigo_kardex(codigo)
                for codigo in codigos
                if _normalizar_codigo_kardex(codigo)
            )
        )

        if not codigos_normalizados:
            return {"status": "ok", "data": []}

    try:

        def consultar():
            return config.supabase_admin.rpc(
                "obtener_demanda_kardex",
                {
                    "p_fecha_inicio": fecha_inicio.isoformat(),
                    "p_fecha_fin": fecha_fin.isoformat(),
                    "p_codigos": codigos_normalizados,
                },
            ).execute()

        
        respuesta = await asyncio.to_thread(consultar)

        # Intervalo calendario inclusivo.
        # Ejemplo: 18/10 al 24/10 = 7 días.
        dias_intervalo = (fecha_fin - fecha_inicio).days + 1

        datos = respuesta.data or []

        # El modo original permanece disponible para
        # los procesos que todavía utilizan esa demanda.
        if modo == "intervalo":
            datos_calculados = []

            for item in datos:
                registro = dict(item)

                unidades = Decimal(
                    str(registro.get("unidades_vendidas") or 0)
                )

                # Nuevo cálculo:
                # Demanda diaria = unidades / días calendario.
                registro["demanda_diaria"] = float(
                    unidades / Decimal(dias_intervalo)
                )

                # Conservamos los días reales con ventas
                # y agregamos la duración del intervalo.
                registro["dias_intervalo"] = dias_intervalo

                datos_calculados.append(registro)

            datos = datos_calculados

        return {
            "status": "ok",
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "modo": modo,
            "dias_intervalo": dias_intervalo,
            "data": datos,
        }


    except Exception as error:
        print("ERROR AL CALCULAR DEMANDA DEL KARDEX:", str(error))

        raise HTTPException(
            status_code=500, detail=("No se pudo calcular la demanda del kardex.")
        )


# ============================================================
# DEMANDA COMERCIAL DEL KARDEX PARA EL MOTOR DE SUGERIDOS
# ============================================================


@router.get("/analisis/demanda-comercial-kardex")
async def consultar_demanda_comercial_kardex(
    fecha_inicio: date,
    fecha_fin: date,
    codigos: Optional[List[str]] = Query(None),
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    user = await obtener_usuario_actual(access_token, refresh_token)

    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    if fecha_inicio > fecha_fin:
        raise HTTPException(status_code=400, detail="Rango de fechas inválido.")

    if not codigos:
        raise HTTPException(
            status_code=400, detail="Debes enviar códigos de productos."
        )

    codigos_normalizados = list(
        dict.fromkeys(
            _normalizar_codigo_kardex(codigo)
            for codigo in codigos
            if _normalizar_codigo_kardex(codigo)
        )
    )

    if not codigos_normalizados:
        return {"status": "ok", "data": []}

    try:

        def consultar():
            return config.supabase_admin.rpc(
                "obtener_demanda_comercial_kardex",
                {
                    "p_fecha_inicio": fecha_inicio.isoformat(),
                    "p_fecha_fin": fecha_fin.isoformat(),
                    "p_codigos": codigos_normalizados,
                },
            ).execute()

        respuesta = await asyncio.to_thread(consultar)

        return {
            "status": "ok",
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "data": respuesta.data or [],
        }

    except Exception as error:
        print("ERROR AL CONSULTAR DEMANDA COMERCIAL KARDEX:", str(error))

        raise HTTPException(
            status_code=500,
            detail="No se pudo calcular la demanda comercial del Kardex.",
        )


# ============================================================
# COMPARACIÓN DE DEMANDA COMERCIAL ACTUAL Y AJUSTADA
# No modifica las cantidades sugeridas.
# ============================================================

@router.get("/analisis/comparar-demanda-comercial-kardex")
async def comparar_demanda_comercial_kardex(
    fecha_inicio: date,
    fecha_fin: date,
    codigos: Optional[List[str]] = Query(None),
    fecha_observacion: Optional[date] = None,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    user = await obtener_usuario_actual(access_token, refresh_token)

    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    hoy = date.today()
    observacion = fecha_observacion or hoy

    if (
        fecha_inicio > fecha_fin
        or (fecha_fin - fecha_inicio).days > 30
        or fecha_fin > hoy
        or observacion < fecha_fin
        or observacion > hoy
    ):
        raise HTTPException(
            status_code=400,
            detail="Fechas inválidas. Utiliza un período de hasta 31 días.",
        )

    codigos_normalizados = list(
        dict.fromkeys(
            _normalizar_codigo_kardex(codigo)
            for codigo in (codigos or [])
            if _normalizar_codigo_kardex(codigo)
        )
    )

    if not codigos_normalizados:
        raise HTTPException(
            status_code=400,
            detail="Debes enviar al menos un código de producto.",
        )

    if len(codigos_normalizados) > 12:
        raise HTTPException(
            status_code=400,
            detail="La comparación admite hasta 12 productos por consulta.",
        )

    parametros = {
        "p_fecha_inicio": fecha_inicio.isoformat(),
        "p_fecha_fin": fecha_fin.isoformat(),
        "p_codigos": codigos_normalizados,
    }

    try:
        def consultar():
            actual = config.supabase_admin.rpc(
                "obtener_demanda_comercial_kardex",
                parametros,
            ).execute()

            ajustada = config.supabase_admin.rpc(
                "obtener_demanda_comercial_ajustada_kardex",
                {
                    **parametros,
                    "p_fecha_observacion": observacion.isoformat(),
                },
            ).execute()

            
            episodios = config.supabase_admin.rpc(
                "detectar_episodios_multisede_kardex",
                parametros,
            ).execute()

            return (
                actual.data or [],
                ajustada.data or [],
                episodios.data or [],
            )


        
        (
            datos_actual,
            datos_ajustada,
            datos_episodios,
        ) = await asyncio.to_thread(consultar)


        return {
            "status": "ok",
            "modo": "solo_comparacion",
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "fecha_observacion": observacion.isoformat(),
            "calendario_actual": "lunes-domingo",
            "calendario_ajustado": "domingo-sabado",
            "data_actual": datos_actual,
            "data_ajustada": datos_ajustada,
            "data_episodios_multi_sede": datos_episodios,

        }

    except Exception as error:
        print(
            "ERROR AL COMPARAR DEMANDA COMERCIAL KARDEX:",
            str(error),
        )
        raise HTTPException(
            status_code=500,
            detail="No se pudo comparar la demanda comercial del Kardex.",
        )



# ============================================================
# GUARDADO TRANSACCIONAL DEL ANÁLISIS
# ============================================================
@router.post("/analisis/guardar-pedido")
async def guardar_analisis_pedido(
    payload: GuardarAnalisisRequest,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
):
    # Obtiene el usuario real desde la cookie.
    user = await obtener_usuario_actual(access_token, refresh_token)

    # No acepta el usuario desde JavaScript.
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    # Evita guardar pedidos vacíos.
    if not payload.detalles:
        raise HTTPException(status_code=400, detail="No existen detalles para guardar.")

    # Convierte los modelos Pydantic al formato JSON esperado por PostgreSQL.
    detalles = [detalle.model_dump() for detalle in payload.detalles]

    try:
        # Ejecuta todo el guardado dentro de una función PostgreSQL.
        res = await config.supabase_async.rpc(
            "guardar_analisis_pedido",
            {
                "p_usuario_id": str(user.id),
                "p_proveedor_id": payload.proveedor_id,
                "p_dias_cobertura": payload.dias_cobertura,
                "p_detalles": detalles,
            },
        ).execute()

        # Recupera la respuesta de la función.
        resultado = res.data or {}

        return {"status": "ok", "analisis_id": resultado.get("analisis_id")}

    except Exception as e:
        # Registra el error internamente.
        print(f"ERROR EN /analisis/guardar-pedido: {str(e)}")

        raise HTTPException(status_code=500, detail="Error al guardar el análisis.")


# ============================================================
# CARGA DEL ÚLTIMO PEDIDO EN UNA SOLA PETICIÓN HTTP
# ============================================================
@router.get("/analisis/ultimo-pedido")
async def obtener_ultimo_pedido(
    access_token: str = Cookie(None), refresh_token: str = Cookie(None)
):
    # Obtiene el usuario real desde la sesión.
    user = await obtener_usuario_actual(access_token, refresh_token)

    # Bloquea usuarios no autenticados.
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    try:
        # Consulta únicamente la última cabecera del usuario.
        res_analisis = await (
            config.supabase_async.table("analisis_pedidos")
            .select("id, proveedor_id, dias_cobertura, updated_at, proveedores(nombre)")
            .eq("usuario_id", str(user.id))
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )

        # Si no existe ningún pedido, termina aquí.
        if not res_analisis.data:
            return {"status": "ok", "encontrado": False}

        # Convierte la primera fila en diccionario independiente.
        analisis = dict(res_analisis.data[0])

        # Extrae la información relacionada del proveedor.
        proveedor = analisis.pop("proveedores", None) or {}

        # Normaliza la relación por si Supabase la devuelve como lista.
        if isinstance(proveedor, list):
            proveedor = proveedor[0] if proveedor else {}

        # Consulta todos los detalles en un solo viaje.
        res_detalles = await (
            config.supabase_async.table("analisis_pedidos_detalle")
            .select("sede, codigo, sugerido, pedido_final")
            .eq("analisis_id", analisis["id"])
            .execute()
        )

        # Obtiene detalles o lista vacía.
        detalles = res_detalles.data or []

        # Extrae códigos únicos para la consulta de productos.
        codigos = list(
            dict.fromkeys(
                str(item.get("codigo")).strip()
                for item in detalles
                if item.get("codigo")
            )
        )

        productos = []

        # Consulta productos solamente si existen códigos.
        if codigos:
            res_productos = await (
                config.supabase_async.table("productos")
                .select("codigo_st, descripcion, precio, unidad_manejo")
                .in_("codigo_st", codigos)
                .execute()
            )

            productos = res_productos.data or []

        # Devuelve todo lo necesario en una sola respuesta HTTP.
        return {
            "status": "ok",
            "encontrado": True,
            "analisis": analisis,
            "proveedor": proveedor,
            "detalles": detalles,
            "productos": productos,
        }

    except Exception as e:
        # Registra error para depuración.
        print(f"ERROR EN /analisis/ultimo-pedido: {str(e)}")

        raise HTTPException(status_code=500, detail="Error al cargar el último pedido.")
