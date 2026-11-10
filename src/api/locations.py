from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from src.database import get_db
from src.models.location import Location
from src.schemas.location import LocationResponse
from src.api.dependencies import get_current_user

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get("/", response_model=List[LocationResponse])
def get_locations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return db.query(Location).order_by(Location.name).all()