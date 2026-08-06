import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pdf_processor import extraer_datos_oc

# Configuración de la página web
st.set_page_config(page_title="Control de Compras", page_icon="📦", layout="wide")

def obtener_conexion():
    return sqlite3.connect('compras.db')

# Cargar órdenes cruzando información con la tabla de proveedores
def cargar_ordenes():
    conn = obtener_conexion()
    query = '''
        SELECT 
            o.id AS "Nº Orden",
            p.nombre AS "Proveedor",
            o.tienda_destino AS "Tienda Destino",
            o.fecha_emision AS "Fecha Emisión",
            o.fecha_vencimiento AS "Fecha Vencimiento",
            o.monto_total AS "Monto Total ($)",
            o.estatus AS "Estatus"
        FROM Ordenes_Compra o
        LEFT JOIN Proveedores p ON o.proveedor_id = p.id
        ORDER BY o.id DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Función para guardar una orden completa y sus productos extraídos del PDF
def guardar_orden_completa(proveedor_nombre, tienda_destino, fecha_emision_str, monto_total, lista_productos):
    conn = obtener_conexion()
    cursor = conn.cursor()
    
    # 1. Buscar o crear el proveedor para obtener sus días de crédito
    cursor.execute("SELECT id, dias_credito FROM Proveedores WHERE LOWER(nombre) = LOWER(?)", (proveedor_nombre.strip(),))
    prov = cursor.fetchone()
    
    if prov:
        proveedor_id, dias_credito = prov[0], prov[1]
    else:
        # Si el proveedor no existe en BD, se registra por defecto con 30 días
        dias_credito = 30
        cursor.execute("INSERT INTO Proveedores (nombre, dias_credito) VALUES (?, ?)", (proveedor_nombre.strip(), dias_credito))
        proveedor_id = cursor.lastrowid

    # 2. Normalizar la fecha de emisión y calcular la fecha de vencimiento
    try:
        if "/" in fecha_emision_str:
            fecha_dt = datetime.strptime(fecha_emision_str, "%d/%m/%Y")
        else:
            fecha_dt = datetime.strptime(fecha_emision_str, "%Y-%m-%d")
    except ValueError:
        fecha_dt = datetime.now()

    fecha_emision_fmt = fecha_dt.strftime("%Y-%m-%d")
    fecha_vencimiento_dt = fecha_dt + timedelta(days=dias_credito)
    fecha_vencimiento_fmt = fecha_vencimiento_dt.strftime("%Y-%m-%d")

    # 3. Insertar la Orden de Compra principal
    cursor.execute('''
        INSERT INTO Ordenes_Compra (proveedor_id, tienda_destino, fecha_emision, fecha_vencimiento, monto_total, estatus)
        VALUES (?, ?, ?, ?, ?, 'No despachado')
    ''', (proveedor_id, tienda_destino, fecha_emision_fmt, fecha_vencimiento_fmt, monto_total))
    
    orden_id = cursor.lastrowid

    # 4. Insertar cada producto vinculado a la orden
    for prod in lista_productos:
        cursor.execute('''
            INSERT INTO Detalles_Productos (orden_id, codigo, descripcion, cantidad, precio_unitario)
            VALUES (?, ?, ?, ?, ?)
        ''', (orden_id, prod['codigo'], prod['descripcion'], prod['cantidad'], prod['precio_unitario']))

    conn.commit()
    conn.close()
    return orden_id

# Función para actualizar el estatus en la base de datos
def actualizar_estatus_orden(orden_id, nuevo_estatus):
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE Ordenes_Compra 
        SET estatus = ? 
        WHERE id = ?
    ''', (nuevo_estatus, orden_id))
    conn.commit()
    conn.close()

# Lógica para calcular alertas de vencimiento
def calcular_alerta(fecha_venc_str):
    if not fecha_venc_str:
        return "Sin Fecha"
    
    fecha_venc = datetime.strptime(fecha_venc_str, "%Y-%m-%d").date()
    hoy = datetime.now().date()
    dias_restantes = (fecha_venc - hoy).days

    if dias_restantes < 0:
        return f"🔴 Vencida ({abs(dias_restantes)} días transcurridos)"
    elif dias_restantes <= 5:
        return f"🟡 Próxima a vencer ({dias_restantes} días restantes)"
    else:
        return f"🟢 Vigente ({dias_restantes} días restantes)"

# --- INTERFAZ GRÁFICA ---
st.title("📦 Diario de Control de Compras")

# Pestañas principales
tab_ordenes, tab_subir, tab_proveedores = st.tabs(["📋 Órdenes de Compra", "📤 Cargar PDF", "🏢 Proveedores"])

