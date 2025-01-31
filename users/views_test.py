"""Tests for the users API views."""

import faker
import pytest
from django.conf import settings

from system_meta.factories import ActiveIntegratedSystemFactory

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()


def test_current_user(user, client, user_client):
    """Test the "me" endpoint."""

    me_api = "/api/v0/users/me/"

    resp = client.get(me_api)

    assert resp.status_code == 200
    assert resp.json() == {
        "id": None,
        "username": "",
    }

    resp = user_client.get(me_api)

    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["id"] == user.id


def test_establish_session_logged_out(client):
    """
    Test that establish session returns a 403 when the user is logged out.

    This is counterintuitive - in reality, you get redirected into Keycloak.
    But that happens upstream, not in the Django app, so _we_ should return a 403.
    """
    integrated_system = ActiveIntegratedSystemFactory.create()

    api_kwargs = {
        "next": integrated_system.slug,
    }

    establish_session_api = "/establish_session/"

    resp = client.get(establish_session_api, query_params=api_kwargs)

    assert resp.status_code == 403


@pytest.mark.parametrize("send_back_to_system", [True, False])
def test_establish_session_logged_in(user_client, send_back_to_system):
    """
    Test that establish session redirects appropriately when the user is logged in.

    If the user is logged in, they should go to either the basket page or back
    to the integrated system.
    """
    integrated_system = ActiveIntegratedSystemFactory.create()

    if send_back_to_system:
        api_kwargs = {
            "system": integrated_system.slug,
            "next": FAKE.uri_path(),
        }
    else:
        api_kwargs = {
            "next": integrated_system.slug,
        }

    establish_session_api = "/establish_session/"

    resp = user_client.get(establish_session_api, query_params=api_kwargs)

    assert resp.status_code == 302

    if send_back_to_system:
        assert integrated_system.homepage_url in resp.headers.get("Location")
    else:
        assert settings.MITOL_UE_PAYMENT_BASKET_CHOOSER in resp.headers.get("Location")
