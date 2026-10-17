
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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

    # Створюємо водія тієї самої компанії.
    driver = User(
        company_id=admin.company_id,
        email=f"driver-{email}",
        hashed_password=get_password_hash("driver-password"),
        role=UserRole.DRIVER,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)

    # Створюємо автомобіль через API.
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

    # Створюємо початкову та кінцеву локації.
    origin = Location(name="Kyiv", slug="kyiv")
    destination = Location(name="Cherkasy", slug="cherkasy")

    db.add_all([origin, destination])
    db.flush()

    now = datetime.now(timezone.utc)

    # Рейси з різними параметрами для перевірки сортування.
    trip_data = [
        (3, 300, 50000, 10),
        (1, 100, 20000, 2),
        (2, 200, 35000, 5),
    ]

    for day, distance, price, passengers in trip_data:
        db.add(
            Trip(
                company_id=admin.company_id,
                vehicle_id=vehicle_id,
                driver_id=driver.id,
                origin_id=origin.id,
                destination_id=destination.id,
                departure_time=now + timedelta(days=day),
                distance_km=distance,
                ticket_price=price,
                passengers_carried=passengers,
                status=TripStatus.SCHEDULED,
            )
        )

    db.commit()

    return headers


def test_sort_trips_by_departure_time(client: TestClient, db: Session):
    headers = setup_trips(client, db)

    # Від найранішого рейсу до найпізнішого.
    response = client.get(
        "/trips/?sort_by=departure_time&sort_order=asc",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    trips = response.json()

    assert len(trips) == 3
    assert [trip["distance_km"] for trip in trips] == [100, 200, 300]

    # У зворотному порядку.
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

    # Беремо рейси, які вже створив setup_trips.
    trips = db.query(Trip).all()
    assert len(trips) == 3

    # Знаходимо рейс, у якого 5 пасажирів.
    original_trip = next(
        trip for trip in trips
        if trip.passengers_carried == 5
    )

    # Створюємо ще один рейс із такою самою кількістю пасажирів.
    duplicate_trip = Trip(
        company_id=original_trip.company_id,
        vehicle_id=original_trip.vehicle_id,
        driver_id=original_trip.driver_id,
        origin_id=original_trip.origin_id,
        destination_id=original_trip.destination_id,
        departure_time=original_trip.departure_time + timedelta(hours=1),
        distance_km=original_trip.distance_km,
        ticket_price=original_trip.ticket_price,
        passengers_carried=5,
        status=TripStatus.SCHEDULED,
    )
    db.add(duplicate_trip)
    db.commit()
    db.refresh(duplicate_trip)

    # Очікуваний порядок ID для рейсів із 5 пасажирами.
    expected_ids = sorted(
        [original_trip.id, duplicate_trip.id]
    )

    response = client.get(
        "/trips/?sort_by=passengers_carried&sort_order=asc",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    result = response.json()

    # Кількість пасажирів має йти за зростанням.
    assert [
        trip["passengers_carried"] for trip in result
    ] == [2, 5, 5, 10]

    # Рейси з однаковою кількістю пасажирів мають іти за ID.
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
