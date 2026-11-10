
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.company import Company
from src.models.user import User, UserRole
from src.models.vehicle import Vehicle, FuelType
from src.models.location import Location
from src.models.trip import Trip
from src.models.fuel_log import FuelLog
from src.models.maintenance_log import MaintenanceLog, MaintenanceType


def create_company(db, name):
    company = Company(name=name)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def create_user(db, company_id, email):
    user = User(
        company_id=company_id,
        email=email,
        hashed_password="test-hash",
        role=UserRole.DRIVER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_vehicle(db, company_id, plate):
    vehicle = Vehicle(
        company_id=company_id,
        brand="Mercedes-Benz",
        model="Sprinter",
        year=2022,
        license_plate=plate,
        current_mileage=100_000,
        fuel_type=FuelType.DIESEL,
        fuel_consumption=12.5,
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


def create_locations(db):
    origin = Location(name="Київ", slug="kyiv")
    destination = Location(name="Черкаси", slug="cherkasy")

    db.add_all([origin, destination])
    db.commit()

    return origin, destination


def test_sqlite_foreign_keys_are_enabled(db):
    result = db.connection().exec_driver_sql(
        "PRAGMA foreign_keys"
    ).scalar()

    assert result == 1


def test_trip_rejects_vehicle_from_another_company(db):
    company_a = create_company(db, "Company A")
    company_b = create_company(db, "Company B")

    vehicle_b = create_vehicle(db, company_b.id, "AA0001AA")
    driver_a = create_user(db, company_a.id, "driver_a@example.com")
    origin, destination = create_locations(db)

    departure = datetime.now(timezone.utc) + timedelta(days=1)

    trip = Trip(
        company_id=company_a.id,
        vehicle_id=vehicle_b.id,
        driver_id=driver_a.id,
        origin_id=origin.id,
        destination_id=destination.id,
        departure_time=departure,
        arrival_time=departure + timedelta(hours=4),
        distance_km=200,
        ticket_price=50_000,
        passengers_carried=10,
    )

    db.add(trip)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_trip_rejects_driver_from_another_company(db):
    company_a = create_company(db, "Company A")
    company_b = create_company(db, "Company B")

    vehicle_a = create_vehicle(db, company_a.id, "AA0002AA")
    driver_b = create_user(db, company_b.id, "driver_b@example.com")
    origin, destination = create_locations(db)

    departure = datetime.now(timezone.utc) + timedelta(days=1)

    trip = Trip(
        company_id=company_a.id,
        vehicle_id=vehicle_a.id,
        driver_id=driver_b.id,
        origin_id=origin.id,
        destination_id=destination.id,
        departure_time=departure,
        arrival_time=departure + timedelta(hours=4),
        distance_km=200,
        ticket_price=50_000,
        passengers_carried=10,
    )

    db.add(trip)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_fuel_log_rejects_vehicle_from_another_company(db):
    company_a = create_company(db, "Company A")
    company_b = create_company(db, "Company B")

    vehicle_b = create_vehicle(db, company_b.id, "AA0003AA")

    fuel_log = FuelLog(
        company_id=company_a.id,
        vehicle_id=vehicle_b.id,
        liters=50,
        price_per_liter=6000,
        total_cost=300_000,
        odometer=100_500,
        refueled_at=datetime.now(timezone.utc),
    )

    db.add(fuel_log)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_maintenance_log_rejects_vehicle_from_another_company(db):
    company_a = create_company(db, "Company A")
    company_b = create_company(db, "Company B")

    vehicle_b = create_vehicle(db, company_b.id, "AA0004AA")

    maintenance_log = MaintenanceLog(
        company_id=company_a.id,
        vehicle_id=vehicle_b.id,
        type=MaintenanceType.REPAIR,
        description="Test repair",
        cost=50_000,
        odometer=100_500,
        performed_at=datetime.now(timezone.utc),
    )

    db.add(maintenance_log)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()
