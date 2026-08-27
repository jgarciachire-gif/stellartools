import pdfplumber
import re

def extraer_datos_oc(pdf_file):
    datos_extraidos = {
        "numero_orden": "",
        "proveedor": "",
        "tienda_destino": "",
        "monto_total": 0.0,
        "fecha_emision": "",
        "fecha_envio": "",
        "productos": []
    }

    try:
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)

        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                width = page.width
                words = page.extract_words()

                rows = []
                for w in sorted(words, key=lambda x: x['top']):
                    placed = False
                    for r in rows:
                        if abs(r['top'] - w['top']) < 3:
                            r['words'].append(w)
                            placed = True
                            break
                    if not placed:
                        rows.append({'top': w['top'], 'words': [w]})

                rows = sorted(rows, key=lambda r: r['top'])
                
                lines_data = []
                for r in rows:
                    sorted_words = sorted(r['words'], key=lambda w: w['x0'])
                    line_text = " ".join(w['text'] for w in sorted_words)
                    lines_data.append({'top': r['top'], 'text': line_text, 'words': sorted_words})

                for idx, ld in enumerate(lines_data):
                    txt_upper = ld['text'].upper()

                    # --- 1. NÚMERO DE ORDEN ---
                    if not datos_extraidos["numero_orden"]:
                        if "ORDEN" in txt_upper or "NO." in txt_upper or "Nº" in txt_upper:
                            m_oc = re.search(r'(?:ORDEN DE COMPRA NO\.?|NO\.|Nº|NRO\.?)[:\s]*([A-Z0-9-]+)', txt_upper)
                            if m_oc and m_oc.group(1) not in ["DE", "COMPRA", "NO"]:
                                datos_extraidos["numero_orden"] = m_oc.group(1)
                            elif idx + 1 < len(lines_data):
                                siguiente_texto = lines_data[idx + 1]['text'].replace('|', '').strip()
                                if siguiente_texto.isdigit() and len(siguiente_texto) >= 4:
                                    datos_extraidos["numero_orden"] = siguiente_texto

                    # --- 2. PROVEEDOR ---
                    if not datos_extraidos["proveedor"] and "PROVEEDOR:" in txt_upper and idx + 1 < len(lines_data):
                        w_left = [w['text'] for w in lines_data[idx + 1]['words'] if w['x0'] < width * 0.5 and w['text'] != '|']
                        if w_left:
                            datos_extraidos["proveedor"] = " ".join(w_left).strip()

                    # --- 3. TIENDA DESTINO ---
                    if not datos_extraidos["tienda_destino"] and ("ENTREGAR A:" in txt_upper or "ENTREGAR A" in txt_upper) and idx + 1 < len(lines_data):
                        w_right = [w['text'] for w in lines_data[idx + 1]['words'] if w['x0'] >= width * 0.4 and w['text'] != '|']
                        if w_right:
                            datos_extraidos["tienda_destino"] = " ".join(w_right).strip()

                    # --- 4. FECHA DE EMISIÓN ---
                    if not datos_extraidos["fecha_emision"]:
                        if "FECHA DE EMISI" in txt_upper or "EMISION" in txt_upper or "EMISIÓN" in txt_upper:
                            m_f = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', txt_upper)
                            if not m_f and idx + 1 < len(lines_data):
                                m_f = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', lines_data[idx + 1]['text'])
                            if m_f:
                                p = m_f.group(1).replace('-', '/').split('/')
                                anio = p[2] if len(p[2]) == 4 else f"20{p[2]}"
                                fecha_formateada = f"{anio}-{p[1].zfill(2)}-{p[0].zfill(2)}"
                                datos_extraidos["fecha_emision"] = fecha_formateada
                                datos_extraidos["fecha_envio"] = fecha_formateada

                    # --- 5. MONTO TOTAL ---
                    if "TOTAL" in txt_upper and "SUBTOTAL" not in txt_upper:
                        m_tot = re.search(r'([\d.,]{4,})', txt_upper)
                        if not m_tot and idx + 1 < len(lines_data):
                            m_tot = re.search(r'([\d.,]{4,})', lines_data[idx + 1]['text'])
                        if m_tot:
                            try:
                                datos_extraidos["monto_total"] = float(m_tot.group(1).replace(',', ''))
                            except ValueError:
                                pass
                    productos_capturados = []

                    # --- 6. EXTRAER DETALLE DE PRODUCTOS EN STELLAR BUSINESS (POR COORDENADAS X/Y) ---
        productos_capturados = []

        for page in pdf.pages:
            words = page.extract_words() # Extrae cada palabra individual con sus coordenadas x0, top, bottom
            width = page.width # Ancho total de la página para delimitar columnas

            # 1. Captura los códigos de producto de 6 dígitos
            codigos_words = [
                w for w in words 
                if re.match(r'^\d{6}$', w['text']) and w['text'] != "000000"
            ]

            # 2. Recorre cada código e identifica las columnas numéricas de su fila
            for cod_w in codigos_words:
                # Filtra valores numéricos en la misma fila (tolerancia vertical 8px) a la derecha del código
                candidatos = [
                    w for w in words 
                    if abs(w['top'] - cod_w['top']) < 8 
                    and w['x0'] > cod_w['x0'] 
                    and re.match(r'^\d+(?:\.\d+)?$', w['text'].replace(',', ''))
                ]
                
                # Ordena las columnas numéricas de izquierda a derecha (PRE -> EMP -> UNI -> COSTO -> SUBTOTAL)
                candidatos_ordenados = sorted(candidatos, key=lambda w: w['x0'])
                
                # Selecciona la 3ª columna numérica (índice 2) que corresponde a 'UNI'
                cant_w = candidatos_ordenados[2] if len(candidatos_ordenados) >= 3 else None
                
                if cant_w:
                    try:
                        # Extrae y convierte el valor de la cantidad
                        cant_val = float(cant_w['text'].replace(',', ''))
                        if cant_val > 0:
                            productos_capturados.append({
                                "codigo": cod_w['text'],
                                "codigo_producto": cod_w['text'],
                                "producto_id": cod_w['text'],
                                "cantidad": cant_val
                            })
                    except ValueError:
                        pass

        datos_extraidos["productos"] = productos_capturados

        # Log de verificación en la terminal de VS Code
        print(f"=== PRODUCTOS DETECTADOS EN STELLAR: {len(datos_extraidos['productos'])} ===")
        print(datos_extraidos["productos"])
        print("==================================================")
    except Exception as e:
            # Imprime el error en la consola de VS Code para depuración sin detener el servidor
        print(f"Error crítico al procesar el PDF: {str(e)}")           

    return datos_extraidos