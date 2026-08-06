import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, date
from pdf_processor import extraer_datos_oc

# Configuración de la aplicación
st.set_page_config(page_title="Control de Compras Pro", page_icon="📦", layout="wide")

# -------------------------------------------------------------------
# INICIALIZACIÓN DEL ESTADO DE LA APLICACIÓN
# -------------------------------------------------------------------
if "pdf_data" not in st.session_state: st.session_state.pdf_data = None
if "last_filename" not in st.session_state: st.session_state.last_filename = None
if "pdf_guardado_exito" not in st.session_state: st.session_state.pdf_guardado_exito = False
if "df_actual" not in st.session_state: st.session_state.df_actual = pd.DataFrame()
if "df_prov_actual" not in st.session_state: st.session_state.df_prov_actual = pd.DataFrame()

# -------------------------------------------------------------------
# FUNCIONES AUXILIARES 
# -------------------------------------------------------------------
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

# -------------------------------------------------------------------
# BASE DE DATOS Y AUTO-GUARDADO (CALLBACKS)
# -------------------------------------------------------------------
def obtener_conexion():
    return sqlite3.connect('compras.db')

def inicializar_db():
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    # Se añade dias_inventario a Proveedores
    cursor.execute('''CREATE TABLE IF NOT EXISTS Proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, dias_credito INTEGER DEFAULT 30, 
        dias_despacho INTEGER DEFAULT 3, dias_inventario INTEGER DEFAULT 15)''')
    
    # Creación de tabla de órdenes si no existe
    cursor.execute('''CREATE TABLE IF NOT EXISTS Ordenes_Compra (
        id INTEGER PRIMARY KEY AUTOINCREMENT, numero_orden TEXT, tienda_destino TEXT, fecha_emision TEXT, 
        fecha_envio TEXT, fecha_recepcion TEXT, monto_total REAL, estatus TEXT)''')
        
    cursor.execute('''CREATE TABLE IF NOT EXISTS Detalles_Productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, orden_id INTEGER, codigo TEXT, descripcion TEXT, cantidad REAL, 
        precio_unitario REAL, FOREIGN KEY (orden_id) REFERENCES Ordenes_Compra(id))''')
    
    # Actualización automática de la base de datos si ya existía (sin borrar datos)
    for col, tipo in [("proveedor_id", "INTEGER"), ("proveedor", "TEXT"), ("dias_inventario", "INTEGER")]:
        try: cursor.execute(f"ALTER TABLE Ordenes_Compra ADD COLUMN {col} {tipo}")
        except sqlite3.OperationalError: pass
        
    try: cursor.execute("ALTER TABLE Proveedores ADD COLUMN dias_inventario INTEGER DEFAULT 15")
    except sqlite3.OperationalError: pass
    
    conn.commit()
    conn.close()

inicializar_db()

