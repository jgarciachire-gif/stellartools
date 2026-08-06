import pdfplumber
import re

def extraer_datos_oc(pdf_file):
    datos_extraidos = {
        "proveedor": "",
        "tienda_destino": "",
        "fecha_emision": "",
        "monto_total": 0.0,
        "productos": []
    }

    try:
        # Reiniciar puntero de lectura para Streamlit
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)

        with pdfplumber.open(pdf_file) as pdf:
            page = pdf.pages[0]
            width = page.width

            # 1. Extraer palabras con sus coordenadas (x, y)
            words = page.extract_words()

            # 2. Reconstruir filas físicas agrupando palabras que comparten la misma altura (top)
            rows = []
            for w in sorted(words, key=lambda x: x['top']):
                placed = False
                for r in rows:
                    if abs(r['top'] - w['top']) < 5:  # Tolerancia de 5px para la misma fila
                        r['words'].append(w)
                        placed = True
                        break
                if not placed:
                    rows.append({'top': w['top'], 'words': [w]})

            # Ordenar filas de arriba a abajo
            rows = sorted(rows, key=lambda r: r['top'])

            # Convertir cada fila en una estructura de texto ordenada de izquierda a derecha
            lines_data = []
            for r in rows:
                sorted_words = sorted(r['words'], key=lambda w: w['x0'])
                line_text = " ".join(w['text'] for w in sorted_words)
                lines_data.append({
                    'top': r['top'],
                    'text': line_text,
                    'words': sorted_words
                })

            # ------------------------------------------------------------------
            # 3. EXTRAER PROVEEDOR, TIENDA, FECHA Y TOTAL
            # ------------------------------------------------------------------
            for idx, ld in enumerate(lines_data):
                txt_upper = ld['text'].upper()

                # Proveedor (lado izquierdo)
                if "PROVEEDOR:" in txt_upper and idx + 1 < len(lines_data):
                    w_left = [w['text'] for w in lines_data[idx + 1]['words'] if w['x0'] < width * 0.5 and w['text'] != '|']
                    if w_left:
                        datos_extraidos["proveedor"] = " ".join(w_left).strip()

                # Tienda Destino (lado derecho)
                if ("ENTREGAR A:" in txt_upper or "ENTREGAR A" in txt_upper) and idx + 1 < len(lines_data):
                    w_right = [w['text'] for w in lines_data[idx + 1]['words'] if w['x0'] >= width * 0.4 and w['text'] != '|']
                    if w_right:
                        datos_extraidos["tienda_destino"] = " ".join(w_right).strip()

                # Fecha de Emisión
                if "FECHA DE EMISI" in txt_upper or "EMISION" in txt_upper or "EMISIÓN" in txt_upper:
                    m_f = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', ld['text'])
                    if not m_f and idx + 1 < len(lines_data):
                        m_f = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', lines_data[idx + 1]['text'])
                    if m_f:
                        p = m_f.group(1).split('/')
                        datos_extraidos["fecha_emision"] = f"{p[2]}-{p[1].zfill(2)}-{p[0].zfill(2)}"

                # Monto Total
                if "TOTAL" in txt_upper and "SUBTOTAL" not in txt_upper:
                    m_tot = re.search(r'([\d.,]{4,})', ld['text'])
                    if not m_tot and idx + 1 < len(lines_data):
                        m_tot = re.search(r'([\d.,]{4,})', lines_data[idx + 1]['text'])
                    if m_tot:
                        try:
                            datos_extraidos["monto_total"] = float(m_tot.group(1).replace(',', ''))
                        except ValueError:
                            pass

            # ------------------------------------------------------------------
            # 4. EXTRAER PRODUCTOS (Líneas Horizontales Reconstruidas)
            # ------------------------------------------------------------------
            for ld in lines_data:
                txt = ld['text']
                words_in_line = ld['words']
                first_word = words_in_line[0]['text'] if words_in_line else ""

                # Identificar filas que inician con un código de producto (ej: 012921, 012923, 015383)
                if re.match(r'^\d{5,8}$', first_word) and not first_word.startswith("0000"):
                    codigo = first_word

                    # Caso A: La línea contiene separadores '|'
                    if '|' in txt:
                        partes = [p.strip() for p in txt.split('|') if p.strip()]
                        if len(partes) >= 6:
                            descripcion = partes[1]
                            try:
                                cantidad = float(partes[4].replace(',', ''))      # Columna UNI.
                                precio = float(partes[5].replace(',', ''))        # Columna COSTO UNI.
                                
                                datos_extraidos["productos"].append({
                                    "codigo": codigo,
                                    "descripcion": descripcion,
                                    "cantidad": cantidad,
                                    "precio_unitario": precio
                                })
                            except (ValueError, IndexError):
                                pass

                    # Caso B: Sin separador '|' (procesamiento por valores numéricos)
                    else:
                        num_vals = []
                        desc_words = []
                        for w in words_in_line[1:]:
                            t = w['text'].replace(',', '')
                            try:
                                val = float(t)
                                num_vals.append(val)
                            except ValueError:
                                if t != '|':
                                    desc_words.append(w['text'])

                        if len(num_vals) >= 3:
                            datos_extraidos["productos"].append({
                                "codigo": codigo,
                                "descripcion": " ".join(desc_words),
                                "cantidad": num_vals[2] if len(num_vals) >= 4 else num_vals[0],
                                "precio_unitario": num_vals[3] if len(num_vals) >= 4 else num_vals[1]
                            })

    except Exception as e:
        print(f"Error al procesar el PDF con coordenadas: {e}")

    return datos_extraidos