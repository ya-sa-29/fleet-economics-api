
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from src.models.company import Company
from src.models.fuel_price import FuelPrice
from src.models.maintenance_log import MaintenanceLog, MaintenanceType
from src.models.vehicle import FuelType, Vehicle
from src.services.economics import EconomicsService


def create_vehicle(db, company_id, fuel_type, consumption, plate):
    vehicle = Vehicle(
        company_id=company_id,
        brand="Mercedes-Benz",
        model="Sprinter",
        year=2022,
        license_plate=plate,
        current_mileage=100_000,
        fuel_type=fuel_type,
        fuel_consumption=Decimal(str(consumption)),
        passenger_capacity=18,
        purchase_price=150_000_000,
        purchase_mileage=0,
        expected_life_km=500_000,
        residual_value=30_000_000,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle



def test_calculate_vehicle_cpm_for_diesel(db):
    company = Company(name="Test Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db,
        company.id,
        FuelType.DIESEL,
        10,
        "TEST001",
    )

    db.add(
        FuelPrice(
            fuel_type="diesel",
            price_per_liter=10_000,
            parsed_at=date(2026, 10, 6),
            source="test",
        )
    )

    db.add(
        MaintenanceLog(
            company_id=company.id,
            vehicle_id=vehicle.id,
            type=MaintenanceType.SERVICE,
            description="Oil and filters",
            cost=500_000,
            odometer=50_000,
            performed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()

    result = EconomicsService.calculate_vehicle_cpm(
        db,
        vehicle.id,
        company.id,
    )

    # Амортизація: (1,500,000 - 300,000) / 500,000 = 2.4 грн/км
    assert result["amortization_cpm"] == 2.4

    # Пальне: 10 л/100 км * 100 грн/л = 10 грн/км
    assert result["fuel_cpm"] == 10.0

    # ТО: 5,000 грн / 100,000 км = 0.05 грн/км
    assert result["maintenance_cpm"] == 0.05

    # Загальна собівартість: 2.4 + 10 + 0.05 = 12.45 грн/км
    assert result["total_cpm"] == 12.45

    # Ринкова ціна пального повертається у гривнях за літр
    assert result["market_fuel_price_used"] == 100.0


def test_calculate_vehicle_cpm_for_petrol_a95(db):
    company = Company(name="Petrol Test Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db,
        company.id,
        FuelType.PETROL,
        20,
        "TEST002",
    )

    db.add(
        FuelPrice(
            fuel_type="a-95",
            price_per_liter=8_915,
            parsed_at=date(2026, 10, 6),
            source="test",
        )
    )
    db.commit()

    result = EconomicsService.calculate_vehicle_cpm(
        db,
        vehicle.id,
        company.id,
    )

    # Пальне: 20 л/100 км * 89.15 грн/л = 17.83 грн/км
    assert result["fuel_cpm"] == 17.83

    # 8,915 копійок = 89.15 гривні за літр
    assert result["market_fuel_price_used"] == 89.15



def test_calculate_vehicle_cpm_returns_404_for_unknown_vehicle(db):
    company = Company(name="Another Test Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    with pytest.raises(HTTPException) as exc_info:
        EconomicsService.calculate_vehicle_cpm(
            db,
            vehicle_id=999_999,
            company_id=company.id,
        )

    assert exc_info.value.status_code == 404
