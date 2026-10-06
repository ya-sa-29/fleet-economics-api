from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.models.vehicle import Vehicle
from src.models.fuel_price import FuelPrice
from src.models.maintenance_log import MaintenanceLog  # Додаємо імпорт моделі ТО

class EconomicsService:
    @staticmethod
    def calculate_vehicle_cpm(db: Session, vehicle_id: int, company_id: int):
        # Шукаємо авто з урахуванням ID компанії для ізоляції даних
        vehicle = db.query(Vehicle).filter(
            Vehicle.id == vehicle_id, 
            Vehicle.company_id == company_id
        ).first()
        
        if not vehicle:
            raise HTTPException(status_code=404, detail="Автомобіль не знайдено або не належить вашій компанії")

        # 1. Амортизація
        amortization_cpm = 0.0
        if vehicle.expected_life_km > 0:
            # Примусово робимо float
            amortization_cpm = float(vehicle.purchase_price - vehicle.residual_value) / vehicle.expected_life_km

        # 2. Пальне
        latest_price = db.query(FuelPrice).filter(FuelPrice.fuel_type == vehicle.fuel_type).order_by(FuelPrice.parsed_at.desc()).first()
        fuel_cpm = 0.0
        if latest_price:
            # Обгортаємо значення з БД у float, щоб позбутися типу Decimal
            fuel_cpm = (float(vehicle.fuel_consumption) / 100) * float(latest_price.price_per_liter)

        # 3. ТО та ремонти
        maintenance_logs = db.query(MaintenanceLog).filter(MaintenanceLog.vehicle_id == vehicle_id).all()
        total_maintenance_cost = sum(log.cost for log in maintenance_logs)
        
        maintenance_cpm = 0.0
        if vehicle.current_mileage > 0:
            # Примусово робимо float
            maintenance_cpm = float(total_maintenance_cost) / vehicle.current_mileage

        # Тепер тут додаються три однакові типи (float), і Python не сваритиметься
        total_cpm = amortization_cpm + fuel_cpm + maintenance_cpm

        return {
            "vehicle_id": vehicle.id,
            "license_plate": vehicle.license_plate,
            "amortization_cpm": round(amortization_cpm, 2),
            "fuel_cpm": round(fuel_cpm, 2),
            "maintenance_cpm": round(maintenance_cpm, 2),
            "total_cpm": round(total_cpm, 2),
            "market_fuel_price_used": latest_price.price_per_liter if latest_price else 0
        }