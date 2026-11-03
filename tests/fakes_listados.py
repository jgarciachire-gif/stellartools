"""Bounded RPC responses for handler/browser tests, using the previous Python semantics.

Actual SQL, paging and RLS are checked separately with transactional fixtures.
"""
import unicodedata
from datetime import datetime, timedelta
from types import SimpleNamespace as NS


def normalizar(value):
    return ''.join(c for c in unicodedata.normalize('NFD', str(value or ''))
                   if unicodedata.category(c) != 'Mn').casefold()


def ordenes_resultado(rows, params, user_id):
    filtered = []
    for row in rows:
        if row.get('usuario_id', user_id) != user_id:
            continue
        supplier = row.get('proveedores') or {}
        received = row.get('fecha_recepcion')
        due = ''
        if received and supplier.get('dias_credito', 30):
            due = (datetime.strptime(received, '%Y-%m-%d') + timedelta(days=supplier.get('dias_credito', 30))).strftime('%d/%m/%Y')
        amount = '{:,.2f}'.format(row.get('monto_total') or 0).replace(',', 'X').replace('.', ',').replace('X', '.')
        text = ' '.join(str(v) for v in (row.get('numero_orden') or '', supplier.get('nombre') or row.get('proveedor') or '',
            row.get('tienda_destino') or '', due, '$' + amount, 'Despacho Recibido' if received else 'Enviada')).lower()
        if all(term.lower() in text for term in params['p_criterios']) and (
            not params['p_fecha'] or params['p_fecha'] in (row.get('fecha_envio'), received)
        ):
            filtered.append(row)
    filtered.sort(key=lambda r: (r.get('fecha_envio') is None, r.get('fecha_envio') or '', r['id']), reverse=True)
    page = min(params['p_pagina'], max(1, (len(filtered) + 19) // 20))
    fields = {'id','numero_orden','proveedor','tienda_destino','fecha_envio','fecha_recepcion','monto_total','estatus','proveedor_id','proveedores'}
    records = [{k:v for k,v in r.items() if k in fields} for r in filtered[(page-1)*20:page*20]]
    return dict(registros=records,total=len(filtered),pagina=page)


def proveedores_resultado(rows, params):
    filtered = []
    for row in rows:
        categories = row.get('categorias') or []
        text = normalizar(' '.join(str(row.get(k) or '') for k in ['codigo','nombre','contacto','telefono','email']) + ' ' +
            (' '.join(map(str,categories)) if isinstance(categories,list) else str(categories)))
        if all(normalizar(term) in text for term in params['p_terminos']):
            filtered.append(row)
    filtered.sort(key=lambda r:(normalizar(r.get(params['p_orden'])),r['id']),reverse=params['p_desc'])
    page = min(params['p_pagina'], max(1,(len(filtered)+19)//20))
    tags = sorted({str(c) for r in rows if isinstance(r.get('categorias'),list) for c in r['categorias']})
    selected = next((r for r in rows if r['id']==params['p_seleccion']),None)
    return dict(registros=filtered[(page-1)*20:page*20],total=len(filtered),pagina=page,etiquetas=tags,seleccion=selected)


class ListadosRPC:
    def __init__(self, rows, user_id='user-1'):
        self.rows, self.user_id, self.rpc_calls = rows, user_id, []

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        async def execute():
            rows = self.rows() if callable(self.rows) else self.rows
            result = ordenes_resultado(rows,params,self.user_id) if name=='st_listar_ordenes' else proveedores_resultado(rows,params)
            return NS(data=[result])
        return NS(execute=execute)
