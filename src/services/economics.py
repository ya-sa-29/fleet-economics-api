
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.vehicle import Vehicle
from src.models.fuel_price import FuelPrice
from src.models.maintenance_log import MaintenanceLog


class EconomicsService:
    @staticmethod
    def _calculate_vehicle_cpm_raw(
        db: Session,
        vehicle_id: int,
        company_id: int,
    ):
        vehicle = (
            db.query(Vehicle)
            .filter(
                Vehicle.id == vehicle_id,
                Vehicle.company_id == company_id,
                Vehicle.deleted_at.is_(None),
            )
            .first()
        )

        if not vehicle:
            raise HTTPException(
                status_code=404,
                detail="Автомобіль не знайдено або не належить вашій компанії",
            )

        # 1. Амортизація: копійки -> гривні, потім гривні/км.
        amortization_cpm = 0.0
        if vehicle.expected_life_km > 0:
            amortization_cpm = (
                float(vehicle.purchase_price - vehicle.residual_value)
                / 100
                / vehicle.expected_life_km
            )

        # 2. Пальне.
        fuel_type_mapping = {
            "petrol": "a-95",
            "diesel": "diesel",
            "gas": "gas",
        }

        fuel_price_type = fuel_type_mapping.get(vehicle.fuel_type.value)
        latest_price = None
        fuel_cpm = 0.0

        if fuel_price_type is not None:
            latest_price = (
                db.query(FuelPrice)
                .filter(FuelPrice.fuel_type == fuel_price_type)
                .order_by(FuelPrice.parsed_at.desc())
                .first()
            )

        if latest_price:
            fuel_cpm = (
                float(vehicle.fuel_consumption)
                / 100
                * (float(latest_price.price_per_liter) / 100)
            )

        # 3. ТО та ремонти: копійки -> гривні.
        maintenance_logs = (
            db.query(MaintenanceLog)
            .filter(
                MaintenanceLog.vehicle_id == vehicle_id,
                MaintenanceLog.company_id == company_id,
            )
            .all()
        )

        total_maintenance_cost = sum(
            log.cost for log in maintenance_logs
        )

        maintenance_cpm = 0.0
        if vehicle.current_mileage > 0:
            maintenance_cpm = (
                float(total_maintenance_cost)
                / 100
                / vehicle.current_mileage
            )

        total_cpm = (
            amortization_cpm
            + fuel_cpm
            + maintenance_cpm
        )

        # Повертаємо точніші проміжні значення для подальших розрахунків.
        return {
            "vehicle_id": vehicle.id,
            "license_plate": vehicle.license_plate,
            "amortization_cpm": amortization_cpm,
            "fuel_cpm": fuel_cpm,
            "maintenance_cpm": maintenance_cpm,
            "total_cpm": total_cpm,
            "market_fuel_price_used": (
                float(latest_price.price_per_liter)/100
                if latest_price
                else 0.0
            ),
        }

    @staticmethod
    def calculate_vehicle_cpm(
        db: Session,
        vehicle_id: int,
        company_id: int,
    ):
        result = EconomicsService._calculate_vehicle_cpm_raw(
            db=db,
            vehicle_id=vehicle_id,
            company_id=company_id,
        )

        # Зберігаємо формат відповіді наявного CPM endpoint.
        return {
            **result,
            "amortization_cpm": round(result["amortization_cpm"], 2),
            "fuel_cpm": round(result["fuel_cpm"], 2),
            "maintenance_cpm": round(result["maintenance_cpm"], 2),
            "total_cpm": round(result["total_cpm"], 2),
            "market_fuel_price_used": round(
                result["market_fuel_price_used"], 2
            ),
        }
