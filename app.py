try:
    import streamlit as st  # type: ignore
except Exception:
    # Fallback stub for environments where streamlit is not installed (for linting/tests)
    from types import SimpleNamespace

    class _SessionState(dict):
        pass

    st = SimpleNamespace(
        secrets={},
        session_state=_SessionState(),
        set_page_config=lambda *a, **k: None,
    )
import sqlite3
from datetime import datetime, timedelta, date
from pdf_processor import extraer_datos_oc
import os

import pandas as pd  # type: ignore

# Intento de conexión a BD en la nube (PostgreSQL) vía st.secrets
try:
    import psycopg2  # type: ignore
    DB_URL = st.secrets["DATABASE_URL"]
    IS_POSTGRES = True
except (FileNotFoundError, KeyError, ImportError):
    DB_URL = 'compras.db'
    IS_POSTGRES = False

st.set_page_config(page_title="Control de Compras Pro", page_icon="📦", layout="wide")

# --- INICIALIZACIÓN DEL ESTADO ---
if "pdf_data" not in st.session_state: st.session_state.pdf_data = None
if "last_filename" not in st.session_state: st.session_state.last_filename = None
if "pdf_guardado_exito" not in st.session_state: st.session_state.pdf_guardado_exito = False
if "df_actual" not in st.session_state: st.session_state.df_actual = pd.DataFrame()
if "df_prov_actual" not in st.session_state: st.session_state.df_prov_actual = pd.DataFrame()
if "grid_diario_ordenes" not in st.session_state: st.session_state.grid_diario_ordenes = {}
if "grid_proveedores" not in st.session_state: st.session_state.grid_proveedores = {}

# --- FUNCIONES AUXILIARES ---
def formato_moneda(valor):
    if pd.isna(valor) or valor is None: return "0,00"
    try: return "{:,.2f}".format(float(valor)).replace(',', 'X').replace('.', ',').replace('X', '.')
    except ValueError: return str(valor)

def parse_a_fecha_obj(d_val):
    if pd.isna(d_val) or not d_val or str(d_val).strip() == "" or str(d_val) == "NaT": return None
    if isinstance(d_val, (date, datetime)): return d_val if isinstance(d_val, date) else d_val.date()
    try: return datetime.strptime(str(d_val).split("T")[0], "%Y-%m-%d").date()
    except ValueError:
        try: return datetime.strptime(str(d_val), "%d-%m-%Y").date()
        except ValueError: return None

def safe_date_str(val):
    if pd.isna(val) or not val: return None
    if hasattr(val, 'strftime'): return val.strftime("%Y-%m-%d")
    return str(val)[:10]

# --- CONEXIÓN MULTI-MOTOR (POSTGRES / SQLITE) ---
def obtener_conexion():
    if IS_POSTGRES: return psycopg2.connect(DB_URL)
    return sqlite3.connect(DB_URL)

def ejecutar_query(query, params=(), is_select=False, return_id=False):
    conn = obtener_conexion()
    if is_select:
        query_sql = query.replace('?', '%s') if IS_POSTGRES else query
        df = pd.read_sql_query(query_sql, conn, params=params)
        conn.close()
        return df
    else:
        cursor = conn.cursor()
        query_sql = query.replace('?', '%s') if IS_POSTGRES else query
        
        if IS_POSTGRES and "AUTOINCREMENT" in query_sql:
            query_sql = query_sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        
        # Manejo especial para obtener IDs insertados en Postgres
        if return_id and IS_POSTGRES and "INSERT" in query_sql.upper():
            query_sql += " RETURNING id"
            
        cursor.execute(query_sql, params)
        
        last_id = None
        if return_id:
            last_id = cursor.fetchone()[0] if IS_POSTGRES else cursor.lastrowid
            
        conn.commit()
        conn.close()
        return last_id

