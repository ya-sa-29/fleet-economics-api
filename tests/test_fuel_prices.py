from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.api.auth_utils import get_password_hash
from src.models.user import UserRole
from src.models.user import User

TEST_PASSWORD = "supersecret123"


def get_admin_headers(
    client: TestClient,
    email: str = "admin@fuelprices.com",
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
            "company_name": "Fuel Prices Test Company",
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

from unittest.mock import patch
from src.models.fuel_price import FuelPrice


@patch("src.api.fuel_prices.MinfinParser.fetch_current_prices")
def test_sync_fuel_prices_success(mock_fetch, client: TestClient, db: Session):
    mock_fetch.return_value = {
        "a-95": 5679,
        "diesel": 5499,
        "gas": 3450,
    }

    headers = get_admin_headers(client)

    response = client.post(
        "/fuel-prices/sync",
        headers=headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["prices_added"] == 3
    assert data["data"] == {
        "a-95": 5679,
        "diesel": 5499,
        "gas": 3450,
    }

    saved_prices = db.query(FuelPrice).all()

    assert len(saved_prices) == 3

    saved_prices_by_type = {
        price.fuel_type: price.price_per_liter
        for price in saved_prices
    }

    assert saved_prices_by_type == {
        "a-95": 5679,
        "diesel": 5499,
        "gas": 3450,
    }

    mock_fetch.assert_called_once()

@patch("src.api.fuel_prices.MinfinParser.fetch_current_prices")
def test_sync_fuel_prices_no_data(mock_fetch, client: TestClient, db: Session):
    mock_fetch.return_value = {}

    headers = get_admin_headers(
        client,
        email="empty-fuel-prices@transauto.com",
    )

    response = client.post(
        "/fuel-prices/sync",
        headers=headers,
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Не вдалося отримати дані з Мінфіну (можливо змінилася верстка)"
    )

    assert db.query(FuelPrice).count() == 0

    mock_fetch.assert_called_once()

def test_sync_fuel_prices_unauthorized(client: TestClient):
    response = client.post("/fuel-prices/sync")

    assert response.status_code == 401

def test_sync_fuel_prices_forbidden(client: TestClient, db: Session):
    headers = get_admin_headers(client)

    admin = db.query(User).filter(
        User.email == "admin@fuelprices.com"
    ).first()

    driver = User(
        company_id=admin.company_id,
        email="driver@fuelprices.com",
        hashed_password=get_password_hash("driver-password"),
        role=UserRole.DRIVER,
    )

    db.add(driver)
    db.commit()

    login_response = client.post(
        "/auth/login",
        data={
            "username": "driver@fuelprices.com",
            "password": "driver-password",
        },
    )

    assert login_response.status_code == 200

    driver_token = login_response.json()["access_token"]
    driver_headers = {
        "Authorization": f"Bearer {driver_token}"
    }

    response = client.post(
        "/fuel-prices/sync",
        headers=driver_headers,
    )

    assert response.status_code == 403

def test_sync_fuel_prices_dispatcher_forbidden(
    client: TestClient,
    db: Session,
):
    headers = get_admin_headers(client)

    admin = db.query(User).filter(
        User.email == "admin@fuelprices.com"
    ).first()

    dispatcher = User(
        company_id=admin.company_id,
        email="dispatcher@fuelprices.com",
        hashed_password=get_password_hash("dispatcher-password"),
        role=UserRole.DISPATCHER,
    )

    db.add(dispatcher)
    db.commit()

    login_response = client.post(
        "/auth/login",
        data={
            "username": "dispatcher@fuelprices.com",
            "password": "dispatcher-password",
        },
    )

    assert login_response.status_code == 200

    dispatcher_token = login_response.json()["access_token"]
    dispatcher_headers = {
        "Authorization": f"Bearer {dispatcher_token}"
    }

    response = client.post(
        "/fuel-prices/sync",
        headers=dispatcher_headers,
    )

    assert response.status_code == 403