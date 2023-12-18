"""User fixtures"""

# pylint: disable=unused-argument, redefined-outer-name
from io import BytesIO

import pytest
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_jwt.settings import api_settings

from unified_ecommerce.factories import UserFactory


@pytest.fixture()
def user(db):  # noqa: ARG001
    """Create a user"""
    return UserFactory.create()


@pytest.fixture()
def staff_user(db):  # noqa: ARG001
    """Create a staff user"""
    return UserFactory.create(is_staff=True)


@pytest.fixture()
def index_user(db):  # noqa: ARG001
    """Create a user to be used for indexing"""
    return UserFactory.create(is_staff=True)


@pytest.fixture()
def logged_in_user(client, user):
    """Log the user in and yield the user object"""
    client.force_login(user)
    return user


@pytest.fixture()
def logged_in_profile(client):
    """Add a Profile and logged-in User"""
    user = UserFactory.create(username="george")
    client.force_login(user)
    return user.profile


@pytest.fixture()
def jwt_token(db, user, client, rf, settings):  # noqa: ARG001
    """Creates a JWT token for a regular user"""  # noqa: D401
    jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
    jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
    payload = jwt_payload_handler(user)
    token = jwt_encode_handler(payload)
    client.cookies[settings.MITOPEN_COOKIE_NAME] = token
    rf.cookies.load({settings.MITOPEN_COOKIE_NAME: token})
    return token


@pytest.fixture()
def client(db):  # noqa: ARG001
    """
    Similar to the builtin client but this provides the DRF client instead of the Django test client.
    """  # noqa: E501
    return APIClient()


@pytest.fixture()
def user_client(user):
    """Version of the client that is authenticated with the user"""
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture()
def staff_client(staff_user):
    """Version of the client that is authenticated with the staff_user"""
    client = APIClient()
    client.force_login(staff_user)
    return client


@pytest.fixture()
def profile_image():
    """Create a PNG image"""
    image_file = BytesIO()
    image = Image.new("RGBA", size=(250, 250), color=(256, 0, 0))
    image.save(image_file, "png")
    image_file.seek(0)
    return image_file