def inicializar_db():
    queries = [
        '''CREATE TABLE IF NOT EXISTS Proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, nombre TEXT UNIQUE, dias_credito INTEGER DEFAULT 30, 
            dias_despacho INTEGER DEFAULT 3, dias_inventario INTEGER DEFAULT 15)''',
        '''CREATE TABLE IF NOT EXISTS Ordenes_Compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT, numero_orden TEXT, proveedor_id INTEGER, proveedor TEXT, 
            tienda_destino TEXT, fecha_emision TEXT, fecha_envio TEXT, fecha_recepcion TEXT, 
            monto_total REAL, estatus TEXT, dias_inventario INTEGER)''',
        '''CREATE TABLE IF NOT EXISTS Detalles_Productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, orden_id INTEGER, codigo TEXT, descripcion TEXT, 
            cantidad REAL, precio_unitario REAL)'''
    ]
    for q in queries:
        ejecutar_query(q)
    
    # Migraciones silenciosas de estructura por si vienen de versiones anteriores
    migraciones = [
        "ALTER TABLE Ordenes_Compra ADD COLUMN proveedor_id INTEGER",
        "ALTER TABLE Ordenes_Compra ADD COLUMN proveedor TEXT",
        "ALTER TABLE Ordenes_Compra ADD COLUMN dias_inventario INTEGER",
        "ALTER TABLE Proveedores ADD COLUMN dias_inventario INTEGER DEFAULT 15",
        "ALTER TABLE Proveedores ADD COLUMN codigo TEXT"
    ]
    for m in migraciones:
        try: ejecutar_query(m)
        except: pass

inicializar_db()

# --- FUNCIONES DE BASE DE DATOS ---
def procesar_cambios_diario():
    cambios = st.session_state.grid_diario_ordenes
    df = st.session_state.df_actual
    
    for idx in cambios.get("deleted_rows", []):
        orden_id = int(df.iloc[int(idx)]["ID_BD"])
        ejecutar_query("DELETE FROM Detalles_Productos WHERE orden_id = ?", (orden_id,))
        ejecutar_query("DELETE FROM Ordenes_Compra WHERE id = ?", (orden_id,))
        
    for idx, col_cambios in cambios.get("edited_rows", {}).items():
        orden_id = int(df.iloc[int(idx)]["ID_BD"])
        mapeo = {"Nº OC": "numero_orden", "Tienda Destino": "tienda_destino", "Monto Total ($)": "monto_total", "Estatus": "estatus"}
        
        for col, valor in col_cambios.items():
            if col in mapeo:
                ejecutar_query(f"UPDATE Ordenes_Compra SET {mapeo[col]} = ? WHERE id = ?", (valor, orden_id))
                if col == "Estatus":
                    if valor == "Recibido":
                        ejecutar_query("UPDATE Ordenes_Compra SET fecha_recepcion = COALESCE(fecha_recepcion, ?) WHERE id = ? AND (fecha_recepcion IS NULL OR fecha_recepcion = '')", (datetime.now().strftime("%Y-%m-%d"), orden_id))
                    elif valor in ["No despachado", "Enviada"]:
                        ejecutar_query("UPDATE Ordenes_Compra SET fecha_recepcion = NULL WHERE id = ?", (orden_id,))
            elif col in ["Fecha Envío", "Fecha Recepción"]:
                campo_bd = "fecha_envio" if col == "Fecha Envío" else "fecha_recepcion"
                f_str = safe_date_str(valor)
                ejecutar_query(f"UPDATE Ordenes_Compra SET {campo_bd} = ? WHERE id = ?", (f_str, orden_id))
                
                if col == "Fecha Recepción":
                    estatus_val = 'Recibido' if f_str else 'No despachado'
                    ejecutar_query("UPDATE Ordenes_Compra SET estatus = ? WHERE id = ?", (estatus_val, orden_id))
            elif col == "Proveedor":
                prov_id, _ = gestionar_proveedor(valor)
                ejecutar_query("UPDATE Ordenes_Compra SET proveedor = ?, proveedor_id = ? WHERE id = ?", (valor, prov_id, orden_id))

def cargar_ordenes():
    query = '''
        SELECT 
            o.id AS "ID_BD", o.numero_orden AS "Nº OC", COALESCE(p.nombre, o.proveedor, 'Desconocido') AS "Proveedor",
            o.tienda_destino AS "Tienda Destino", o.fecha_envio AS "Fecha Envío", o.fecha_recepcion AS "Fecha Recepción",
            CASE WHEN o.fecha_recepcion IS NOT NULL AND TRIM(o.fecha_recepcion) != '' 
                THEN date(o.fecha_recepcion, '+' || CAST(IFNULL(p.dias_credito, 30) AS TEXT) || ' days')
                ELSE NULL END AS "Vencimiento Factura",
            o.monto_total AS "Monto Total ($)", o.estatus AS "Estatus"
        FROM Ordenes_Compra o LEFT JOIN Proveedores p ON o.proveedor_id = p.id
        ORDER BY o.id DESC
    '''
    return ejecutar_query(query, is_select=True)

