import json  # Manejo de formatos JSON
from typing import Optional  # Anotaciones de tipos opcionales
import xml.etree.ElementTree as ET  # Procesamiento de archivos XML
from datetime import datetime  # Fechas
from fastapi import APIRouter, Request, Form, UploadFile, File, Cookie  # Dependencias FastAPI
from fastapi.responses import RedirectResponse, HTMLResponse, Response, JSONResponse  # Importa JSONResponse para respuestas de API
from config import (
    templates,
    obtener_usuario_actual,
    obtener_supabase_async,
    script_alerta_error,
)

router = APIRouter()

async def _db():
    """
    Obtiene el cliente asíncrono compartido de Supabase.

    Mantiene toda la capa de proveedores trabajando
    con I/O no bloqueante.
    """
    return await obtener_supabase_async()

@router.get("/proveedores")
async def vista_proveedores(
    request: Request,
    select: int = None,
    access_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    client = await _db()

    res = await (
        client
        .table("proveedores")
        .select("*")
        .order("nombre")
        .execute()
    )

    proveedores = res.data if res and res.data else []

    res_cats = await (
        client
        .table("categorias")
        .select("*")
        .eq("usuario_id", user.id)
        .order("nombre")
        .execute()
    )

    categorias_disponibles = (
        res_cats.data
        if res_cats and res_cats.data
        else []
    )

    prov_obj = None

    if select:
        res_sel = await (
            client
            .table("proveedores")
            .select("*")
            .eq("id", select)
            .maybe_single()
            .execute()
        )

        if res_sel and res_sel.data:
            prov_obj = res_sel.data

    return templates.TemplateResponse(
        request=request,
        name="proveedores.html",
        context={
            "proveedores": proveedores,
            "prov_obj": prov_obj,
            "categorias_disponibles": categorias_disponibles,
        }
    )
    
@router.post("/proveedores/importar-xml")
async def importar_proveedores_xml(
    archivo_xml: UploadFile = File(...),
    access_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    MAX_XML_SIZE = 10 * 1024 * 1024  # 10 MB
    TAMANO_LOTE = 100

    nombre_archivo = (archivo_xml.filename or "").strip()

    if not nombre_archivo.lower().endswith(".xml"):
        return script_alerta_error(
            "El archivo seleccionado no tiene extensión XML.",
            redireccionar="/proveedores"
        )

    contenido = await archivo_xml.read()

    if not contenido:
        return script_alerta_error(
            "El archivo XML está vacío.",
            redireccionar="/proveedores"
        )

    if len(contenido) > MAX_XML_SIZE:
        return script_alerta_error(
            "El archivo XML supera el límite permitido de 10 MB.",
            redireccionar="/proveedores"
        )

    try:
        arbol = ET.fromstring(contenido)
    except ET.ParseError:
        return script_alerta_error(
            "El archivo XML no tiene un formato válido.",
            redireccionar="/proveedores"
        )

    registros = arbol.findall(".//Proveedor")

    if not registros:
        return script_alerta_error(
            "El XML no contiene registros de proveedores.",
            redireccionar="/proveedores"
        )

    def convertir_entero(valor, defecto):
        try:
            return int(str(valor).strip())
        except (TypeError, ValueError):
            return defecto

    datos_importacion = []
    errores = []

    # Transformamos y validamos el XML antes de tocar la base de datos.
    for indice, prov in enumerate(registros, start=1):

        nombre = (
            prov.findtext("Nombre") or ""
        ).strip()

        if not nombre:
            errores.append(
                f"Registro {indice}: falta el nombre del proveedor."
            )
            continue

        codigo = (
            prov.findtext("Codigo") or ""
        ).strip()

        contacto = (
            prov.findtext("Contacto") or ""
        ).strip()

        telefono = (
            prov.findtext("Telefono") or ""
        ).strip()

        email = (
            prov.findtext("Email") or ""
        ).strip()

        categorias_texto = (
            prov.findtext("Categorias") or ""
        ).strip()

        categorias = [
            categoria.strip()
            for categoria in categorias_texto.split(",")
            if categoria.strip()
        ]

        datos_importacion.append({
            "codigo": codigo,
            "nombre": nombre,
            "contacto": contacto,
            "telefono": telefono,
            "email": email,
            "dias_credito": convertir_entero(
                prov.findtext("DiasCredito"),
                0
            ),
            "dias_despacho": convertir_entero(
                prov.findtext("FrecuenciaPedidos"),
                3
            ),
            "categorias": categorias,
        })

    if not datos_importacion:
        return script_alerta_error(
            "No se encontraron proveedores válidos para importar.",
            redireccionar="/proveedores"
        )

    client = await _db()

    # Consultamos una sola vez qué proveedores ya existen.
    res_existentes = await (
        client
        .table("proveedores")
        .select("nombre")
        .execute()
    )

    nombres_existentes = set()

    if res_existentes and res_existentes.data:
        nombres_existentes = {
            str(proveedor.get("nombre") or "").strip()
            for proveedor in res_existentes.data
            if proveedor.get("nombre")
        }

    procesados = 0
    nuevos = 0
    actualizados = 0

    # Evita contar dos veces el mismo nombre si el XML lo contiene.
    nombres_procesados = set()

    for inicio in range(
        0,
        len(datos_importacion),
        TAMANO_LOTE
    ):
        lote = datos_importacion[
            inicio:inicio + TAMANO_LOTE
        ]

        try:
            resultado = await (
                client
                .table("proveedores")
                .upsert(
                    lote,
                    on_conflict="nombre"
                )
                .execute()
            )

            if not resultado or not resultado.data:
                raise Exception(
                    "Supabase no confirmó el procesamiento del lote."
                )

            for proveedor in lote:
                nombre = proveedor["nombre"]

                # Un mismo nombre dentro del XML solo cuenta una vez.
                if nombre in nombres_procesados:
                    continue

                nombres_procesados.add(nombre)
                procesados += 1

                if nombre in nombres_existentes:
                    actualizados += 1
                else:
                    nuevos += 1

        except Exception:
            # Si falla el lote, procesamos individualmente
            # para identificar exactamente los registros problemáticos.
            for posicion, proveedor in enumerate(lote):
                numero_registro = inicio + posicion + 1
                nombre = proveedor["nombre"]

                if nombre in nombres_procesados:
                    continue

                try:
                    resultado = await (
                        client
                        .table("proveedores")
                        .upsert(
                            proveedor,
                            on_conflict="nombre"
                        )
                        .execute()
                    )

                    if not resultado or not resultado.data:
                        raise Exception(
                            "Supabase no confirmó el procesamiento."
                        )

                    nombres_procesados.add(nombre)
                    procesados += 1

                    if nombre in nombres_existentes:
                        actualizados += 1
                    else:
                        nuevos += 1

                except Exception as exc:
                    errores.append(
                        f"Registro {numero_registro} "
                        f"({nombre}): {str(exc)}"
                    )

    if errores:
        resumen = (
            f"Importación terminada. "
            f"Procesados: {procesados}. "
            f"Nuevos: {nuevos}. "
            f"Actualizados: {actualizados}. "
            f"Errores: {len(errores)}."
        )

        muestra = " | ".join(errores[:5])

        if len(errores) > 5:
            muestra += " | ..."

        return script_alerta_error(
            f"{resumen} {muestra}",
            redireccionar="/proveedores"
        )

    return script_alerta_error(
        (
            f"Importación terminada correctamente. "
            f"Procesados: {procesados}. "
            f"Nuevos: {nuevos}. "
            f"Actualizados: {actualizados}."
        ),
        redireccionar="/proveedores"
    )

@router.get("/proveedores/exportar-xml")
async def exportar_proveedores_xml(
    request: Request,
    access_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    client = await _db()

    res = await (
        client
        .table("proveedores")
        .select("*")
        .order("nombre")
        .execute()
    )

    proveedores = res.data if res and res.data else []

    root = ET.Element("Proveedores")

    for proveedor in proveedores:
        item = ET.SubElement(root, "Proveedor")

        ET.SubElement(item, "Codigo").text = (
            str(proveedor.get("codigo") or "")
        )

        ET.SubElement(item, "Nombre").text = (
            str(proveedor.get("nombre") or "")
        )

        ET.SubElement(item, "Contacto").text = (
            str(proveedor.get("contacto") or "")
        )

        ET.SubElement(item, "Telefono").text = (
            str(proveedor.get("telefono") or "")
        )

        ET.SubElement(item, "Email").text = (
            str(proveedor.get("email") or "")
        )

        ET.SubElement(item, "DiasCredito").text = str(
            proveedor.get("dias_credito")
            if proveedor.get("dias_credito") is not None
            else 0
        )

        ET.SubElement(item, "FrecuenciaPedidos").text = str(
            proveedor.get("dias_despacho")
            if proveedor.get("dias_despacho") is not None
            else 3
        )

        categorias = proveedor.get("categorias") or []

        if isinstance(categorias, list):
            categorias_str = ", ".join(
                str(categoria)
                for categoria in categorias
            )
        else:
            categorias_str = str(categorias)

        ET.SubElement(item, "Categorias").text = categorias_str

    xml_data = ET.tostring(
        root,
        encoding="utf-8",
        method="xml"
    )

    return Response(
        content=xml_data,
        media_type="application/xml",
        headers={
            "Content-Disposition": (
                "attachment; filename=proveedores.xml"
            )
        }
    )

@router.post("/proveedores/guardar")
async def guardar_proveedor(
    id: Optional[str] = Form(None),
    codigo: str = Form(""),
    nombre: Optional[str] = Form(""),
    contacto: str = Form(""),
    telefono: str = Form(""),
    email: str = Form(""),
    dias_credito: Optional[str] = Form("0"),
    dias_despacho: Optional[str] = Form("3"),
    categorias: str = Form("[]"),
    access_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    nombre_limpio = (nombre or "").strip()

    if not nombre_limpio:
        return script_alerta_error(
            "El nombre del proveedor es obligatorio.",
            redireccionar="/proveedores"
        )

    prov_id = int(id) if id and id.strip().isdigit() else None

    credito_num = (
        int(dias_credito)
        if dias_credito and dias_credito.strip().isdigit()
        else 0
    )

    despacho_num = (
        int(dias_despacho)
        if dias_despacho and dias_despacho.strip().isdigit()
        else 3
    )

    try:
        lista_categorias = json.loads(categorias)

        if not isinstance(lista_categorias, list):
            lista_categorias = []

    except (json.JSONDecodeError, TypeError):
        lista_categorias = []

    fecha_actual = datetime.now().strftime("%d-%m-%Y")
    usuario_str = (
        user.email
        if user and hasattr(user, "email")
        else "Usuario"
    )

    historial_mod = (
        f"Última modificación hecha por "
        f"{usuario_str} el {fecha_actual}."
    )

    datos_payload = {
        "codigo": codigo.strip(),
        "nombre": nombre_limpio,
        "contacto": contacto.strip(),
        "telefono": telefono.strip(),
        "email": email.strip(),
        "dias_credito": credito_num,
        "dias_despacho": despacho_num,
        "categorias": lista_categorias,
        "ultima_modificacion": historial_mod
    }

    client = await _db()

    try:
        if prov_id:
            resultado = await (
                client
                .table("proveedores")
                .update(datos_payload)
                .eq("id", prov_id)
                .execute()
            )

            if not resultado or not resultado.data:
                return script_alerta_error(
                    "No se pudo actualizar el proveedor.",
                    redireccionar=f"/proveedores?select={prov_id}"
                )

            redirect_url = f"/proveedores?select={prov_id}"

        else:
            datos_payload["dias_inventario"] = 15

            resultado = await (
                client
                .table("proveedores")
                .insert(datos_payload)
                .execute()
            )

            if not resultado or not resultado.data:
                return script_alerta_error(
                    "No se pudo guardar el proveedor.",
                    redireccionar="/proveedores"
                )

            nuevo_id = resultado.data[0]["id"]

            redirect_url = (
                f"/proveedores?select={nuevo_id}"
            )

    except Exception as exc:
        error_code = getattr(exc, "code", None)

        if error_code == "23505":
            return script_alerta_error(
                "Ya existe un proveedor con ese nombre.",
                redireccionar="/proveedores"
            )

        return script_alerta_error(
            "No se pudo guardar el proveedor. "
            "Inténtalo nuevamente.",
            redireccionar=(
                f"/proveedores?select={prov_id}"
                if prov_id
                else "/proveedores"
            )
        )

    return RedirectResponse(
        url=redirect_url,
        status_code=303
    )

@router.post("/proveedores/eliminar/{prov_id}")
async def eliminar_proveedor(
    prov_id: int,
    access_token: str = Cookie(None)
):
    user = await obtener_usuario_actual(access_token)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        client = await _db()

        res = await (
            client
            .table("proveedores")
            .delete()
            .eq("id", prov_id)
            .execute()
        )

        if not res.data:
            return script_alerta_error(
                "No se pudo eliminar el proveedor. "
                "Es posible que ya no exista.",
                redireccionar="/proveedores"
            )

        return RedirectResponse(
            url="/proveedores",
            status_code=303
        )

    except Exception as exc:
        error_code = getattr(exc, "code", None)

        if error_code == "23503":
            return script_alerta_error(
                "No se puede eliminar el proveedor porque tiene "
                "registros relacionados en el sistema.",
                redireccionar=f"/proveedores?select={prov_id}"
            )

        return script_alerta_error(
            "No se pudo eliminar el proveedor. "
            "Inténtalo nuevamente.",
            redireccionar=f"/proveedores?select={prov_id}"
        )

@router.get("/api/proveedores")
async def listar_proveedores_api(access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return JSONResponse(status_code=401, content={"error": "No autorizado"})

    client = await _db()

    res = await (
        client
        .table("proveedores")
        .select("id, nombre, dias_despacho")
        .order("nombre")
        .execute()
    )
    proveedores = res.data if res and res.data else []
    return proveedores
    
@router.get("/api/proveedores/{proveedor_id}")
async def obtener_proveedor_api(proveedor_id: int, access_token: str = Cookie(None)):
    user = await obtener_usuario_actual(access_token)
    if not user:
        return JSONResponse(status_code=401, content={"error": "No autorizado"})

    # Consulta el proveedor en Supabase usando el ID solicitado
    client = await _db()

    res = await (
        client
        .table("proveedores")
        .select("*")
        .eq("id", proveedor_id)
        .maybe_single()
        .execute()
    )
    if not res or not res.data:
        return JSONResponse(status_code=404, content={"error": "Proveedor no encontrado"})

    p = res.data
    # Estructura y devuelve los datos del proveedor en formato JSON para autocompletar el formulario
    return {
        "id": p.get("id"),
        "nombre": p.get("nombre") or "",
        "contacto": p.get("contacto") or "",
        "telefono": p.get("telefono") or "",
        "dias_credito": p.get("dias_credito") if p.get("dias_credito") is not None else "",
        "frecuencia": p.get("dias_despacho") or p.get("frecuencia") or "",
        "etiquetas": p.get("categorias") or p.get("etiquetas") or ""
    }
