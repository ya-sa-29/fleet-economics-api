from src.models.user import User, UserRole
from src.models.company import Company
from src.api.auth_utils import get_password_hash


def create_company(db, name="Test Company"):
    company = Company(name=name)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def create_user(db, company_id, email, role):
    user = User(
        email=email,
        hashed_password=get_password_hash("password123"),
        company_id=company_id,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_auth_headers(client, email):
    response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": "password123",
        },
    )
    assert response.status_code == 200

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_creates_driver(client, db):
    company = create_company(db)
    admin = create_user(
        db, company.id, "admin@example.com", UserRole.ADMIN
    )

    headers = get_auth_headers(client, admin.email)

    response = client.post(
        "/users/",
        json={
            "email": "driver@example.com",
            "password": "password123",
            "role": "driver",
        },
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["email"] == "driver@example.com"
    assert response.json()["role"] == "driver"
    assert response.json()["company_id"] == company.id
    assert "hashed_password" not in response.json()


def test_dispatcher_creates_driver(client, db):
    company = create_company(db)
    dispatcher = create_user(
        db, company.id, "dispatcher@example.com", UserRole.DISPATCHER
    )

    headers = get_auth_headers(client, dispatcher.email)

    response = client.post(
        "/users/",
        json={
            "email": "driver@example.com",
            "password": "password123",
            "role": "driver",
        },
        headers=headers,
    )

    assert response.status_code == 201


def test_dispatcher_cannot_create_dispatcher(client, db):
    company = create_company(db)
    dispatcher = create_user(
        db, company.id, "dispatcher@example.com", UserRole.DISPATCHER
    )

    headers = get_auth_headers(client, dispatcher.email)

    response = client.post(
        "/users/",
        json={
            "email": "another@example.com",
            "password": "password123",
            "role": "dispatcher",
        },
        headers=headers,
    )

    assert response.status_code == 403


def test_admin_cannot_create_second_admin(client, db):
    company = create_company(db)
    admin = create_user(
        db, company.id, "admin@example.com", UserRole.ADMIN
    )

    headers = get_auth_headers(client, admin.email)

    response = client.post(
        "/users/",
        json={
            "email": "another-admin@example.com",
            "password": "password123",
            "role": "admin",
        },
        headers=headers,
    )

    assert response.status_code == 400


def test_driver_cannot_view_users(client, db):
    company = create_company(db)
    driver = create_user(
        db, company.id, "driver@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, driver.email)

    response = client.get("/users/", headers=headers)

    assert response.status_code == 403


def test_admin_updates_user_role(client, db):
    company = create_company(db)
    admin = create_user(
        db, company.id, "admin@example.com", UserRole.ADMIN
    )
    driver = create_user(
        db, company.id, "driver@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, admin.email)

    response = client.patch(
        f"/users/{driver.id}",
        json={"role": "dispatcher"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["role"] == "dispatcher"


def test_dispatcher_cannot_update_user_role(client, db):
    company = create_company(db)
    dispatcher = create_user(
        db, company.id, "dispatcher@example.com", UserRole.DISPATCHER
    )
    driver = create_user(
        db, company.id, "driver@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, dispatcher.email)

    response = client.patch(
        f"/users/{driver.id}",
        json={"role": "dispatcher"},
        headers=headers,
    )

    assert response.status_code == 403


def test_admin_deactivates_user(client, db):
    company = create_company(db)
    admin = create_user(
        db, company.id, "admin@example.com", UserRole.ADMIN
    )
    driver = create_user(
        db, company.id, "driver@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, admin.email)

    response = client.delete(
        f"/users/{driver.id}",
        headers=headers,
    )

    assert response.status_code == 204

    db.refresh(driver)
    assert driver.deleted_at is not None


def test_admin_cannot_deactivate_another_admin(client, db):
    company = create_company(db)
    admin = create_user(
        db, company.id, "admin@example.com", UserRole.ADMIN
    )
    another_admin = create_user(
        db, company.id, "another@example.com", UserRole.ADMIN
    )

    headers = get_auth_headers(client, admin.email)

    response = client.delete(
        f"/users/{another_admin.id}",
        headers=headers,
    )

    assert response.status_code == 400


def test_user_cannot_access_another_company_user(client, db):
    company1 = create_company(db, "Company One")
    company2 = create_company(db, "Company Two")

    admin = create_user(
        db, company1.id, "admin@example.com", UserRole.ADMIN
    )
    other_user = create_user(
        db, company2.id, "other@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, admin.email)

    response = client.get(
        f"/users/{other_user.id}",
        headers=headers,
    )

    assert response.status_code == 404

def test_driver_cannot_view_user_by_id(client, db):
    company = create_company(db)

    driver = create_user(
        db, company.id, "driver@example.com", UserRole.DRIVER
    )
    another_driver = create_user(
        db, company.id, "another@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, driver.email)

    response = client.get(
        f"/users/{another_driver.id}",
        headers=headers,
    )

    assert response.status_code == 403

def test_dispatcher_can_view_users(client, db):
    company = create_company(db)

    dispatcher = create_user(
        db, company.id, "dispatcher@example.com", UserRole.DISPATCHER
    )
    driver = create_user(
        db, company.id, "driver@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, dispatcher.email)

    response = client.get("/users/", headers=headers)

    assert response.status_code == 200

    emails = [user["email"] for user in response.json()]

    assert dispatcher.email in emails
    assert driver.email in emails

def test_dispatcher_can_view_user_by_id(client, db):
    company = create_company(db)

    dispatcher = create_user(
        db, company.id, "dispatcher@example.com", UserRole.DISPATCHER
    )
    driver = create_user(
        db, company.id, "driver@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, dispatcher.email)

    response = client.get(
        f"/users/{driver.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["email"] == driver.email

def test_dispatcher_cannot_deactivate_user(client, db):
    company = create_company(db)

    dispatcher = create_user(
        db, company.id, "dispatcher@example.com", UserRole.DISPATCHER
    )
    driver = create_user(
        db, company.id, "driver@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, dispatcher.email)

    response = client.delete(
        f"/users/{driver.id}",
        headers=headers,
    )

    assert response.status_code == 403

    db.refresh(driver)
    assert driver.deleted_at is None

def test_admin_cannot_update_own_role(client, db):
    company = create_company(db)

    admin = create_user(
        db, company.id, "admin@example.com", UserRole.ADMIN
    )

    headers = get_auth_headers(client, admin.email)

    response = client.patch(
        f"/users/{admin.id}",
        json={"role": "driver"},
        headers=headers,
    )

    assert response.status_code == 400

    db.refresh(admin)
    assert admin.role == UserRole.ADMIN

def test_admin_cannot_deactivate_self(client, db):
    company = create_company(db)

    admin = create_user(
        db, company.id, "admin@example.com", UserRole.ADMIN
    )

    headers = get_auth_headers(client, admin.email)

    response = client.delete(
        f"/users/{admin.id}",
        headers=headers,
    )

    assert response.status_code == 400

    db.refresh(admin)
    assert admin.deleted_at is None

def test_admin_cannot_update_another_company_user(client, db):
    company1 = create_company(db, "Company One")
    company2 = create_company(db, "Company Two")

    admin = create_user(
        db, company1.id, "admin@example.com", UserRole.ADMIN
    )
    other_user = create_user(
        db, company2.id, "other@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, admin.email)

    response = client.patch(
        f"/users/{other_user.id}",
        json={"role": "dispatcher"},
        headers=headers,
    )

    assert response.status_code == 404

    db.refresh(other_user)
    assert other_user.role == UserRole.DRIVER

def test_admin_cannot_deactivate_another_company_user(client, db):
    company1 = create_company(db, "Company One")
    company2 = create_company(db, "Company Two")

    admin = create_user(
        db, company1.id, "admin@example.com", UserRole.ADMIN
    )
    other_user = create_user(
        db, company2.id, "other@example.com", UserRole.DRIVER
    )

    headers = get_auth_headers(client, admin.email)

    response = client.delete(
        f"/users/{other_user.id}",
        headers=headers,
    )

    assert response.status_code == 404

    db.refresh(other_user)
    assert other_user.deleted_at is None

def test_role_change_applies_to_existing_token(client, db):
    company = create_company(db)
    admin = create_user(
        db, company.id, "admin@example.com", UserRole.ADMIN
    )
    dispatcher = create_user(
        db, company.id, "dispatcher@example.com", UserRole.DISPATCHER
    )

    # Dispatcher отримує JWT до зміни ролі
    dispatcher_headers = get_auth_headers(client, dispatcher.email)

    # Admin змінює роль Dispatcher на Driver
    admin_headers = get_auth_headers(client, admin.email)

    update_response = client.patch(
        f"/users/{dispatcher.id}",
        json={"role": "driver"},
        headers=admin_headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["role"] == "driver"

    # Використовуємо старий JWT Dispatcher
    response = client.get(
        "/users/",
        headers=dispatcher_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Водій не має доступу до списку співробітників"