# --- PESTAÑA: CARGAR PDF ---
with tab_subir:
    st.subheader("Cargar Orden de Compra desde PDF")
    
    archivo_pdf = st.file_uploader("Selecciona o arrastra el archivo PDF de la OC:", type=["pdf"])
    
    if archivo_pdf is not None:
        with st.spinner("Extrayendo datos del PDF..."):
            datos_oc = extraer_datos_oc(archivo_pdf)

        # --- PROTECCIÓN CONTRA ERRORES DE LECTURA ---
        if datos_oc is None:
            st.warning("⚠️ No se pudieron extraer datos automáticamente de este PDF (puede ser una imagen escaneada). Por favor, completa los campos manualmente.")
            datos_oc = {
                "proveedor": "",
                "tienda_destino": "",
                "fecha_emision": "",
                "monto_total": 0.0,
                "productos": []
            }
        else:
            st.success("¡PDF procesado exitosamente! Verifica la información antes de guardar:")
        
        # Formulario de verificación/modificación
        with st.form(key="form_confirmar_oc"):
            col1, col2 = st.columns(2)
            
            with col1:
                proveedor = st.text_input("Proveedor:", value=datos_oc["proveedor"])
                tienda_destino = st.text_input("Tienda Destino:", value=datos_oc["tienda_destino"])
            
            with col2:
                fecha_emision = st.text_input("Fecha Emisión (YYYY-MM-DD):", value=datos_oc["fecha_emision"] or "")
                monto_total = st.number_input("Monto Total ($):", value=float(datos_oc["monto_total"]), step=0.01)

            st.write("### Productos Detectados")
            if datos_oc["productos"]:
                df_productos = pd.DataFrame(datos_oc["productos"])
                st.dataframe(df_productos, use_container_width=True)
            else:
                st.warning("No se detectaron tablas de productos automáticamente en este PDF.")

            btn_guardar = st.form_submit_button("💾 Guardar Orden en la Base de Datos", type="primary")
            
            if btn_guardar:
                if not proveedor or not tienda_destino:
                    st.error("Por favor completa al menos el Proveedor y la Tienda Destino.")
                else:
                    nueva_orden_id = guardar_orden_completa(
                        proveedor_nombre=proveedor,
                        tienda_destino=tienda_destino,
                        fecha_emision_str=fecha_emision,
                        monto_total=monto_total,
                        lista_productos=datos_oc["productos"]
                    )
                    st.success(f"¡Orden Nº {nueva_orden_id} registrada con éxito!")
                    st.balloons()

# --- PESTAÑA: ÓRDENES DE COMPRA ---
with tab_ordenes:
    df_ordenes = cargar_ordenes()

    # 1. Resumen en Tarjetas (Métricas rápidas)
    if not df_ordenes.empty:
        col1, col2, col3, col4 = st.columns(4)
        total_ordenes = len(df_ordenes)
        enviadas = len(df_ordenes[df_ordenes["Estatus"] == "Enviada"])
        recibidas = len(df_ordenes[df_ordenes["Estatus"] == "Recibido"])
        no_despachadas = len(df_ordenes[df_ordenes["Estatus"] == "No despachado"])
        
        col1.metric("Total Órdenes", total_ordenes)
        col2.metric("🟢 Recibidas", recibidas)
        col3.metric("🔵 Enviadas", enviadas)
        col4.metric("🟠 No Despachadas", no_despachadas)
        
        st.divider()

    # 2. Tabla Principal de Órdenes
    st.subheader("Estado de las Órdenes")
    
    if df_ordenes.empty:
        st.info("Aún no hay órdenes registradas en la base de datos.")
    else:
        df_display = df_ordenes.copy()
        df_display["Días de Crédito / Alerta"] = df_display["Fecha Vencimiento"].apply(calcular_alerta)
        
        # Mostrar tabla interactiva
        st.dataframe(df_display, use_container_width=True)

        st.divider()

        # 3. Formulario para cambiar Estatus
        st.subheader("🔄 Cambiar Estatus de una Orden")
        
        col_form1, col_form2 = st.columns([1, 2])
        
        with col_form1:
            # Crear dict con etiqueta descriptiva para el selector: "Nº 1 | Distribuidora Central ($1250.0)"
            opciones_ordenes = {
                f"Nº {row['Nº Orden']} | {row['Proveedor']} (${row['Monto Total ($)']})": row['Nº Orden']
                for _, row in df_ordenes.iterrows()
            }
            
            orden_seleccionada_label = st.selectbox(
                "Selecciona la Orden a Modificar:",
                options=list(opciones_ordenes.keys())
            )
            
            orden_id_seleccionada = opciones_ordenes[orden_seleccionada_label]
            estatus_actual = df_ordenes[df_ordenes["Nº Orden"] == orden_id_seleccionada]["Estatus"].values[0]

        with col_form2:
            with st.form(key="form_cambiar_estatus"):
                st.write(f"Modificando la **Orden Nº {orden_id_seleccionada}** (Estatus actual: `{estatus_actual}`)")
                
                opciones_estatus = ["Enviada", "Recibido", "No despachado"]
                indice_predeterminado = opciones_estatus.index(estatus_actual) if estatus_actual in opciones_estatus else 0
                
                nuevo_estatus = st.selectbox(
                    "Nuevo Estatus:",
                    options=opciones_estatus,
                    index=indice_predeterminado
                )
                
                btn_actualizar = st.form_submit_button("Actualizar Estatus", type="primary")
                
                if btn_actualizar:
                    actualizar_estatus_orden(orden_id_seleccionada, nuevo_estatus)
                    st.success(f"¡Estatus de la Orden Nº {orden_id_seleccionada} actualizado a **'{nuevo_estatus}'**!")
                    st.rerun()  # Recarga la página para refrescar la tabla al instante

# --- PESTAÑA: PROVEEDORES ---
with tab_proveedores:
    st.subheader("Lista de Proveedores")
    conn = obtener_conexion()
    df_prov = pd.read_sql_query("SELECT id AS 'ID', nombre AS 'Proveedor', dias_credito AS 'Días de Crédito' FROM Proveedores", conn)
    conn.close()
    
    if df_prov.empty:
        st.info("No hay proveedores registrados.")
    else:
        st.dataframe(df_prov, use_container_width=True)