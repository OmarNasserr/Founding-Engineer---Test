from types import SimpleNamespace

from rest_framework import status

from accounts_app.validations import AccountValidations


def test_validate_register_invalid_returns_400_with_error_message():
    response = AccountValidations.validate_register({}, False, "The field 'email' is required")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['message'] == "The field 'email' is required"
    assert response.data['status'] == status.HTTP_400_BAD_REQUEST


def test_validate_register_valid_returns_201():
    response = AccountValidations.validate_register({'email': 'x@x.com'}, True, "")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['message'] == "Registered successfully"
    assert response.data['status'] == status.HTTP_201_CREATED


def test_validate_login_invalid_returns_400_with_error_message():
    response = AccountValidations.validate_login({}, False, "The field 'email' is required")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data['message'] == "The field 'email' is required"
    assert response.data['status'] == status.HTTP_400_BAD_REQUEST


def test_validate_login_valid_but_no_user_returns_401():
    response = AccountValidations.validate_login({'email': 'x@x.com'}, True, "", user=None)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data['message'] == "Invalid email or password."
    assert response.data['status'] == status.HTTP_401_UNAUTHORIZED


def test_validate_login_valid_with_user_returns_200():
    mock_user = SimpleNamespace(id=1, email='x@x.com')

    response = AccountValidations.validate_login({'email': 'x@x.com'}, True, "", user=mock_user)

    assert response.status_code == status.HTTP_200_OK
    assert response.data['message'] == "Login successful."
    assert response.data['status'] == status.HTTP_200_OK
