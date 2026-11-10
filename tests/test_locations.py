
from src.models.user import User, UserRole
from src.models.company import Company
from src.models.location import Location
from src.api.auth_utils import get_password_hash


def create_company(db, name="Test Company"):
    company = Company(name=name)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def create_user(db, company_id, email, role=UserRole.ADMIN):
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


def test_authenticated_user_can_view_locations(client, db, test_locations):
    company = create_company(db)
    admin = create_user(db, company.id, "admin@example.com")
    headers = get_auth_headers(client, admin.email)

    response = client.get("/locations/", headers=headers)

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert {location["name"] for location in data} == {
        "Київ",
        "Черкаси",
    }


def test_locations_are_sorted_by_name(client, db, test_locations):
    company = create_company(db)
    admin = create_user(db, company.id, "admin@example.com")
    headers = get_auth_headers(client, admin.email)

    response = client.get("/locations/", headers=headers)

    assert response.status_code == 200

    names = [location["name"] for location in response.json()]
    assert names == sorted(names)


def test_unauthenticated_user_cannot_view_locations(client, test_locations):
    response = client.get("/locations/")

    assert response.status_code == 401


def test_users_from_different_companies_see_same_locations(
    client, db, test_locations
):
    company1 = create_company(db, "Company One")
    company2 = create_company(db, "Company Two")

    admin1 = create_user(db, company1.id, "admin1@example.com")
    admin2 = create_user(db, company2.id, "admin2@example.com")

    headers1 = get_auth_headers(client, admin1.email)
    headers2 = get_auth_headers(client, admin2.email)

    response1 = client.get("/locations/", headers=headers1)
    response2 = client.get("/locations/", headers=headers2)

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json() == response2.json()


def test_locations_directory_is_read_only(client, db, test_locations):
    company = create_company(db)
    admin = create_user(db, company.id, "admin@example.com")
    headers = get_auth_headers(client, admin.email)

    post_response = client.post(
        "/locations/",
        json={"name": "Умань", "slug": "uman"},
        headers=headers,
    )
    
    patch_response = client.patch(
        "/locations/",
        json={"name": "Умань"},
        headers=headers,
    )

    delete_response = client.delete(
        "/locations/",
        headers=headers,
    )

    assert post_response.status_code == 405
    assert patch_response.status_code == 405
    assert delete_response.status_code == 405
