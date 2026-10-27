from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.vehicle import Vehicle
from src.models.trip import Trip
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
    
    @staticmethod
    def calculate_trip_profit_per_km(
        db: Session,
        trip_id: int,
        company_id: int,
        driver_id: int | None = None,
    ):
        query = db.query(Trip).filter(
            Trip.id == trip_id,
            Trip.company_id == company_id,
            Trip.deleted_at.is_(None),
        )

        # Водій може переглядати економіку лише власних рейсів.
        if driver_id is not None:
            query = query.filter(Trip.driver_id == driver_id)

        trip = query.first()

        if not trip:
            raise HTTPException(
                status_code=404,
                detail="Рейс не знайдено або немає доступу до нього",
            )

        if trip.distance_km <= 0:
            raise HTTPException(
                status_code=400,
                detail="Відстань рейсу має бути більшою за нуль",
            )

        # Виручка: ціна квитка в копійках -> гривні.
        revenue = (
            trip.ticket_price * trip.passengers_carried / 100
        )

        # Отримуємо точну собівартість кілометра автомобіля.
        cpm = EconomicsService._calculate_vehicle_cpm_raw(
            db=db,
            vehicle_id=trip.vehicle_id,
            company_id=company_id,
        )

        total_cpm = cpm["total_cpm"]

        # Оцінюємо загальні витрати на рейс.
        estimated_costs = total_cpm * trip.distance_km

        # Прибуток рейсу та прибуток на кілометр.
        profit = revenue - estimated_costs
        profit_per_km = profit / trip.distance_km

        return {
            "trip_id": trip.id,
            "vehicle_id": trip.vehicle_id,
            "distance_km": trip.distance_km,
            "revenue": round(revenue, 2),
            "estimated_costs": round(estimated_costs, 2),
            "profit": round(profit, 2),
            "profit_per_km": round(profit_per_km, 2),
            "total_cpm": round(total_cpm, 2),
        }

    

    @staticmethod
    def calculate_trip_load_factor(
        db: Session,
        trip_id: int,
        company_id: int,
        driver_id: int | None = None,
    ):
        query = db.query(Trip).filter(
            Trip.id == trip_id,
            Trip.company_id == company_id,
            Trip.deleted_at.is_(None),
        )

        if driver_id is not None:
            query = query.filter(Trip.driver_id == driver_id)

        trip = query.first()

        if not trip:
            raise HTTPException(
                status_code=404,
                detail="Рейс не знайдено або немає доступу до нього",
            )

        vehicle = db.query(Vehicle).filter(
            Vehicle.id == trip.vehicle_id,
            Vehicle.company_id == company_id,
            Vehicle.deleted_at.is_(None),
        ).first()

        if not vehicle:
            raise HTTPException(
                status_code=404,
                detail="Транспортний засіб не знайдено",
            )

        if vehicle.passenger_capacity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Місткість транспортного засобу має бути більшою за нуль",
            )

        passengers_carried = trip.passengers_carried or 0
        load_factor = (
            passengers_carried / vehicle.passenger_capacity * 100
        )

        return {
            "trip_id": trip.id,
            "vehicle_id": vehicle.id,
            "passengers_carried": passengers_carried,
            "passenger_capacity": vehicle.passenger_capacity,
            "load_factor": round(load_factor, 2),
        }


    @staticmethod
    def calculate_trip_cask_rask(
        db: Session,
        trip_id: int,
        company_id: int,
        driver_id: int | None = None,
    ):
        query = db.query(Trip).filter(
            Trip.id == trip_id,
            Trip.company_id == company_id,
            Trip.deleted_at.is_(None),
        )

        # Водій може переглядати економіку лише власних рейсів.
        if driver_id is not None:
            query = query.filter(Trip.driver_id == driver_id)

        trip = query.first()

        if not trip:
            raise HTTPException(
                status_code=404,
                detail="Рейс не знайдено або немає доступу до нього",
            )

        if trip.distance_km <= 0:
            raise HTTPException(
                status_code=400,
                detail="Відстань рейсу має бути більшою за нуль",
            )

        vehicle = db.query(Vehicle).filter(
            Vehicle.id == trip.vehicle_id,
            Vehicle.company_id == company_id,
            Vehicle.deleted_at.is_(None),
        ).first()

        if not vehicle:
            raise HTTPException(
                status_code=404,
                detail="Транспортний засіб не знайдено",
            )

        if vehicle.passenger_capacity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Місткість транспортного засобу має бути більшою за нуль",
            )

        # Доступні місце-кілометри.
        available_seat_kilometers = (
            vehicle.passenger_capacity * trip.distance_km
        )

        # Виручка: копійки -> гривні.
        revenue = (
            float(trip.ticket_price)
            * (trip.passengers_carried or 0)
            / 100
        )

        # Використовуємо неокруглену собівартість кілометра.
        cpm = EconomicsService._calculate_vehicle_cpm_raw(
            db=db,
            vehicle_id=trip.vehicle_id,
            company_id=company_id,
        )

        total_cpm = cpm["total_cpm"]
        estimated_costs = total_cpm * trip.distance_km

        # Вартість і дохід на одне доступне місце-кілометр.
        cask = estimated_costs / available_seat_kilometers
        rask = revenue / available_seat_kilometers

        return {
            "trip_id": trip.id,
            "vehicle_id": vehicle.id,
            "distance_km": trip.distance_km,
            "passenger_capacity": vehicle.passenger_capacity,
            "available_seat_kilometers": available_seat_kilometers,
            "estimated_costs": round(estimated_costs, 2),
            "revenue": round(revenue, 2),
            "cask": round(cask, 2),
            "rask": round(rask, 2),
        }
