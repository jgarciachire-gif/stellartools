import sqlite3

def inicializar_base_de_datos():
    # 1. Conectar a la base de datos (si el archivo no existe, SQLite lo crea automáticamente)
    conexion = sqlite3.connect('compras.db')
    
    # El cursor es la herramienta que usaremos para ejecutar comandos SQL
    cursor = conexion.cursor()

    # 2. Crear tabla de Proveedores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            dias_credito INTEGER DEFAULT 30
        )
    ''')

    # 3. Crear tabla de Órdenes de Compra
    # Esta tabla controlará los estatus y las fechas que necesitas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Ordenes_Compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedor_id INTEGER,
            tienda_destino TEXT NOT NULL,
            fecha_emision DATE,
            fecha_vencimiento DATE,
            monto_total REAL,
            estatus TEXT DEFAULT 'No despachado', -- Estados: Enviada, Recibido, No despachado
            ruta_pdf TEXT, -- Aquí guardaremos el nombre o ubicación del archivo PDF subido
            FOREIGN KEY (proveedor_id) REFERENCES Proveedores(id)
        )
    ''')

    # 4. Crear tabla de Productos de la Orden (Detalles)
    # Aquí se guardarán los códigos, descripciones y cantidades extraídas del PDF
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

    # 5. Guardar los cambios y cerrar la conexión
    conexion.commit()
    conexion.close()
    
    print("¡Base de datos 'compras.db' inicializada con éxito!")

# Esto permite que el script se ejecute si lo llamas directamente desde la consola
if __name__ == '__main__':
    inicializar_base_de_datos()