def procesar_cambios_diario():
    cambios = st.session_state.grid_diario_ordenes
    df = st.session_state.df_actual
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    for idx in cambios.get("deleted_rows", []):
        real_idx = int(idx)
        orden_id = int(df.iloc[real_idx]["ID_BD"])
        cursor.execute("DELETE FROM Detalles_Productos WHERE orden_id = ?", (orden_id,))
        cursor.execute("DELETE FROM Ordenes_Compra WHERE id = ?", (orden_id,))
        
    for idx, col_cambios in cambios.get("edited_rows", {}).items():
        real_idx = int(idx)
        orden_id = int(df.iloc[real_idx]["ID_BD"])
        mapeo = {"Nº OC": "numero_orden", "Tienda Destino": "tienda_destino", "Monto Total ($)": "monto_total", "Estatus": "estatus", "Días Inventario": "dias_inventario"}
        
        for col, valor in col_cambios.items():
            if col in mapeo:
                cursor.execute(f"UPDATE Ordenes_Compra SET {mapeo[col]} = ? WHERE id = ?", (valor, orden_id))
                
                if col == "Estatus":
                    if valor == "Recibido":
                        hoy_str = datetime.now().strftime("%Y-%m-%d")
                        cursor.execute("UPDATE Ordenes_Compra SET fecha_recepcion = COALESCE(fecha_recepcion, ?) WHERE id = ? AND (fecha_recepcion IS NULL OR fecha_recepcion = '')", (hoy_str, orden_id))
                    elif valor in ["No despachado", "Enviada"]:
                        cursor.execute("UPDATE Ordenes_Compra SET fecha_recepcion = NULL WHERE id = ?", (orden_id,))

            elif col in ["Fecha Emisión", "Fecha Envío", "Fecha Recepción"]:
                campo_bd = "fecha_emision" if col == "Fecha Emisión" else "fecha_envio" if col == "Fecha Envío" else "fecha_recepcion"
                f_str = safe_date_str(valor)
                cursor.execute(f"UPDATE Ordenes_Compra SET {campo_bd} = ? WHERE id = ?", (f_str, orden_id))
                
                if col == "Fecha Recepción":
                    if f_str:
                        cursor.execute("UPDATE Ordenes_Compra SET estatus = 'Recibido' WHERE id = ?", (orden_id,))
                    else:
                        cursor.execute("UPDATE Ordenes_Compra SET estatus = 'No despachado' WHERE id = ?", (orden_id,))
            elif col == "Proveedor":
                prov_id, _ = gestionar_proveedor(valor, cursor)
                cursor.execute("UPDATE Ordenes_Compra SET proveedor = ?, proveedor_id = ? WHERE id = ?", (valor, prov_id, orden_id))
    
    for row in cambios.get("added_rows", []):
        prov_nombre = row.get("Proveedor", "Desconocido")
        prov_id, _ = gestionar_proveedor(prov_nombre, cursor)
        f_rec = safe_date_str(row.get("Fecha Recepción"))
        estatus_inicial = "Recibido" if f_rec else row.get("Estatus", "No despachado")
        
        cursor.execute('''
            INSERT INTO Ordenes_Compra (numero_orden, proveedor_id, proveedor, tienda_destino, fecha_emision, fecha_envio, fecha_recepcion, monto_total, estatus, dias_inventario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (row.get("Nº OC", "N/A"), prov_id, prov_nombre, row.get("Tienda Destino", ""), safe_date_str(row.get("Fecha Emisión")), safe_date_str(row.get("Fecha Envío")), f_rec, row.get("Monto Total ($)", 0.0), estatus_inicial, row.get("Días Inventario", 0)))
    
    conn.commit()
    conn.close()

def procesar_cambios_proveedores():
    cambios = st.session_state.grid_proveedores
    df = st.session_state.df_prov_actual
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    for idx in cambios.get("deleted_rows", []):
        real_idx = int(idx)
        prov_id = int(df.iloc[real_idx]["ID"])
        cursor.execute("DELETE FROM Proveedores WHERE id = ?", (prov_id,))
        
    for idx, col_cambios in cambios.get("edited_rows", {}).items():
        real_idx = int(idx)
        prov_id = int(df.iloc[real_idx]["ID"])
        for col, valor in col_cambios.items():
            if col == "Proveedor": cursor.execute("UPDATE Proveedores SET nombre = ? WHERE id = ?", (valor, prov_id))
            elif col == "Días de Crédito": cursor.execute("UPDATE Proveedores SET dias_credito = ? WHERE id = ?", (valor, prov_id))
            elif col == "Días de Despacho": cursor.execute("UPDATE Proveedores SET dias_despacho = ? WHERE id = ?", (valor, prov_id))
            elif col == "Días Inventario (Estándar)": cursor.execute("UPDATE Proveedores SET dias_inventario = ? WHERE id = ?", (valor, prov_id))
                
    for row in cambios.get("added_rows", []):
        cursor.execute("INSERT INTO Proveedores (nombre, dias_credito, dias_despacho, dias_inventario) VALUES (?, ?, ?, ?)", 
                       (row.get("Proveedor", "Nuevo Proveedor"), row.get("Días de Crédito", 30), row.get("Días de Despacho", 3), row.get("Días Inventario (Estándar)", 15)))
        
    conn.commit()
    conn.close()

# -------------------------------------------------------------------
# FUNCIONES DE CONSULTA Y GUARDADO GENERAL
# -------------------------------------------------------------------
def cargar_ordenes():
    conn = obtener_conexion()
    query = '''
        SELECT 
            o.id AS "ID_BD",
            o.numero_orden AS "Nº OC",
            COALESCE(p.nombre, o.proveedor, 'Desconocido') AS "Proveedor",
            o.tienda_destino AS "Tienda Destino",
            o.fecha_emision AS "Fecha Emisión",
            o.fecha_envio AS "Fecha Envío",
            o.fecha_recepcion AS "Fecha Recepción",
            CASE 
                WHEN o.fecha_recepcion IS NOT NULL AND TRIM(o.fecha_recepcion) != '' 
                THEN date(o.fecha_recepcion, '+' || CAST(IFNULL(p.dias_credito, 30) AS TEXT) || ' days')
                ELSE NULL 
            END AS "Vencimiento Factura",
            o.monto_total AS "Monto Total ($)",
            o.estatus AS "Estatus",
            o.dias_inventario AS "Días Inventario",
            CASE 
                WHEN o.fecha_recepcion IS NOT NULL AND TRIM(o.fecha_recepcion) != '' AND o.dias_inventario > 0
                THEN date(o.fecha_recepcion, '+' || CAST(IFNULL(o.dias_inventario, 0) AS TEXT) || ' days')
                ELSE NULL 
            END AS "Fin Inventario"
        FROM Ordenes_Compra o
        LEFT JOIN Proveedores p ON o.proveedor_id = p.id
        ORDER BY o.id DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def cargar_productos_orden(orden_id):
    conn = obtener_conexion()
    query = 'SELECT codigo AS "Código", descripcion AS "Descripción", cantidad AS "Cantidad", precio_unitario AS "Precio Unitario ($)" FROM Detalles_Productos WHERE orden_id = ?'
    df = pd.read_sql_query(query, conn, params=(orden_id,))
    conn.close()
    return df

def obtener_estandar_inventario(proveedor_nombre):
    if not proveedor_nombre: return 15
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT dias_inventario FROM Proveedores WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(?))", (proveedor_nombre.strip(),))
    prov = cursor.fetchone()
    conn.close()
    return prov[0] if prov and prov[0] is not None else 15

