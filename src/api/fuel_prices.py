from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.user import User, UserRole
from src.api.dependencies import require_roles
from src.models.fuel_price import FuelPrice
from src.services.minfin_parser import MinfinParser

router = APIRouter(prefix="/fuel-prices", tags=["Fuel Prices (Market)"])

@router.post("/sync", status_code=status.HTTP_201_CREATED)
def sync_fuel_prices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN]))
):
    # 1. Запускаємо наш парсер
    prices = MinfinParser.fetch_current_prices()
    
    if not prices:
        raise HTTPException(status_code=500, detail="Не вдалося отримати дані з Мінфіну (можливо змінилася верстка)")

    # 2. Зберігаємо отримані ціни в базу даних
    saved_count = 0
    for fuel_type, price in prices.items():
        new_price = FuelPrice(
            fuel_type=fuel_type,
            price_per_liter=price
        )
        db.add(new_price)
        saved_count += 1
        
    db.commit()
    
    return {
        "message": "Ціни успішно синхронізовані", 
        "prices_added": saved_count,
        "data": prices
    }