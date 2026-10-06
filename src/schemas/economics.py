from pydantic import BaseModel
from decimal import Decimal

class VehicleCPMResponse(BaseModel):
    vehicle_id: int
    license_plate: str
    
    amortization_cpm: Decimal  # Амортизація на 1 км (у копійках)
    fuel_cpm: Decimal          # Вартість пального на 1 км (у копійках)
    total_cpm: Decimal         # Загальна базова собівартість 1 км
    maintenance_cpm: float
    
    market_fuel_price_used: int # Яку ринкову ціну ми взяли для розрахунку (копійки)