from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from src.models.company import Company
from src.models.fuel_price import FuelPrice
from src.models.maintenance_log import MaintenanceLog, MaintenanceType
from src.models.vehicle import FuelType, Vehicle
from src.services.economics import EconomicsService
from src.models.trip import Trip, TripStatus

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


def create_trip(
    db,
    company_id,
    vehicle_id,
    driver_id=101,
    distance_km=100,
    ticket_price=50_000,
    passengers_carried=4,
    deleted_at=None,
):
    trip = Trip(
        company_id=company_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        origin_id=1,
        destination_id=2,
        departure_time=datetime(2026, 10, 20, tzinfo=timezone.utc),
        distance_km=distance_km,
        ticket_price=ticket_price,
        passengers_carried=passengers_carried,
        status=TripStatus.COMPLETED,
        deleted_at=deleted_at,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip




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


def test_calculate_vehicle_cpm_returns_404_for_vehicle_from_another_company(db):
    owner = Company(name="Vehicle Owner")
    requester = Company(name="Another Company")
    db.add_all([owner, requester])
    db.commit()
    db.refresh(owner)
    db.refresh(requester)

    vehicle = create_vehicle(
        db,
        owner.id,
        FuelType.DIESEL,
        10,
        "OTHER001",
    )

    with pytest.raises(HTTPException) as exc_info:
        EconomicsService.calculate_vehicle_cpm(
            db,
            vehicle_id=vehicle.id,
            company_id=requester.id,
        )

    assert exc_info.value.status_code == 404


def test_calculate_vehicle_cpm_returns_404_for_deleted_vehicle(db):
    company = Company(name="Deleted Vehicle Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db,
        company.id,
        FuelType.DIESEL,
        10,
        "DELETED001",
    )

    vehicle.deleted_at = datetime.now(timezone.utc)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        EconomicsService.calculate_vehicle_cpm(
            db,
            vehicle_id=vehicle.id,
            company_id=company.id,
        )

    assert exc_info.value.status_code == 404


def test_calculate_vehicle_cpm_without_fuel_price(db):
    company = Company(name="No Fuel Price Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db,
        company.id,
        FuelType.DIESEL,
        10,
        "NOPRICE001",
    )

    result = EconomicsService.calculate_vehicle_cpm(
        db,
        vehicle.id,
        company.id,
    )

    # За поточною логікою відсутня ціна означає нульові витрати на пальне.
    assert result["amortization_cpm"] == 2.4
    assert result["fuel_cpm"] == 0.0
    assert result["maintenance_cpm"] == 0.0
    assert result["total_cpm"] == 2.4
    assert result["market_fuel_price_used"] == 0.0


def test_calculate_vehicle_cpm_with_zero_mileage(db):
    company = Company(name="Zero Mileage Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db,
        company.id,
        FuelType.DIESEL,
        10,
        "ZERO001",
    )
    vehicle.current_mileage = 0
    db.commit()

    db.add(
        MaintenanceLog(
            company_id=company.id,
            vehicle_id=vehicle.id,
            type=MaintenanceType.SERVICE,
            description="Test service",
            cost=500_000,
            odometer=0,
            performed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()

    result = EconomicsService.calculate_vehicle_cpm(
        db,
        vehicle.id,
        company.id,
    )

    # За поточною логікою при нульовому пробігу ділення не виконується.
    assert result["maintenance_cpm"] == 0.0
    assert result["amortization_cpm"] == 2.4
    assert result["fuel_cpm"] == 0.0
    assert result["total_cpm"] == 2.4


def test_calculate_trip_profit_per_km_calculates_financial_values(db):
    company = Company(name="Profit Test Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db, company.id, FuelType.DIESEL, 10, "PROFIT001"
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
            description="Service",
            cost=500_000,
            odometer=50_000,
            performed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()

    trip = create_trip(db, company.id, vehicle.id)

    result = EconomicsService.calculate_trip_profit_per_km(
        db=db,
        trip_id=trip.id,
        company_id=company.id,
    )

    # 50 000 коп. × 4 пасажири = 2 000 грн виручки.
    assert result["revenue"] == 2_000.00

    # 12,45 грн/км × 100 км = 1 245 грн витрат.
    assert result["total_cpm"] == 12.45
    assert result["estimated_costs"] == 1_245.00

    assert result["profit"] == 755.00
    assert result["profit_per_km"] == 7.55
    assert result["distance_km"] == 100


def test_calculate_trip_profit_per_km_supports_a_loss(db):
    company = Company(name="Loss Test Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db, company.id, FuelType.DIESEL, 10, "LOSS001"
    )
    trip = create_trip(
        db,
        company.id,
        vehicle.id,
        distance_km=100,
        ticket_price=1_000,
        passengers_carried=1,
    )

    result = EconomicsService.calculate_trip_profit_per_km(
        db=db,
        trip_id=trip.id,
        company_id=company.id,
    )

    # Без ціни пального й записів ТО CPM становить 2,40 грн/км.
    # Виручка 10 грн, витрати 240 грн, збиток 230 грн.
    assert result["revenue"] == 10.00
    assert result["estimated_costs"] == 240.00
    assert result["profit"] == -230.00
    assert result["profit_per_km"] == -2.30


def test_calculate_trip_profit_per_km_returns_404_for_unknown_trip(db):
    company = Company(name="Unknown Trip Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    with pytest.raises(HTTPException) as exc_info:
        EconomicsService.calculate_trip_profit_per_km(
            db=db,
            trip_id=999_999,
            company_id=company.id,
        )

    assert exc_info.value.status_code == 404


def test_calculate_trip_profit_per_km_returns_404_for_another_company(db):
    owner = Company(name="Trip Owner")
    requester = Company(name="Trip Requester")
    db.add_all([owner, requester])
    db.commit()
    db.refresh(owner)
    db.refresh(requester)

    vehicle = create_vehicle(
        db, owner.id, FuelType.DIESEL, 10, "PRIVATE001"
    )
    trip = create_trip(db, owner.id, vehicle.id)

    with pytest.raises(HTTPException) as exc_info:
        EconomicsService.calculate_trip_profit_per_km(
            db=db,
            trip_id=trip.id,
            company_id=requester.id,
        )

    assert exc_info.value.status_code == 404


def test_calculate_trip_profit_per_km_returns_404_for_deleted_trip(db):
    company = Company(name="Deleted Trip Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db, company.id, FuelType.DIESEL, 10, "TRIPDEL001"
    )
    trip = create_trip(
        db,
        company.id,
        vehicle.id,
        deleted_at=datetime.now(timezone.utc),
    )

    with pytest.raises(HTTPException) as exc_info:
        EconomicsService.calculate_trip_profit_per_km(
            db=db,
            trip_id=trip.id,
            company_id=company.id,
        )

    assert exc_info.value.status_code == 404


def test_calculate_trip_profit_per_km_denies_driver_access_to_another_driver_trip(db):
    company = Company(name="Driver Access Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db, company.id, FuelType.DIESEL, 10, "DRIVER001"
    )
    trip = create_trip(db, company.id, vehicle.id, driver_id=202)

    with pytest.raises(HTTPException) as exc_info:
        EconomicsService.calculate_trip_profit_per_km(
            db=db,
            trip_id=trip.id,
            company_id=company.id,
            driver_id=101,
        )

    assert exc_info.value.status_code == 404


def test_calculate_trip_profit_per_km_allows_driver_to_access_own_trip(db):
    company = Company(name="Own Trip Company")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db, company.id, FuelType.DIESEL, 10, "DRIVEROWN001"
    )
    trip = create_trip(db, company.id, vehicle.id, driver_id=101)

    result = EconomicsService.calculate_trip_profit_per_km(
        db=db,
        trip_id=trip.id,
        company_id=company.id,
        driver_id=101,
    )

    assert result["trip_id"] == trip.id


@pytest.mark.parametrize("distance_km", [0, -1])
def test_calculate_trip_profit_per_km_rejects_invalid_distance(
    db, distance_km
):
    company = Company(name=f"Invalid Distance {distance_km}")
    db.add(company)
    db.commit()
    db.refresh(company)

    vehicle = create_vehicle(
        db, company.id, FuelType.DIESEL, 10, f"DIST{abs(distance_km)}"
    )
    trip = create_trip(
        db,
        company.id,
        vehicle.id,
        distance_km=distance_km,
    )

    with pytest.raises(HTTPException) as exc_info:
        EconomicsService.calculate_trip_profit_per_km(
            db=db,
            trip_id=trip.id,
            company_id=company.id,
        )

    assert exc_info.value.status_code == 400


def test_load_factor_calculation(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.DIESEL,
        consumption=10,
        plate="LF-001",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        passengers_carried=12,
    )

    result = EconomicsService.calculate_trip_load_factor(
        db=db,
        trip_id=trip.id,
        company_id=1,
    )

    assert result["trip_id"] == trip.id
    assert result["vehicle_id"] == vehicle.id
    assert result["passengers_carried"] == 12
    assert result["passenger_capacity"] == 18
    assert result["load_factor"] == 66.67


def test_load_factor_zero_passengers(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.DIESEL,
        consumption=10,
        plate="LF-002",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        passengers_carried=0,
    )

    result = EconomicsService.calculate_trip_load_factor(
        db=db,
        trip_id=trip.id,
        company_id=1,
    )

    assert result["load_factor"] == 0.0


def test_load_factor_over_capacity(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.DIESEL,
        consumption=10,
        plate="LF-003",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        passengers_carried=20,
    )

    result = EconomicsService.calculate_trip_load_factor(
        db=db,
        trip_id=trip.id,
        company_id=1,
    )

    assert result["passenger_capacity"] == 18
    assert result["load_factor"] == 111.11


def test_load_factor_trip_not_found(db):
    with pytest.raises(HTTPException) as exc:
        EconomicsService.calculate_trip_load_factor(
            db=db,
            trip_id=9999,
            company_id=1,
        )

    assert exc.value.status_code == 404


def test_load_factor_foreign_company_trip(db):
    vehicle = create_vehicle(
        db,
        company_id=2,
        fuel_type=FuelType.DIESEL,
        consumption=10,
        plate="LF-004",
    )
    trip = create_trip(
        db,
        company_id=2,
        vehicle_id=vehicle.id,
        passengers_carried=10,
    )

    with pytest.raises(HTTPException) as exc:
        EconomicsService.calculate_trip_load_factor(
            db=db,
            trip_id=trip.id,
            company_id=1,
        )

    assert exc.value.status_code == 404


def test_load_factor_deleted_trip(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.DIESEL,
        consumption=10,
        plate="LF-005",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        passengers_carried=10,
        deleted_at=datetime.now(timezone.utc),
    )

    with pytest.raises(HTTPException) as exc:
        EconomicsService.calculate_trip_load_factor(
            db=db,
            trip_id=trip.id,
            company_id=1,
        )

    assert exc.value.status_code == 404


def test_load_factor_driver_cannot_access_other_driver_trip(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.DIESEL,
        consumption=10,
        plate="LF-006",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        driver_id=202,
        passengers_carried=10,
    )

    with pytest.raises(HTTPException) as exc:
        EconomicsService.calculate_trip_load_factor(
            db=db,
            trip_id=trip.id,
            company_id=1,
            driver_id=101,
        )

    assert exc.value.status_code == 404


def test_load_factor_driver_can_access_own_trip(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.DIESEL,
        consumption=10,
        plate="LF-007",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        driver_id=101,
        passengers_carried=9,
    )

    result = EconomicsService.calculate_trip_load_factor(
        db=db,
        trip_id=trip.id,
        company_id=1,
        driver_id=101,
    )

    assert result["load_factor"] == 50.0

def test_cask_rask_calculation(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.PETROL,
        consumption=0,
        plate="CASK001",
    )
    vehicle.purchase_price = 0
    vehicle.residual_value = 0
    vehicle.expected_life_km = 0
    vehicle.current_mileage = 0
    db.commit()

    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        distance_km=100,
        ticket_price=12_500,
        passengers_carried=12,
    )

    result = EconomicsService.calculate_trip_cask_rask(
        db=db,
        trip_id=trip.id,
        company_id=1,
    )

    # У цьому сценарії витрати нульові, тому CASK = 0.
    # Виручка: 125 грн * 12 пасажирів = 1500 грн.
    # ASK: 18 місць * 100 км = 1800.
    assert result["available_seat_kilometers"] == 1800
    assert result["revenue"] == 1500
    assert result["estimated_costs"] == 0
    assert result["cask"] == 0
    assert result["rask"] == pytest.approx(0.83, abs=0.01)


def test_cask_rask_zero_passengers(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.PETROL,
        consumption=0,
        plate="CASK002",
    )
    vehicle.purchase_price = 0
    vehicle.residual_value = 0
    vehicle.expected_life_km = 0
    vehicle.current_mileage = 0
    db.commit()

    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        distance_km=100,
        ticket_price=12_500,
        passengers_carried=0,
    )

    result = EconomicsService.calculate_trip_cask_rask(
        db=db,
        trip_id=trip.id,
        company_id=1,
    )

    assert result["revenue"] == 0
    assert result["rask"] == 0


def test_cask_rask_trip_not_found(db):
    with pytest.raises(HTTPException) as exc:
        EconomicsService.calculate_trip_cask_rask(
            db=db,
            trip_id=999999,
            company_id=1,
        )

    assert exc.value.status_code == 404


def test_cask_rask_foreign_company_trip(db):
    vehicle = create_vehicle(
        db,
        company_id=2,
        fuel_type=FuelType.PETROL,
        consumption=0,
        plate="CASK003",
    )
    trip = create_trip(
        db,
        company_id=2,
        vehicle_id=vehicle.id,
    )

    with pytest.raises(HTTPException) as exc:
        EconomicsService.calculate_trip_cask_rask(
            db=db,
            trip_id=trip.id,
            company_id=1,
        )

    assert exc.value.status_code == 404


def test_cask_rask_deleted_trip(db):
    from datetime import datetime, timezone

    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.PETROL,
        consumption=0,
        plate="CASK004",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        deleted_at=datetime.now(timezone.utc),
    )

    with pytest.raises(HTTPException) as exc:
        EconomicsService.calculate_trip_cask_rask(
            db=db,
            trip_id=trip.id,
            company_id=1,
        )

    assert exc.value.status_code == 404


def test_cask_rask_driver_cannot_access_other_driver_trip(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.PETROL,
        consumption=0,
        plate="CASK005",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        driver_id=101,
    )

    with pytest.raises(HTTPException) as exc:
        EconomicsService.calculate_trip_cask_rask(
            db=db,
            trip_id=trip.id,
            company_id=1,
            driver_id=202,
        )

    assert exc.value.status_code == 404


def test_cask_rask_invalid_distance(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.PETROL,
        consumption=0,
        plate="CASK006",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        distance_km=0,
    )

    with pytest.raises(HTTPException) as exc:
        EconomicsService.calculate_trip_cask_rask(
            db=db,
            trip_id=trip.id,
            company_id=1,
        )

    assert exc.value.status_code == 400


def test_cask_rask_invalid_capacity(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.PETROL,
        consumption=0,
        plate="CASK007",
    )
    vehicle.passenger_capacity = 0
    db.commit()

    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
    )

    with pytest.raises(HTTPException) as exc:
        EconomicsService.calculate_trip_cask_rask(
            db=db,
            trip_id=trip.id,
            company_id=1,
        )

    assert exc.value.status_code == 400


