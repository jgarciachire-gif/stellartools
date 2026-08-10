import pdfplumber
import re

def extraer_datos_oc(pdf_file):
    datos_extraidos = {
        "numero_orden": "",
        "proveedor": "",
        "tienda_destino": "",
        "monto_total": 0.0,
        "fecha_emision": "",
        "fecha_envio": ""
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
                        if abs(r['top'] - w['top']) < 10:
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

    except Exception as e:
        print(f"Error al procesar el PDF: {e}")

    return datos_extraidos