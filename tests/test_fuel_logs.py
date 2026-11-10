
from datetime import datetime, timezone, timedelta

from src.models.user import User
from src.models.trip import Trip
from src.models.location import Location


def get_base_vehicle_payload(plate: str):
    return {
        "brand": "Mercedes-Benz",
        "model": "Sprinter",
        "year": 2022,
        "license_plate": plate,
        "fuel_type": "diesel",
        "fuel_consumption": 10.5,
        "passenger_capacity": 18,
        "purchase_price": 150000000,
        "purchase_mileage": 50000,
        "expected_life_km": 500000,
        "residual_value": 30000000,
    }


def login(client, email, password):
    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )
    assert response.status_code == 200, response.text

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def register_and_login(client, email, password="password123"):
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "company_name": "Fuel Test Company",
        },
    )
    assert response.status_code == 201, response.text

    return login(client, email, password)


def create_vehicle(client, headers, plate):
    response = client.post(
        "/vehicles/",
        json=get_base_vehicle_payload(plate),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_fuel_log(client, headers, vehicle_id):
    payload = {
        "vehicle_id": vehicle_id,
        "liters": 50.5,
        "price_per_liter": 5450,
        "total_cost": 275225,
        "odometer": 150000,
        "refueled_at": datetime.now(timezone.utc).isoformat(),
    }

    return client.post(
        "/fuel-logs/",
        json=payload,
        headers=headers,
    )


def create_trip(db, company_id, vehicle_id, driver_id, origin, destination):
    departure_time = datetime.now(timezone.utc) - timedelta(hours=5)

    trip = Trip(
        company_id=company_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        origin_id=origin.id,
        destination_id=destination.id,
        departure_time=departure_time,
        arrival_time=departure_time + timedelta(hours=4),
        distance_km=150,
        ticket_price=25000,
        passengers_carried=5,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def setup_fuel_scenario(client, db, test_locations):
    admin_headers = register_and_login(
        client,
        "fuel-admin@test.com",
    )

    admin = db.query(User).filter(
        User.email == "fuel-admin@test.com"
    ).first()

    assigned_vehicle_id = create_vehicle(
        client, admin_headers, "FUEL001"
    )
    unassigned_vehicle_id = create_vehicle(
        client, admin_headers, "FUEL002"
    )

    # Створюємо водія через API користувачів.
    driver_create = client.post(
        "/users/",
        headers=admin_headers,
        json={
            "email": "fuel-driver@test.com",
            "password": "driverpassword123",
            "role": "driver",
        },
    )
    assert driver_create.status_code in (200, 201), driver_create.text

    # Користувач уже створений, тому лише авторизуємо його.
    driver_headers = login(
        client,
        "fuel-driver@test.com",
        "driverpassword123",
    )

    driver = db.query(User).filter(
        User.email == "fuel-driver@test.com"
    ).first()

    origin = db.query(Location).filter(
        Location.slug == "kyiv"
    ).first()

    destination = db.query(Location).filter(
        Location.slug == "cherkasy"
    ).first()

    own_trip = create_trip(
        db,
        admin.company_id,
        assigned_vehicle_id,
        driver.id,
        origin,
        destination,
    )

    return {
        "admin_headers": admin_headers,
        "driver_headers": driver_headers,
        "admin": admin,
        "driver": driver,
        "assigned_vehicle_id": assigned_vehicle_id,
        "unassigned_vehicle_id": unassigned_vehicle_id,
        "own_trip": own_trip,
    }


def test_driver_can_create_fuel_log_without_trip(
    client, db, test_locations
):
    scenario = setup_fuel_scenario(client, db, test_locations)

    response = create_fuel_log(
        client,
        scenario["driver_headers"],
        scenario["assigned_vehicle_id"],
    )

    assert response.status_code == 201, response.text
    assert "trip_id" not in response.json()


def test_driver_cannot_create_fuel_log_for_unassigned_vehicle(
    client, db, test_locations
):
    scenario = setup_fuel_scenario(client, db, test_locations)

    response = create_fuel_log(
        client,
        scenario["driver_headers"],
        scenario["unassigned_vehicle_id"],
    )

    assert response.status_code == 403



def test_driver_sees_only_fuel_logs_for_assigned_vehicles(
    client, db, test_locations
):
    scenario = setup_fuel_scenario(client, db, test_locations)

    assigned_log = create_fuel_log(
        client,
        scenario["admin_headers"],
        scenario["assigned_vehicle_id"],
    )
    assert assigned_log.status_code == 201, assigned_log.text

    unassigned_log = create_fuel_log(
        client,
        scenario["admin_headers"],
        scenario["unassigned_vehicle_id"],
    )
    assert unassigned_log.status_code == 201, unassigned_log.text

    response = client.get(
        "/fuel-logs/",
        headers=scenario["driver_headers"],
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["vehicle_id"] == scenario["assigned_vehicle_id"]


def test_admin_can_create_fuel_log_for_any_company_vehicle(
    client, db, test_locations
):
    scenario = setup_fuel_scenario(client, db, test_locations)

    response = create_fuel_log(
        client,
        scenario["admin_headers"],
        scenario["unassigned_vehicle_id"],
    )

    assert response.status_code == 201, response.text


def test_dispatcher_can_create_fuel_log_for_any_company_vehicle(
    client, db, test_locations
):
    scenario = setup_fuel_scenario(client, db, test_locations)

    dispatcher_create = client.post(
        "/users/",
        headers=scenario["admin_headers"],
        json={
            "email": "fuel-dispatcher@test.com",
            "password": "dispatcherpassword123",
            "role": "dispatcher",
        },
    )
    assert dispatcher_create.status_code in (200, 201), dispatcher_create.text

    # Диспетчер уже створений через /users/, тому лише авторизуємо його.
    dispatcher_headers = login(
        client,
        "fuel-dispatcher@test.com",
        "dispatcherpassword123",
    )

    response = create_fuel_log(
        client,
        dispatcher_headers,
        scenario["unassigned_vehicle_id"],
    )

    assert response.status_code == 201, response.text


def test_driver_can_see_fuel_logs_created_by_admin(
    client, db, test_locations
):
    scenario = setup_fuel_scenario(client, db, test_locations)

    created_log = create_fuel_log(
        client,
        scenario["admin_headers"],
        scenario["assigned_vehicle_id"],
    )
    assert created_log.status_code == 201, created_log.text

    response = client.get(
        "/fuel-logs/",
        headers=scenario["driver_headers"],
    )

    assert response.status_code == 200
    assert any(
        log["id"] == created_log.json()["id"]
        for log in response.json()
    )
