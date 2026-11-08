from datetime import datetime, timezone

from src.models.user import User, UserRole
from src.api.auth_utils import get_password_hash
from jose import jwt
from src.config import settings

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Fleet Economics API is running"}

def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "test@transauto.com",
            "password": "securepassword",
            "company_name": "Test Company"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@transauto.com"
    assert "id" in data
    assert "company_id" in data

def test_login_user(client):
    # Спочатку реєструємо
    register_response = client.post(
        "/auth/register",
        json={
            "email": "test@transauto.com",
            "password": "securepassword",
            "company_name": "Test Company"
        }
    )
    assert register_response.status_code == 201
    
    # Тепер логінимось
    login_response = client.post(
        "/auth/login",
        data={
            "username": "test@transauto.com",
            "password": "securepassword"
        }
    )
    assert login_response.status_code == 200
    data = login_response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_success(client, db):
    user = User(
        email="active@example.com",
        hashed_password=get_password_hash("password123"),
        company_id=1,
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()

    response = client.post(
        "/auth/login",
        data={
            "username": "active@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_deactivated_user(client, db):
    user = User(
        email="inactive@example.com",
        hashed_password=get_password_hash("password123"),
        company_id=1,
        role=UserRole.ADMIN,
        deleted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()

    response = client.post(
        "/auth/login",
        data={
            "username": "inactive@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Користувач деактивований"
    assert "access_token" not in response.json()

def test_deactivated_user_cannot_use_old_token(client, db):
    user = User(
        email="old-token@example.com",
        hashed_password=get_password_hash("password123"),
        company_id=1,
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()

    login_response = client.post(
        "/auth/login",
        data={
            "username": "old-token@example.com",
            "password": "password123",
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user.deleted_at = datetime.now(timezone.utc)
    db.commit()

    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Користувач деактивований"

def test_get_my_profile(client, db):
    user = User(
        email="profile@example.com",
        hashed_password=get_password_hash("password123"),
        company_id=1,
        role=UserRole.DRIVER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    login_response = client.post(
        "/auth/login",
        data={
            "username": "profile@example.com",
            "password": "password123",
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == user.id
    assert data["email"] == "profile@example.com"
    assert data["company_id"] == 1
    assert data["role"] == "driver"
    assert "hashed_password" not in data

def test_get_my_profile_with_invalid_token(client):
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Не вдалося перевірити облікові дані"

def test_get_my_profile_with_token_without_sub(client):
    token = jwt.encode(
        {"role": "admin"},
        settings.JWT_SECRET_KEY,
        algorithm="HS256",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Не вдалося перевірити облікові дані"