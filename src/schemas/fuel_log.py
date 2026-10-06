from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

class FuelLogBase(BaseModel):
    vehicle_id: int
    trip_id: Optional[int] = None
    liters: Decimal = Field(gt=0, max_digits=8, decimal_places=2, description="Кількість літрів")
    price_per_liter: int = Field(gt=0, description="Ціна за літр у копійках")
    total_cost: int = Field(gt=0, description="Загальна вартість у копійках")
    odometer: int = Field(gt=0, description="Пробіг на момент заправки")
    refueled_at: datetime

    @field_validator('refueled_at')
    def ensure_timezone(cls, v):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

class FuelLogCreate(FuelLogBase):
    pass

class FuelLogResponse(FuelLogBase):
    id: int
    company_id: int

    model_config = ConfigDict(from_attributes=True)