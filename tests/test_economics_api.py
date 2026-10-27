
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api.auth_utils import get_password_hash
from src.models.location import Location
from src.models.trip import Trip, TripStatus
from src.models.user import User, UserRole


TEST_PASSWORD = "supersecret123"


def setup_economics_trip(
    client: TestClient,
    db: Session,
    email: str = "economics-admin@transauto.com",
) -> dict:
    """Створює компанію, адміністратора, водія, автомобіль і рейс."""

    # Реєструємо адміністратора компанії.
    register_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
            "company_name": "Economics Test Company",
        },
    )
    assert register_response.status_code == 201, register_response.text

    # Авторизуємо адміністратора.
    login_response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": TEST_PASSWORD,
        },
    )
    assert login_response.status_code == 200, login_response.text

    admin_token = login_response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    admin = db.query(User).filter(User.email == email).first()
    assert admin is not None

    # Створюємо водія цієї компанії.
    driver_email = f"driver-{email}"
    driver = User(
        company_id=admin.company_id,
        email=driver_email,
        hashed_password=get_password_hash(TEST_PASSWORD),
        role=UserRole.DRIVER,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)

    # Створюємо автомобіль через API.
    vehicle_response = client.post(
        "/vehicles/",
        headers=admin_headers,
        json={
            "brand": "Mercedes-Benz",
            "model": "Sprinter",
            "year": 2022,
            "license_plate": "ECONTEST001",
            "fuel_type": "petrol",
            "fuel_consumption": 10.5,
            "passenger_capacity": 18,
            "purchase_price": 150000000,
            "purchase_mileage": 0,
            "expected_life_km": 500000,
            "residual_value": 30000000,
        },
    )
    assert vehicle_response.status_code == 201, vehicle_response.text
    vehicle_id = vehicle_response.json()["id"]

    # Створюємо локації.
    origin = Location(name="Kyiv", slug="kyiv")
    destination = Location(name="Cherkasy", slug="cherkasy")
    db.add_all([origin, destination])
    db.flush()

    # Створюємо рейс із відомими параметрами.
    trip = Trip(
        company_id=admin.company_id,
        vehicle_id=vehicle_id,
        driver_id=driver.id,
        origin_id=origin.id,
        destination_id=destination.id,
        departure_time=datetime.now(timezone.utc),
        distance_km=100,
        ticket_price=50000,
        passengers_carried=10,
        status=TripStatus.COMPLETED,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)

    # Авторизуємо водія.
    driver_login = client.post(
        "/auth/login",
        data={
            "username": driver_email,
            "password": TEST_PASSWORD,
        },
    )
    assert driver_login.status_code == 200, driver_login.text

    driver_token = driver_login.json()["access_token"]

    return {
        "trip_id": trip.id,
        "admin_headers": admin_headers,
        "driver_headers": {
            "Authorization": f"Bearer {driver_token}",
        },
    }


def test_profit_per_km_http_success(client: TestClient, db: Session):
    data = setup_economics_trip(client, db)

    response = client.get(
        f"/economics/trip/{data['trip_id']}/profit-per-km",
        headers=data["admin_headers"],
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert result["trip_id"] == data["trip_id"]
    assert result["distance_km"] == 100
    assert result["revenue"] == 5000.0
    assert result["estimated_costs"] == 240.0
    assert result["profit"] == 4760.0
    assert result["profit_per_km"] == 47.6
    assert result["total_cpm"] == 2.4


def test_profit_per_km_http_requires_authentication(
    client: TestClient,
    db: Session,
):
    data = setup_economics_trip(client, db)

    response = client.get(
        f"/economics/trip/{data['trip_id']}/profit-per-km",
    )

    assert response.status_code == 401, response.text


def test_profit_per_km_http_trip_not_found(
    client: TestClient,
    db: Session,
):
    data = setup_economics_trip(client, db)

    response = client.get(
        "/economics/trip/999999/profit-per-km",
        headers=data["admin_headers"],
    )

    assert response.status_code == 404, response.text


def test_profit_per_km_http_driver_can_access_own_trip(
    client: TestClient,
    db: Session,
):
    data = setup_economics_trip(client, db)

    response = client.get(
        f"/economics/trip/{data['trip_id']}/profit-per-km",
        headers=data["driver_headers"],
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert result["trip_id"] == data["trip_id"]
    assert result["profit"] == 4760.0
    assert result["profit_per_km"] == 47.6


def test_profit_per_km_http_driver_cannot_access_other_trip(
    client: TestClient,
    db: Session,
):
    data = setup_economics_trip(client, db)

    # Створюємо другий рейс, призначений іншому водієві.
    original_trip = db.query(Trip).filter(
        Trip.id == data["trip_id"]
    ).first()
    assert original_trip is not None

    other_driver = User(
        company_id=original_trip.company_id,
        email="another-driver@transauto.com",
        hashed_password=get_password_hash(TEST_PASSWORD),
        role=UserRole.DRIVER,
    )
    db.add(other_driver)
    db.flush()

    other_trip = Trip(
        company_id=original_trip.company_id,
        vehicle_id=original_trip.vehicle_id,
        driver_id=other_driver.id,
        origin_id=original_trip.origin_id,
        destination_id=original_trip.destination_id,
        departure_time=datetime.now(timezone.utc),
        distance_km=100,
        ticket_price=50000,
        passengers_carried=10,
        status=TripStatus.COMPLETED,
    )
    db.add(other_trip)
    db.commit()
    db.refresh(other_trip)

    response = client.get(
        f"/economics/trip/{other_trip.id}/profit-per-km",
        headers=data["driver_headers"],
    )

    assert response.status_code == 404, response.text
