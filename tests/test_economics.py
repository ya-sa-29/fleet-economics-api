
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

    # (150,000,000 - 30,000,000) / 500,000 = 240
    assert result["amortization_cpm"] == 240.0

    # 10 L / 100 km * 10,000 kopecks = 1,000 kopecks/km
    assert result["fuel_cpm"] == 1_000.0

    # 500,000 / 100,000 km = 5 kopecks/km
    assert result["maintenance_cpm"] == 5.0

    assert result["total_cpm"] == 1_245.0
    assert result["market_fuel_price_used"] == 10_000


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

    # 20 L / 100 km * 8,915 kopecks = 1,783 kopecks/km
    assert result["fuel_cpm"] == 1_783.0
    assert result["market_fuel_price_used"] == 8_915


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