def test_cask_rask_calculation_with_nonzero_costs(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.PETROL,
        consumption=0,
        plate="CASK001",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        distance_km=100,
        ticket_price=12_500,
        passengers_carried=12,
    )

    result = EconomicsService.calculate_trip_cask_rask(
        db,
        trip_id=trip.id,
        company_id=1,
    )

    # Амортизація: (1 500 000 - 300 000) / 500 000 = 2.4 грн/км.
    # Витрати на 100 км: 2.4 * 100 = 240 грн.
    # ASK: 18 місць * 100 км = 1800.
    assert result["estimated_costs"] == 240.0
    assert result["available_seat_kilometers"] == 1800
    assert result["revenue"] == 1500.0
    assert result["cask"] == 0.13
    assert result["rask"] == 0.83


def test_cask_rask_driver_can_access_own_trip(db):
    vehicle = create_vehicle(
        db,
        company_id=1,
        fuel_type=FuelType.PETROL,
        consumption=0,
        plate="CASK002",
    )
    trip = create_trip(
        db,
        company_id=1,
        vehicle_id=vehicle.id,
        driver_id=101,
        distance_km=100,
        ticket_price=12_500,
        passengers_carried=12,
    )

    result = EconomicsService.calculate_trip_cask_rask(
        db,
        trip_id=trip.id,
        company_id=1,
        driver_id=101,
    )

    assert result["trip_id"] == trip.id
    assert result["vehicle_id"] == vehicle.id
    assert result["cask"] == 0.13
    assert result["rask"] == 0.83
