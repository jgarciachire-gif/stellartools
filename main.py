from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
from pdf_processor import extraer_datos_oc
import os
import io

app = FastAPI(title="Control de Compras Pro - ERP", version="2.0")

# Configuración de plantillas
templates = Jinja2Templates(directory="templates")
def formato_moneda_latina(valor):
    if valor is None:
        return "0,00"
    # Formatea con comas para miles y puntos para decimales, luego invierte los roles
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

templates.env.filters["moneda"] = formato_moneda_latina
DB_URL = 'compras.db'

def obtener_conexion():
    return sqlite3.connect(DB_URL)

def inicializar_db():
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            codigo TEXT, 
            nombre TEXT UNIQUE, 
            dias_credito INTEGER DEFAULT 30, 
            dias_despacho INTEGER DEFAULT 3, 
            dias_inventario INTEGER DEFAULT 15,
            contacto TEXT
        )''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Ordenes_Compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            numero_orden TEXT, 
            proveedor_id INTEGER, 
            proveedor TEXT, 
            tienda_destino TEXT, 
            fecha_emision TEXT, 
            fecha_envio TEXT, 
            fecha_recepcion TEXT, 
            monto_total REAL, 
            estatus TEXT, 
            dias_inventario INTEGER)''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Detalles_Productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            orden_id INTEGER, 
            codigo TEXT, 
            descripcion TEXT, 
            cantidad REAL, 
            precio_unitario REAL)''')
    conn.commit()
    conn.close()

inicializar_db()

def ejecutar_query(query, params=(), is_select=False, return_id=False):
    conn = obtener_conexion()
    if is_select:
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    else:
        cursor = conn.cursor()
        cursor.execute(query, params)
        last_id = cursor.lastrowid if return_id else None
        conn.commit()
        conn.close()
        return last_id

# --- RUTAS DE NAVEGACIÓN Y VISTAS ---

@app.get("/")
def dashboard(request: Request):
    # Consulta que trae todas las OCs con datos de tienda e inventario
    query = '''
        SELECT o.id, o.numero_orden, COALESCE(p.nombre, o.proveedor) as proveedor,
               o.tienda_destino, o.fecha_envio, o.fecha_recepcion, o.estatus, o.dias_inventario
        FROM Ordenes_Compra o 
        LEFT JOIN Proveedores p ON o.proveedor_id = p.id
        ORDER BY o.id DESC
    '''
    df = ejecutar_query(query, is_select=True)
    df = df.where(pd.notnull(df), None)

    proveedores_desglose = {}
    hoy = datetime.now().date() # Capturamos la fecha actual del sistema

    if not df.empty:
        for _, row in df.iterrows():
            prov = row['proveedor']
            tienda = row['tienda_destino'] or "Sin Tienda Asignada"
            
            if prov not in proveedores_desglose:
                proveedores_desglose[prov] = {}
            
            # Solo conservamos la última OC registrada para cada tienda específica
            if tienda not in proveedores_desglose[prov]:
                f_rec_raw = str(row.get('fecha_recepcion')).strip() if row.get('fecha_recepcion') else ""
                tiene_fecha_rec = f_rec_raw != "" and f_rec_raw.lower() not in ['none', 'nan', 'nat']
                
                estatus_oc = "Recibido" if tiene_fecha_rec else "Enviada"
                dias_inv_totales = int(row.get('dias_inventario') or 15)
                
                # --- NUEVA LÓGICA DE ALERTAS DE INVENTARIO ---
                if tiene_fecha_rec:
                    try:
                        # 1. Convertimos la fecha de recepción a objeto Date
                        f_rec = datetime.strptime(f_rec_raw, "%Y-%m-%d").date()
                        
                        # 2. Calculamos cuándo se debería acabar el inventario
                        fecha_agotamiento = f_rec + timedelta(days=dias_inv_totales)
                        
                        # 3. Calculamos la diferencia contra el día de hoy
                        dias_restantes = (fecha_agotamiento - hoy).days
                        
                        # 4. Asignamos alertas dinámicas
                        if dias_restantes <= 0:
                            estatus_inv = "Reponer inventario"
                            color_inv = "text-red-700 bg-red-100"
                            dias_mostrar = f"Vencido hace {abs(dias_restantes)}d"
                        elif dias_restantes <= 5: # Alerta a los 5 días previos
                            estatus_inv = "Próximo a Agotar"
                            color_inv = "text-amber-700 bg-amber-100"
                            dias_mostrar = f"Quedan {dias_restantes}d"
                        else:
                            estatus_inv = "Stock OK"
                            color_inv = "text-emerald-700 bg-emerald-100"
                            dias_mostrar = f"Quedan {dias_restantes}d"
                            
                    except ValueError:
                        estatus_inv = "Error de Fecha"
                        color_inv = "text-slate-600 bg-slate-100"
                        dias_mostrar = f"{dias_inv_totales} totales"
                else:
                    # Si no ha llegado la mercancía, el inventario no ha empezado a descontarse
                    estatus_inv = "Esperando Recepción"
                    color_inv = "text-blue-700 bg-blue-100"
                    dias_mostrar = "Sin iniciar"

                proveedores_desglose[prov][tienda] = {
                    "ultima_oc": row['numero_orden'],
                    "fecha_envio": row['fecha_envio'] or "-",
                    "estatus_oc": estatus_oc,
                    "dias_inventario": dias_mostrar,
                    "estatus_inv": estatus_inv,
                    "color_inv": color_inv
                }

    return templates.TemplateResponse(request, "dashboard.html", {
        "proveedores_desglose": proveedores_desglose
    })

@app.get("/ordenes")
def listar_ordenes(request: Request):
    query = '''
        SELECT o.id, o.numero_orden, COALESCE(p.nombre, o.proveedor) as proveedor, 
               o.tienda_destino, o.fecha_envio, o.fecha_recepcion, o.monto_total, 
               p.dias_credito
        FROM Ordenes_Compra o LEFT JOIN Proveedores p ON o.proveedor_id = p.id
        ORDER BY o.id DESC
    '''
    df = ejecutar_query(query, is_select=True)
    df = df.where(pd.notnull(df), None)
    
    hoy = datetime.now().date()
    ordenes = []
    
    if not df.empty:
        for _, row in df.iterrows():
            o = row.to_dict()
            
            # --- CORRECCIÓN DE ESTATUS STRICTO ---
            f_rec_raw = str(o.get('fecha_recepcion')).strip() if o.get('fecha_recepcion') else ""
            tiene_fecha_rec = f_rec_raw != "" and f_rec_raw.lower() not in ['none', 'nan', 'nat']
            
            o['estatus'] = 'Recibido' if tiene_fecha_rec else 'Enviada'
            o['vencimiento_factura_str'] = ""
            o['alerta_text'] = ""
            o['alerta_color'] = "transparent"
            
            if tiene_fecha_rec and o.get('dias_credito'):
                try:
                    f_rec = datetime.strptime(f_rec_raw, "%Y-%m-%d").date()
                    venc_date = f_rec + timedelta(days=int(o['dias_credito']))
                    o['vencimiento_factura_str'] = venc_date.strftime("%d/%m/%Y")
                    dias_restantes = (venc_date - hoy).days
                    
                    if dias_restantes < 0:
                        o['alerta_text'] = f"Vencido ({abs(dias_restantes)}d)"
                        o['alerta_color'] = "bg-red-500"
                    elif dias_restantes <= 5:
                        o['alerta_text'] = f"Por vencer ({dias_restantes}d)"
                        o['alerta_color'] = "bg-yellow-400"
                    else:
                        o['alerta_text'] = "Al día"
                        o['alerta_color'] = "bg-green-500"
                except ValueError:
                    pass
            
            ordenes.append(o)
            
    return templates.TemplateResponse(request, "ordenes.html", {"ordenes": ordenes})

@app.post("/ordenes/actualizar/{orden_id}")
def actualizar_orden(
    orden_id: int, 
    fecha_envio: str = Form(None), 
    fecha_recepcion: str = Form(None)
):
    f_rec = fecha_recepcion if fecha_recepcion else None
    f_env = fecha_envio if fecha_envio else None
    
    # El estatus se define estrictamente de acuerdo a si existe fecha de recepción
    estatus = "Recibido" if f_rec else "Enviada"

    ejecutar_query('''
        UPDATE Ordenes_Compra 
        SET estatus = ?, fecha_envio = ?, fecha_recepcion = ?
        WHERE id = ?
    ''', (estatus, f_env, f_rec, orden_id))
    
    return RedirectResponse(url="/ordenes", status_code=303)

@app.post("/ordenes/eliminar/{orden_id}")
def eliminar_orden(orden_id: int):
    ejecutar_query("DELETE FROM Ordenes_Compra WHERE id = ?", (orden_id,))
    return RedirectResponse(url="/ordenes", status_code=303)

@app.get("/proveedores")
def gestionar_proveedores(request: Request, buscar: str = ""):
    if buscar:
        query = "SELECT id, codigo, nombre, dias_credito, dias_despacho, contacto FROM Proveedores WHERE nombre LIKE ? ORDER BY nombre ASC"
        df = ejecutar_query(query, (f"%{buscar}%",), is_select=True)
    else:
        query = "SELECT id, codigo, nombre, dias_credito, dias_despacho, contacto FROM Proveedores ORDER BY nombre ASC"
        df = ejecutar_query(query, is_select=True)
        
    proveedores = df.to_dict(orient="records") if not df.empty else []
    return templates.TemplateResponse(request, "proveedores.html", {"proveedores": proveedores, "busqueda": buscar})

@app.post("/proveedores/guardar")
def guardar_proveedor(id: int = Form(None), codigo: str = Form(""), nombre: str = Form(...), dias_credito: int = Form(30), contacto: str = Form("")):
    if id:
        ejecutar_query('''
            UPDATE Proveedores SET codigo = ?, nombre = ?, dias_credito = ?, contacto = ? WHERE id = ?
        ''', (codigo, nombre, dias_credito, contacto, id))
    else:
        try:
            ejecutar_query('''
                INSERT INTO Proveedores (codigo, nombre, dias_credito, contacto, dias_despacho, dias_inventario) 
                VALUES (?, ?, ?, ?, 3, 15)
            ''', (codigo, nombre, dias_credito, contacto))
        except sqlite3.IntegrityError:
            pass 
    return RedirectResponse(url="/proveedores", status_code=303)

@app.post("/proveedores/eliminar/{prov_id}")
def eliminar_proveedor(prov_id: int):
    ejecutar_query("DELETE FROM Proveedores WHERE id = ?", (prov_id,))
    return RedirectResponse(url="/proveedores", status_code=303)

@app.get("/escanear")
def vista_escanear(request: Request):
    return templates.TemplateResponse(request, "escanear.html", {"datos": None})

@app.post("/escanear/procesar")
async def procesar_pdf(request: Request, archivo_pdf: UploadFile = File(...)):
    # 1. Leemos el contenido en bytes del PDF subido
    contenido_bytes = await archivo_pdf.read()
    
    # 2. Convertimos los bytes en un objeto tipo archivo en la memoria RAM
    pdf_en_memoria = io.BytesIO(contenido_bytes)
    
    # 3. Llamamos a tu script real pasándole el PDF en memoria
    datos_extraidos = extraer_datos_oc(pdf_en_memoria)
    
    # 4. Validación por si el PDF es ilegible o no es una Orden de Compra
    if not datos_extraidos:
        datos_extraidos = {
            "numero_orden": "",
            "proveedor": "",
            "tienda_destino": "",
            "fecha_emision": "",
            "monto_total": 0.0
        }
    
    # 5. Renderizamos de nuevo 'escanear.html' con los datos REALES
    return templates.TemplateResponse(request, "escanear.html", {
        "datos": datos_extraidos
    })

@app.post("/ordenes/crear")
def crear_orden_manual(
    numero_orden: str = Form(...),
    proveedor: str = Form(...),
    tienda_destino: str = Form(...),
    monto_total: float = Form(0.0),
    fecha_emision: str = Form(...),
    dias_inventario: int = Form(...) # Solicitamos este nuevo dato del formulario
):
    # 1. Validación de duplicidad
    df_existe = ejecutar_query("SELECT id FROM Ordenes_Compra WHERE numero_orden = ?", (numero_orden,), is_select=True)
    if not df_existe.empty:
        # Lanza una alerta emergente y regresa a la pantalla anterior sin borrar los datos
        alerta_js = f"<script>alert('Cuidado: La Orden de Compra N° {numero_orden} ya fue registrada.'); window.history.back();</script>"
        return HTMLResponse(content=alerta_js)

    # 2. Gestión del Proveedor
    df_p = ejecutar_query("SELECT id FROM Proveedores WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(?))", (proveedor,), is_select=True)
    if not df_p.empty:
        prov_id = int(df_p.iloc[0]['id'])
    else:
        prov_id = ejecutar_query("INSERT INTO Proveedores (nombre, dias_credito, dias_despacho, dias_inventario) VALUES (?, 30, 3, 15)", (proveedor,), return_id=True)

    # 3. Inserción con los días de inventario definidos manualmente
    ejecutar_query('''
        INSERT INTO Ordenes_Compra (numero_orden, proveedor_id, proveedor, tienda_destino, fecha_envio, monto_total, estatus, dias_inventario)
        VALUES (?, ?, ?, ?, ?, ?, 'Enviada', ?)
    ''', (numero_orden, prov_id, proveedor, tienda_destino, fecha_emision, monto_total, dias_inventario))
    
    return RedirectResponse(url="/ordenes", status_code=303)