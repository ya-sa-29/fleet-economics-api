from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List

from src.database import get_db
from src.models.user import User
from src.models.vehicle import Vehicle
from src.schemas.vehicle import VehicleCreate, VehicleResponse
from src.api.dependencies import get_current_user
from src.api.dependencies import get_current_user, require_roles
from src.models.user import UserRole

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])

@router.post("/", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    vehicle_in: VehicleCreate,
    db: Session = Depends(get_db),
    # Тільки Адмін та Диспетчер можуть створювати авто
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.DISPATCHER])) 
):
    # Перевіряємо, чи немає вже авто з таким номером (навіть в інших компаніях)
    existing_vehicle = db.query(Vehicle).filter(Vehicle.license_plate == vehicle_in.license_plate).first()
    if existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Автомобіль з таким номерним знаком вже зареєстровано"
        )

    # Створюємо авто, жорстко прив'язуючи його до компанії поточного юзера
    new_vehicle = Vehicle(
        **vehicle_in.model_dump(),
        company_id=current_user.company_id
    )
    db.add(new_vehicle)
    db.commit()
    db.refresh(new_vehicle)
    
    return new_vehicle

@router.get("/", response_model=List[VehicleResponse])
def get_vehicles(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Юзер отримує ТІЛЬКИ автомобілі своєї компанії
    vehicles = db.query(Vehicle).filter(
        Vehicle.company_id == current_user.company_id,
        Vehicle.deleted_at == None
    ).offset(skip).limit(limit).all()
    
    return vehicles

@router.patch("/{vehicle_id}/mileage", response_model=VehicleResponse)
def update_vehicle_mileage(
    vehicle_id: int,
    current_mileage: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Шукаємо авто, перевіряючи, чи належить воно компанії юзера
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.company_id == current_user.company_id,
        Vehicle.deleted_at == None
    ).first()

    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Автомобіль не знайдено"
        )

    # Оновлюємо поле та зберігаємо зміни
    vehicle.current_mileage = current_mileage
    db.commit()
    db.refresh(vehicle)
    
    return vehicle