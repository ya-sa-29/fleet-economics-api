from datetime import datetime, timezone

# --- Допоміжна функція для отримання токена ---

from src.models.user import User
from src.api.auth_utils import verify_password


def get_auth_headers(client):
    register_resp = client.post(
        "/auth/register",
        json={
            "email": "admin@b2bfleet.com",
            "password": "supersecure",
            "company_name": "Global Logistics",
        },
    )
    assert register_resp.status_code in (200, 201), (
        f"Registration failed: {register_resp.status_code}, "
        f"{register_resp.text}"
    )

    login_resp = client.post(
        "/auth/login",
        data={
            "username": "admin@b2bfleet.com",
            "password": "supersecure",
        },
    )
    assert login_resp.status_code == 200, (
        f"Login failed: {login_resp.status_code}, "
        f"{login_resp.text}"
    )

    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}



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
