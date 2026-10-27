from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User
from src.api.dependencies import get_current_user
from src.services.economics import EconomicsService
from src.schemas.economics import VehicleCPMResponse, TripProfitResponse, TripLoadFactorResponse, TripCaskRaskResponse
from src.models.user import User, UserRole

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

@router.get(
    "/trip/{trip_id}/profit-per-km",
    response_model=TripProfitResponse,
)
def get_trip_profit_per_km(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Повертає оцінку виручки, витрат і прибутку окремого рейсу."""

    driver_id = (
        current_user.id
        if current_user.role == UserRole.DRIVER
        else None
    )

    return EconomicsService.calculate_trip_profit_per_km(
        db=db,
        trip_id=trip_id,
        company_id=current_user.company_id,
        driver_id=driver_id,
    )


@router.get(
    "/trip/{trip_id}/load-factor",
    response_model=TripLoadFactorResponse,
)
def get_trip_load_factor(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    driver_id = (
        current_user.id
        if current_user.role == UserRole.DRIVER
        else None
    )

    return EconomicsService.calculate_trip_load_factor(
        db=db,
        trip_id=trip_id,
        company_id=current_user.company_id,
        driver_id=driver_id,
    )


@router.get(
    "/trip/{trip_id}/cask-rask",
    response_model=TripCaskRaskResponse,
)
def get_trip_cask_rask(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    driver_id = (
        current_user.id
        if current_user.role == UserRole.DRIVER
        else None
    )

    return EconomicsService.calculate_trip_cask_rask(
        db=db,
        trip_id=trip_id,
        company_id=current_user.company_id,
        driver_id=driver_id,
    )
