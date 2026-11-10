from datetime import datetime, timezone, timedelta

from src.models.user import User, UserRole
from src.models.trip import Trip
from src.models.vehicle import Vehicle
from src.models.location import Location

def get_auth_headers(client, email="test@transauto.com", password="password123"):
    register_resp = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "company_name": "Test Company",
        },
    )
    assert register_resp.status_code in (200, 201), register_resp.text

    login_resp = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )
    assert login_resp.status_code == 200, login_resp.text

    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_driver_sees_only_assigned_vehicles(client, db, test_locations):
    headers = setup_trips(
        client,
        db,
        email="vehicle-driver@transauto.com",
    )

    # Створюємо другий автомобіль, не призначений водієві
    unassigned_vehicle = client.post(
        "/vehicles/",
        json=get_base_vehicle_payload("TRIPTEST002"),
        headers=headers,
    )
    assert unassigned_vehicle.status_code == 201, unassigned_vehicle.text

    driver = db.query(User).filter(
        User.email == "vehicle-driver@transauto.com"
    ).first()

    driver.role = UserRole.DRIVER
    db.commit()

    vehicle = db.query(Vehicle).filter(
        Vehicle.license_plate == "TRIPTEST001"
    ).first()

    origin = db.query(Location).filter(
        Location.slug == "kyiv"
    ).first()

    destination = db.query(Location).filter(
        Location.slug == "cherkasy"
    ).first()

    # Призначаємо перший автомобіль водієві через рейс
    trip = Trip(
        company_id=driver.company_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin_id=origin.id,
        destination_id=destination.id,
        departure_time=datetime.now(timezone.utc),
        arrival_time=datetime.now(timezone.utc) + timedelta(hours=4),
        distance_km=150,
        ticket_price=25000,
        passengers_carried=5,
    )
    db.add(trip)
    db.commit()

    response = client.get("/vehicles/", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == vehicle.id



# --- Базовий payload для створення авто ---
def get_base_vehicle_payload(plate: str):
    return {
        "brand": "Mercedes-Benz",
        "model": "Sprinter",
        "year": 2022,
        "license_plate": plate,
        "fuel_type": "diesel",  # Зміни, якщо в enum інше значення
        "fuel_consumption": 10.5,
        "passenger_capacity": 18,
        "purchase_price": 150000000,  # 1.5 млн грн у копійках
        "purchase_mileage": 50000,
        "expected_life_km": 500000,
        "residual_value": 30000000
    }

# --- Тест 1: Створення та отримання Автомобіля ---
def test_create_and_get_vehicle(client):
    headers = get_auth_headers(client)
    vehicle_data = get_base_vehicle_payload("KA1234XX")
    
    post_resp = client.post("/vehicles/", json=vehicle_data, headers=headers)
    assert post_resp.status_code == 201
    
    get_resp = client.get("/vehicles/", headers=headers)
    assert get_resp.status_code == 200
    assert len(get_resp.json()) >= 1
    assert get_resp.json()[0]["license_plate"] == "KA1234XX"



# --- Тест 2: Створення запису про заправку (Fuel Log) ---
def test_create_fuel_log(client):
    headers = get_auth_headers(client)
    
    vehicle_resp = client.post("/vehicles/", json=get_base_vehicle_payload("AA0001BB"), headers=headers)
    assert vehicle_resp.status_code == 201
    vehicle_id = vehicle_resp.json()["id"]
    
    fuel_log_data = {
        "vehicle_id": vehicle_id,
        "liters": 50.5,
        "price_per_liter": 5450, 
        "total_cost": 275225,
        "odometer": 150000,
        "refueled_at": datetime.now(timezone.utc).isoformat()
    }
    
    log_resp = client.post("/fuel-logs/", json=fuel_log_data, headers=headers)
    assert log_resp.status_code == 201
    assert log_resp.json()["total_cost"] == 275225

# --- Тест 3: Створення журналу ремонтів (Maintenance Log) ---
def test_create_maintenance_log(client):
    headers = get_auth_headers(client)
    
    vehicle_resp = client.post("/vehicles/", json=get_base_vehicle_payload("BC9999AA"), headers=headers)
    assert vehicle_resp.status_code == 201
    vehicle_id = vehicle_resp.json()["id"]
    
    maintenance_data = {
        "vehicle_id": vehicle_id,
        "type": "service",
        "description": "Заміна мастила та фільтрів",
        "cost": 350000,
        "odometer": 155000,
        "performed_at": datetime.now(timezone.utc).isoformat()
    }
    
    maint_resp = client.post("/maintenance-logs/", json=maintenance_data, headers=headers)
    assert maint_resp.status_code == 201
    assert maint_resp.json()["type"] == "service"


# --- Тест 4: Валідація пагінації автомобілів ---
def test_vehicle_pagination_validation(client):
    headers = get_auth_headers(client)

    # Коректні параметри пагінації
    valid_resp = client.get(
        "/vehicles/?skip=0&limit=10",
        headers=headers
    )
    assert valid_resp.status_code == 200

    # skip не може бути від'ємним
    negative_skip_resp = client.get(
        "/vehicles/?skip=-1",
        headers=headers
    )
    assert negative_skip_resp.status_code == 422

    # limit повинен бути не менше 1
    zero_limit_resp = client.get(
        "/vehicles/?limit=0",
        headers=headers
    )
    assert zero_limit_resp.status_code == 422

    # limit не може перевищувати 100
    excessive_limit_resp = client.get(
        "/vehicles/?limit=101",
        headers=headers
    )
    assert excessive_limit_resp.status_code == 422


# --- Тест 5: Валідація пагінації заправок ---
def test_fuel_logs_pagination_validation(client):
    headers = get_auth_headers(client)

    valid_resp = client.get(
        "/fuel-logs/?skip=0&limit=10",
        headers=headers
    )
    assert valid_resp.status_code == 200

    negative_skip_resp = client.get(
        "/fuel-logs/?skip=-1",
        headers=headers
    )
    assert negative_skip_resp.status_code == 422

    zero_limit_resp = client.get(
        "/fuel-logs/?limit=0",
        headers=headers
    )
    assert zero_limit_resp.status_code == 422

    excessive_limit_resp = client.get(
        "/fuel-logs/?limit=101",
        headers=headers
    )
    assert excessive_limit_resp.status_code == 422

def setup_trips(client, db, email):
    register_resp = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "supersecure",
            "company_name": "Global Logistics",
        },
    )
    assert register_resp.status_code in (200, 201), register_resp.text

    login_resp = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "supersecure",
        },
    )
    assert login_resp.status_code == 200, login_resp.text

    headers = {
        "Authorization": f"Bearer {login_resp.json()['access_token']}"
    }

    vehicle_resp = client.post(
        "/vehicles/",
        json=get_base_vehicle_payload("TRIPTEST001"),
        headers=headers,
    )
    assert vehicle_resp.status_code == 201, vehicle_resp.text

    return headers

