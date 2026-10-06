from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime, timezone
from src.models.maintenance_log import MaintenanceType

class MaintenanceLogBase(BaseModel):
    vehicle_id: int
    type: MaintenanceType
    description: str = Field(min_length=3, description="Опис робіт")
    cost: int = Field(ge=0, description="Вартість у копійках")
    odometer: int = Field(gt=0, description="Пробіг під час обслуговування")
    performed_at: datetime

    @field_validator('performed_at')
    def ensure_timezone(cls, v):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

class MaintenanceLogCreate(MaintenanceLogBase):
    pass

class MaintenanceLogResponse(MaintenanceLogBase):
    id: int
    company_id: int

    model_config = ConfigDict(from_attributes=True)