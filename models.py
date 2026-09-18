from typing import List, Optional  # Tipos usados por las solicitudes API
from pydantic import BaseModel, Field  # Modelos y validaciones

class ProductoModificado(BaseModel):
    codigo: str  # Código del producto
    unidad_manejo: int  # Unidades de empaque o manejo
    precio: float  # Precio unitario ajustado
class CodigosProductosRequest(BaseModel):
    codigos: List[str] = Field(default_factory=list, max_length=1000)  # Máximo 1000 códigos por solicitud


class CodigosVentasRequest(BaseModel):
    codigos: List[str] = Field(default_factory=list, max_length=2000)  # Máximo 2000 códigos por consulta


class AnalisisDetalle(BaseModel):
    sede: str  # Sede donde se guarda el pedido
    codigo: str  # Código del producto
    sugerido: float = 0  # Inventario/empaque sugerido guardado actualmente
    pedido_final: float = 0  # Cantidad final pedida


class GuardarAnalisisRequest(BaseModel):
    proveedor_id: Optional[int] = None  # Proveedor seleccionado
    dias_cobertura: int = Field(default=7, ge=1, le=365)  # Días válidos de cobertura
    detalles: List[AnalisisDetalle] = Field(default_factory=list, max_length=10000)  # Detalles del pedido