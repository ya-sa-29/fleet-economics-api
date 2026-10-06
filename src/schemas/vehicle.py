from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from src.models.vehicle import FuelType

class VehicleBase(BaseModel):
    brand: str
    model: str
    year: int = Field(ge=1990, le=2100)
    license_plate: str
    fuel_type: FuelType
    fuel_consumption: Decimal = Field(gt=0, max_digits=5, decimal_places=2)
    passenger_capacity: int = Field(gt=0)
    
    # Фінанси у копійках
    purchase_price: int = Field(gt=0, description="Ціна в копійках")
    purchase_mileage: int = Field(default=0, ge=0)
    expected_life_km: int = Field(gt=0)
    residual_value: int = Field(default=0, ge=0)

class VehicleCreate(VehicleBase):
    pass

class VehicleResponse(VehicleBase):
    id: int
    company_id: int
    current_mileage: int

    model_config = ConfigDict(from_attributes=True)