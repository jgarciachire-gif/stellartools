import pdfplumber
import re

def extraer_datos_oc(pdf_file):
    datos_extraidos = {
        "numero_orden": "",
        "proveedor": "",
        "tienda_destino": "",
        "fecha_emision": "",
        "monto_total": 0.0,
        "productos": []
    }

    try:
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)

        with pdfplumber.open(pdf_file) as pdf:
            page = pdf.pages[0]
            width = page.width
            words = page.extract_words()

            rows = []
            for w in sorted(words, key=lambda x: x['top']):
                placed = False
                for r in rows:
                    if abs(r['top'] - w['top']) < 5:
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

                # Buscar número de orden: Busca específicamente "ORDEN DE COMPRA NO."
                if "ORDEN" in txt_upper or "NO." in txt_upper or "Nº" in txt_upper:
                    # Esta regla captura lo que esté después de estas combinaciones, ignorando espacios
                    m_oc = re.search(r'(?:ORDEN DE COMPRA NO\.?|NO\.|Nº|NRO\.?)[:\s]*([A-Z0-9-]+)', txt_upper)
                    
                    # Nos aseguramos de que no capture palabras sueltas como "DE" o "COMPRA" por error
                    if m_oc and m_oc.group(1) not in ["DE", "COMPRA"]:
                        datos_extraidos["numero_orden"] = m_oc.group(1)

                if "PROVEEDOR:" in txt_upper and idx + 1 < len(lines_data):
                    w_left = [w['text'] for w in lines_data[idx + 1]['words'] if w['x0'] < width * 0.5 and w['text'] != '|']
                    if w_left:
                        datos_extraidos["proveedor"] = " ".join(w_left).strip()

                if ("ENTREGAR A:" in txt_upper or "ENTREGAR A" in txt_upper) and idx + 1 < len(lines_data):
                    w_right = [w['text'] for w in lines_data[idx + 1]['words'] if w['x0'] >= width * 0.4 and w['text'] != '|']
                    if w_right:
                        datos_extraidos["tienda_destino"] = " ".join(w_right).strip()

                if "FECHA DE EMISI" in txt_upper or "EMISION" in txt_upper or "EMISIÓN" in txt_upper:
                    m_f = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', ld['text'])
                    if not m_f and idx + 1 < len(lines_data):
                        m_f = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', lines_data[idx + 1]['text'])
                    if m_f:
                        p = m_f.group(1).split('/')
                        datos_extraidos["fecha_emision"] = f"{p[2]}-{p[1].zfill(2)}-{p[0].zfill(2)}"

                if "TOTAL" in txt_upper and "SUBTOTAL" not in txt_upper:
                    m_tot = re.search(r'([\d.,]{4,})', ld['text'])
                    if not m_tot and idx + 1 < len(lines_data):
                        m_tot = re.search(r'([\d.,]{4,})', lines_data[idx + 1]['text'])
                    if m_tot:
                        try:
                            datos_extraidos["monto_total"] = float(m_tot.group(1).replace(',', ''))
                        except ValueError:
                            pass

            for ld in lines_data:
                txt = ld['text']
                words_in_line = ld['words']
                first_word = words_in_line[0]['text'] if words_in_line else ""

                if re.match(r'^\d{5,8}$', first_word) and not first_word.startswith("0000"):
                    codigo = first_word
                    if '|' in txt:
                        partes = [p.strip() for p in txt.split('|') if p.strip()]
                        if len(partes) >= 6:
                            try:
                                datos_extraidos["productos"].append({
                                    "codigo": codigo,
                                    "descripcion": partes[1],
                                    "cantidad": float(partes[4].replace(',', '')),
                                    "precio_unitario": float(partes[5].replace(',', ''))
                                })
                            except:
                                pass
                    else:
                        num_vals = []
                        desc_words = []
                        for w in words_in_line[1:]:
                            t = w['text'].replace(',', '')
                            try:
                                num_vals.append(float(t))
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
        print(f"Error al procesar el PDF: {e}")

    return datos_extraidos