def gestionar_proveedor(proveedor_nombre, cursor):
    prov_clean = proveedor_nombre.strip() if proveedor_nombre else "Proveedor Desconocido"
    cursor.execute("SELECT id, dias_credito FROM Proveedores WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(?))", (prov_clean,))
    prov = cursor.fetchone()
    if prov: return prov[0], prov[1]
    
    cursor.execute("INSERT INTO Proveedores (nombre, dias_credito, dias_despacho, dias_inventario) VALUES (?, ?, ?, ?)", (prov_clean, 30, 3, 15))
    return cursor.lastrowid, 30

def existe_orden_duplicada(numero_orden, tienda_destino):
    if not numero_orden or not tienda_destino: return False
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM Ordenes_Compra WHERE LOWER(TRIM(numero_orden)) = LOWER(TRIM(?)) AND LOWER(TRIM(tienda_destino)) = LOWER(TRIM(?))', 
                   (str(numero_orden).strip(), str(tienda_destino).strip()))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def guardar_orden(numero_orden, proveedor_nombre, tienda_destino, fecha_emi_dt, fecha_env_dt, fecha_rec_dt, monto_total, df_productos, estatus, dias_inventario):
    if existe_orden_duplicada(numero_orden, tienda_destino):
        return None, f"⚠️ La Orden N° '{numero_orden}' ya está registrada para la tienda '{tienda_destino}'."

    if fecha_rec_dt: estatus = "Recibido"

    conn = obtener_conexion()
    cursor = conn.cursor()
    proveedor_id, _ = gestionar_proveedor(proveedor_nombre, cursor)

    cursor.execute('''
        INSERT INTO Ordenes_Compra (numero_orden, proveedor_id, proveedor, tienda_destino, fecha_emision, fecha_envio, fecha_recepcion, monto_total, estatus, dias_inventario)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (numero_orden, proveedor_id, proveedor_nombre, tienda_destino, safe_date_str(fecha_emi_dt), safe_date_str(fecha_env_dt), safe_date_str(fecha_rec_dt), monto_total, estatus, dias_inventario))
    
    orden_id = cursor.lastrowid
    if df_productos is not None and not df_productos.empty:
        for _, prod in df_productos.iterrows():
            cursor.execute('INSERT INTO Detalles_Productos (orden_id, codigo, descripcion, cantidad, precio_unitario) VALUES (?, ?, ?, ?, ?)', 
                           (orden_id, str(prod.get('codigo', '')), str(prod.get('descripcion', '')), float(prod.get('cantidad', 0) or 0), float(prod.get('precio_unitario', 0) or 0)))
    conn.commit()
    conn.close()
    return orden_id, None

def calcular_alerta_pago(row):
    fecha_venc_str = row["Vencimiento Factura"]
    if not fecha_venc_str or pd.isna(fecha_venc_str): return "Sin recepción"
    try: fecha_venc = fecha_venc_str if isinstance(fecha_venc_str, date) else datetime.strptime(str(fecha_venc_str).split("T")[0], "%Y-%m-%d").date()
    except Exception: return "Sin recepción"
        
    dias_restantes = (fecha_venc - datetime.now().date()).days
    if dias_restantes < 0: return f"🔴 Vencida hace {abs(dias_restantes)} días"
    elif dias_restantes <= 5: return f"🟡 Por vencer ({dias_restantes} días)"
    else: return f"🟢 Vigente ({dias_restantes} días)"

def calcular_alerta_inventario(row):
    dias_inv = row.get("Días Inventario", 0)
    if pd.isna(dias_inv) or not dias_inv or dias_inv == 0: return "No definido"
    
    fin_str = row["Fin Inventario"]
    if not fin_str or pd.isna(fin_str): return "Sin recepción"
    
    try: fecha_fin = fin_str if isinstance(fin_str, date) else datetime.strptime(str(fin_str).split("T")[0], "%Y-%m-%d").date()
    except Exception: return "Error fecha"
        
    dias_restantes = (fecha_fin - datetime.now().date()).days
    if dias_restantes < 0: return f"🔴 Agotado hace {abs(dias_restantes)} días"
    elif dias_restantes <= 10: return f"🟡 Reponer pronto ({dias_restantes} días)" # Margen de 10 días para reponer
    else: return f"🟢 OK ({dias_restantes} días)"

# -------------------------------------------------------------------
# INTERFAZ DE USUARIO (PESTAÑAS)
# -------------------------------------------------------------------
st.title("📦 Diario de Control de Compras")

tab_ordenes, tab_escaner, tab_manual, tab_proveedores = st.tabs([
    "📋 Diario de Órdenes", "📥 Escanear PDF", "✍️ Registro Manual", "🏢 Proveedores (Auto-Guardado)"
])

# --- PESTAÑA 1: DIARIO ---
with tab_ordenes:
    st.subheader("📋 Registro General de Órdenes")
    st.caption("💡 El inventario se calcula automáticamente sumando los días a la **Fecha de Recepción**.")

    df_ordenes = cargar_ordenes()
    st.session_state.df_actual = df_ordenes.copy()

    if not df_ordenes.empty:
        df_editor = df_ordenes.copy()
        
        df_editor["Fecha Emisión"] = df_editor["Fecha Emisión"].apply(parse_a_fecha_obj)
        df_editor["Fecha Envío"] = df_editor["Fecha Envío"].apply(parse_a_fecha_obj)
        df_editor["Fecha Recepción"] = df_editor["Fecha Recepción"].apply(parse_a_fecha_obj)
        df_editor["Vencimiento Factura"] = df_editor["Vencimiento Factura"].apply(parse_a_fecha_obj)
        df_editor["Fin Inventario"] = df_editor["Fin Inventario"].apply(parse_a_fecha_obj)

        df_editor["Alerta de Pago"] = df_editor.apply(calcular_alerta_pago, axis=1)
        df_editor["Alerta Inventario"] = df_editor.apply(calcular_alerta_inventario, axis=1)

        col_config = {
            "ID_BD": None,
            "Nº OC": st.column_config.TextColumn("Nº OC", required=True),
            "Proveedor": st.column_config.TextColumn("Proveedor", required=True),
            "Tienda Destino": st.column_config.TextColumn("Tienda Destino", required=True),
            "Fecha Emisión": st.column_config.DateColumn("Fecha Emisión", format="DD/MM/YYYY"),
            "Fecha Envío": st.column_config.DateColumn("Fecha Envío", format="DD/MM/YYYY"),
            "Fecha Recepción": st.column_config.DateColumn("Fecha Recepción", format="DD/MM/YYYY"),
            "Vencimiento Factura": st.column_config.DateColumn("Venc. Factura", format="DD/MM/YYYY", disabled=True),
            "Alerta de Pago": st.column_config.TextColumn("Alerta de Pago", disabled=True),
            "Monto Total ($)": st.column_config.NumberColumn("Monto Total ($)", format="$%.2f", min_value=0.0),
            "Estatus": st.column_config.SelectboxColumn("Estatus", options=["No despachado", "Enviada", "Recibido"], required=True),
            "Días Inventario": st.column_config.NumberColumn("Días Inv.", min_value=0, step=1),
            "Fin Inventario": st.column_config.DateColumn("Fin Inventario (Auto)", format="DD/MM/YYYY", disabled=True),
            "Alerta Inventario": st.column_config.TextColumn("Alerta Inventario", disabled=True)
        }

        st.data_editor(
            df_editor,
            column_config=col_config,
            width="stretch",
            num_rows="dynamic",
            key="grid_diario_ordenes",
            on_change=procesar_cambios_diario
        )

        st.divider()
        opciones_ordenes = {f"ID #{r['ID_BD']} | OC: {r['Nº OC']} | {r['Proveedor']}": r['ID_BD'] for _, r in df_ordenes.iterrows()}
        if opciones_ordenes:
            sel_label = st.selectbox("🔍 Ver detalle de productos de una orden:", options=list(opciones_ordenes.keys()))
            df_items = cargar_productos_orden(opciones_ordenes[sel_label])
            if not df_items.empty:
                df_items["Precio Unitario ($)"] = df_items["Precio Unitario ($)"].apply(formato_moneda)
                st.dataframe(df_items, width="stretch")
            else:
                st.info("No hay productos registrados para esta orden.")
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
                col1, col2 = st.columns(2)
                with col1:
                    num_oc = st.text_input("Número de OC:", value=datos_oc.get("numero_orden", ""))
                    proveedor = st.text_input("Proveedor:", value=datos_oc.get("proveedor", ""))
                    tienda = st.text_input("Tienda Destino:", value=datos_oc.get("tienda_destino", ""))
                    monto = st.number_input("Monto Total ($):", value=float(datos_oc.get("monto_total", 0.0) or 0.0), step=0.01)
                with col2:
                    f_emision = st.date_input("Fecha Emisión:", value=datetime.now().date(), format="DD/MM/YYYY")
                    f_envio = st.date_input("Fecha de Envío:", value=datetime.now().date(), format="DD/MM/YYYY")
                    
                    # Carga el estándar de inventario basado en el proveedor (O usa 15 si es nuevo)
                    estandar_inv = obtener_estandar_inventario(proveedor)
                    dias_inv = st.number_input("Días de Inventario a cubrir:", value=estandar_inv, min_value=0, step=1, help="Esta OC cubre esta cantidad de días de inventario.")
                    
                    recibida = st.checkbox("¿Orden recibida?")
                    f_recepcion = st.date_input("Fecha de Recepción:", value=datetime.now().date(), format="DD/MM/YYYY") if recibida else None

                df_p = pd.DataFrame(datos_oc["productos"]) if datos_oc.get("productos") else pd.DataFrame(columns=["codigo", "descripcion", "cantidad", "precio_unitario"])
                prods_editados = st.data_editor(df_p, num_rows="dynamic", width="stretch")

                if st.form_submit_button("Guardar Orden Extraída", type="primary"):
                    estatus = "Recibido" if recibida else "No despachado"
                    orden_id, err = guardar_orden(num_oc, proveedor, tienda, f_emision, f_envio, f_recepcion, monto, prods_editados, estatus, dias_inv)
                    if err: st.error(err)
                    else:
                        st.session_state.pdf_guardado_exito = True
                        st.rerun()

# --- PESTAÑA 3: REGISTRO MANUAL ---
with tab_manual:
    st.subheader("Registrar Orden Manualmente (Sin PDF)")
    
    with st.form("form_manual_limpio"):
        col_m1, col_m2 = st.columns(2)
        
        with col_m1:
            m_num = st.text_input("Número de OC:")
            m_prov = st.text_input("Proveedor:")
            m_tienda = st.text_input("Tienda Destino:")
            m_monto = st.number_input("Monto Total ($):", min_value=0.0, step=0.01)
            
        with col_m2:
            m_emi = st.date_input("Fecha Emisión:", format="DD/MM/YYYY")
            m_env = st.date_input("Fecha Envío:", format="DD/MM/YYYY")
            m_dias_inv = st.number_input("Días de Inventario a cubrir:", value=15, min_value=0, step=1)
            
            m_recibida = st.checkbox("Marcar como Recibida")
            m_rec = st.date_input("Fecha Recepción:", format="DD/MM/YYYY") if m_recibida else None

        st.write("Añadir Productos (Opcional)")
        m_prods = st.data_editor(pd.DataFrame(columns=["codigo", "descripcion", "cantidad", "precio_unitario"]), num_rows="dynamic", width="stretch")

        btn_guardar_manual = st.form_submit_button("Guardar Orden Manual", type="primary")

        if btn_guardar_manual:
            if m_prov and m_num and m_tienda:
                fecha_recepcion_final = m_rec if m_recibida else None
                if m_recibida and not fecha_recepcion_final:
                    fecha_recepcion_final = datetime.now().date()
                
                estatus_m = "Recibido" if fecha_recepcion_final else "No despachado"
                
                # Para registros manuales, en el momento del "submit" verificamos el estándar de la BD en caso de que sea nuevo
                estandar_manual = obtener_estandar_inventario(m_prov) if m_dias_inv == 15 else m_dias_inv
                
                orden_id, err = guardar_orden(m_num, m_prov, m_tienda, m_emi, m_env, fecha_recepcion_final, m_monto, m_prods, estatus_m, estandar_manual)
                if err: st.error(err)
                else: st.success(f"¡Orden manual N° {m_num} registrada con éxito!")
            else: 
                st.error("Por favor completa los campos obligatorios: Número de OC, Proveedor y Tienda Destino.")

# --- PESTAÑA 4: PROVEEDORES ---
with tab_proveedores:
    st.subheader("Base de Datos de Proveedores")
    st.caption("💡 Todo lo que edites, agregues o borres aquí **se guarda automáticamente** e impacta de inmediato en el Diario.")
    
    conn = obtener_conexion()
    df_prov = pd.read_sql_query("SELECT id AS 'ID', nombre AS 'Proveedor', dias_credito AS 'Días de Crédito', dias_despacho AS 'Días de Despacho', dias_inventario AS 'Días Inventario (Estándar)' FROM Proveedores", conn)
    conn.close()
    
    st.session_state.df_prov_actual = df_prov.copy()
    
    st.data_editor(
        df_prov,
        column_config={"ID": None, "Días Inventario (Estándar)": st.column_config.NumberColumn("Días Inventario (Estándar)", min_value=0, step=1)},
        width="stretch",
        num_rows="dynamic",
        key="grid_proveedores",
        on_change=procesar_cambios_proveedores
    )