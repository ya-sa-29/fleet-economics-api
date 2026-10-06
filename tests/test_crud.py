from datetime import datetime, timezone

# --- Допоміжна функція для отримання токена ---
def get_auth_headers(client):
    client.post(
        "/auth/register",
        json={
            "email": "admin@b2bfleet.com",
            "password": "supersecure",
            "company_name": "Global Logistics"
        }
    )
    login_resp = client.post(
        "/auth/login",
        data={
            "username": "admin@b2bfleet.com",
            "password": "supersecure"
        }
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