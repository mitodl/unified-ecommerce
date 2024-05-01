"""API functions for authentication."""

import json
import logging

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from oauthlib.oauth2 import (
    BackendApplicationClient,
    InvalidGrantError,
    TokenExpiredError,
)
from requests_oauthlib import OAuth2Session

from authentication.models import KeycloakAdminToken
from unified_ecommerce.celery import app
from unified_ecommerce.exceptions import KeycloakAuthError
from unified_ecommerce.utils import decode_x_header

User = get_user_model()
log = logging.getLogger(__name__)


def decode_apisix_headers(request):
    """Decode the APISIX-specific headers."""

    try:
        apisix_result = decode_x_header(request, "HTTP_X_USERINFO")
        if not apisix_result:
            log.debug(
                "decode_apisix_headers: No APISIX-specific header found",
            )
            return None
    except json.JSONDecodeError:
        log.debug(
            "decode_apisix_headers: Got bad APISIX-specific header: %s",
            request.META.get("HTTP_X_USERINFO", ""),
        )

        return None

    log.debug("decode_apisix_headers: Got %s", apisix_result)

    return {
        "email": apisix_result["email"],
        "preferred_username": apisix_result["sub"],
        "given_name": apisix_result["given_name"],
        "family_name": apisix_result["family_name"],
    }


def get_user_from_apisix_headers(request):
    """Get a user based on the APISIX headers."""

    decoded_headers = decode_apisix_headers(request)

    if not decoded_headers:
        return None

    (
        email,
        preferred_username,
        given_name,
        family_name,
    ) = decoded_headers.values()

    log.debug("get_user_from_apisix_headers: Authenticating %s", preferred_username)

    user, created = User.objects.filter(username=preferred_username).get_or_create(
        defaults={
            "username": preferred_username,
            "email": email,
            "first_name": given_name,
            "last_name": family_name,
        }
    )

    if created:
        log.debug(
            "get_user_from_apisix_headers: User %s not found, created new",
            preferred_username,
        )
        user.set_unusable_password()
        user.save()
    else:
        log.debug(
            "get_user_from_apisix_headers: Found existing user for %s: %s",
            preferred_username,
            user,
        )

        user.first_name = given_name
        user.last_name = family_name
        user.save()

    return user


def keycloak_session_init(url, **kwargs):  # noqa: C901
    """
    Initialize a Keycloak session.

    This is a helper function that will initialize a Keycloak session with the
    provided URL. It will also handle refreshing the token if it has expired.

    Args:
    url (str): The Keycloak admin URL.
    **kwargs: Additional arguments to pass to the OAuth2Session initializer.

    Returns:
    None, or dict of data returned.
    """

    token_url = (
        f"{settings.KEYCLOAK_ADMIN_URL}/realms/master/protocol/openid-connect/token"
    )
    client = BackendApplicationClient(client_id=settings.KEYCLOAK_ADMIN_CLIENT_ID)

    auto_refresh_kwargs = {
        "client_id": settings.KEYCLOAK_ADMIN_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
    }

    def update_token(token):
        log.debug("Refreshing Keycloak token %s", token)
        KeycloakAdminToken.objects.all().delete()
        KeycloakAdminToken.objects.create(
            authorization_token=token.get("access_token"),
            refresh_token=token.get("refresh_token", ""),
            authorization_token_expires_in=token.get("access_token_expires_in", 60),
            refresh_token_expires_in=token.get("refresh_token_expires_in", 60),
        )

    def check_for_token():
        token = KeycloakAdminToken.latest()

        if not token:
            token_error_msg = "No token found"  # noqa: S105
            raise TokenExpiredError(token_error_msg)

        return token

    def regenerate_token(client):
        """Regenerate the token, or raise an exception."""

        try:
            session = OAuth2Session(client=client)
            new_token = session.fetch_token(
                token_url=token_url,
                client_id=settings.KEYCLOAK_ADMIN_CLIENT_ID,
                client_secret=settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
                verify=settings.KEYCLOAK_ADMIN_SECURE,
            )

            log.debug("Successfully refreshed token %s", new_token)

            update_token(new_token)
        except InvalidGrantError:
            log.exception(
                (
                    "keycloak_session_init couldn't refresh token because of an"
                    " invalid grant error"
                ),
            )
            return None
        except TokenExpiredError:
            log.exception(
                (
                    "keycloak_session_init couldn't refresh token because of an"
                    " expired token error"
                ),
            )
            return None
        except requests.exceptions.RequestException:
            log.exception(
                (
                    "keycloak_session_init couldn't refresh token because of an"
                    " HTTP error"
                ),
            )
            return None

        return session

    try:
        token = check_for_token()

        log.debug("Trying to start up a session with token %s", token.token_formatted)

        session = OAuth2Session(
            client=client,
            token=token.token_formatted,
            auto_refresh_url=token_url,
            auto_refresh_kwargs=auto_refresh_kwargs,
            token_updater=update_token,
        )

        keycloak_response = session.get(url, **kwargs).json()
    except (InvalidGrantError, TokenExpiredError) as ige:
        log.debug("Token error, trying to get a new token: %s", ige)

        session = regenerate_token(client)

        if not session:
            log.exception(
                "keycloak_session_init: attempted to regenerate the token, but"
                " failed to"
            )
            return None

        keycloak_response = session.get(url, **kwargs).json()
    except requests.exceptions.RequestException:
        log.exception(
            (
                "keycloak_session_init couldn't establish the session because of"
                " an HTTP error: %s"
            ),
            token,
        )
        return None
    except AttributeError:
        log.exception("keycloak_session_init failed")
        return None

    log.debug("Keycloak response: %s", keycloak_response)

    if "error" in keycloak_response:
        log.error("Keycloak returned an error: %s", keycloak_response["error"])
        raise KeycloakAuthError(keycloak_response)

    return keycloak_response


def keycloak_get_user(user: User):
    """Get a user from Keycloak."""

    userinfo_url = (
        f"{settings.KEYCLOAK_ADMIN_URL}/auth/admin/"
        f"realms/{settings.KEYCLOAK_REALM}/users/"
    )

    log.debug("Trying to get user info for %s", user.username)

    if user.keycloak_user_tokens.exists():
        params = {"id": user.keycloak_user_tokens.first().keycloak_id}
    else:
        params = {"email": user.username}

    userinfo = keycloak_session_init(
        userinfo_url, verify=settings.KEYCLOAK_ADMIN_SECURE, params=params
    )

    if len(userinfo) == 0:
        log.debug("Keycloak didn't return anything")
        return None

    return userinfo[0]


@app.task
def keycloak_update_user_account(user_id: int):
    """Update the user account using info from Keycloak asynchronously."""

    user = User.objects.get(id=user_id)

    keycloak_user = keycloak_get_user(user)

    if keycloak_user is None:
        return

    user.first_name = keycloak_user["firstName"]
    user.last_name = keycloak_user["lastName"]
    user.email = keycloak_user["email"]
    user.username = keycloak_user["id"]
    user.save()

    user.keycloak_user_tokens.all().delete()
    user.keycloak_user_tokens.create(keycloak_id=keycloak_user["id"])
    user.save()
