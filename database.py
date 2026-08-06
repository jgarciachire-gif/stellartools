import sqlite3

def inicializar_base_de_datos():
    conexion = sqlite3.connect('compras.db')
    cursor = conexion.cursor()

    # Se añade "dias_despacho" a la tabla
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            dias_credito INTEGER DEFAULT 30,
            dias_despacho INTEGER DEFAULT 3
        )
    ''')

    # Se añade "fecha_envio" a la tabla
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Ordenes_Compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedor_id INTEGER,
            tienda_destino TEXT NOT NULL,
            fecha_emision DATE,
            fecha_envio DATE,
            fecha_vencimiento DATE,
            monto_total REAL,
            estatus TEXT DEFAULT 'No despachado',
            ruta_pdf TEXT,
            FOREIGN KEY (proveedor_id) REFERENCES Proveedores(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Detalles_Productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orden_id INTEGER,
            codigo TEXT,
            descripcion TEXT,
            cantidad REAL,
            precio_unitario REAL,
            FOREIGN KEY (orden_id) REFERENCES Ordenes_Compra(id)
        )
    ''')

    conexion.commit()
    conexion.close()
    print("¡Base de datos 'compras.db' inicializada con éxito con las nuevas columnas!")

if __name__ == '__main__':
    inicializar_base_de_datos()