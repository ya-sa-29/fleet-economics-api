from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.vehicle import Vehicle
from src.models.location import Location
from src.models.trip import Trip, TripStatus
from src.models.user import User, UserRole
from src.api.auth_utils import get_password_hash


TEST_PASSWORD = "supersecret123"


def get_admin_headers(
    client: TestClient,
    email: str = "admin@transauto.com",
) -> dict:
    """Реєструє тестового адміністратора та повертає заголовки авторизації."""

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
            "company_name": "Trips Test Company",
        },
    )
    assert response.status_code == 201, response.text

    login_response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": TEST_PASSWORD,
        },
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def setup_trips(
    client: TestClient,
    db: Session,
    email: str = "admin@transauto.com",
) -> dict:
    """Створює адміністратора, водія, автомобіль і три тестові рейси."""

    headers = get_admin_headers(client, email=email)

    admin = db.query(User).filter(User.email == email).first()
    assert admin is not None

    driver = User(
        company_id=admin.company_id,
        email=f"driver-{email}",
        hashed_password=get_password_hash("driver-password"),
        role=UserRole.DRIVER,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)

    vehicle_response = client.post(
        "/vehicles/",
        headers=headers,
        json={
            "brand": "Mercedes-Benz",
            "model": "Sprinter",
            "year": 2022,
            "license_plate": "TRIPTEST001",
            "fuel_type": "diesel",
            "fuel_consumption": 10.5,
            "passenger_capacity": 18,
            "purchase_price": 150000000,
            "purchase_mileage": 50000,
            "expected_life_km": 500000,
            "residual_value": 30000000,
        },
    )
    assert vehicle_response.status_code == 201, vehicle_response.text

    vehicle_id = vehicle_response.json()["id"]

    origin = Location(name="Kyiv", slug="kyiv")
    destination = Location(name="Cherkasy", slug="cherkasy")

    db.add_all([origin, destination])
    db.flush()

    now = datetime.now(timezone.utc)

    trip_data = [
        (3, 300, 50000, 10),
        (1, 100, 20000, 2),
        (2, 200, 35000, 5),
    ]

    for day, distance, price, passengers in trip_data:
        departure = now + timedelta(days=day)

        db.add(
            Trip(
                company_id=admin.company_id,
                vehicle_id=vehicle_id,
                driver_id=driver.id,
                origin_id=origin.id,
                destination_id=destination.id,
                departure_time=departure,
                arrival_time=departure + timedelta(hours=4),
                distance_km=distance,
                ticket_price=price,
                passengers_carried=passengers,
            )
        )

    db.commit()

    return headers


