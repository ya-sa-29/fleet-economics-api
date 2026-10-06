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