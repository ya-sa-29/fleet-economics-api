
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime, timezone

from src.models.trip import TripStatus


class TripBase(BaseModel):
    vehicle_id: int
    driver_id: int
    origin_id: int
    destination_id: int
    departure_time: datetime
    arrival_time: datetime
    distance_km: int = Field(gt=0, description="Дистанція у кілометрах")
    ticket_price: int = Field(ge=0, description="Ціна квитка в копійках")
    passengers_carried: int = Field(default=0, ge=0)

    @field_validator('departure_time', 'arrival_time')
    @classmethod
    def ensure_timezone(cls, v):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator('arrival_time')
    @classmethod
    def ensure_arrival_after_departure(cls, v, info):
        departure = info.data.get('departure_time')

        if departure is not None and v <= departure:
            raise ValueError("Час прибуття має бути пізніше часу відправлення")

        return v


class TripCreate(TripBase):
    pass


class TripResponse(TripBase):
    id: int
    company_id: int
    status: TripStatus

    model_config = ConfigDict(from_attributes=True)
