from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User
from src.api.dependencies import get_current_user
from src.services.economics import EconomicsService
from src.schemas.economics import VehicleCPMResponse

router = APIRouter(prefix="/economics", tags=["Economics Engine"])

@router.get("/vehicle/{vehicle_id}/cpm", response_model=VehicleCPMResponse)
def get_vehicle_cpm(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Повертає фінансову аналітику по конкретному автомобілю: 
    вартість 1 кілометра пробігу (Cost Per Kilometer).
    """
    return EconomicsService.calculate_vehicle_cpm(db, vehicle_id, current_user.company_id)