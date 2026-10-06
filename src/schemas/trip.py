from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime, timezone
from src.models.trip import TripStatus

class TripBase(BaseModel):
    vehicle_id: int
    driver_id: int
    origin_id: int
    destination_id: int
    departure_time: datetime
    distance_km: int = Field(gt=0, description="Дистанція у кілометрах")
    ticket_price: int = Field(ge=0, description="Ціна квитка в копійках")
    passengers_carried: int = Field(default=0, ge=0)
    status: TripStatus = TripStatus.SCHEDULED

    # Переконуємося, що час передається з урахуванням часового поясу (UTC)
    @field_validator('departure_time')
    def ensure_timezone(cls, v):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

class TripCreate(TripBase):
    pass

class TripResponse(TripBase):
    id: int
    company_id: int

    model_config = ConfigDict(from_attributes=True)