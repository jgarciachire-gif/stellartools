import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pdf_processor import extraer_datos_oc

st.set_page_config(page_title="Control de Compras", page_icon="📦", layout="wide")

# --- FUNCIONES DE FORMATO ---
def formato_moneda(valor):
    if pd.isna(valor): return "0,00"
    return "{:,.2f}".format(float(valor)).replace(',', 'X').replace('.', ',').replace('X', '.')

def formato_fecha(fecha_str):
    if not fecha_str or pd.isna(fecha_str): return ""
    try:
        return datetime.strptime(str(fecha_str), "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return fecha_str

def obtener_conexion():
    return sqlite3.connect('compras.db')

def cargar_ordenes():
    conn = obtener_conexion()
    query = '''
        SELECT 
            o.id AS "Nº Orden",
            p.nombre AS "Proveedor",
            o.tienda_destino AS "Tienda Destino",
            o.fecha_emision AS "Fecha Emisión",
            o.fecha_envio AS "Fecha Envío",
            o.fecha_vencimiento AS "Fecha Vencimiento",
            o.monto_total AS "Monto Total ($)",
            o.estatus AS "Estatus",
            p.dias_credito AS "_dias_credito"
        FROM Ordenes_Compra o
        LEFT JOIN Proveedores p ON o.proveedor_id = p.id
        ORDER BY o.id DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def guardar_orden_completa(proveedor_nombre, tienda_destino, fecha_emision_dt, fecha_envio_dt, monto_total, df_productos_editados):
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    # Proveedor
    cursor.execute("SELECT id, dias_credito FROM Proveedores WHERE LOWER(nombre) = LOWER(?)", (proveedor_nombre.strip(),))
    prov = cursor.fetchone()
    
    if prov:
        proveedor_id, dias_credito = prov[0], prov[1]
    else:
        dias_credito = 30
        cursor.execute("INSERT INTO Proveedores (nombre, dias_credito, dias_despacho) VALUES (?, ?, ?)", (proveedor_nombre.strip(), dias_credito, 3))
        proveedor_id = cursor.lastrowid

    fecha_emision_fmt = fecha_emision_dt.strftime("%Y-%m-%d")
    fecha_envio_fmt = fecha_envio_dt.strftime("%Y-%m-%d")
    fecha_vencimiento_dt = fecha_emision_dt + timedelta(days=dias_credito)
    fecha_vencimiento_fmt = fecha_vencimiento_dt.strftime("%Y-%m-%d")

    cursor.execute('''
        INSERT INTO Ordenes_Compra (proveedor_id, tienda_destino, fecha_emision, fecha_envio, fecha_vencimiento, monto_total, estatus)
        VALUES (?, ?, ?, ?, ?, ?, 'No despachado')
    ''', (proveedor_id, tienda_destino, fecha_emision_fmt, fecha_envio_fmt, fecha_vencimiento_fmt, monto_total))
    
    orden_id = cursor.lastrowid

    for _, prod in df_productos_editados.iterrows():
        cursor.execute('''
            INSERT INTO Detalles_Productos (orden_id, codigo, descripcion, cantidad, precio_unitario)
            VALUES (?, ?, ?, ?, ?)
        ''', (orden_id, prod['codigo'], prod['descripcion'], prod['cantidad'], prod['precio_unitario']))

    conn.commit()
    conn.close()
    return orden_id

def calcular_alerta(row):
    fecha_venc_str = row["Fecha Vencimiento"]
    dias_credito = row["_dias_credito"]
    
    if not fecha_venc_str: return "Sin Fecha"
    
    fecha_venc = datetime.strptime(fecha_venc_str, "%Y-%m-%d").date()
    hoy = datetime.now().date()
    dias_restantes = (fecha_venc - hoy).days

    alerta = f"({dias_restantes} días rest. de {dias_credito})"
    if dias_restantes < 0:
        return f"🔴 Vencida hace {abs(dias_restantes)} días"
    elif dias_restantes <= 5:
        return f"🟡 Por vencer {alerta}"
    else:
        return f"🟢 Vigente {alerta}"

# --- INTERFAZ GRÁFICA ---
st.title("📦 Diario de Control de Compras")

tab_ordenes, tab_subir, tab_proveedores = st.tabs(["📋 Órdenes de Compra", "📤 Cargar PDF", "🏢 Proveedores"])

# --- PESTAÑA: CARGAR PDF ---
with tab_subir:
    st.subheader("Cargar Orden de Compra desde PDF")
    
    archivo_pdf = st.file_uploader("Selecciona o arrastra el archivo PDF de la OC:", type=["pdf"])
    
    if archivo_pdf is not None:
        with st.spinner("Extrayendo datos del PDF..."):
            datos_oc = extraer_datos_oc(archivo_pdf)

        if datos_oc is None:
            st.warning("⚠️ No se pudieron extraer datos automáticamente. Completa los campos manualmente.")
            datos_oc = {"proveedor": "", "tienda_destino": "", "fecha_emision": "", "monto_total": 0.0, "productos": []}
        
        with st.form(key="form_confirmar_oc"):
            col1, col2 = st.columns(2)
            
            with col1:
                proveedor = st.text_input("Proveedor:", value=datos_oc["proveedor"])
                tienda_destino = st.text_input("Tienda Destino:", value=datos_oc["tienda_destino"])
            
            with col2:
                # Convertir string extraído a objeto date para el calendario
                fecha_str = datos_oc.get("fecha_emision", "")
                fecha_defecto = datetime.now().date()
                if fecha_str:
                    try:
                        fecha_defecto = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                    except ValueError:
                        pass
                        
                fecha_emision = st.date_input("Fecha Emisión:", value=fecha_defecto, format="DD/MM/YYYY")
                fecha_envio = st.date_input("Fecha de Envío:", value=datetime.now().date(), format="DD/MM/YYYY")
                monto_total = st.number_input("Monto Total ($):", value=float(datos_oc["monto_total"]), step=0.01)

            st.write("### Productos Detectados (¡Puedes editarlos libremente!)")
            df_prods_temp = pd.DataFrame(datos_oc["productos"]) if datos_oc["productos"] else pd.DataFrame(columns=["codigo", "descripcion", "cantidad", "precio_unitario"])
            
            # Editor interactivo de datos extraídos
            productos_editados = st.data_editor(df_prods_temp, num_rows="dynamic", use_container_width=True)

            btn_guardar = st.form_submit_button("💾 Guardar Orden en la Base de Datos", type="primary")
            
            if btn_guardar:
                if not proveedor or not tienda_destino:
                    st.error("Por favor completa al menos el Proveedor y la Tienda Destino.")
                else:
                    nueva_orden_id = guardar_orden_completa(
                        proveedor, tienda_destino, fecha_emision, fecha_envio, monto_total, productos_editados
                    )
                    st.success(f"¡Orden Nº {nueva_orden_id} registrada con éxito!")
                    st.balloons()

# --- PESTAÑA: ÓRDENES DE COMPRA ---
with tab_ordenes:
    df_ordenes = cargar_ordenes()

    if not df_ordenes.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Órdenes", len(df_ordenes))
        col2.metric("🟢 Recibidas", len(df_ordenes[df_ordenes["Estatus"] == "Recibido"]))
        col3.metric("🔵 Enviadas", len(df_ordenes[df_ordenes["Estatus"] == "Enviada"]))
        col4.metric("🟠 No Despachadas", len(df_ordenes[df_ordenes["Estatus"] == "No despachado"]))
        st.divider()

    st.subheader("Diario / Estado de las Órdenes")
    
    if df_ordenes.empty:
        st.info("Aún no hay órdenes registradas.")
    else:
        df_display = df_ordenes.copy()
        
        # Calcular alertas
        df_display["Alerta de Crédito"] = df_display.apply(calcular_alerta, axis=1)
        
        # Aplicar formato Venezolano y fechas DD-MM-YYYY para visualización
        df_display["Monto Total ($)"] = df_display["Monto Total ($)"].apply(formato_moneda)
        df_display["Fecha Emisión"] = df_display["Fecha Emisión"].apply(formato_fecha)
        df_display["Fecha Envío"] = df_display["Fecha Envío"].apply(formato_fecha)
        df_display["Fecha Vencimiento"] = df_display["Fecha Vencimiento"].apply(formato_fecha)
        
        df_display = df_display.drop(columns=["_dias_credito"]) # Ocultar columna técnica
        
        st.dataframe(df_display, use_container_width=True)
        st.divider()

        # Cambiar Estatus
        st.subheader("🔄 Cambiar Estatus de una Orden")
        col_form1, col_form2 = st.columns([1, 2])
        
        with col_form1:
            opciones_ordenes = {f"Nº {r['Nº Orden']} | {r['Proveedor']}": r['Nº Orden'] for _, r in df_ordenes.iterrows()}
            orden_seleccionada_label = st.selectbox("Selecciona la Orden:", options=list(opciones_ordenes.keys()))
            orden_id_seleccionada = opciones_ordenes[orden_seleccionada_label]
            estatus_actual = df_ordenes[df_ordenes["Nº Orden"] == orden_id_seleccionada]["Estatus"].values[0]

        with col_form2:
            with st.form(key="form_cambiar_estatus"):
                opciones_estatus = ["No despachado", "Enviada", "Recibido"]
                idx_estatus = opciones_estatus.index(estatus_actual) if estatus_actual in opciones_estatus else 0
                nuevo_estatus = st.selectbox("Nuevo Estatus:", options=opciones_estatus, index=idx_estatus)
                
                if st.form_submit_button("Actualizar Estatus", type="primary"):
                    conn = obtener_conexion()
                    conn.execute('UPDATE Ordenes_Compra SET estatus = ? WHERE id = ?', (nuevo_estatus, orden_id_seleccionada))
                    conn.commit()
                    conn.close()
                    st.success(f"Estatus actualizado a {nuevo_estatus}")
                    st.rerun()

# --- PESTAÑA: PROVEEDORES ---
with tab_proveedores:
    st.subheader("Gestión de Proveedores (Base de Datos)")
    st.write("Edita directamente los días en la tabla inferior y presiona Guardar.")
    
    conn = obtener_conexion()
    df_prov = pd.read_sql_query("SELECT id AS 'ID', nombre AS 'Proveedor', dias_credito AS 'Días de Crédito', dias_despacho AS 'Días de Despacho' FROM Proveedores", conn)
    conn.close()
    
    if df_prov.empty:
        st.info("No hay proveedores registrados.")
    else:
        with st.form("form_proveedores"):
            # Editor de tabla de proveedores
            prov_editados = st.data_editor(df_prov, disabled=["ID", "Proveedor"], use_container_width=True)
            
            if st.form_submit_button("Guardar Cambios en Proveedores"):
                conn = obtener_conexion()
                cursor = conn.cursor()
                for _, row in prov_editados.iterrows():
                    cursor.execute('''
                        UPDATE Proveedores SET dias_credito = ?, dias_despacho = ? WHERE id = ?
                    ''', (row['Días de Crédito'], row['Días de Despacho'], row['ID']))
                conn.commit()
                conn.close()
                st.success("¡Base de datos de proveedores actualizada!")
                st.rerun()