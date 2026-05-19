import pytest
from rest_framework import status

from accounts_app.models import User, UserRole


pytestmark = pytest.mark.django_db


REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
DASHBOARD_SURVEYS_URL = "/api/v1/dashboard/surveys/"


def test_register_valid_data(api_client):
    payload = {
        "email": "new-user@test.com",
        "username": "new-user",
        "password": "Pass1234!",
        "role": UserRole.ANALYST,
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["message"] == "Registered successfully"
    assert response.data["status"] == status.HTTP_201_CREATED
    assert response.data["email"] == payload["email"]
    assert response.data["username"] == payload["username"]
    assert response.data["role"] == payload["role"]
    assert "password" not in response.data

    user = User.objects.get(email=payload["email"])
    assert user.username == payload["username"]
    assert user.role == payload["role"]
    assert user.password != payload["password"]
    assert user.check_password(payload["password"]) is True


def test_register_duplicate_email(api_client):
    User.objects.create_user(
        username="existing-user",
        email="existing@test.com",
        password="Pass1234!",
        role=UserRole.ADMIN,
    )
    payload = {
        "email": "existing@test.com",
        "username": "second-user",
        "password": "Pass1234!",
        "role": UserRole.ANALYST,
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["message"] == "A user with this email already exists."
    assert response.data["status"] == status.HTTP_400_BAD_REQUEST
    assert User.objects.filter(email=payload["email"]).count() == 1


def test_register_missing_email(api_client):
    payload = {
        "username": "missing-email",
        "password": "Pass1234!",
        "role": UserRole.ANALYST,
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["message"] == "The field 'email' is required"
    assert response.data["status"] == status.HTTP_400_BAD_REQUEST
    assert User.objects.filter(username=payload["username"]).exists() is False


def test_register_missing_password(api_client):
    payload = {
        "email": "missing-password@test.com",
        "username": "missing-password",
        "role": UserRole.ANALYST,
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["message"] == "The field 'password' is required"
    assert response.data["status"] == status.HTTP_400_BAD_REQUEST
    assert User.objects.filter(email=payload["email"]).exists() is False


def test_register_default_role(api_client):
    payload = {
        "email": "default-role@test.com",
        "username": "default-role",
        "password": "Pass1234!",
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["role"] == UserRole.DATA_VIEWER

    user = User.objects.get(email=payload["email"])
    assert user.role == UserRole.DATA_VIEWER


def test_register_invalid_role(api_client):
    payload = {
        "email": "invalid-role@test.com",
        "username": "invalid-role",
        "password": "Pass1234!",
        "role": "superuser",
    }

    response = api_client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "valid choice" in response.data["message"]
    assert response.data["status"] == status.HTTP_400_BAD_REQUEST
    assert User.objects.filter(email=payload["email"]).exists() is False


def test_login_valid_credentials(api_client, admin_user):
    payload = {
        "email": admin_user.email,
        "password": "Pass1234!",
    }

    response = api_client.post(LOGIN_URL, payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "Login successful."
    assert response.data["status"] == status.HTTP_200_OK
    assert response.data["access"]
    assert response.data["refresh"]


def test_login_wrong_password(api_client, admin_user):
    payload = {
        "email": admin_user.email,
        "password": "WrongPass123!",
    }

    response = api_client.post(LOGIN_URL, payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["message"] == "Invalid email or password."
    assert response.data["status"] == status.HTTP_401_UNAUTHORIZED


def test_login_nonexistent_email(api_client):
    payload = {
        "email": "missing@test.com",
        "password": "Pass1234!",
    }

    response = api_client.post(LOGIN_URL, payload, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data["message"] == "Invalid email or password."
    assert response.data["status"] == status.HTTP_401_UNAUTHORIZED


def test_login_missing_fields(api_client):
    response = api_client.post(LOGIN_URL, {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["message"] == "The field 'email' is required"
    assert response.data["status"] == status.HTTP_400_BAD_REQUEST


def test_login_returns_jwt_usable_for_auth(api_client, admin_user):
    login_response = api_client.post(
        LOGIN_URL,
        {
            "email": admin_user.email,
            "password": "Pass1234!",
        },
        format="json",
    )
    access_token = login_response.data["access"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    dashboard_response = api_client.get(DASHBOARD_SURVEYS_URL)

    assert login_response.status_code == status.HTTP_200_OK
    assert dashboard_response.status_code == status.HTTP_200_OK