def test_sort_trips_by_departure_time(client: TestClient, db: Session):
    headers = setup_trips(client, db)

    response = client.get(
        "/trips/?sort_by=departure_time&sort_order=asc",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    trips = response.json()

    assert len(trips) == 3
    assert [trip["distance_km"] for trip in trips] == [100, 200, 300]

    response = client.get(
        "/trips/?sort_by=departure_time&sort_order=desc",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    trips = response.json()

    assert [trip["distance_km"] for trip in trips] == [300, 200, 100]


def test_sort_trips_by_passengers(client: TestClient, db: Session):
    headers = setup_trips(
        client,
        db,
        email="passengers-admin@transauto.com",
    )

    response = client.get(
        "/trips/?sort_by=passengers_carried&sort_order=asc",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    trips = response.json()
    assert [trip["passengers_carried"] for trip in trips] == [2, 5, 10]


def test_sort_trips_with_equal_passengers(client: TestClient, db: Session):
    headers = setup_trips(
        client,
        db,
        email="equal-passengers-admin@transauto.com",
    )

    trips = db.query(Trip).all()
    assert len(trips) == 3

    original_trip = next(
        trip for trip in trips
        if trip.passengers_carried == 5
    )

    duplicate_trip = Trip(
        company_id=original_trip.company_id,
        vehicle_id=original_trip.vehicle_id,
        driver_id=original_trip.driver_id,
        origin_id=original_trip.origin_id,
        destination_id=original_trip.destination_id,
        departure_time=original_trip.departure_time + timedelta(hours=1),
        arrival_time=original_trip.arrival_time + timedelta(hours=1),
        distance_km=original_trip.distance_km,
        ticket_price=original_trip.ticket_price,
        passengers_carried=5,
    )

    db.add(duplicate_trip)
    db.commit()
    db.refresh(duplicate_trip)

    expected_ids = sorted(
        [original_trip.id, duplicate_trip.id]
    )

    response = client.get(
        "/trips/?sort_by=passengers_carried&sort_order=asc",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert [
        trip["passengers_carried"] for trip in result
    ] == [2, 5, 5, 10]

    actual_ids = [
        trip["id"] for trip in result
        if trip["passengers_carried"] == 5
    ]
    assert actual_ids == expected_ids


def test_trip_pagination(client: TestClient, db: Session):
    headers = setup_trips(
        client,
        db,
        email="pagination-admin@transauto.com",
    )

    first_page = client.get(
        "/trips/?skip=0&limit=2&sort_by=distance_km&sort_order=asc",
        headers=headers,
    )
    second_page = client.get(
        "/trips/?skip=2&limit=2&sort_by=distance_km&sort_order=asc",
        headers=headers,
    )

    assert first_page.status_code == 200, first_page.text
    assert second_page.status_code == 200, second_page.text

    assert [trip["distance_km"] for trip in first_page.json()] == [100, 200]
    assert [trip["distance_km"] for trip in second_page.json()] == [300]


def test_trip_query_validation(client: TestClient, db: Session):
    headers = setup_trips(
        client,
        db,
        email="validation-admin@transauto.com",
    )

    invalid_queries = [
        "?skip=-1",
        "?limit=101",
        "?limit=0",
        "?sort_by=unknown",
        "?sort_order=invalid",
    ]

    for query in invalid_queries:
        response = client.get(
            f"/trips/{query}",
            headers=headers,
        )

        assert response.status_code == 422, (
            f"Query {query} returned {response.status_code}: {response.text}"
        )


def get_trip_payload(db: Session, email: str, **overrides) -> dict:
    driver = db.query(User).filter(
        User.email == f"driver-{email}"
    ).first()

    vehicle = db.query(Vehicle).filter(
        Vehicle.license_plate == "TRIPTEST001"
    ).first()

    origin = db.query(Location).filter(
        Location.slug == "kyiv"
    ).first()

    destination = db.query(Location).filter(
        Location.slug == "cherkasy"
    ).first()

    now = datetime.now(timezone.utc)

    payload = {
        "vehicle_id": vehicle.id,
        "driver_id": driver.id,
        "origin_id": origin.id,
        "destination_id": destination.id,
        "departure_time": now.isoformat(),
        "arrival_time": (now + timedelta(hours=4)).isoformat(),
        "distance_km": 150,
        "ticket_price": 25000,
        "passengers_carried": 5,
    }

    payload.update(overrides)
    return payload


def test_create_trip_success(client: TestClient, db: Session):
    email = "create-trip-admin@transauto.com"
    headers = setup_trips(client, db, email=email)

    payload = get_trip_payload(db, email)

    response = client.post(
        "/trips/",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["vehicle_id"] == payload["vehicle_id"]
    assert data["driver_id"] == payload["driver_id"]
    assert data["distance_km"] == 150
    assert data["ticket_price"] == 25000
    assert data["passengers_carried"] == 5
    assert data["status"] == "in_progress"


def test_create_trip_status_is_not_client_controlled(
    client: TestClient,
    db: Session,
):
    email = "status-control-admin@transauto.com"
    headers = setup_trips(client, db, email=email)

    payload = get_trip_payload(db, email)
    payload["status"] = "completed"

    response = client.post(
        "/trips/",
        headers=headers,
        json=payload,
    )

    # Pydantic за замовчуванням ігнорує зайві поля.
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "in_progress"


def test_create_trip_vehicle_not_found(client: TestClient, db: Session):
    email = "missing-vehicle-admin@transauto.com"
    headers = setup_trips(client, db, email=email)

    payload = get_trip_payload(db, email, vehicle_id=99999)

    response = client.post(
        "/trips/",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Автомобіль не знайдено"


def test_create_trip_exceeds_vehicle_capacity(
    client: TestClient,
    db: Session,
):
    email = "capacity-admin@transauto.com"
    headers = setup_trips(client, db, email=email)

    payload = get_trip_payload(db, email, passengers_carried=19)

    response = client.post(
        "/trips/",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Кількість пасажирів (19) перевищує місткість авто (18)"
    )


def test_create_trip_admin_can_assign_self(
    client: TestClient,
    db: Session,
):
    email = "admin-driver@transauto.com"
    headers = setup_trips(client, db, email=email)

    admin = db.query(User).filter(
        User.email == email
    ).first()

    payload = get_trip_payload(db, email, driver_id=admin.id)

    response = client.post(
        "/trips/",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["driver_id"] == admin.id
    assert data["company_id"] == admin.company_id


def test_create_trip_dispatcher_cannot_assign_self(
    client: TestClient,
    db: Session,
):
    email = "dispatcher-driver@transauto.com"
    headers = setup_trips(client, db, email=email)

    dispatcher = db.query(User).filter(
        User.email == email
    ).first()

    dispatcher.role = UserRole.DISPATCHER
    db.commit()

    payload = get_trip_payload(db, email, driver_id=dispatcher.id)

    response = client.post(
        "/trips/",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Водія не знайдено у вашій компанії"


def create_trip_for_another_driver(db: Session, admin_email: str):
    admin = db.query(User).filter(
        User.email == admin_email
    ).first()

    vehicle = db.query(Vehicle).filter(
        Vehicle.license_plate == "TRIPTEST001"
    ).first()

    origin = db.query(Location).filter(
        Location.slug == "kyiv"
    ).first()

    destination = db.query(Location).filter(
        Location.slug == "cherkasy"
    ).first()

    other_driver = User(
        company_id=admin.company_id,
        email=f"other-driver-{admin_email}",
        hashed_password=get_password_hash("driver-password"),
        role=UserRole.DRIVER,
    )

    db.add(other_driver)
    db.commit()
    db.refresh(other_driver)

    departure = datetime.now(timezone.utc)

    trip = Trip(
        company_id=admin.company_id,
        vehicle_id=vehicle.id,
        driver_id=other_driver.id,
        origin_id=origin.id,
        destination_id=destination.id,
        departure_time=departure,
        arrival_time=departure + timedelta(hours=4),
        distance_km=180,
        ticket_price=30000,
        passengers_carried=8,
    )

    db.add(trip)
    db.commit()
    db.refresh(trip)

    return trip


def test_driver_sees_only_own_trips(client: TestClient, db: Session):
    admin_email = "driver-isolation@transauto.com"
    setup_trips(client, db, email=admin_email)

    driver = db.query(User).filter(
        User.email == f"driver-{admin_email}"
    ).first()

    driver_login = client.post(
        "/auth/login",
        data={
            "username": driver.email,
            "password": "driver-password",
        },
    )
    assert driver_login.status_code == 200, driver_login.text

    driver_headers = {
        "Authorization": f"Bearer {driver_login.json()['access_token']}"
    }

    other_trip = create_trip_for_another_driver(db, admin_email)

    response = client.get(
        "/trips/",
        headers=driver_headers,
    )

    assert response.status_code == 200, response.text

    trips = response.json()

    assert len(trips) == 3
    assert all(trip["driver_id"] == driver.id for trip in trips)
    assert all(trip["id"] != other_trip.id for trip in trips)


def test_admin_sees_all_company_trips(client: TestClient, db: Session):
    admin_email = "admin-all-trips@transauto.com"
    admin_headers = setup_trips(client, db, email=admin_email)

    other_trip = create_trip_for_another_driver(db, admin_email)

    response = client.get(
        "/trips/",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    trips = response.json()

    assert len(trips) == 4
    assert any(trip["id"] == other_trip.id for trip in trips)


def test_dispatcher_sees_all_company_trips(
    client: TestClient,
    db: Session,
):
    admin_email = "dispatcher-all-trips@transauto.com"
    admin_headers = setup_trips(client, db, email=admin_email)

    admin = db.query(User).filter(
        User.email == admin_email
    ).first()

    admin.role = UserRole.DISPATCHER
    db.commit()

    other_trip = create_trip_for_another_driver(db, admin_email)

    response = client.get(
        "/trips/",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    trips = response.json()

    assert len(trips) == 4
    assert any(trip["id"] == other_trip.id for trip in trips)


def create_trip_with_times(
    db: Session,
    admin_email: str,
    departure: datetime,
    arrival: datetime,
) -> Trip:
    admin = db.query(User).filter(
        User.email == admin_email
    ).first()

    vehicle = db.query(Vehicle).filter(
        Vehicle.license_plate == "TRIPTEST001"
    ).first()

    driver = db.query(User).filter(
        User.email == f"driver-{admin_email}"
    ).first()

    origin = db.query(Location).filter(
        Location.slug == "kyiv"
    ).first()

    destination = db.query(Location).filter(
        Location.slug == "cherkasy"
    ).first()

    trip = Trip(
        company_id=admin.company_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin_id=origin.id,
        destination_id=destination.id,
        departure_time=departure,
        arrival_time=arrival,
        distance_km=150,
        ticket_price=25000,
        passengers_carried=5,
    )

    db.add(trip)
    db.commit()
    db.refresh(trip)

    return trip


def test_trip_status_scheduled(client: TestClient, db: Session):
    email = "scheduled-status@transauto.com"
    headers = setup_trips(client, db, email=email)

    trip = create_trip_with_times(
        db,
        email,
        datetime.now(timezone.utc) + timedelta(hours=2),
        datetime.now(timezone.utc) + timedelta(hours=6),
    )

    response = client.get("/trips/", headers=headers)

    assert response.status_code == 200
    result = next(item for item in response.json() if item["id"] == trip.id)
    assert result["status"] == "scheduled"


def test_trip_status_in_progress(client: TestClient, db: Session):
    email = "progress-status@transauto.com"
    headers = setup_trips(client, db, email=email)

    now = datetime.now(timezone.utc)

    trip = create_trip_with_times(
        db,
        email,
        now - timedelta(hours=1),
        now + timedelta(hours=2),
    )

    response = client.get("/trips/", headers=headers)

    assert response.status_code == 200
    result = next(item for item in response.json() if item["id"] == trip.id)
    assert result["status"] == "in_progress"


def test_trip_status_completed(client: TestClient, db: Session):
    email = "completed-status@transauto.com"
    headers = setup_trips(client, db, email=email)

    now = datetime.now(timezone.utc)

    trip = create_trip_with_times(
        db,
        email,
        now - timedelta(hours=5),
        now - timedelta(hours=1),
    )

    response = client.get("/trips/", headers=headers)

    assert response.status_code == 200
    result = next(item for item in response.json() if item["id"] == trip.id)
    assert result["status"] == "completed"


def test_cancel_scheduled_trip(client: TestClient, db: Session):
    email = "cancel-scheduled@transauto.com"
    headers = setup_trips(client, db, email=email)

    now = datetime.now(timezone.utc)

    trip = create_trip_with_times(
        db,
        email,
        now + timedelta(hours=2),
        now + timedelta(hours=6),
    )

    response = client.post(
        f"/trips/{trip.id}/cancel",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"

    db.refresh(trip)
    assert trip.cancelled_at is not None


def test_cannot_cancel_in_progress_trip(client: TestClient, db: Session):
    email = "cancel-progress@transauto.com"
    headers = setup_trips(client, db, email=email)

    now = datetime.now(timezone.utc)

    trip = create_trip_with_times(
        db,
        email,
        now - timedelta(hours=1),
        now + timedelta(hours=2),
    )

    response = client.post(
        f"/trips/{trip.id}/cancel",
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Скасувати можна тільки запланований рейс"
    )


def test_cannot_cancel_completed_trip(client: TestClient, db: Session):
    email = "cancel-completed@transauto.com"
    headers = setup_trips(client, db, email=email)

    now = datetime.now(timezone.utc)

    trip = create_trip_with_times(
        db,
        email,
        now - timedelta(hours=5),
        now - timedelta(hours=1),
    )

    response = client.post(
        f"/trips/{trip.id}/cancel",
        headers=headers,
    )

    assert response.status_code == 400


def test_cannot_cancel_trip_twice(client: TestClient, db: Session):
    email = "cancel-twice@transauto.com"
    headers = setup_trips(client, db, email=email)

    now = datetime.now(timezone.utc)

    trip = create_trip_with_times(
        db,
        email,
        now + timedelta(hours=2),
        now + timedelta(hours=6),
    )

    first_response = client.post(
        f"/trips/{trip.id}/cancel",
        headers=headers,
    )
    assert first_response.status_code == 200

    second_response = client.post(
        f"/trips/{trip.id}/cancel",
        headers=headers,
    )

    assert second_response.status_code == 400


def test_driver_cannot_cancel_trip(client: TestClient, db: Session):
    email = "driver-cancel@transauto.com"
    setup_trips(client, db, email=email)

    driver = db.query(User).filter(
        User.email == f"driver-{email}"
    ).first()

    driver_login = client.post(
        "/auth/login",
        data={
            "username": driver.email,
            "password": "driver-password",
        },
    )
    assert driver_login.status_code == 200, driver_login.text

    driver_headers = {
        "Authorization": f"Bearer {driver_login.json()['access_token']}"
    }

    trip = db.query(Trip).filter(
        Trip.driver_id == driver.id
    ).first()

    response = client.post(
        f"/trips/{trip.id}/cancel",
        headers=driver_headers,
    )

    assert response.status_code == 403
