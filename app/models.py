from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class MovementData(BaseModel):
    movement_id: str
    warehouse_id: str
    timestamp: datetime
    event: Literal['arrival', 'departure']
    product_id: str
    quantity: int


class KafkaMessage(BaseModel):
    id: str
    source: str
    specversion: str
    type: str
    datacontenttype: str
    dataschema: str
    time: int
    subject: str
    destination: str
    data: MovementData


class MovementInfo(BaseModel):
    movement_id: str
    source_warehouse: Optional[str] = None
    destination_warehouse: Optional[str] = None
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    transit_time_seconds: Optional[int] = None
    product_id: str
    quantity: int
    quantity_difference: int = 0


class WarehouseProductInfo(BaseModel):
    warehouse_id: str
    product_id: str
    quantity: int
