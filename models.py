from pydantic import BaseModel  # Clase base para definición de esquemas de datos

class ProductoModificado(BaseModel):
    codigo: str  # Código del producto
    unidad_manejo: int  # Unidades de empaque o manejo
    precio: float  # Precio unitario ajustado