def test_driver_can_update_assigned_vehicle_mileage(client, db, test_locations):
    headers = setup_trips(
        client,
        db,
        email="mileage-driver@transauto.com",
    )

    driver = db.query(User).filter(
        User.email == "mileage-driver@transauto.com"
    ).first()

    driver.role = UserRole.DRIVER
    db.commit()

    vehicle = db.query(Vehicle).filter(
        Vehicle.license_plate == "TRIPTEST001"
    ).first()

    origin = db.query(Location).filter(
        Location.slug == "kyiv"
    ).first()

    destination = db.query(Location).filter(
        Location.slug == "cherkasy"
    ).first()

    trip = Trip(
        company_id=driver.company_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin_id=origin.id,
        destination_id=destination.id,
        departure_time=datetime.now(timezone.utc),
        arrival_time=datetime.now(timezone.utc) + timedelta(hours=4),
        distance_km=150,
        ticket_price=25000,
        passengers_carried=5,
    )
    db.add(trip)
    db.commit()

    new_mileage = vehicle.current_mileage + 100

    response = client.patch(
        f"/vehicles/{vehicle.id}/mileage",
        headers=headers,
        json={"current_mileage": new_mileage},
    )

    assert response.status_code == 200
    assert response.json()["current_mileage"] == new_mileage


def test_driver_cannot_update_unassigned_vehicle_mileage(client, db):
    headers = setup_trips(
        client,
        db,
        email="unauthorized-driver@transauto.com",
    )

    driver = db.query(User).filter(
        User.email == "unauthorized-driver@transauto.com"
    ).first()

    driver.role = UserRole.DRIVER
    db.commit()

    vehicle = db.query(Vehicle).filter(
        Vehicle.license_plate == "TRIPTEST001"
    ).first()

    response = client.patch(
        f"/vehicles/{vehicle.id}/mileage",
        headers=headers,
        json={"current_mileage": vehicle.current_mileage + 100},
    )

    assert response.status_code == 403


def test_vehicle_mileage_cannot_decrease(client, db):
    headers = setup_trips(
        client,
        db,
        email="mileage-admin@transauto.com",
    )

    vehicle = db.query(Vehicle).filter(
        Vehicle.license_plate == "TRIPTEST001"
    ).first()

    vehicle.current_mileage = 100000
    db.commit()

    response = client.patch(
        f"/vehicles/{vehicle.id}/mileage",
        headers=headers,
        json={"current_mileage": 90000},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Новий пробіг не може бути меншим за поточний"
