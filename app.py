import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pdf_processor import extraer_datos_oc

st.set_page_config(page_title="Control de Compras", page_icon="📦", layout="wide")

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
            o.id AS "ID_BD",
            o.numero_orden AS "Nº OC",
            p.nombre AS "Proveedor",
            o.tienda_destino AS "Tienda Destino",
            o.fecha_emision AS "Fecha Emisión",
            o.fecha_envio AS "Fecha Envío",
            o.fecha_recepcion AS "Fecha Recepción",
            o.fecha_vencimiento AS "Vencimiento Factura",
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

def guardar_orden(numero_orden, proveedor_nombre, tienda_destino, fecha_emi_dt, fecha_env_dt, fecha_rec_dt, monto_total, df_productos, estatus="No despachado"):
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, dias_credito FROM Proveedores WHERE LOWER(nombre) = LOWER(?)", (proveedor_nombre.strip(),))
    prov = cursor.fetchone()
    
    if prov:
        proveedor_id, dias_credito = prov[0], prov[1]
    else:
        dias_credito = 30
        cursor.execute("INSERT INTO Proveedores (nombre, dias_credito, dias_despacho) VALUES (?, ?, ?)", (proveedor_nombre.strip(), dias_credito, 3))
        proveedor_id = cursor.lastrowid

    fecha_emi_fmt = fecha_emi_dt.strftime("%Y-%m-%d") if fecha_emi_dt else None
    fecha_env_fmt = fecha_env_dt.strftime("%Y-%m-%d") if fecha_env_dt else None
    fecha_rec_fmt = fecha_rec_dt.strftime("%Y-%m-%d") if fecha_rec_dt else None
    
    if fecha_rec_dt:
        fecha_venc_dt = fecha_rec_dt + timedelta(days=dias_credito)
        fecha_venc_fmt = fecha_venc_dt.strftime("%Y-%m-%d")
    else:
        fecha_venc_fmt = None

    cursor.execute('''
        INSERT INTO Ordenes_Compra (numero_orden, proveedor_id, tienda_destino, fecha_emision, fecha_envio, fecha_recepcion, fecha_vencimiento, monto_total, estatus)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (numero_orden, proveedor_id, tienda_destino, fecha_emi_fmt, fecha_env_fmt, fecha_rec_fmt, fecha_venc_fmt, monto_total, estatus))
    
    orden_id = cursor.lastrowid

    for _, prod in df_productos.iterrows():
        cursor.execute('''
            INSERT INTO Detalles_Productos (orden_id, codigo, descripcion, cantidad, precio_unitario)
            VALUES (?, ?, ?, ?, ?)
        ''', (orden_id, prod.get('codigo', ''), prod.get('descripcion', ''), prod.get('cantidad', 0), prod.get('precio_unitario', 0)))

    conn.commit()
    conn.close()
    return orden_id

def actualizar_orden(orden_id, num_oc, tienda, f_emi, f_env, f_rec, f_ven, monto, estatus):
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    f_emi_str = f_emi.strftime("%Y-%m-%d") if f_emi else None
    f_env_str = f_env.strftime("%Y-%m-%d") if f_env else None
    f_rec_str = f_rec.strftime("%Y-%m-%d") if f_rec else None
    f_ven_str = f_ven.strftime("%Y-%m-%d") if f_ven else None

    cursor.execute('''
        UPDATE Ordenes_Compra 
        SET numero_orden = ?, tienda_destino = ?, fecha_emision = ?, 
            fecha_envio = ?, fecha_recepcion = ?, fecha_vencimiento = ?, 
            monto_total = ?, estatus = ?
        WHERE id = ?
    ''', (num_oc, tienda, f_emi_str, f_env_str, f_rec_str, f_ven_str, monto, estatus, orden_id))
    
    conn.commit()
    conn.close()

def eliminar_orden(orden_id):
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Detalles_Productos WHERE orden_id = ?", (orden_id,))
    cursor.execute("DELETE FROM Ordenes_Compra WHERE id = ?", (orden_id,))
    conn.commit()
    conn.close()

def calcular_alerta(row):
    fecha_venc_str = row["Vencimiento Factura"]
    if not fecha_venc_str: return "Sin recepción"
    
    fecha_venc = datetime.strptime(fecha_venc_str, "%Y-%m-%d").date()
    hoy = datetime.now().date()
    dias_restantes = (fecha_venc - hoy).days

    if dias_restantes < 0:
        return f"🔴 Vencida hace {abs(dias_restantes)} días"
    elif dias_restantes <= 5:
        return f"🟡 Por vencer ({dias_restantes} días)"
    else:
        return f"🟢 Vigente ({dias_restantes} días)"

st.title("📦 Diario de Control de Compras")

tab_ordenes, tab_escaner, tab_manual, tab_proveedores = st.tabs(["📋 Diario de Órdenes", "📥 Escanear PDF", "✍️ Registro Manual", "🏢 Proveedores"])

# --- PESTAÑA 1: DIARIO Y ESTATUS ---
with tab_ordenes:
    df_ordenes = cargar_ordenes()
    if not df_ordenes.empty:
        df_display = df_ordenes.copy()
        df_display["Alerta de Pago"] = df_display.apply(calcular_alerta, axis=1)
        
        df_display["Monto Total ($)"] = df_display["Monto Total ($)"].apply(formato_moneda)
        df_display["Fecha Emisión"] = df_display["Fecha Emisión"].apply(formato_fecha)
        df_display["Fecha Envío"] = df_display["Fecha Envío"].apply(formato_fecha)
        df_display["Fecha Recepción"] = df_display["Fecha Recepción"].apply(formato_fecha)
        df_display["Vencimiento Factura"] = df_display["Vencimiento Factura"].apply(formato_fecha)
        
        # Ocultamos la columna técnica de BD para la vista
        st.dataframe(df_display.drop(columns=["ID_BD", "_dias_credito"]), use_container_width=True)
        
        st.divider()
        st.subheader("⚙️ Gestionar, Editar o Eliminar Orden")
        
        # Selector de orden a editar
        opciones_ordenes = {f"OC: {r['Nº OC']} | {r['Proveedor']}": r['ID_BD'] for _, r in df_ordenes.iterrows()}
        orden_seleccionada_label = st.selectbox("Selecciona la Orden:", options=list(opciones_ordenes.keys()))
        orden_id_seleccionada = opciones_ordenes[orden_seleccionada_label]
        
        # Filtrar datos de la orden seleccionada para llenar el formulario
        orden_data = df_ordenes[df_ordenes["ID_BD"] == orden_id_seleccionada].iloc[0]
        
        with st.form(key="form_editar_orden"):
            st.write(f"Modificando datos de la orden de **{orden_data['Proveedor']}**")
            c1, c2, c3 = st.columns(3)
            
            with c1:
                e_num = st.text_input("Número de OC:", value=str(orden_data["Nº OC"]) if pd.notna(orden_data["Nº OC"]) else "")
                e_tienda = st.text_input("Tienda Destino:", value=str(orden_data["Tienda Destino"]) if pd.notna(orden_data["Tienda Destino"]) else "")
                e_monto = st.number_input("Monto Total ($):", value=float(orden_data["Monto Total ($)"]), step=0.01)
                
                opciones_estatus = ["No despachado", "Enviada", "Recibido"]
                idx_estatus = opciones_estatus.index(orden_data["Estatus"]) if orden_data["Estatus"] in opciones_estatus else 0
                e_estatus = st.selectbox("Estatus:", options=opciones_estatus, index=idx_estatus)
            
            with c2:
                # Helper para convertir texto de BD a objeto fecha para el widget
                def parse_date(d_str):
                    if pd.isna(d_str) or not d_str: return None
                    return datetime.strptime(str(d_str), "%Y-%m-%d").date()
                
                d_emi = parse_date(orden_data["Fecha Emisión"])
                d_env = parse_date(orden_data["Fecha Envío"])
                d_rec = parse_date(orden_data["Fecha Recepción"])
                
                e_emi = st.date_input("Fecha Emisión:", value=d_emi if d_emi else datetime.now().date(), format="DD/MM/YYYY")
                e_env = st.date_input("Fecha Envío:", value=d_env if d_env else datetime.now().date(), format="DD/MM/YYYY")
                
                rec_check = st.checkbox("Orden Recibida (Habilita Recepción)", value=True if d_rec else False)
                e_rec = st.date_input("Fecha Recepción:", value=d_rec if d_rec else datetime.now().date(), format="DD/MM/YYYY") if rec_check else None
                
            with c3:
                st.write("### Acciones")
                btn_actualizar = st.form_submit_button("💾 Guardar Cambios", type="primary")
                st.write("") # Espaciador visual
                btn_eliminar = st.form_submit_button("🗑️ Eliminar Orden permanentemente")
                
        # Acciones según el botón presionado
        if btn_actualizar:
            e_ven = None
            if e_rec: # Si se marca como recibida, se recalculan los días de vencimiento
                e_ven = e_rec + timedelta(days=int(orden_data["_dias_credito"]))
                
            actualizar_orden(orden_id_seleccionada, e_num, e_tienda, e_emi, e_env, e_rec, e_ven, e_monto, e_estatus)
            st.success("¡Orden actualizada con éxito!")
            st.rerun()
            
        if btn_eliminar:
            eliminar_orden(orden_id_seleccionada)
            st.success("¡Orden eliminada de la base de datos!")
            st.rerun()

    else:
        st.info("Aún no hay órdenes registradas.")

# --- PESTAÑA 2: ESCANEAR PDF ---
with tab_escaner:
    st.subheader("Extraer datos desde PDF")
    archivo_pdf = st.file_uploader("Sube el PDF de la OC:", type=["pdf"])
    
    if archivo_pdf is not None:
        with st.spinner("Extrayendo datos..."):
            datos_oc = extraer_datos_oc(archivo_pdf)

        st.info("💡 Todos los campos a continuación son libres. Modifica cualquier dato si el escáner cometió un error.")
        
        with st.form("form_pdf"):
            col1, col2 = st.columns(2)
            with col1:
                num_oc = st.text_input("Número de OC:", value=datos_oc.get("numero_orden", ""))
                proveedor = st.text_input("Proveedor:", value=datos_oc.get("proveedor", ""))
                tienda = st.text_input("Tienda Destino:", value=datos_oc.get("tienda_destino", ""))
                monto = st.number_input("Monto Total ($):", value=float(datos_oc.get("monto_total", 0.0)), step=0.01)
            with col2:
                fecha_str = datos_oc.get("fecha_emision", "")
                fecha_defecto = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else datetime.now().date()
                
                f_emision = st.date_input("Fecha Emisión:", value=fecha_defecto, format="DD/MM/YYYY")
                f_envio = st.date_input("Fecha de Envío:", value=datetime.now().date(), format="DD/MM/YYYY")
                
                recibida = st.checkbox("¿Esta orden ya fue recibida hoy?")
                f_recepcion = st.date_input("Fecha de Recepción:", value=datetime.now().date(), format="DD/MM/YYYY") if recibida else None

            st.write("### Productos (Modificables)")
            df_p = pd.DataFrame(datos_oc["productos"]) if datos_oc["productos"] else pd.DataFrame(columns=["codigo", "descripcion", "cantidad", "precio_unitario"])
            prods_editados = st.data_editor(df_p, num_rows="dynamic", use_container_width=True)

            if st.form_submit_button("Guardar Orden Extraída", type="primary"):
                estatus = "Recibido" if recibida else "No despachado"
                guardar_orden(num_oc, proveedor, tienda, f_emision, f_envio, f_recepcion, monto, prods_editados, estatus)
                st.success("¡Orden guardada exitosamente!")
                st.rerun()

# --- PESTAÑA 3: REGISTRO MANUAL ---
with tab_manual:
    st.subheader("Registrar Orden Manualmente (Sin PDF)")
    with st.form("form_manual"):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            m_num = st.text_input("Número de OC:")
            m_prov = st.text_input("Proveedor:")
            m_tienda = st.text_input("Tienda Destino:")
            m_monto = st.number_input("Monto Total ($):", min_value=0.0, step=0.01)
        with col_m2:
            m_emi = st.date_input("Fecha Emisión (Manual):", format="DD/MM/YYYY")
            m_env = st.date_input("Fecha Envío (Manual):", format="DD/MM/YYYY")
            m_recibida = st.checkbox("Marcar como Recibida")
            m_rec = st.date_input("Fecha Recepción (Manual):", format="DD/MM/YYYY") if m_recibida else None

        st.write("Añadir Productos (Opcional)")
        m_prods = st.data_editor(pd.DataFrame(columns=["codigo", "descripcion", "cantidad", "precio_unitario"]), num_rows="dynamic", use_container_width=True)

        if st.form_submit_button("Guardar Orden Manual"):
            if m_prov and m_num:
                estatus_m = "Recibido" if m_recibida else "No despachado"
                guardar_orden(m_num, m_prov, m_tienda, m_emi, m_env, m_rec, m_monto, m_prods, estatus_m)
                st.success("Orden manual registrada.")
                st.rerun()
            else:
                st.error("Por favor completa el Número de OC y el Proveedor.")

# --- PESTAÑA 4: PROVEEDORES ---
with tab_proveedores:
    st.subheader("Base de Datos de Proveedores")
    conn = obtener_conexion()
    df_prov = pd.read_sql_query("SELECT id AS 'ID', nombre AS 'Proveedor', dias_credito AS 'Días de Crédito', dias_despacho AS 'Días de Despacho' FROM Proveedores", conn)
    conn.close()
    
    with st.expander("➕ Agregar Nuevo Proveedor Manualmente"):
        with st.form("form_nuevo_prov"):
            n_prov = st.text_input("Nombre del Proveedor:")
            n_credito = st.number_input("Días de Crédito:", min_value=0, value=30)
            n_despacho = st.number_input("Días de Despacho:", min_value=0, value=3)
            if st.form_submit_button("Registrar Proveedor"):
                if n_prov:
                    conn = obtener_conexion()
                    conn.execute("INSERT INTO Proveedores (nombre, dias_credito, dias_despacho) VALUES (?, ?, ?)", (n_prov, n_credito, n_despacho))
                    conn.commit()
                    conn.close()
                    st.success("Proveedor agregado.")
                    st.rerun()

    st.write("Editar Proveedores Existentes:")
    if not df_prov.empty:
        with st.form("form_editar_prov"):
            prov_editados = st.data_editor(df_prov, disabled=["ID", "Proveedor"], use_container_width=True)
            if st.form_submit_button("Guardar Cambios en Tiempos"):
                conn = obtener_conexion()
                for _, row in prov_editados.iterrows():
                    conn.execute('UPDATE Proveedores SET dias_credito = ?, dias_despacho = ? WHERE id = ?', (row['Días de Crédito'], row['Días de Despacho'], row['ID']))
                conn.commit()
                conn.close()
                st.success("Tiempos actualizados.")
                st.rerun()