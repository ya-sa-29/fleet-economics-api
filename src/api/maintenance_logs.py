
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from src.database import get_db
from src.models.user import User, UserRole
from src.models.maintenance_log import MaintenanceLog
from src.models.vehicle import Vehicle
from src.models.trip import Trip
from src.schemas.maintenance_log import MaintenanceLogCreate, MaintenanceLogResponse
from src.api.dependencies import get_current_user

router = APIRouter(prefix="/maintenance-logs", tags=["Maintenance Logs"])


@router.post("/", response_model=MaintenanceLogResponse, status_code=status.HTTP_201_CREATED)
def create_maintenance_log(
    log_in: MaintenanceLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == log_in.vehicle_id,
        Vehicle.company_id == current_user.company_id,
        Vehicle.deleted_at == None
    ).first()

    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail="Автомобіль не знайдено у вашому автопарку"
        )

    # DRIVER може створювати записи лише для призначених йому автомобілів
    if current_user.role == UserRole.DRIVER:
        assigned_trip = db.query(Trip).filter(
            Trip.vehicle_id == log_in.vehicle_id,
            Trip.driver_id == current_user.id,
            Trip.company_id == current_user.company_id,
            Trip.deleted_at == None
        ).first()

        if not assigned_trip:
            raise HTTPException(
                status_code=403,
                detail="Ви не маєте права додавати записи для цього автомобіля"
            )

    new_log = MaintenanceLog(
        **log_in.model_dump(),
        company_id=current_user.company_id
    )

    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    return new_log


@router.get("/", response_model=List[MaintenanceLogResponse])
def get_maintenance_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(MaintenanceLog).filter(
        MaintenanceLog.company_id == current_user.company_id
    )

    # DRIVER бачить записи лише для автомобілів, призначених йому через рейси
    if current_user.role == UserRole.DRIVER:
        query = query.join(
            Trip,
            Trip.vehicle_id == MaintenanceLog.vehicle_id
        ).filter(
            Trip.driver_id == current_user.id,
            Trip.company_id == current_user.company_id,
            Trip.deleted_at == None
        ).distinct()

    return query.offset(skip).limit(limit).all()