def gestionar_proveedor(proveedor_nombre):
    prov_clean = proveedor_nombre.strip() if proveedor_nombre else "Proveedor Desconocido"
    df_prov = ejecutar_query("SELECT id, dias_credito FROM Proveedores WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(?))", (prov_clean,), is_select=True)
    if not df_prov.empty: return int(df_prov.iloc[0]['id']), int(df_prov.iloc[0]['dias_credito'])
    
    nuevo_id = ejecutar_query("INSERT INTO Proveedores (nombre, dias_credito, dias_despacho, dias_inventario) VALUES (?, 30, 3, 15)", (prov_clean,), return_id=True)
    return nuevo_id, 30

def existe_orden_duplicada(numero_orden, tienda_destino):
    if not numero_orden or not tienda_destino: return False
    df = ejecutar_query('SELECT id FROM Ordenes_Compra WHERE LOWER(TRIM(numero_orden)) = LOWER(TRIM(?)) AND LOWER(TRIM(tienda_destino)) = LOWER(TRIM(?))', 
                        (str(numero_orden).strip(), str(tienda_destino).strip()), is_select=True)
    return not df.empty

def guardar_orden(numero_orden, proveedor_nombre, tienda_destino, fecha_emi_dt, fecha_env_dt, fecha_rec_dt, monto_total, df_productos, estatus, dias_inventario):
    if existe_orden_duplicada(numero_orden, tienda_destino):
        return None, f"⚠️ La Orden N° '{numero_orden}' ya está registrada para la tienda '{tienda_destino}'."
    if fecha_rec_dt: estatus = "Recibido"

    proveedor_id, _ = gestionar_proveedor(proveedor_nombre)
    orden_id = ejecutar_query('''
        INSERT INTO Ordenes_Compra (numero_orden, proveedor_id, proveedor, tienda_destino, fecha_emision, fecha_envio, fecha_recepcion, monto_total, estatus, dias_inventario)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (numero_orden, proveedor_id, proveedor_nombre, tienda_destino, safe_date_str(fecha_emi_dt), safe_date_str(fecha_env_dt), safe_date_str(fecha_rec_dt), monto_total, estatus, dias_inventario), return_id=True)
    
    if df_productos is not None and not df_productos.empty:
        for _, prod in df_productos.iterrows():
            ejecutar_query('INSERT INTO Detalles_Productos (orden_id, codigo, descripcion, cantidad, precio_unitario) VALUES (?, ?, ?, ?, ?)', 
                           (orden_id, str(prod.get('codigo', '')), str(prod.get('descripcion', '')), float(prod.get('cantidad', 0) or 0), float(prod.get('precio_unitario', 0) or 0)))
    return orden_id, None

def calcular_alerta_pago(row):
    fecha_venc_str = row["Vencimiento Factura"]
    if not fecha_venc_str or pd.isna(fecha_venc_str): return "Sin recepción"
    try: fecha_venc = fecha_venc_str if isinstance(fecha_venc_str, date) else datetime.strptime(str(fecha_venc_str).split("T")[0], "%Y-%m-%d").date()
    except Exception: return "Sin recepción"
    dias_restantes = (fecha_venc - datetime.now().date()).days
    if dias_restantes < 0: return f"🔴 Vencida hace {abs(dias_restantes)} días"
    elif dias_restantes <= 5: return f"🟡 Por vencer ({dias_restantes} días)"
    return f"🟢 Vigente ({dias_restantes} días)"

def calcular_alerta_inventario(row):
    try:
        f_rec = parse_a_fecha_obj(row['fecha_recepcion'])
        dias = int(row['dias_inventario'])
        if not f_rec or dias <= 0: return "No definido"
        fecha_fin = f_rec + timedelta(days=dias)
        dias_restantes = (fecha_fin - datetime.now().date()).days
        if dias_restantes < 0: return f"🔴 Agotado ({abs(dias_restantes)} días)"
        elif dias_restantes <= 10: return f"🟡 Reponer pronto ({dias_restantes} días)"
        return f"🟢 OK ({dias_restantes} días)"
    except: return "N/A"

# --- UI PRINCIPAL ---
st.title("📦 Diario de Control de Compras")

tab_ordenes, tab_escaner, tab_manual, tab_proveedores = st.tabs([
    "📋 Registro Diario", "📥 Escanear PDF", "✍️ Registro Manual", "🏢 Proveedores e Inventario"
])

# --- PESTAÑA 1: REGISTRO DIARIO (LIMPIO) ---
with tab_ordenes:
    st.subheader("📋 Registro Diario de Órdenes")
    st.caption("💡 Se han ocultado los detalles de emisión e inventario para priorizar el seguimiento diario de facturas.")

    df_ordenes = cargar_ordenes()
    st.session_state.df_actual = df_ordenes.copy()

    if not df_ordenes.empty:
        df_editor = df_ordenes.copy()
        df_editor["Fecha Envío"] = df_editor["Fecha Envío"].apply(parse_a_fecha_obj)
        df_editor["Fecha Recepción"] = df_editor["Fecha Recepción"].apply(parse_a_fecha_obj)
        df_editor["Vencimiento Factura"] = df_editor["Vencimiento Factura"].apply(parse_a_fecha_obj)
        df_editor["Alerta de Pago"] = df_editor.apply(calcular_alerta_pago, axis=1)

        col_config = {
            "ID_BD": None,
            "Nº OC": st.column_config.TextColumn("Nº OC", required=True),
            "Proveedor": st.column_config.TextColumn("Proveedor", required=True),
            "Tienda Destino": st.column_config.TextColumn("Tienda Destino", required=True),
            "Fecha Envío": st.column_config.DateColumn("Fecha Envío", format="DD/MM/YYYY"),
            "Fecha Recepción": st.column_config.DateColumn("Fecha Recepción", format="DD/MM/YYYY"),
            "Vencimiento Factura": st.column_config.DateColumn("Venc. Factura", format="DD/MM/YYYY", disabled=True),
            "Monto Total ($)": st.column_config.NumberColumn("Monto Total ($)", format="$%.2f"),
            "Estatus": st.column_config.SelectboxColumn("Estatus", options=["No despachado", "Enviada", "Recibido"], required=True),
            "Alerta de Pago": st.column_config.TextColumn("Alerta de Pago", disabled=True)
        }

        st.data_editor(df_editor, column_config=col_config, width="stretch", num_rows="dynamic", key="grid_diario_ordenes", on_change=procesar_cambios_diario)
    else:
        st.info("Aún no hay órdenes registradas.")

# --- PESTAÑA 2: ESCANEAR PDF ---
with tab_escaner:
    st.subheader("Extraer datos desde PDF")
    archivo_pdf = st.file_uploader("Sube el PDF de la OC:", type=["pdf"], key="uploader_pdf")
    
    if archivo_pdf is not None:
        if st.session_state.last_filename != archivo_pdf.name:
            with st.spinner("Extrayendo datos..."):
                st.session_state.pdf_data = extraer_datos_oc(archivo_pdf)
                st.session_state.last_filename = archivo_pdf.name
                st.session_state.pdf_guardado_exito = False

        datos_oc = st.session_state.pdf_data
        if st.session_state.pdf_guardado_exito:
            st.success("🎉 ¡Orden registrada exitosamente!")
            if st.button("🔄 Cargar Nuevo PDF"):
                st.session_state.pdf_data, st.session_state.last_filename, st.session_state.pdf_guardado_exito = None, None, False
                st.rerun()
        elif datos_oc:
            with st.form("form_pdf"):
                c1, c2 = st.columns(2)
                with c1:
                    num_oc = st.text_input("Número de OC:", value=datos_oc.get("numero_orden", ""))
                    proveedor = st.text_input("Proveedor:", value=datos_oc.get("proveedor", ""))
                    tienda = st.text_input("Tienda Destino:", value=datos_oc.get("tienda_destino", ""))
                    monto = st.number_input("Monto Total ($):", value=float(datos_oc.get("monto_total", 0.0) or 0.0), step=0.01)
                with c2:
                    f_emision = st.date_input("Fecha Emisión:", value=datetime.now().date())
                    f_envio = st.date_input("Fecha de Envío:", value=datetime.now().date())
                    
                    df_std = ejecutar_query("SELECT dias_inventario FROM Proveedores WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(?))", (proveedor,), is_select=True)
                    estandar_inv = int(df_std.iloc[0]['dias_inventario']) if not df_std.empty else 15
                    dias_inv = st.number_input("Días de Inventario a cubrir:", value=estandar_inv, min_value=0, step=1)
                    
                    recibida = st.checkbox("¿Orden recibida?")
                    f_recepcion = st.date_input("Fecha de Recepción:", value=datetime.now().date()) if recibida else None

                prods_editados = st.data_editor(pd.DataFrame(datos_oc["productos"]) if datos_oc.get("productos") else pd.DataFrame(columns=["codigo", "descripcion", "cantidad", "precio_unitario"]), num_rows="dynamic", width="stretch")

                if st.form_submit_button("Guardar Orden Extraída", type="primary"):
                    orden_id, err = guardar_orden(num_oc, proveedor, tienda, f_emision, f_envio, f_recepcion, monto, prods_editados, "Recibido" if recibida else "No despachado", dias_inv)
                    if err: st.error(err)
                    else:
                        st.session_state.pdf_guardado_exito = True
                        st.rerun()

# --- PESTAÑA 3: REGISTRO MANUAL ---
with tab_manual:
    with st.form("form_manual_limpio"):
        c1, c2 = st.columns(2)
        with c1:
            m_num = st.text_input("Número de OC:")
            m_prov = st.text_input("Proveedor:")
            m_tienda = st.text_input("Tienda Destino:")
            m_monto = st.number_input("Monto Total ($):", min_value=0.0, step=0.01)
        with c2:
            m_emi = st.date_input("Fecha Emisión:")
            m_env = st.date_input("Fecha Envío:")
            m_dias_inv = st.number_input("Días Inventario a cubrir:", value=15, min_value=0, step=1)
            m_recibida = st.checkbox("Marcar como Recibida")
            m_rec = st.date_input("Fecha Recepción:") if m_recibida else None

        m_prods = st.data_editor(pd.DataFrame(columns=["codigo", "descripcion", "cantidad", "precio_unitario"]), num_rows="dynamic", width="stretch")
        if st.form_submit_button("Guardar Orden Manual", type="primary"):
            if m_prov and m_num and m_tienda:
                f_rec_fin = m_rec if m_recibida else None
                orden_id, err = guardar_orden(m_num, m_prov, m_tienda, m_emi, m_env, f_rec_fin, m_monto, m_prods, "Recibido" if f_rec_fin else "No despachado", m_dias_inv)
                if err: st.error(err)
                else: st.success(f"¡Orden manual N° {m_num} registrada con éxito!")
            else: st.error("Completa Número de OC, Proveedor y Tienda Destino.")

# --- PESTAÑA 4: PROVEEDORES E INVENTARIO ---
with tab_proveedores:
    st.subheader("Base de Datos y Control de Inventario por Proveedor")
    
    # 1. Carga masiva por XML
    with st.expander("📥 Cargar Lista de Proveedores vía XML"):
        xml_file = st.file_uploader("Sube el archivo XML (Debe contener columnas/nodos 'codigo' y 'descripcion')", type=["xml"])
        if xml_file:
            try:
                df_xml = pd.read_xml(xml_file)
                # Normalizar nombres de columnas ignorando mayúsculas/minúsculas
                df_xml.columns = df_xml.columns.str.lower()
                
                if 'codigo' in df_xml.columns and 'descripcion' in df_xml.columns:
                    registros_nuevos = 0
                    for _, row in df_xml.iterrows():
                        cod = str(row['codigo']).strip()
                        desc = str(row['descripcion']).strip()
                        
                        # Evitar duplicados por nombre
                        existe = ejecutar_query("SELECT id FROM Proveedores WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(?))", (desc,), is_select=True)
                        if existe.empty:
                            ejecutar_query("INSERT INTO Proveedores (codigo, nombre, dias_credito, dias_despacho, dias_inventario) VALUES (?, ?, 30, 3, 15)", (cod, desc))
                            registros_nuevos += 1
                    
                    st.success(f"✅ Archivo procesado. Se agregaron {registros_nuevos} proveedores nuevos a la base de datos.")
                else:
                    st.error("❌ El XML no tiene el formato esperado. Necesita nodos <codigo> y <descripcion>.")
            except Exception as e:
                st.error(f"❌ Error leyendo XML: Verifica la estructura del archivo. (Detalle: {e})")
    
    st.divider()

    # 2. Detalles de Inventario Desplegables (Autocompletado)
    df_prov = ejecutar_query("SELECT id AS 'ID', codigo AS 'Código', nombre AS 'Proveedor', dias_credito AS 'Días de Crédito', dias_despacho AS 'Días de Despacho', dias_inventario AS 'Días Inventario (Estándar)' FROM Proveedores ORDER BY Proveedor ASC", is_select=True)
    
    if not df_prov.empty:
        opciones_prov = [""] + df_prov["Proveedor"].tolist()
        prov_seleccionado = st.selectbox("🔍 Buscar y seleccionar un Proveedor para ver su estatus actual:", options=opciones_prov)
        
        if prov_seleccionado:
            st.markdown(f"### Estatus de Inventario: **{prov_seleccionado}**")
            # Extraer las órdenes para el proveedor y obtener la ÚLTIMA por Tienda
            df_ocs_prov = ejecutar_query('''
                SELECT tienda_destino AS "Tienda", numero_orden AS "Último Nº OC", estatus AS "Estatus", 
                       dias_inventario, fecha_recepcion, fecha_emision
                FROM Ordenes_Compra
                WHERE LOWER(TRIM(proveedor)) = LOWER(TRIM(?))
                ORDER BY fecha_emision DESC
            ''', (prov_seleccionado,), is_select=True)
            
            if not df_ocs_prov.empty:
                # Filtrar solo la más reciente por Tienda
                df_ultimas = df_ocs_prov.drop_duplicates(subset=['Tienda'], keep='first').copy()
                
                # Calcular dinámicamente las alertas
                df_ultimas["Alerta de Inventario"] = df_ultimas.apply(calcular_alerta_inventario, axis=1)
                
                # Renombrar para estética
                df_ultimas = df_ultimas.rename(columns={"dias_inventario": "Días Inventario OC"})
                
                # Ocultar campos de cálculo y mostrar la tabla limpia
                st.dataframe(df_ultimas[["Tienda", "Último Nº OC", "Estatus", "Días Inventario OC", "Alerta de Inventario"]], hide_index=True, use_container_width=True)
            else:
                st.info("No hay historial de órdenes de compra registradas para este proveedor en ninguna tienda.")
            
    st.divider()

    # 3. Editor de Base de Datos
    st.write("🔧 **Gestión de Base de Datos de Proveedores**")
    def procesar_cambios_proveedores():
        cambios = st.session_state.grid_proveedores
        df = st.session_state.df_prov_actual
        
        for idx in cambios.get("deleted_rows", []):
            prov_id = int(df.iloc[int(idx)]["ID"])
            ejecutar_query("DELETE FROM Proveedores WHERE id = ?", (prov_id,))
            
        for idx, col_cambios in cambios.get("edited_rows", {}).items():
            prov_id = int(df.iloc[int(idx)]["ID"])
            for col, valor in col_cambios.items():
                campo = {"Código": "codigo", "Proveedor": "nombre", "Días de Crédito": "dias_credito", "Días de Despacho": "dias_despacho", "Días Inventario (Estándar)": "dias_inventario"}.get(col)
                if campo: ejecutar_query(f"UPDATE Proveedores SET {campo} = ? WHERE id = ?", (valor, prov_id))
                    
        for row in cambios.get("added_rows", []):
            ejecutar_query("INSERT INTO Proveedores (codigo, nombre, dias_credito, dias_despacho, dias_inventario) VALUES (?, ?, ?, ?, ?)", 
                           (row.get("Código", ""), row.get("Proveedor", "Nuevo Proveedor"), row.get("Días de Crédito", 30), row.get("Días de Despacho", 3), row.get("Días Inventario (Estándar)", 15)))

    st.session_state.df_prov_actual = df_prov.copy()
    
    st.data_editor(
        df_prov,
        column_config={
            "ID": None, 
            "Código": st.column_config.TextColumn("Código"),
            "Días Inventario (Estándar)": st.column_config.NumberColumn("Días Inv (Estándar)", min_value=0, step=1)
        },
        width="stretch",
        num_rows="dynamic",
        key="grid_proveedores",
        on_change=procesar_cambios_proveedores
    )